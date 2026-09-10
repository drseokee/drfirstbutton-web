import bpy, bmesh, json, math
from mathutils import Vector, Matrix
from zana import *
import zana

# ---- frame: origin at the talus centre; anatomical axes in this file: lateral = -x, anterior = -y, up = +z (right foot) ----
ANKLE_CENTER = Vector((-0.072, 0.035, 0.066))
Z0 = Vector((0, 0, 0))
LEG_CUT_Z = ANKLE_CENTER.z + 0.085          # keep 8.5 cm of tibia/fibula above the ankle (skin envelope reaches this height)
STRUCT_CUT_Z = LEG_CUT_Z - 0.004               # everything else stops 4 mm lower so it stays under the skin's rounded top edge
OUTA = "/home/claude/out_ankle"; import os; os.makedirs(OUTA, exist_ok=True)

objs = open_src()
TOE = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth"}
def get(name, cut=False, cap=True):
    bm = world_bm(name)
    if cut: cut_z(bm, STRUCT_CUT_Z, keep="below", cap=cap)
    return bm
def get_join(names, cut=False):
    return join_bms([get(n, cut) for n in names if n in objs])

bones = {
    "bone__tibia_distal": ("Tibia.r", True), "bone__fibula_distal": ("Fibula.r", True),
    "bone__talus": ("Talus.r", False), "bone__calcaneus": ("Calcaneus.r", False), "bone__navicular": ("Navicular bone.r", False),
    "bone__cuboid": ("Cuboid bone.r", False), "bone__cun_med": ("Medial cuneiform bone.r", False), "bone__cun_int": ("Intermediate cuneiform bone.r", False), "bone__cun_lat": ("Lateral cuneiform bone.r", False),
}
for i, w in TOE.items():
    bones[f"bone__mt{i}"] = (f"{['First','Second','Third','Fourth','Fifth'][i-1]} metatarsal bone.r", False)
    bones[f"bone__pp{i}"] = (f"Proximal phalanx of {w} finger of foot.r", False)
    if i != 1: bones[f"bone__mp{i}"] = (f"Middle phalanx of {w} finger of foot.r", False)
    bones[f"bone__dp{i}"] = (f"Distal phalanx of {w} finger of foot.r", False)
ligs = {   # Z-Anatomy ligaments kept as background / reference (the three lateral ones are rebuilt procedurally in step B)
    "lig__atfl_ref": "Anterior talofibular ligament.r", "lig__cfl_ref": "Calcaneofibular ligament.r", "lig__ptfl_ref": "Posterior talofibular ligament.r",
    "lig__ant_tibfib": "Anterior tibiofibular ligament.r", "lig__post_tibfib": "Posterior tibiofibular ligament.r",
    "lig__talocalc_interosseous": "Talocalcaneal interosseous ligament.r", "lig__lat_talocalc": "Lateral talocalcaneal ligament.r",
    "lig__deltoid": "Deltoid ligament.r", "lig__spring": "Plantar calcaneonavicular ligament.r", "lig__bifurcate": "Calcaneonavicular ligament.r",
    "lig__dorsal_talonav": "Talonavicular ligament.r", "lig__dorsal_calccub": "Dorsal calcaneocuboid ligament.r",
    "lig__sup_fib_retinaculum": "Superior fibular retinaculum.r", "lig__inf_fib_retinaculum": "Inferior fibular retinaculum.r",
    "lig__sup_ext_retinaculum": "Superior extensor retinaculum of ankle.r", "lig__inf_ext_retinaculum": "Inferior extensor retinaculum of ankle.r",
}
tendons = {
    "tendon__fibularis_longus": (["Fibularis longus muscle.r"], True), "tendon__fibularis_brevis": (["Fibularis brevis muscle.r"], True),
    "tendon__tibialis_ant": (["Tibialis anterior muscle.r"], True), "tendon__tibialis_post": (["Tibialis posterior muscle.r"], True),
    "tendon__ehl": (["Extensor hallucis longus.r"], True), "tendon__edl": (["Extensor digitorum longus.r", "Tendon of extensor digitorum longus.r"], True),
    "tendon__fhl": (["Flexor hallucis longus.r"], True), "tendon__fdl": (["Flexor digitorum longus.r"], True),
    "tendon__achilles": (["Calcaneal tendon.r"], True), "tendon__fibularis_tertius": (["Fibularis tertius muscle.r"], True),
}
muscles = {"muscle__soleus": (["Soleus muscle.r"], True), "muscle__gastrocnemius": (["Lateral head of gastrocnemius.r", "Medial head of gastrocnemius.r"], True),
           "muscle__edb": (["Extensor digitorum brevis.r", "Extensor hallucis brevis.r"], False), "muscle__abd_hallucis": (["Abductor hallucis.r"], False),
           "muscle__abd_dig_min": (["Abductor digiti minimi of foot.r"], False), "muscle__fdb": (["Flexor digitorum brevis.r"], False),
           "muscle__plantar_aponeurosis": (["Plantar aponeurosis.r"], False)}
nerves = {"nerve__sural": "Sural nerve.r", "nerve__sup_fibular": "Superficial fibular nerve.r", "nerve__sup_fibular_digital": "Dorsal digital branches of superficial fibular nerve.r",
          "nerve__deep_fibular": "Deep fibular nerve.r", "nerve__tibial": "Tibial nerve.r",
          "nerve__med_dorsal_cut": "Medial dorsal cutaneous nerve of foot.r", "nerve__int_dorsal_cut": "Intermediate dorsal cutaneous nerve of foot.r"}   # the two terminal branches the superficial fibular nerve splits into above the ankle
vessels = {"vessel__small_saphenous": "Small saphenous vein.r", "vessel__great_saphenous": "Great saphenous vein.r", "vessel__post_tibial_a": "Posterior tibial artery.r", "vessel__ant_tibial_a": "Anterior tibial artery.r", "vessel__dorsalis_pedis": "Dorsalis pedis artery.r"}
RADIUS = {"nerve__med_dorsal_cut": 0.0009, "nerve__int_dorsal_cut": 0.0009, "nerve__sural": 0.0012, "nerve__sup_fibular": 0.0012, "nerve__sup_fibular_digital": 0.0006, "nerve__deep_fibular": 0.0010, "nerve__tibial": 0.0018,
          "vessel__small_saphenous": 0.0015, "vessel__great_saphenous": 0.0018, "vessel__post_tibial_a": 0.0013, "vessel__ant_tibial_a": 0.0012, "vessel__dorsalis_pedis": 0.0011}
for k, name in {**nerves, **vessels}.items():
    if name in objs and objs[name].type == "CURVE":
        c = objs[name].data
        for sp in c.splines:                                   # Z-Anatomy curves carry per-point radius multipliers (3-6x on vessels): normalise
            for p in (sp.points if sp.type != "BEZIER" else sp.bezier_points): p.radius = 1.0
        c.bevel_depth = RADIUS[k]; c.bevel_resolution = 6; c.use_fill_caps = True
refresh()

built = {}
missing = []
for k, (name, cut) in bones.items():
    if name in objs: built[k] = get(name, cut)
    else: missing.append(name)
for k, name in ligs.items():
    if name in objs: built[k] = get(name)
    else: missing.append(name)
for k, (names, cut) in {**tendons, **muscles}.items():
    present = [n for n in names if n in objs]; missing += [n for n in names if n not in objs]
    if present: built[k] = get_join(present, cut)
for k, name in {**nerves, **vessels}.items():
    if name in objs:
        bm = world_bm(name); cut_z(bm, LEG_CUT_Z - 0.012, keep="below", cap=True); built[k] = bm   # thin tubes stop 12 mm under the skin's top: no tips poking out of the rounded rim
    else: missing.append(name)
# small saphenous vein: keep its course behind the lateral malleolus and up the calf; drop Z-Anatomy's hairpin to the dorsal venous arch
if "vessel__small_saphenous" in built:
    cut_plane(built["vessel__small_saphenous"], (0, ANKLE_CENTER.y - 0.001, 0), (0, -1, 0), remove="outer", cap=True)
print("missing:", missing)
for k, bm in built.items(): print(f"{k:32} {len(bm.verts):6} v")

# ---- skin envelope: union of solids (bones, tendons, muscles, nerves, vessels), toe gaps carved like the finger gaps ----
solid = [k for k in built if k.split("__")[0] in ("bone", "tendon", "muscle", "nerve", "vessel", "lig")]
union = join_bms([built[k].copy() for k in solid])
bpy.ops.wm.read_homefile(use_empty=True)
ob = bm_to_object(union, "skin_src")
# extend the union 4 mm upward so the skin's top sits at LEG_CUT_Z after the closing below
for kind, kw in [("REMESH", dict(mode="VOXEL", voxel_size=0.0022)), ("SMOOTH", dict(factor=1.0, iterations=3)),
                 ("DISPLACE", dict(strength=0.0070, mid_level=0, direction="NORMAL")),          # dilate: valleys between structures close up
                 ("REMESH", dict(mode="VOXEL", voxel_size=0.0022)), ("SMOOTH", dict(factor=1.0, iterations=6)),
                 ("DISPLACE", dict(strength=-0.0035, mid_level=0, direction="NORMAL")),         # erode back: net +3.5 mm, but with the valleys filled (subcutaneous padding)
                 ("REMESH", dict(mode="VOXEL", voxel_size=0.0018)), ("SMOOTH", dict(factor=1.0, iterations=4))]:
    m = ob.modifiers.new(kind.lower() + str(len(ob.modifiers)), kind)
    for a, v in kw.items(): setattr(m, a, v)
# toe gaps: slabs between adjacent toes from 8 mm past the proximal phalanx bases to beyond the tips
def centre(k): mn, mx = bbox(built[k]); return (mn + mx) / 2
cutters = bmesh.new(); UP = Vector((0, 0, 1))
def smooth01(t): t = max(0.0, min(1.0, t)); return t * t * (3 - 2 * t)
for i in (1, 2, 3, 4):
    axes = {}
    for f in (i, i + 1):
        pp, dp = centre(f"bone__pp{f}"), centre(f"bone__dp{f}"); a = (dp - pp).normalized()
        base = pp - a * ((bbox(built[f"bone__pp{f}"])[1] - bbox(built[f"bone__pp{f}"])[0]).length / 2)
        axes[f] = (base + a * 0.008, dp + a * 0.012)
    p0 = (axes[i][0] + axes[i + 1][0]) / 2; p1 = (axes[i][1] + axes[i + 1][1]) / 2
    a = (p1 - p0).normalized(); n = a.cross(UP).normalized(); p = n.cross(a).normalized(); L = (p1 - p0).length
    box = bmesh.new(); bmesh.ops.create_cube(box, size=1.0)
    M = Matrix.Translation((p0 + p1) / 2) @ Matrix((n, p, a)).transposed().to_4x4() @ Matrix.Diagonal((0.0022, 0.05, L + 0.006, 1))
    bmesh.ops.transform(box, matrix=M, verts=box.verts[:])
    me = bpy.data.meshes.new("cut"); box.to_mesh(me); cutters.from_mesh(me); bpy.data.meshes.remove(me)
    # nerves between toes: ease each to its own toe's side
    for k in [x for x in built if x.startswith("nerve__sup_fibular_digital")]:
        for v in built[k].verts:
            d = v.co - p0; along = d.dot(a); dn = d.dot(n)
            if along > -0.002 and abs(dn) < 0.002:
                w = smooth01((along + 0.002) / 0.004); v.co += n * ((0.002 - abs(dn)) * (1 if dn >= 0 else -1) * w)
cob = bm_to_object(cutters, "toe_cutters")
m = ob.modifiers.new("gaps", "BOOLEAN"); m.operation = "DIFFERENCE"; m.solver = "EXACT"; m.object = cob; m.use_hole_tolerant = True
for kind, kw in [("REMESH", dict(mode="VOXEL", voxel_size=0.0016)), ("SMOOTH", dict(factor=1.0, iterations=6)), ("DECIMATE", dict(ratio=0.4))]:
    m = ob.modifiers.new(kind.lower() + "2", kind)
    for a_, v in kw.items(): setattr(m, a_, v)
skin = evaluated_bm(ob); cut_z(skin, LEG_CUT_Z, keep="below", cap=True); print("skin:", len(skin.verts), "verts")
built["skin__foot"] = skin
# 4) tuck: anything thin that ended up outside the padded skin (nerves, vessels, retinacula) is pushed 1 mm inside along the skin normal
from mathutils.bvhtree import BVHTree
skin_bvh = BVHTree.FromBMesh(skin); tucked = 0
for k, bm in built.items():
    if k.split("__")[0] not in ("nerve", "vessel", "lig", "tendon"): continue
    for v in bm.verts:
        loc, nrm, idx, dist = skin_bvh.find_nearest(v.co)
        if loc is not None and (v.co - loc).dot(nrm) > -0.0004: v.co = v.co - nrm * ((v.co - loc).dot(nrm) + 0.0010); tucked += 1
print("tucked inside the skin:", tucked, "verts")

# ---- export ----
objects = []
for k, bm in built.items():
    v, t = to_arrays(bm, center=ANKLE_CENTER)
    objects.append({"name": k, "layer": k.split("__")[0], "verts": v, "tris": t})
meta = {"frame": "ankle-centred (talus centre); lateral=-x, anterior=-y, up=+z; right foot", "unit": "m", "attribution": ATTR,
        "lateral_malleolus_tip": [round(c - o, 5) for c, o in zip((-0.102, 0.052, 0.055), ANKLE_CENTER)]}
zana.OUT = OUTA
json.dump({"meta": meta, "objects": objects}, open(f"{OUTA}/ankle_a.json", "w"), separators=(",", ":"))
rebuild_scene(objects, meta)
bpy.ops.wm.save_as_mainfile(filepath=f"{OUTA}/ankle_a.blend")
print(f"exported ankle_a: {sum(len(o['verts'])//3 for o in objects)} verts, {os.path.getsize(f'{OUTA}/ankle_a.json')//1024} KB")

# ---- previews: lateral view (from -x), anterolateral ----
LAT, ANT, UPV = Vector((-1, 0, 0)), Vector((0, -1, 0)), Vector((0, 0, 1))
from mathutils import Matrix
def look2(cam, sun, pos, up):
    fwd = (-pos).normalized(); right = fwd.cross(up).normalized(); up2 = right.cross(fwd).normalized()
    m = Matrix((right, up2, -fwd)).transposed(); cam.location = pos; cam.rotation_quaternion = m.to_quaternion(); sun.rotation_quaternion = (m @ Matrix.Rotation(0.5, 3, 'X') @ Matrix.Rotation(-0.4, 3, 'Y')).to_quaternion()
zana.look = look2
render_views({"lateral_skin": (LAT + ANT * 0.15, UPV)}, "ankle_a", dist=0.40, res=700, samples=16)
render_views({"lateral_noskin": (LAT + ANT * 0.3, UPV), "anterolat_noskin": (LAT * 0.8 + ANT * 0.7 + UPV * 0.25, UPV)}, "ankle_a", hide_layers=("skin", "muscle"), dist=0.30, res=700, samples=16)
