import bpy, bmesh, json, math, os
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from zana import *
import zana

OUTK = "/home/claude/out_knee"; os.makedirs(OUTK, exist_ok=True); zana.OUT = OUTK
objs = open_src()
# ---- frame: origin at the knee joint line centre; Z-Anatomy: right = -x, anterior = -y, up = +z; medial = +x (toward the midline) for the right knee ----
fem = objs["Femur.r"]; tib = objs["Tibia.r"]
fv = [fem.matrix_world @ v.co for v in fem.data.vertices]; tv = [tib.matrix_world @ v.co for v in tib.data.vertices]
JZ = (min(v.z for v in fv) + max(v.z for v in tv)) / 2
cond = [v for v in fv if v.z < JZ + 0.04]; CENTER = Vector((sum(v.x for v in cond) / len(cond), sum(v.y for v in cond) / len(cond), JZ))
Z_TOP, Z_BOT = JZ + 0.15, JZ - 0.15
print("joint line z %.3f, centre" % JZ, [round(c, 3) for c in CENTER])
def clip(bm, top=Z_TOP, bot=Z_BOT): cut_z(bm, top, keep="below", cap=True, ngon=True); cut_z(bm, bot, keep="above", cap=True, ngon=True); return bm
def get(name, cutz=True):
    bm = world_bm(name); return clip(bm) if cutz else bm

built = {}
built["bone__femur"] = get("Femur.r"); built["bone__tibia"] = get("Tibia.r"); built["bone__fibula"] = get("Fibula.r"); built["bone__patella"] = get("Patella.r", False)
for k in ("bone__tibia", "bone__fibula"):                                                 # Z-Anatomy's bones nearly touch: open the joint 3 mm so cartilage + menisci fit
    for v in built[k].verts: v.co.z -= 0.003
# Z-Anatomy's femur sits with its medial condyle low on the plateau: lift it 2.5° (about the joint centre, AP axis) so both compartments have room for cartilage + meniscus
_Rv = Matrix.Rotation(math.radians(-2.5), 3, Vector((0, 1, 0)))
for k in ("bone__femur", "bone__patella"):
    for v in built[k].verts: v.co = _Rv @ (v.co - CENTER) + CENTER
_probe = _Rv @ Vector((0.04, 0, 0)); print("femur tilt check: medial side moved up by %.1f mm" % (_probe.z * 1e3))
# ---- menisci are built procedurally after the tibial cartilage (see MENISCI) ----
# cruciate footprints (built as live bands in the viewer so they show tension/slack with motion)
notch_x = sum(v.x for v in epi_zone) / len(epi_zone) if False else None
# ---- collateral ligaments built from bony landmarks (Z-Anatomy's are crude sheets) ----
fv_ = [v.co for v in built["bone__femur"].verts]; tv_ = [v.co for v in built["bone__tibia"].verts]; fbv_ = [v.co for v in built["bone__fibula"].verts]
epi_zone = [v for v in fv_ if JZ + 0.008 < v.z < JZ + 0.045]
MED_EPI = max(epi_zone, key=lambda v: v.x); LAT_EPI = min(epi_zone, key=lambda v: v.x)
# superficial MCL: origin just proximal-posterior of the medial epicondyle; insertion on the medial tibia ~5.5 cm below the joint, posterior to the pes
mcl_o = MED_EPI + Vector((0, 0.004, 0.003))
tib_med_zone = [v for v in tv_ if JZ - 0.062 < v.z < JZ - 0.048]; mcl_i = max(tib_med_zone, key=lambda v: v.x - 0.3 * v.y); mcl_i = mcl_i + Vector((0, 0.004, 0))
# LCL: origin proximal-posterior of the lateral epicondyle; insertion on the anterolateral fibular head
lcl_o = LAT_EPI + Vector((0, 0.003, 0.003))
fib_head = [v for v in fbv_ if v.z > max(q.z for q in fbv_) - 0.018]; lcl_i = min(fib_head, key=lambda v: v.x + 0.4 * v.y)
print("MCL %.0f mm (%s -> %s), LCL %.0f mm" % ((mcl_i - mcl_o).length * 1e3, [round(c*1e3) for c in (mcl_o - CENTER)], [round(c*1e3) for c in (mcl_i - CENTER)], (lcl_i - lcl_o).length * 1e3))
BONE_BVH = BVHTree.FromBMesh(join_bms([built["bone__femur"].copy(), built["bone__tibia"].copy(), built["bone__fibula"].copy()]))
def collateral(a, b, w0, w1, thick, out, n=22, segs=12, clearance=0.0010):
    """band from a to b hugging the bone: at each station the centre is pushed to (bone surface + clearance) along `out`; width tapers w0 -> w1, elliptical section"""
    d = b - a; t = d.normalized(); side = t.cross(out).normalized(); nrm = side.cross(t).normalized()
    bm = bmesh.new(); rings = []
    offs = []
    for i in range(n + 1):
        u = i / n; c = a + d * u; best = None
        for sw in (-0.4, 0, 0.4):                                              # probe across the band's width, keep the highest bone
            cc = c + side * (sw * (w0 * (1 - u) + w1 * u) / 2)
            hit = BONE_BVH.ray_cast(cc + nrm * 0.03, -nrm, 0.06)
            if hit[0] is not None:
                o_ = (hit[0] - cc).dot(nrm) + clearance
                if best is None or o_ > best: best = o_
        offs.append(max(-0.006, min(0.016, best if best is not None else 0.0)))
    offs[0] = offs[-1] = thick * 0.15                                                        # ends sit half-embedded at the footprints
    # taut band: upper convex hull of the profile (a ligament under tension bridges concavities, it does not follow them)
    hull = []
    for i, o_ in enumerate(offs):
        while len(hull) >= 2:
            (i1, o1), (i2, o2) = hull[-2], hull[-1]
            if (o_ - o1) * (i2 - i1) - (o2 - o1) * (i - i1) >= 0: hull.pop()      # upper hull: drop the middle point when the new one lies above the line
            else: break
        hull.append((i, o_))
    taut = [0.0] * (n + 1)
    for (i1, o1), (i2, o2) in zip(hull, hull[1:]):
        for i in range(i1, i2 + 1): taut[i] = o1 + (o2 - o1) * (i - i1) / max(1, i2 - i1)
    for i in range(n + 1):
        u = i / n; c = a + d * u + nrm * taut[i]
        w = (w0 * (1 - u) + w1 * u) * (1 + 0.12 * math.sin(math.pi * u))                          # slightly fusiform
        rings.append([bm.verts.new(c + side * (w / 2 * math.cos(2 * math.pi * k / segs)) + nrm * (thick / 2 * math.sin(2 * math.pi * k / segs))) for k in range(segs)])
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(segs): bm.faces.new((r0[k], r0[(k + 1) % segs], r1[(k + 1) % segs], r1[k]))
    bm.faces.new(rings[0][::-1]); bm.faces.new(rings[-1]); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bmesh.ops.triangulate(bm, faces=bm.faces); return bm
built["lig__mcl"] = collateral(mcl_o, mcl_i, 0.012, 0.020, 0.0025, Vector((1, 0, 0)))     # superficial MCL: 12 mm proximally widening to 20 mm, 2.5 mm thick, ~10 cm
built["lig__lcl"] = collateral(lcl_o, lcl_i, 0.0075, 0.0095, 0.0038, Vector((-1, 0, 0)))  # LCL: flattened cord 7.5 → 9.5 mm wide, 3.8 mm thick
# ---- cruciate footprints ----
fx_ = sum(v.x for v in fv_ if JZ - 0.005 < v.z < JZ + 0.03) / max(1, len([v for v in fv_ if JZ - 0.005 < v.z < JZ + 0.03]))
notch = [v for v in fv_ if JZ + 0.004 < v.z < JZ + 0.028 and abs(v.x - fx_) < 0.012]                       # intercondylar notch walls
lat_wall = [v for v in notch if v.x < fx_ - 0.003]; med_wall = [v for v in notch if v.x > fx_ + 0.003]
ymid_n = sum(v.y for v in notch) / len(notch)
acl_f = sum([v for v in lat_wall if v.y > ymid_n + 0.004], Vector()) / max(1, len([v for v in lat_wall if v.y > ymid_n + 0.004]))   # posteromedial aspect of the lateral condyle (in the notch)
pcl_f = sum([v for v in med_wall if v.y < ymid_n - 0.002 and v.z < JZ + 0.018], Vector()) / max(1, len([v for v in med_wall if v.y < ymid_n - 0.002 and v.z < JZ + 0.018]))   # lateral aspect of the medial condyle, anterior-distal
tv_top = max(v.z for v in tv_); tx_ = sum(v.x for v in tv_ if v.z > tv_top - 0.01) / max(1, len([v for v in tv_ if v.z > tv_top - 0.01])); ty_ = sum(v.y for v in tv_ if v.z > tv_top - 0.01) / max(1, len([v for v in tv_ if v.z > tv_top - 0.01]))
acl_t = Vector((tx_ - 0.002, ty_ - 0.012, tv_top - 0.003))                                                  # anterior to the tibial spines, slightly medial
pcl_t = Vector((tx_ + 0.001, ty_ + 0.017, tv_top - 0.010))                                                  # posterior intercondylar fossa, 1 cm below the plateau
print("ACL %.0f mm, PCL %.0f mm" % ((acl_t - acl_f).length * 1e3, (pcl_t - pcl_f).length * 1e3))
LANDMARKS = {"medial_epicondyle": MED_EPI, "lateral_epicondyle": LAT_EPI, "mcl_origin": mcl_o, "mcl_insertion": mcl_i, "lcl_origin": lcl_o, "lcl_insertion": lcl_i,
             "acl_femur": acl_f, "acl_tibia": acl_t, "pcl_femur": pcl_f, "pcl_tibia": pcl_t}
print("objects:", len(built))

# ---- articular cartilage: shells offset from the bone surfaces (2.5 mm femur/tibia, 3 mm patella) over the articular regions ----
def shell(bm_src, keep_face, thick, name, smooth=2):
    bm = bm_src.copy(); bm.faces.ensure_lookup_table()
    drop = [f for f in bm.faces if not keep_face(f)]
    bmesh.ops.delete(bm, geom=drop, context="FACES")
    if not len(bm.faces): return None
    # keep the largest connected piece (drops stray patches)
    comps = []; seen = set()
    for f in bm.faces:
        if f in seen: continue
        stack = [f]; comp = []
        while stack:
            g = stack.pop()
            if g in seen: continue
            seen.add(g); comp.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h not in seen: stack.append(h)
        comps.append(comp)
    comps.sort(key=len, reverse=True)
    for comp in comps[1:]: bmesh.ops.delete(bm, geom=comp, context="FACES")
    src_bvh = BVHTree.FromBMesh(bm_src)
    for _ in range(smooth): bmesh.ops.smooth_vert(bm, verts=bm.verts[:], factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    for v in bm.verts:                                              # smoothing shrinks the patch inward: lift every vertex back to the bone surface + 0.3 mm
        loc, nrm, idx, dist = src_bvh.find_nearest(v.co)
        if loc is not None:
            dd = (v.co - loc).dot(nrm)
            if dd < 0.0003: v.co = loc + nrm * 0.0003
    bm.normal_update()
    # solidify outward: an offset copy of every vertex, mirrored faces, side walls along the boundary
    outer = {v: bm.verts.new(v.co + v.normal * thick) for v in list(bm.verts)}
    for f in list(bm.faces):
        try: bm.faces.new([outer[v] for v in reversed(f.verts)])
        except ValueError: pass
    for e in [e for e in list(bm.edges) if e.is_boundary and e.verts[0] in outer and e.verts[1] in outer]:
        a_, b_ = e.verts
        try: bm.faces.new((a_, b_, outer[b_], outer[a_]))
        except ValueError: pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bmesh.ops.triangulate(bm, faces=bm.faces)
    return bm
femur = built["bone__femur"]; tibia = built["bone__tibia"]; patella = built["bone__patella"]
fx = sum(v.co.x for v in femur.verts) / len(femur.verts)
# femoral condyles + trochlea: faces near the joint whose normal points down or forward (not the metaphysis sides)
def femur_art(f):
    c = f.calc_center_median(); n = f.normal
    if c.z > JZ + 0.038 or c.z < JZ - 0.01: return False
    down = -n.z; fwd = -n.y
    if abs(n.x) > 0.82 or abs(c.x - fx) > 0.040: return False                 # only true flank faces (epicondyles) are excluded
    return (down > 0.25) or (fwd > 0.5 and c.z > JZ + 0.005 and abs(c.x - fx) < 0.02) or (down > 0.05 and n.y > 0.4)   # inferior, trochlea, posterior condyles
def tibia_art(f):
    c = f.calc_center_median(); n = f.normal; tz = max(v.co.z for v in tibia.verts)
    return c.z > tz - 0.016 and n.z > 0.20                                     # the whole plateau surface, including its gently sloping margins
def patella_art(f):
    c = f.calc_center_median(); n = f.normal
    return n.y > 0.45                                                        # posterior facet
built["cartilage__femur"] = shell(femur, femur_art, 0.0025, "cf")
built["cartilage__tibia"] = shell(tibia, tibia_art, 0.0025, "ct")
built["cartilage__patella"] = shell(patella, patella_art, 0.003, "cp")
for k in ("cartilage__femur", "cartilage__tibia", "cartilage__patella"):
    print(k, len(built[k].verts) if built[k] else None, "verts")

# ---- MENISCI: medial = larger C (open toward the centre), lateral = rounder, nearly closed; both rest on the tibial cartilage ----
tib_bvh = BVHTree.FromBMesh(join_bms([built["bone__tibia"].copy(), built["cartilage__tibia"].copy()])); fem_bvh = BVHTree.FromBMesh(join_bms([built["bone__femur"].copy(), built["cartilage__femur"].copy()]))
ct = built["cartilage__tibia"]; cpts = [v.co for v in ct.verts]
_tt = max(v.co.z for v in built["bone__tibia"].verts); _sp = [v.co for v in built["bone__tibia"].verts if v.co.z > _tt - 0.0035]     # intercondylar eminence (spines) = the divider between compartments
cx_mid = sum(p.x for p in _sp) / len(_sp); print("eminence x %.1f mm" % ((cx_mid) * 1e3))
def compartment_centre(side):
    sel = [p for p in cpts if (p.x > cx_mid) == (side == "medial")]; return sum(sel, Vector()) / len(sel)
tpl_top = max(v.co.z for v in built["bone__tibia"].verts)
ct_bvh = BVHTree.FromBMesh(built["cartilage__tibia"].copy())                                     # the plateau = the cartilage patch (covers the whole articular surface)
def compartment_extent(side):
    sel = [p for p in cpts if (p.x > cx_mid) == (side == "medial") and abs(p.x - cx_mid) > 0.004]; return (max(p.x for p in sel) - min(p.x for p in sel)), (max(p.y for p in sel) - min(p.y for p in sel))
def compartment_centre(side):
    sel = [p for p in cpts if (p.x > cx_mid) == (side == "medial") and abs(p.x - cx_mid) > 0.004]; return sum(sel, Vector()) / len(sel)
def meniscus(side, rx, ry, thick, gap_deg, n_th=40, n_r=6):
    c = compartment_centre(side)
    open_c = 0.0 if side == "lateral" else math.pi                                          # the C opens toward the notch: lateral compartment (-x) opens to +x (angle 0), medial (+x) opens to -x (pi)
    bm = bmesh.new(); rows = []; half_gap = math.radians(gap_deg / 2)
    ths = [open_c + half_gap + (2 * math.pi - 2 * half_gap) * k / n_th for k in range(n_th + 1)]
    ex, ey = compartment_extent(side); rx = min(rx, ex * 0.58); ry = min(ry, ey * 0.58)      # the rim is found by the plateau-edge search below
    rmax = []
    for th in ths:                                                                          # the rim stops where the plateau ends (ray must land on the plateau top, facing up)
        r_max = 1.0
        for _ in range(16):
            hx = c.x + rx * r_max * math.cos(th); hy = c.y + ry * r_max * math.sin(th)
            hh = ct_bvh.ray_cast(Vector((hx, hy, c.z + 0.03)), Vector((0, 0, -1)), 0.045)
            if hh[0] is not None: break                                                          # lands on the plateau cartilage → that is the rim
            r_max -= 0.03
        rmax.append(max(0.6, r_max))
    rmax = [sum(rmax[max(0, i - 2):i + 3]) / len(rmax[max(0, i - 2):i + 3]) for i in range(len(rmax))]   # smooth outline
    for th, r_max in zip(ths, rmax):
        ring = []
        for j in range(n_r + 1):
            r = (0.42 + 0.58 * j / n_r) * r_max                                                 # 0.42 = free inner edge, r_max = outer rim (at the plateau edge)
            px = c.x + rx * r * math.cos(th); py = c.y + ry * r * math.sin(th)
            hit = tib_bvh.ray_cast(Vector((px, py, c.z + 0.03)), Vector((0, 0, -1)), 0.06)
            base = (hit[0].z + 0.0003) if hit[0] is not None else c.z
            h = thick * (0.15 + 0.85 * (j / n_r) ** 1.2)                                      # wedge: thin free edge, thick rim
            up = fem_bvh.ray_cast(Vector((px, py, base + 0.0005)), Vector((0, 0, 1)), 0.03)   # never into the femoral condyle above: cap the height 0.4 mm under it
            if up[0] is not None: h = max(0.0005, min(h, up[0].z - base - 0.0010))
            ring.append((bm.verts.new(Vector((px, py, base))), bm.verts.new(Vector((px, py, base + h)))))
        rows.append(ring)
    for r0, r1 in zip(rows, rows[1:]):
        for j in range(n_r):
            (a0, t0), (a1, t1) = r0[j], r0[j + 1]; (b0, u0), (b1, u1) = r1[j], r1[j + 1]
            bm.faces.new((a0, a1, b1, b0)); bm.faces.new((t0, u0, u1, t1))
        (a0, t0) = r0[0]; (b0, u0) = r1[0]; bm.faces.new((a0, b0, u0, t0))
        (a1, t1) = r0[-1]; (b1, u1) = r1[-1]; bm.faces.new((a1, t1, u1, b1))
    for ring in (rows[0], rows[-1]):
        try: bm.faces.new([ring[j][0] for j in range(n_r + 1)] + [ring[j][1] for j in range(n_r, -1, -1)])
        except ValueError: pass
    for _ in range(2): bmesh.ops.smooth_vert(bm, verts=bm.verts[:], factor=0.35, use_axis_x=False, use_axis_y=False, use_axis_z=True)   # even out steps from the polygonal plateau
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bmesh.ops.triangulate(bm, faces=bm.faces)
    # final clean-up: any vertex still inside the femur (bone or cartilage) is pushed straight down out of it, any inside the tibia straight up
    pairs = [(rows[i][j][0], rows[i][j][1]) for i in range(len(rows)) for j in range(n_r + 1)]
    for _ in range(3):
        for vb, vt in pairs:
            loc, nrm, idx, dist = fem_bvh.find_nearest(vt.co)
            if loc is not None and (vt.co - loc).dot(nrm) < 0.0006: vt.co.z -= (0.0006 - (vt.co - loc).dot(nrm))
            loc2, nrm2, idx2, dist2 = tib_bvh.find_nearest(vb.co)
            if loc2 is not None and (vb.co - loc2).dot(nrm2) < 0.0003: vb.co.z += (0.0003 - (vb.co - loc2).dot(nrm2))
            if vt.co.z < vb.co.z + 0.0005: vt.co.z = vb.co.z + 0.0005                           # the wedge never inverts (no holes)
    return bm
built["meniscus__medial"] = meniscus("medial", 0.026, 0.0245, 0.0065, 70)                   # medial: ~37 x 49 mm C, rim 6.5 mm
built["meniscus__lateral"] = meniscus("lateral", 0.021, 0.022, 0.006, 40)                    # lateral: ~34 x 38 mm ring, rim 6 mm
print("menisci: medial", len(built["meniscus__medial"].verts), "v, lateral", len(built["meniscus__lateral"].verts), "v")
objects = []
for k, bm in built.items():
    if bm is None: continue
    v, t = to_arrays(bm, center=CENTER); objects.append({"name": k, "layer": k.split("__")[0], "verts": v, "tris": t})
meta = {"frame": "knee-joint-centred; right=-x, anterior=-y, up=+z; medial=+x (right knee)", "unit": "m", "attribution": ATTR, "joint_z": 0.0, "landmarks": {k: [round(c, 5) for c in (v - CENTER)] for k, v in LANDMARKS.items()}}
json.dump({"meta": meta, "objects": objects}, open(f"{OUTK}/knee_a.json", "w"), separators=(",", ":"))
print("exported knee_a:", len(objects), "objects,", sum(len(o["verts"]) // 3 for o in objects), "verts,", os.path.getsize(f"{OUTK}/knee_a.json") // 1024, "KB")

ANT, LAT, UPV = Vector((0, -1, 0)), Vector((-1, 0, 0)), Vector((0, 0, 1)); MED = -LAT
def look2(cam, sun, pos, up):
    fwd = (-pos).normalized(); right = fwd.cross(up).normalized(); up2 = right.cross(fwd).normalized()
    m = Matrix((right, up2, -fwd)).transposed(); cam.location = pos; cam.rotation_quaternion = m.to_quaternion(); sun.rotation_quaternion = (m @ Matrix.Rotation(0.5, 3, 'X') @ Matrix.Rotation(-0.4, 3, 'Y')).to_quaternion()
zana.look = look2
rebuild_scene([o for o in objects if o["layer"] in ("bone", "cartilage", "meniscus", "lig")], meta)
bpy.data.materials.get("mat__cartilage") or None
render_views({"ant": (ANT + UPV * 0.15, UPV), "antmed": (ANT * 0.7 + MED * 0.7 + UPV * 0.1, UPV), "flexed_lat": (LAT + ANT * 0.3, UPV)}, "knee_a", dist=0.30, res=700, samples=14)
