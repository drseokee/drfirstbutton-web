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
built["meniscus__medial"] = get("Medial meniscus.r", False); built["meniscus__lateral"] = get("Lateral meniscus.r", False)
LIGS = {"lig__acl": "Anterior cruciate ligament.r", "lig__pcl": "Posterior cruciate ligament.r"}
for k, n in LIGS.items():
    if n in objs: built[k] = get(n, False)
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
    for i in range(n + 1):
        u = i / n; c = a + d * u
        hit = BONE_BVH.ray_cast(c + nrm * 0.02, -nrm, 0.04)
        off = ((hit[0] - c).dot(nrm) + clearance) if hit[0] is not None else 0.0
        off = max(-0.006, min(0.014, off)); c = c + nrm * off              # wraps over the bulging condyle/plateau
        w = w0 * (1 - u) + w1 * u
        rings.append([bm.verts.new(c + side * (w / 2 * math.cos(2 * math.pi * k / segs)) + nrm * (thick / 2 * math.sin(2 * math.pi * k / segs))) for k in range(segs)])
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(segs): bm.faces.new((r0[k], r0[(k + 1) % segs], r1[(k + 1) % segs], r1[k]))
    bm.faces.new(rings[0][::-1]); bm.faces.new(rings[-1]); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bmesh.ops.triangulate(bm, faces=bm.faces); return bm
built["lig__mcl"] = collateral(mcl_o, mcl_i, 0.012, 0.020, 0.0025, Vector((1, 0, 0)))     # superficial MCL: 12 mm proximally widening to 20 mm, 2.5 mm thick, ~10 cm
built["lig__lcl"] = collateral(lcl_o, lcl_i, 0.006, 0.006, 0.004, Vector((-1, 0, 0)))     # LCL: 6 x 4 mm cord, ~6 cm
LANDMARKS = {"medial_epicondyle": MED_EPI, "lateral_epicondyle": LAT_EPI, "mcl_origin": mcl_o, "mcl_insertion": mcl_i, "lcl_origin": lcl_o, "lcl_insertion": lcl_i}
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
    for _ in range(smooth): bmesh.ops.smooth_vert(bm, verts=bm.verts[:], factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
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
    return (down > 0.25) or (fwd > 0.5 and c.z > JZ + 0.005 and abs(c.x - fx) < 0.02) or (down > 0.05 and n.y > 0.4)   # inferior, trochlea, posterior condyles
def tibia_art(f):
    c = f.calc_center_median(); n = f.normal; tz = max(v.co.z for v in tibia.verts)
    return c.z > tz - 0.007 and n.z > 0.45
def patella_art(f):
    c = f.calc_center_median(); n = f.normal
    return n.y > 0.45                                                        # posterior facet
built["cartilage__femur"] = shell(femur, femur_art, 0.0025, "cf")
built["cartilage__tibia"] = shell(tibia, tibia_art, 0.0025, "ct")
built["cartilage__patella"] = shell(patella, patella_art, 0.003, "cp")
for k in ("cartilage__femur", "cartilage__tibia", "cartilage__patella"):
    print(k, len(built[k].verts) if built[k] else None, "verts")

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
