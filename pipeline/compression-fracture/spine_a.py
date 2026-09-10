import bpy, bmesh, json, math, os
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from zana import *
import zana

OUTS = "/home/claude/out_spine"; os.makedirs(OUTS, exist_ok=True); zana.OUT = OUTS
objs = open_src()
# ---- frame: origin at the L1 body centre; Z-Anatomy axes: right = -x, anterior = -y, up = +z ----
L1 = objs["Vertebra L2"]; vs = [L1.matrix_world @ v.co for v in L1.data.vertices]   # frame centred on the fractured level (L2)
CENTER = sum(vs, Vector()) / len(vs); CENTER.y -= 0.012            # shift toward the body (the vertebra centroid sits near the pedicles)
Z_TOP, Z_BOT = 1.172, 0.925                                        # T12 top plate .. S2 level
print("centre", [round(c, 3) for c in CENTER])

def clip(bm, top=Z_TOP, bot=Z_BOT):
    cut_z(bm, top, keep="below", cap=True, ngon=True); cut_z(bm, bot, keep="above", cap=True, ngon=True); return bm
def get(name, clipz=True, top=Z_TOP, bot=Z_BOT):
    bm = world_bm(name); return clip(bm, top, bot) if clipz else bm
def get_join(names, clipz=True): return clip(join_bms([world_bm(n) for n in names if n in objs])) if clipz else join_bms([world_bm(n) for n in names if n in objs])

built = {}
for lv in ["T12", "L1", "L2", "L3", "L4", "L5"]:
    built[f"bone__{lv.lower()}"] = get(f"Vertebra {lv}", clipz=(lv == "T12"))
built["bone__sacrum"] = get("Sacrum")
built["bone__rib12_r"] = get("Twelfth rib.r"); built["bone__rib12_l"] = get("Twelfth rib.l")
for d in ["T12-L1", "L1-L2", "L2-L3", "L3-L4", "L4-L5", "L5-S1"]:
    built[f"disc__{d.lower().replace('-', '_')}"] = get(f"Intervertebral disc {d}", clipz=False)
built["nerve__dural_sac"] = get("Spinal dura")
c = objs["Cauda equina"].data
for sp in c.splines:
    for p in (sp.points if sp.type != "BEZIER" else sp.bezier_points): p.radius = 1.0
c.bevel_depth = 0.0007; c.bevel_resolution = 4; c.use_fill_caps = True; refresh()
built["nerve__cauda_equina"] = get("Cauda equina")
for k, n in {"lig__all": "Anterior longitudinal ligament", "lig__pll": "Posterior longitudinal ligament", "lig__flava": "Ligamenta flava",
             "lig__interspinous": "Interspinous ligaments", "lig__supraspinous": "Supraspinous ligament"}.items():
    if n in objs: built[k] = get(n)
MUSC = {"muscle__multifidus": ["Multifidus lumborum muscle", "Multifidus thoracis muscle"], "muscle__longissimus": ["Longissimus thoracis muscle"],
        "muscle__iliocostalis": ["Iliocostalis lumborum muscle", "Iliocostalis thoracis muscle"], "muscle__spinalis": ["Spinalis thoracis muscle"],
        "muscle__quadratus_lumborum": ["Quadratus lumborum muscle"], "muscle__psoas": ["Psoas major"], "muscle__latissimus": ["Latissimus dorsi muscle"],
        "muscle__thoracolumbar_fascia": ["Posterior layer of thoracolumbar fascia"],
        "muscle__rectus_abdominis": ["Rectus abdominis muscle"], "muscle__ext_oblique": ["External oblique muscle", "External abdominal oblique muscle"],
        "muscle__int_oblique": ["Internal oblique muscle", "Internal abdominal oblique muscle"], "muscle__transversus": ["Transversus abdominis muscle", "Transverse abdominal muscle"]}
missing = []
for k, names in MUSC.items():
    for side in ("r", "l"):
        present = [f"{n}.{side}" for n in names if f"{n}.{side}" in objs]
        if present: built[f"{k}_{side}"] = get_join(present)
        else: missing.append(f"{names[0]}.{side}")
print("missing:", missing)
for k, bm in built.items(): print(f"{k:34} {len(bm.verts):6} v")

# ---- torso skin: union of everything solid + skin-only context (pelvis, upper buttocks, arms with hands), subcutaneous closing ----
Z_SKIN_BOT, Z_ARM_BOT, TRUNK_HALF_W = 0.850, 0.735, 0.185                 # trunk stops at the upper half of the buttocks; arms continue to the fingertips
EXTRA = ["Hip bone", "Coccyx", "Piriformis muscle", "Gluteus maximus muscle", "Gluteus medius muscle", "Gluteus minimus muscle", "Tensor fasciae latae",
         "Humerus", "Radius", "Ulna", "Long head of biceps brachii", "Short head of biceps brachii", "Brachialis muscle", "Lateral head of triceps brachii", "Medial head of triceps brachii", "Long head of triceps brachii",
         "Brachioradialis muscle", "Extensor carpi radialis longus", "Extensor carpi radialis brevis", "Extensor digitorum", "Extensor digiti minimi", "Ulnar head of extensor carpi ulnaris", "Humeral head of extensor carpi ulnaris", "Anconeus muscle",
         "Flexor carpi radialis", "Humeral head of flexor carpi ulnaris", "Ulnar head of flexor carpi ulnaris", "Superficial head of pronator teres", "Humero-ulnar head of flexor digitorum superficialis", "Radial head of flexor digitorum superficialis", "Flexor digitorum profundus", "Flexor pollicis longus", "Abductor pollicis longus"]
HAND = [f"{w} metacarpal bone" for w in ("First", "Second", "Third", "Fourth", "Fifth")] + [f"{p} phalanx of {w} finger of hand" for p in ("Proximal", "Middle", "Distal") for w in ("first", "second", "third", "fourth", "fifth")]
extras = []
for side in ("r", "l"):
    for n in EXTRA + HAND:
        nm = f"{n}.{side}"
        if nm in objs:
            bm = world_bm(nm); cut_z(bm, Z_TOP, keep="below", cap=True, ngon=True); cut_z(bm, Z_ARM_BOT, keep="above", cap=True, ngon=True); extras.append(bm)
# filler over the sacrum: the gluteal cleft leaves a pit between the two gluteus maximus masses that no muscle covers
sac = objs["Sacrum"]; sv = [sac.matrix_world @ v.co for v in sac.data.vertices]; sc_ = sum(sv, Vector()) / len(sv)
fill = bmesh.new(); bmesh.ops.create_uvsphere(fill, u_segments=24, v_segments=16, radius=1.0)
bmesh.ops.transform(fill, matrix=Matrix.Translation((sc_.x, max(v.y for v in sv) - 0.014, sc_.z + 0.02)) @ Matrix.Diagonal((0.065, 0.02, 0.085, 1)), verts=fill.verts[:])
cut_z(fill, Z_ARM_BOT, keep="above", cap=True); extras.append(fill)
print("skin-only context objects:", len(extras))
solid = [k for k in built if k.split("__")[0] in ("bone", "muscle", "disc")]
union = join_bms([built[k].copy() for k in solid] + extras)
bpy.ops.wm.read_homefile(use_empty=True)
ob = bm_to_object(union, "skin_src")
for kind, kw in [("REMESH", dict(mode="VOXEL", voxel_size=0.004)), ("SMOOTH", dict(factor=1.0, iterations=3)),
                 ("DISPLACE", dict(strength=0.020, mid_level=0, direction="NORMAL")),          # dilate 20 mm: closes the gaps between muscle groups
                 ("REMESH", dict(mode="VOXEL", voxel_size=0.004)), ("SMOOTH", dict(factor=1.0, iterations=6)),
                 ("DISPLACE", dict(strength=-0.009, mid_level=0, direction="NORMAL")),         # erode 9 mm: net 11 mm of subcutaneous padding
                 ("REMESH", dict(mode="VOXEL", voxel_size=0.0035)), ("SMOOTH", dict(factor=1.0, iterations=6)), ("DECIMATE", dict(ratio=0.5))]:
    m = ob.modifiers.new(kind.lower() + str(len(ob.modifiers)), kind)
    for a, v in kw.items(): setattr(m, a, v)
skin = evaluated_bm(ob); cut_z(skin, Z_TOP - 0.004, keep="below", cap=True, ngon=True); cut_z(skin, Z_ARM_BOT + 0.004, keep="above", cap=True, ngon=True)
# trunk ends at the upper buttocks; the arms keep going down to the hands: carve the lower trunk out with a box
skin_ob = bm_to_object(skin, "skin_full"); box = bmesh.new(); bmesh.ops.create_cube(box, size=1.0)
bmesh.ops.transform(box, matrix=Matrix.Translation((0, 0.03, (Z_SKIN_BOT + 0.5) / 2)) @ Matrix.Diagonal((TRUNK_HALF_W * 2, 0.6, Z_SKIN_BOT - 0.5, 1)), verts=box.verts[:])
cutter = bm_to_object(box, "trunk_cutter")
m = skin_ob.modifiers.new("trunk_cut", "BOOLEAN"); m.operation = "DIFFERENCE"; m.solver = "EXACT"; m.object = cutter; m.use_hole_tolerant = True
skin = evaluated_bm(skin_ob)
print("skin:", len(skin.verts), "verts")
built["skin__trunk"] = skin
skin_bvh = BVHTree.FromBMesh(skin); tucked = 0
for k, bm in built.items():
    if k.split("__")[0] not in ("nerve", "lig"): continue
    for v in bm.verts:
        loc, nrm, idx, dist = skin_bvh.find_nearest(v.co)
        if loc is not None and (v.co - loc).dot(nrm) > -0.0004: v.co = v.co - nrm * ((v.co - loc).dot(nrm) + 0.001); tucked += 1
print("tucked:", tucked)

objects = []
for k, bm in built.items():
    v, t = to_arrays(bm, center=CENTER); objects.append({"name": k, "layer": k.split("__")[0], "verts": v, "tris": t})
meta = {"frame": "L2-body-centred; right=-x, anterior=-y, up=+z", "unit": "m", "attribution": ATTR, "levels": ["T12", "L1", "L2", "L3", "L4", "L5", "S1-2"]}
json.dump({"meta": meta, "objects": objects}, open(f"{OUTS}/spine_a.json", "w"), separators=(",", ":"))
print("exported spine_a:", len(objects), "objects,", sum(len(o["verts"]) // 3 for o in objects), "verts,", os.path.getsize(f"{OUTS}/spine_a.json") // 1024, "KB")

# ---- previews ----
POST, LAT, UPV = Vector((0, 1, 0)), Vector((1, 0, 0)), Vector((0, 0, 1))   # posterior = +y; left side = +x
def look2(cam, sun, pos, up):
    fwd = (-pos).normalized(); right = fwd.cross(up).normalized(); up2 = right.cross(fwd).normalized()
    m = Matrix((right, up2, -fwd)).transposed(); cam.location = pos; cam.rotation_quaternion = m.to_quaternion(); sun.rotation_quaternion = (m @ Matrix.Rotation(0.5, 3, 'X') @ Matrix.Rotation(-0.4, 3, 'Y')).to_quaternion()
zana.look = look2
full = objects
rebuild_scene(full, meta); render_views({"skin_post": (POST + LAT * 0.3 + UPV * 0.1, UPV), "skin_lat": (LAT + POST * 0.2, UPV)}, "spine_a", dist=1.05, res=700, samples=14)
rebuild_scene([o for o in full if o["layer"] in ("bone", "disc", "lig", "nerve")], meta); render_views({"bones_post": (POST + LAT * 0.25 + UPV * 0.15, UPV), "bones_lat": (LAT + POST * 0.15, UPV)}, "spine_a", dist=0.55, res=700, samples=14)
