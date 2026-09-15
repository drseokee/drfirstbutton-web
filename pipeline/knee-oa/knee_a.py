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
LIGS = {"lig__acl": "Anterior cruciate ligament.r", "lig__pcl": "Posterior cruciate ligament.r", "lig__mcl": "Superficial part of tibial collateral ligament.r", "lig__lcl": "Fibular collateral ligament.r"}
for k, n in LIGS.items():
    if n in objs: built[k] = get(n, False)
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
meta = {"frame": "knee-joint-centred; right=-x, anterior=-y, up=+z; medial=+x (right knee)", "unit": "m", "attribution": ATTR, "joint_z": 0.0}
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
