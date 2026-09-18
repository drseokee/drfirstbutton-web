import bpy, bmesh, json, math, os, random
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from zana import *
import zana

OUTK = "/home/claude/out_knee"; zana.OUT = OUTK
d = json.load(open(f"{OUTK}/knee_a.json")); objs = {o["name"]: o for o in d["objects"]}
def bm_of(o): return bm_from_arrays([tuple(o["verts"][i:i+3]) for i in range(0, len(o["verts"]), 3)], [tuple(o["tris"][i:i+3]) for i in range(0, len(o["tris"]), 3)])
def V(o, i): return Vector(o["verts"][3*i:3*i+3])
def nverts(o): return len(o["verts"]) // 3
def smooth01(t): t = max(0.0, min(1.0, t)); return t * t * (3 - 2 * t)
MED = Vector((1, 0, 0)); ANT = Vector((0, -1, 0)); UP = Vector((0, 0, 1))
random.seed(3)

# ---------- flexion axis: through the centres of the two femoral condyles ----------
fem = objs["bone__femur"]; fpts = [V(fem, i) for i in range(nverts(fem))]
cond = [p for p in fpts if -0.006 < p.z < 0.030]
xm = sorted(p.x for p in cond)[len(cond) // 2]
medC = sum((p for p in cond if p.x > xm), Vector()) / max(1, len([p for p in cond if p.x > xm]))
latC = sum((p for p in cond if p.x <= xm), Vector()) / max(1, len([p for p in cond if p.x <= xm]))
axis_p = (medC + latC) / 2; axis_d = (medC - latC).normalized()
print("flexion axis point", [round(c*1e3, 1) for c in axis_p], "dir", [round(c, 3) for c in axis_d])
# two-centre model: circle fits (sagittal y-z) to the DISTAL condyle profile (used near extension) and the POSTERIOR condyle profile (used in flexion)
def fit_circle(pts2):
    import numpy as np
    P = np.array(pts2); A = np.c_[2 * P[:, 0], 2 * P[:, 1], np.ones(len(P))]; bb = (P ** 2).sum(axis=1); sol = np.linalg.lstsq(A, bb, rcond=None)[0]
    cy, cz = sol[0], sol[1]; r = math.sqrt(max(1e-9, sol[2] + cy * cy + cz * cz)); return cy, cz, r
slab = [p for p in cond if abs(p.x - medC.x) < 0.008 or abs(p.x - latC.x) < 0.008]                 # both condyles' sagittal profiles
ymid = sum(p.y for p in slab) / len(slab)
dist_pts = [(p.y, p.z) for p in slab if p.z < -0.001 + 0.014 and abs(p.y - ymid) < 0.018]            # bottom of the condyles
post_pts = [(p.y, p.z) for p in slab if p.y > ymid + 0.006 and p.z < 0.026]                          # posterior curve
cyd, czd, rd = fit_circle(dist_pts); cyp, czp, rp = fit_circle(post_pts)
print(f"condyle circles: distal centre y {cyd*1e3:+.1f} z {czd*1e3:+.1f} r {rd*1e3:.1f} mm | posterior centre y {cyp*1e3:+.1f} z {czp*1e3:+.1f} r {rp*1e3:.1f} mm")

# ---------- cartilage: wear (thinning, medial first) and rough (fibrillation) morphs ----------
BONE = {"cartilage__femur": "bone__femur", "cartilage__tibia": "bone__tibia", "cartilage__patella": "bone__patella"}
for ck, bk in BONE.items():
    if ck not in objs: continue
    c = objs[ck]; bvh = BVHTree.FromBMesh(bm_of(objs[bk])); wear = []; rough = []
    xs = [V(c, i).x for i in range(nverts(c))]; x0, x1 = min(xs), max(xs)
    for i in range(nverts(c)):
        p = V(c, i); loc, nrm, idx, dist = bvh.find_nearest(p)
        outer = dist > 0.0009                                                   # outer layer of the shell
        med = smooth01((p.x - x0) / max(1e-6, x1 - x0))                          # 0 lateral .. 1 medial
        wgt = 0.25 + 0.75 * med if ck != "cartilage__patella" else 0.6
        if outer and loc is not None:
            toward = (loc - p); depth = toward.length; keep = 0.0003
            dw = toward.normalized() * max(0.0, depth - keep) * wgt                 # thins down to 0.3 mm (medial fully, lateral a quarter)
            dr = nrm * 0.0007 * random.uniform(-1, 1) * (0.4 + 0.6 * med)           # surface fibrillation
        else: dw = Vector((0, 0, 0)); dr = Vector((0, 0, 0))
        wear += [round(dw.x, 5), round(dw.y, 5), round(dw.z, 5)]; rough += [round(dr.x, 5), round(dr.y, 5), round(dr.z, 5)]
    # craters: 3 (femur) / 2 (tibia) full-thickness defects on the medial compartment — outer verts drop to the bone within a soft-edged disc
    crater = []; cw = []
    pts_c = [V(c, i) for i in range(nverts(c))]
    if ck == "cartilage__patella": centers = []
    else:
        med_pts = [p for p in pts_c if (p.x - x0) / max(1e-6, x1 - x0) > 0.55]
        random.shuffle(med_pts)
        n_big, n_small = (3, 14) if ck == "cartilage__femur" else (2, 9)
        centers = [(q, 0.007 + 0.006 * random.random(), [random.uniform(0.55, 1.0) for _ in range(12)]) for q in med_pts[:n_big]]
        centers += [(q, 0.0015 + 0.002 * random.random(), [random.uniform(0.7, 1.0) for _ in range(12)]) for q in med_pts[n_big:n_big + n_small]]   # pits: the "moth-eaten" look
    for i in range(nverts(c)):
        p = pts_c[i]; loc, nrm, idx, dist = bvh.find_nearest(p); outer = dist > 0.0009
        wgt = 0.0
        for (q, rad, lobes) in centers:                                                # jagged outline: the radius varies with the angle around the centre
            dv_ = p - q; dd = dv_.length; ang = math.atan2(dv_.y, dv_.x); k = int(((ang + math.pi) / (2 * math.pi)) * 12) % 12; k2 = (k + 1) % 12; fr = ((ang + math.pi) / (2 * math.pi)) * 12 - k
            r_eff = rad * (lobes[k] * (1 - fr) + lobes[k2] * fr); wgt = max(wgt, smooth01(1 - dd / r_eff) ** 0.6)
        if loc is not None and wgt > 0:
            toward = (loc - p); dep = toward.length; dv = (toward.normalized() if dep > 1e-6 else -Vector(nrm)) * (dep + 0.0012) * wgt     # sinks 1.2 mm under the bone surface: the patch vanishes into the bone = exposed bone
        else: dv = Vector((0, 0, 0))
        crater += [round(dv.x, 5), round(dv.y, 5), round(dv.z, 5)]; cw.append(round(wgt, 2))
    c["morphs"] = {"wear": wear, "rough": rough, "crater": crater}; c["cw"] = cw
    # bone under the craters: per-vertex weight for the red "exposed, inflamed bone" tint
    bo = objs[bk]; cbvh_pts = [(pts_c[i], cw[i]) for i in range(nverts(c)) if cw[i] > 0.05]
    fxb = []
    for i in range(nverts(bo)):
        p = V(bo, i); wgt = 0.0
        for (q, wq) in cbvh_pts:
            if (p - q).length < 0.004: wgt = max(wgt, wq)
        fxb.append(round(wgt, 2))
    bo["fx"] = [max(x, y) for x, y in zip(bo.get("fx", [0.0] * nverts(bo)), fxb)]
    c["medial"] = [round(smooth01((V(c, i).x - x0) / max(1e-6, x1 - x0)), 2) for i in range(nverts(c))]
    print(f"{ck}: wear/rough morphs on {sum(1 for i in range(nverts(c)) if wear[3*i:3*i+3] != [0,0,0])} outer verts")

# ---------- osteophytes: bone spurs along the medial margins of the articular surfaces ----------
def osteophyte(bk, ck, zband, side_sign=1):
    """marginal spurs: bone vertices on the medial side, at the joint level, just OUTSIDE the cartilage patch (1–7 mm from its edge) grow outward"""
    b = objs[bk]; cbvh = BVHTree.FromBMesh(bm_of(objs[ck])); dl = []; n_hit = 0
    for i in range(nverts(b)):
        p = V(b, i)
        if (p.x - axis_p.x) * side_sign < 0.010 or not (zband[0] < p.z < zband[1]): dl += [0, 0, 0]; continue
        loc, nrm, idx, dist = cbvh.find_nearest(p)
        w = smooth01(1 - abs(dist - 0.005) / 0.006) if dist is not None else 0
        if w <= 0: dl += [0, 0, 0]; continue
        out = Vector((side_sign, 0, 0)); lip = Vector((0, 0, -1 if bk == "bone__femur" else 1)) * 0.3
        dd = (out + lip).normalized() * 0.0065 * w * (0.75 + 0.25 * random.random()); n_hit += 1
        dl += [round(dd.x, 5), round(dd.y, 5), round(dd.z, 5)]
    b.setdefault("morphs", {})["osteophyte"] = dl
    print(f"{bk}: osteophyte on {n_hit} verts (medial rim)")
osteophyte("bone__femur", "cartilage__femur", (-0.004, 0.030)); osteophyte("bone__tibia", "cartilage__tibia", (-0.014, 0.006))

# ---------- tendons: quadriceps (patella top → femur shaft) and patellar (patella apex → tibial tuberosity) ----------
pat = objs["bone__patella"]; ppts = [V(pat, i) for i in range(nverts(pat))]
pat_top = max(ppts, key=lambda p: p.z); pat_bot = min(ppts, key=lambda p: p.z); pat_c = sum(ppts, Vector()) / len(ppts)
tib = objs["bone__tibia"]; tpts = [V(tib, i) for i in range(nverts(tib))]
tub = min([p for p in tpts if -0.055 < p.z < -0.025], key=lambda p: p.y)                # most anterior point 2.5-5.5 cm below the joint = tibial tuberosity
fsh = min([p for p in fpts if 0.06 < p.z < 0.07], key=lambda p: p.y)                    # anterior femoral shaft 6-7 cm up (quadriceps tendon origin end)
def band(pts_line, width, thick, segs=12):
    bm = bmesh.new(); rings = []
    for i, p in enumerate(pts_line):
        t = (pts_line[min(i + 1, len(pts_line) - 1)] - pts_line[max(i - 1, 0)]).normalized(); n = ANT.copy(); n = (n - t * t.dot(n)).normalized(); s = t.cross(n).normalized()
        ring = []
        for k in range(segs):
            a = 2 * math.pi * k / segs; ring.append(bm.verts.new(p + s * (width / 2 * math.cos(a)) + n * (thick / 2 * math.sin(a))))
        rings.append(ring)
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(segs): bm.faces.new((r0[k], r0[(k + 1) % segs], r1[(k + 1) % segs], r1[k]))
    bm.faces.new(rings[0][::-1]); bm.faces.new(rings[-1]); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bmesh.ops.triangulate(bm, faces=bm.faces); return bm
objects = d["objects"]
print("no tendons (removed by request)")

# ---------- skinning weights: femur / tibia(+fibula) / patella groups, blended near the joint ----------
GRP = {"femur": ["bone__femur"], "tibia": ["bone__tibia", "bone__fibula"], "patella": ["bone__patella"]}
GBVH = {g: BVHTree.FromBMesh(join_bms([bm_of(objs[n]) for n in names])) for g, names in GRP.items()}
GI = {"femur": 0, "tibia": 1, "patella": 2}
FIXED = {"cartilage__femur": "femur", "cartilage__tibia": "tibia", "cartilage__patella": "patella", "meniscus__medial": "tibia", "meniscus__lateral": "tibia",
         "bone__femur": "femur", "bone__tibia": "tibia", "bone__fibula": "tibia", "bone__patella": "patella"}
for o in objects:
    if o["name"] in FIXED: o["group"] = GI[FIXED[o["name"]]]; continue
    w = []
    for i in range(nverts(o)):
        p = V(o, i); ds = []
        for g in ("femur", "tibia", "patella"):
            loc, nrm, idx, dist = GBVH[g].find_nearest(p); ds.append(dist if loc is not None else 1.0)
        if p.z > 0.045: ww = [1.0, 0.0, 0.0]
        elif p.z < -0.035: ww = [0.0, 1.0, 0.0]
        else:
            inv = [1.0 / (dd + 0.004) ** 2 for dd in ds]; tot = sum(inv); ww = [x / tot for x in inv]
        w += [round(x, 2) for x in ww]
    o["w"] = w
# ---------- curve deformers for muscles / ligaments / tendons crossing the joint ----------
# each object gets a rest centreline (slab centroids along its principal axis); every vertex is stored as (t along the curve, offsets in the
# curve frame). At runtime the curve's points move with the bone they sit on (blended near the joint), the curve is re-smoothed, and the
# vertices are rebuilt around it — the belly bends and shortens as one piece instead of crumpling.
import numpy as np
def principal_axis(pts):
    P = np.array([[p.x, p.y, p.z] for p in pts]); c = P.mean(axis=0); u, s, vt = np.linalg.svd(P - c, full_matrices=False); ax = Vector(vt[0])
    if ax.z < 0: ax = -ax                                                       # proximal = +z end
    return Vector(c), ax
for o in objects:
    lay = o["layer"]
    if lay not in ("lig", "tendon"): continue
    pts = [V(o, i) for i in range(nverts(o))]
    c0, ax = principal_axis(pts)
    proj = [(p - c0).dot(ax) for p in pts]; pmin, pmax = min(proj), max(proj); L = pmax - pmin
    n_sl = max(3, min(14, int(L / 0.012) + 1))
    curve = []
    for k in range(n_sl):
        a = pmin + L * k / (n_sl - 1); sl = [p for p, q in zip(pts, proj) if abs(q - a) <= L / (n_sl - 1) * 0.75]
        if not sl: sl = [c0 + ax * a]
        curve.append(sum(sl, Vector()) / len(sl))
    curve = curve[::-1]                                                          # index 0 = proximal end (max projection)
    # smooth the polyline
    for _ in range(2): curve = [curve[0]] + [(curve[i - 1] + curve[i] * 2 + curve[i + 1]) / 4 for i in range(1, len(curve) - 1)] + [curve[-1]]
    S = [0.0]
    for i in range(1, len(curve)): S.append(S[-1] + (curve[i] - curve[i - 1]).length)
    Ltot = max(1e-6, S[-1])
    # parallel-transport frame: N starts anterior at the proximal end and is carried along the curve (no flips when a segment turns)
    frames = []; N_prev = None
    for i in range(len(curve)):
        T = (curve[min(i + 1, len(curve) - 1)] - curve[max(i - 1, 0)]).normalized()
        src = ANT if N_prev is None else N_prev
        N = (src - T * T.dot(src)); N = N.normalized() if N.length > 1e-6 else Vector((1, 0, 0)); B = T.cross(N).normalized(); frames.append((T, N, B)); N_prev = N
    tv = []; strip = []
    for p in pts:
        # nearest point on the polyline
        best = (1e9, 0, 0.0)
        for i in range(len(curve) - 1):
            a_, b_ = curve[i], curve[i + 1]; ab = b_ - a_; u = max(0.0, min(1.0, (p - a_).dot(ab) / max(1e-9, ab.length_squared))); q = a_ + ab * u; dd = (p - q).length
            if dd < best[0]: best = (dd, i, u)
        dd, i, u = best; q = curve[i] + (curve[i + 1] - curve[i]) * u; t = (S[i] + (S[i + 1] - S[i]) * u) / Ltot
        T0, N0, B0 = frames[i]; T1, N1, B1 = frames[i + 1]; T = (T0 * (1 - u) + T1 * u).normalized(); N = (N0 * (1 - u) + N1 * u).normalized(); Bv = (B0 * (1 - u) + B1 * u).normalized()
        off = p - q; tv += [round(t, 4), round(off.dot(T), 5), round(off.dot(N), 5), round(off.dot(Bv), 5)]
        strip.append(round(math.atan2(off.dot(Bv), off.dot(N)), 3))
    # curve points → bone group weights (femur / tibia / patella), blended within ±25 mm of the joint line
    cw = []
    for cpt in curve:
        ds = []
        for g in ("femur", "tibia", "patella"):
            loc, nrm, idx, dist = GBVH[g].find_nearest(cpt); ds.append(dist if loc is not None else 1.0)
        if cpt.z > 0.05: ww = [1.0, 0.0, 0.0]
        elif cpt.z < -0.04: ww = [0.0, 1.0, 0.0]
        else: inv = [1.0 / (dd + 0.006) ** 2 for dd in ds]; tot = sum(inv); ww = [x / tot for x in inv]
        cw += [round(x, 3) for x in ww]
    o["curve"] = {"pts": [round(c, 5) for cpt in curve for c in cpt], "w": cw, "tv": tv, "L0": round(Ltot, 5)}; o["strip"] = strip
    o.pop("w", None)
print("curve deformers built")
ct = objs["cartilage__tibia"]; cpts = [V(ct, i) for i in range(nverts(ct))]; xm2 = sorted(p.x for p in cpts)[len(cpts) // 2]
med_piv = sum((p for p in cpts if p.x > xm2), Vector()) / max(1, len([p for p in cpts if p.x > xm2]))
# ---------- contact table: for each flexion angle, how far the tibia must shift along its own axis so the tibial cartilage just touches the femoral condyle (0.5 mm) ----------
fem_bvh = BVHTree.FromBMesh(bm_of(objs["bone__femur"]))                                    # bone only; the target is the REST clearance so 0° gives offset 0
ct_ = objs["cartilage__tibia"]; ct_pts = [V(ct_, i) for i in range(nverts(ct_))]
probe = Vector((0, 0, -0.1)); sgn = 1 if (Matrix.Rotation(0.5, 3, axis_d) @ probe).y > 0 else -1     # flexion sends the distal tibia posterior
def min_signed(deg, off):
    Rm = Matrix.Rotation(math.radians(deg) * sgn, 3, axis_d); up_local = Rm @ Vector((0, 0, 1)); m = 1.0
    for p in ct_pts:
        q = Rm @ (p - axis_p) + axis_p + up_local * off
        loc, nrm, idx, dist = fem_bvh.find_nearest(q)
        if loc is None: continue
        s = dist if (q - loc).dot(nrm) >= 0 else -dist
        if s < m: m = s
    return m
def penetrating(deg, off):
    Rm = Matrix.Rotation(math.radians(deg) * sgn, 3, axis_d); up_local = Rm @ Vector((0, 0, 1)); n = 0; mind = 1.0
    for p in ct_pts:
        q = Rm @ (p - axis_p) + axis_p + up_local * off
        loc, nrm, idx, dist = fem_bvh.find_nearest(q)
        if loc is None: continue
        if (q - loc).dot(nrm) < 0: n += 1
        elif dist < mind: mind = dist
    return n, mind
CONTACT = []
for deg in range(0, 121, 5):
    best = -0.012
    for k in range(0, 97):                                        # scan upward in 0.25 mm steps; keep the highest position with no penetration and ≥0.3 mm clearance
        off = -0.012 + k * 0.00025; n, mind = penetrating(deg, off)
        if n == 0 and mind >= 0.0003: best = off
        elif n > 0 and off > best + 0.001: break
    CONTACT.append(best)
base0 = CONTACT[0]; CONTACT = [round(c - base0, 5) for c in CONTACT]                       # relative to the rest pose (0° = 0)
CONTACT = CONTACT[:19] + [CONTACT[18]] * (len(CONTACT) - 19)
CONTACT = [round(sum(CONTACT[max(0, i - 1):i + 2]) / len(CONTACT[max(0, i - 1):i + 2]), 5) for i in range(len(CONTACT))]
print("contact (smoothed, mm):", [round(c*1e3, 1) for c in CONTACT])
print("contact offsets (mm) by 5°:", [round(c*1e3, 1) for c in CONTACT])
# ---------- patellar track: the femoral (cartilage) surface profile in the sagittal plane of the trochlear groove, sampled by rays from the axis point ----------
troch_bvh = BVHTree.FromBMesh(join_bms([bm_of(objs["bone__femur"]), bm_of(objs["cartilage__femur"])]))
ant = Vector((0, -1, 0)); dn = Vector((0, 0, -1)); raw = []
for k in range(0, 81):                                                                       # -50° .. +150° in 2.5° steps
    a_deg = -50 + 2.5 * k; a = math.radians(a_deg); dirv = (ant * math.cos(a) + dn * math.sin(a)).normalized()
    hits = []
    for dx in (-0.004, 0.0, 0.004):
        o_ = Vector((axis_p.x + dx, axis_p.y, axis_p.z)); hit = troch_bvh.ray_cast(o_ + dirv * 0.010, dirv, 0.09)
        if hit[0] is not None: hits.append((hit[0] - o_).length)
    raw.append((a_deg, (sum(hits) / len(hits)) if hits else None))
# fill gaps and smooth the radius profile r(a) (5-tap, 3 passes) — a smooth profile means a smooth patellar path with no jumps
rs = [r for a_, r in raw]
for i in range(len(rs)):
    if rs[i] is None: rs[i] = next((rs[j] for j in list(range(i - 1, -1, -1)) + list(range(i + 1, len(rs))) if rs[j] is not None), 0.04)
for _ in range(3): rs = [sum(rs[max(0, i - 2):i + 3]) / len(rs[max(0, i - 2):i + 3]) for i in range(len(rs))]
TROCH = []
for (a_deg, _), r in zip(raw, rs):
    a = math.radians(a_deg); dirv = (ant * math.cos(a) + dn * math.sin(a)).normalized(); p = axis_p + dirv * r
    TROCH.append({"a": a_deg, "p": [round(c, 5) for c in p]})
print("patellar track:", len(TROCH), "samples, radius %.0f..%.0f mm" % (min(rs) * 1e3, max(rs) * 1e3))
# ---------- sagittal section set for the cruciate demo: femur / tibia / cartilages cut just lateral of the ACL's femoral footprint, medial part kept, cut faces capped ----------
SAG_X = d["meta"]["landmarks"]["acl_femur"][0] - 0.003; SAG_MID = -0.004
FEM_P = Vector((-0.016, 0, 0.0)); _top = Vector((-0.004, 0, 0.15)); _d = (_top - FEM_P).normalized(); FEM_N = Vector((-_d.z, 0, _d.x)).normalized()   # normal in the x-z plane, pointing lateral(-x)
if FEM_N.x > 0: FEM_N = -FEM_N
for nm in ("bone__femur", "bone__tibia", "cartilage__femur", "cartilage__tibia"):
    src = objs[nm]; bm = bm_of(src)
    if nm.startswith("bone__femur") or nm.startswith("cartilage__femur"):
        # femur: an oblique plane — 16 mm lateral at the joint (the ACL stays whole) tilting to 4 mm lateral at the top of the block (a real shaft section, no step)
        pco, pno = FEM_P, FEM_N
    else: pco, pno = Vector((SAG_X, 0, 0)), Vector((-1, 0, 0))
    cut_plane(bm, tuple(pco), tuple(pno), remove="outer", cap=True, ngon=True)              # remove the lateral side, keep medial
    if not len(bm.faces): continue
    cortex = None
    if nm.startswith("bone__"):
        # cap = cortical rim + cancellous centre: inset the cap polygon(s) by 2.2 mm; ring faces are cortex (1), inner faces marrow (0), blended by the shader
        bm.faces.ensure_lookup_table(); caps = [f for f in bm.faces if abs(abs(f.normal.dot(pno)) - 1) < 0.01 and abs((f.calc_center_median() - pco).dot(pno)) < 0.0005]
        U_ = Vector((0, 1, 0)); W_ = pno.cross(U_).normalized()                                   # in-plane basis: U = y (anterior/posterior), W = 'up' along the plane
        # the cap comes out as many triangles: merge them into one polygon per connected region first (otherwise every triangle becomes its own "outline" = solid cortex)
        res_d = bmesh.ops.dissolve_faces(bm, faces=caps, use_verts=False); caps = [f for f in res_d["region"] if f.is_valid]
        print(f"   {nm}: {len(caps)} cap polygon(s) with", [len(f.verts) for f in caps], "verts")
        from mathutils.geometry import delaunay_2d_cdt
        from mathutils import Vector as _V2
        cortex = {}
        for f in caps:
            loop = [l.vert for l in f.loops]; n_ = len(loop); cap_o = f.calc_center_median()
            poly2 = [_V2(((v_.co - cap_o).dot(U_), (v_.co - cap_o).dot(W_))) for v_ in loop]
            # interior grid points (2 mm) inside the outline → a dense, well-shaped triangulation; cortex = distance to the outline vs local thickness
            ys_ = [p.x for p in poly2]; zs_ = [p.y for p in poly2]; grid = []
            def inside(pt):
                c_ = False; j_ = n_ - 1
                for i_ in range(n_):
                    pi, pj = poly2[i_], poly2[j_]
                    if ((pi.y > pt.y) != (pj.y > pt.y)) and (pt.x < (pj.x - pi.x) * (pt.y - pi.y) / (pj.y - pi.y + 1e-12) + pi.x): c_ = not c_
                    j_ = i_
                return c_
            gy = min(ys_); 
            while gy < max(ys_):
                gz = min(zs_)
                while gz < max(zs_):
                    pt = _V2((gy + 0.0007, gz + 0.0004))
                    if inside(pt): grid.append(pt)
                    gz += 0.002
                gy += 0.002
            edges2 = [(i_, (i_ + 1) % n_) for i_ in range(n_)]
            out = delaunay_2d_cdt(poly2 + grid, edges2, [list(range(n_))], 1, 1e-6)      # output 1 = keep only faces inside the constraint polygon
            vco, vedges, vfaces, orig_v, orig_e, orig_f = out
            bmesh.ops.delete(bm, geom=[f], context="FACES_ONLY")
            newv = []
            for k_, p2 in enumerate(vco):
                if k_ < n_ and orig_v[k_] and orig_v[k_][0] < n_: newv.append(loop[orig_v[k_][0]])            # boundary vertex → reuse the existing one
                else: newv.append(bm.verts.new(cap_o + U_ * p2.x + W_ * p2.y))
            for fc in vfaces:
                try: bm.faces.new([newv[i_] for i_ in fc])
                except ValueError: pass
            # cortex attribute: distance to the outline / local cortical thickness (thin at the joint, thick toward the shaft)
            def dist_to_outline(pt):
                best = 1e9
                for i_ in range(n_):
                    a_, b_ = poly2[i_], poly2[(i_ + 1) % n_]; ab = b_ - a_; u_ = max(0.0, min(1.0, (pt - a_).dot(ab) / max(1e-12, ab.length_squared))); best = min(best, (a_ + ab * u_ - pt).length)
                return best
            for k_, v_ in enumerate(newv):
                p2 = vco[k_]; zz = (cap_o + U_ * p2.x + W_ * p2.y).z; th = 0.0015 + 0.0045 * smooth01((abs(zz) - 0.040) / 0.090)
                cortex[v_] = 1.0 if k_ < n_ else max(0.0, 1.0 - dist_to_outline(p2) / th)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bmesh.ops.triangulate(bm, faces=bm.faces)
    v, t = to_arrays(bm, center=Vector((0, 0, 0)))
    o_ = {"name": nm + "__cut", "layer": nm.split("__")[0], "verts": v, "tris": t, "group": GI["femur" if "femur" in nm else "tibia"], "cut": True}
    if cortex is not None:
        bm.verts.ensure_lookup_table(); o_["cortex"] = [round(cortex.get(vv, 1.0), 1) for vv in bm.verts]     # surface verts (not on the cap) → 1 = cortex colour anyway
    objects.append(o_)
print("sagittal section set built at x = %.1f mm" % (SAG_X * 1e3))
meta = dict(d["meta"]); meta["rig"] = {"sag_x": round(SAG_X, 5), "fem_plane": {"p": [round(c, 5) for c in FEM_P], "n": [round(c, 4) for c in FEM_N]}, "troch": TROCH, "contact": CONTACT, "medial_pivot": [round(c, 5) for c in med_piv], "centre_ext": [round(axis_p.x, 5), round(cyd, 5), round(czd, 5)], "centre_flex": [round(axis_p.x, 5), round(cyp, 5), round(czp, 5)], "flex_axis": {"point": [round(c, 5) for c in axis_p], "dir": [round(c, 4) for c in axis_d]},
                                        "patella": {"centre": [round(c, 5) for c in pat_c]}, "tuberosity": [round(c, 5) for c in tub]}
d["meta"] = meta
json.dump(d, open(f"{OUTK}/knee_b.json", "w"), separators=(",", ":"))
print("exported knee_b:", len(objects), "objects")
