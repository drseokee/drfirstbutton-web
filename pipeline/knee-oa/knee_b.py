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
    c["morphs"] = {"wear": wear, "rough": rough}
    print(f"{ck}: wear/rough morphs on {sum(1 for i in range(nverts(c)) if wear[3*i:3*i+3] != [0,0,0])} outer verts")

# ---------- osteophytes: bone spurs along the medial margins of the articular surfaces ----------
def osteophyte(bk, ck, zband, side_sign=1):
    """marginal spurs: bone vertices on the medial side, at the joint level, just OUTSIDE the cartilage patch (1–7 mm from its edge) grow outward"""
    b = objs[bk]; cbvh = BVHTree.FromBMesh(bm_of(objs[ck])); dl = []; n_hit = 0
    for i in range(nverts(b)):
        p = V(b, i)
        if (p.x - axis_p.x) * side_sign < 0.010 or not (zband[0] < p.z < zband[1]): dl += [0, 0, 0]; continue
        loc, nrm, idx, dist = cbvh.find_nearest(p)
        w = smooth01(1 - abs(dist - 0.004) / 0.004) if dist is not None else 0
        if w <= 0: dl += [0, 0, 0]; continue
        out = Vector((side_sign, 0, 0)); lip = Vector((0, 0, -1 if bk == "bone__femur" else 1)) * 0.3
        dd = (out + lip).normalized() * 0.0040 * w * (0.7 + 0.3 * random.random()); n_hit += 1
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
pl = [pat_bot + Vector((0, -0.004, 0)), (pat_bot + tub) / 2 + Vector((0, -0.006, 0)), tub + Vector((0, -0.002, 0))]
qt = [fsh + Vector((0, -0.003, 0)), (fsh + pat_top) / 2 + Vector((0, -0.006, 0)), pat_top + Vector((0, -0.003, 0))]
objects = d["objects"]
for nm, line, w, th in (("tendon__patellar", pl, 0.026, 0.006), ("tendon__quadriceps", qt, 0.030, 0.006)):
    bm = band([line[0].lerp(line[1], u) if u < 1 else line[1].lerp(line[2], u - 1) for u in [i / 6 for i in range(13)]], w, th)
    v, t = to_arrays(bm, center=Vector((0, 0, 0))); objects.append({"name": nm, "layer": "tendon", "verts": v, "tris": t})
print("tendons: patellar", [round(c*1e3) for c in tub], "quadriceps origin", [round(c*1e3) for c in fsh])

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
meta = dict(d["meta"]); meta["rig"] = {"flex_axis": {"point": [round(c, 5) for c in axis_p], "dir": [round(c, 4) for c in axis_d]},
                                        "patella": {"centre": [round(c, 5) for c in pat_c]}, "tuberosity": [round(c, 5) for c in tub]}
d["meta"] = meta
json.dump(d, open(f"{OUTK}/knee_b.json", "w"), separators=(",", ":"))
print("exported knee_b:", len(objects), "objects")
