import bpy, bmesh, json
from mathutils import Vector
from zana import *

objs = open_src()
CZ = CARPAL_CENTER.z
PROX_Z = CZ + 0.065           # proximal cut plane (same as Step 4)

def get(name, cut=True, cap=True):
    bm = world_bm(name)
    if cut: cut_z(bm, PROX_Z, keep="below", cap=cap)
    return bm

def get_join(names, cut=True):
    return join_bms([get(n, cut) for n in names])

def fuzzy(*keys, exclude=("foot", "toe", "ligament", "sheath", "capsule")):
    ks = [k.lower() for k in keys]
    return sorted(o.name for o in objs if o.type == "MESH" and o.name.endswith(".r")
                  and all(k in o.name.lower() for k in ks) and not any(e in o.name.lower() for e in exclude))

# ---- names ----
FING = ["first", "second", "third", "fourth", "fifth"]
phal = {}
for i, f in enumerate(FING, 1):
    for part, tag in (("Proximal", "pp"), ("Middle", "mp"), ("Distal", "dp")):
        n = f"{part} phalanx of {f} finger of hand.r"
        if n in objs: phal[f"bone__{tag}{i}"] = n
print("phalanges:", len(phal))
hypo_fdm = fuzzy("flexor digiti minimi", "hand") + fuzzy("flexor digiti minimi brevis")
print("FDM candidates:", hypo_fdm)

base_bones = {  # Step 4 set
    "bone__scaphoid": "Scaphoid bone.r", "bone__lunate": "Lunate bone.r", "bone__triquetrum": "Triquetrum bone.r",
    "bone__pisiform": "Pisiform bone.r", "bone__trapezium": "Trapezium bone.r", "bone__trapezoid": "Trapezoid bone.r",
    "bone__capitate": "Capitate bone.r", "bone__hamate": "Hamate bone.r",
    "bone__radius_distal": "Radius.r", "bone__ulna_distal": "Ulna.r",
    "bone__mc1": "First metacarpal bone.r", "bone__mc2": "Second metacarpal bone.r", "bone__mc3": "Third metacarpal bone.r",
    "bone__mc4": "Fourth metacarpal bone.r", "bone__mc5": "Fifth metacarpal bone.r"}
nerves = {"nerve__median": "Median nerve.r", "nerve__median_palmar_branch": "Palmar branch of median nerve.r",
          "nerve__median_digital_common": "Common palmar digital branches of median nerve.r",
          "nerve__median_digital_proper": "Proper palmar digital branches of median nerve.r"}
for key, name in nerves.items():
    c = objs[name].data; c.bevel_depth = 0.0018 if key == "nerve__median" else 0.0009; c.bevel_resolution = 6; c.use_fill_caps = True
refresh()

tendons = {
    "tendon__fds": ["Humero-ulnar head of flexor digitorum superficialis.r", "Radial head of flexor digitorum superficialis.r"],
    "tendon__fdp": ["Flexor digitorum profundus.r"],
    "tendon__fpl": ["Flexor pollicis longus.r"],
    "tendon__fcr": ["Flexor carpi radialis.r"],
    "tendon__pl":  ["Palmaris longus muscle.r"],
}
muscles = {
    "muscle__thenar": ["Abductor pollicis brevis.r", "Superficial head of flexor pollicis brevis.r", "Deep head of flexor pollicis brevis.r", "Opponens pollicis muscle.r"],
    "muscle__adductor_pollicis": ["Oblique head of adductor pollicis.r", "Transverse head of adductor pollicis.r"],
    "muscle__hypothenar": ["Abductor digiti minimi of hand.r", "Opponens digiti minimi muscle of hand.r"] + [n for n in hypo_fdm if "hand" in n.lower() or "brevis" in n.lower()][:1],
    "muscle__lumbricals": ["Lumbrical muscles of hand.r"],
    "muscle__interossei": ["Dorsal interossei muscles of hand.r", "Palmar interossei muscles.r"],
    "muscle__forearm": ["Pronator quadratus.r", "Humeral head of flexor carpi ulnaris.r", "Ulnar head of flexor carpi ulnaris.r",
                        "Brachioradialis muscle.r", "Abductor pollicis longus.r", "Extensor pollicis brevis.r", "Extensor pollicis longus.r",
                        "Extensor carpi radialis longus.r", "Extensor carpi radialis brevis.r", "Humeral head of extensor carpi ulnaris.r",
                        "Ulnar head of extensor carpi ulnaris.r", "Extensor digitorum.r", "Extensor indicis.r", "Extensor digiti minimi.r"],
}
for k, names in muscles.items():
    missing = [n for n in names if n not in objs]
    if missing: print("MISSING", k, missing)
    muscles[k] = [n for n in names if n in objs]

# ---- build ----
built = {}   # key -> bmesh (world coords)
for k, n in {**base_bones, **phal}.items():
    built[k] = get(n, cut=(k in ("bone__radius_distal", "bone__ulna_distal")))
for k, n in nerves.items():
    built[k] = get(n, cut=(k in ("nerve__median", "nerve__median_palmar_branch")))
built["lig__tcl_raw"] = get("Flexor retinaculum of wrist.r", cut=False)
for k, names in tendons.items(): built[k] = get_join(names)
for k, names in muscles.items(): built[k] = get_join(names)
for k, bm in built.items(): print(f"{k:28} {len(bm.verts):6} v")

# ---- skin envelope: voxel remesh of the union of solids ----
solid_keys = [k for k in built if k.startswith(("bone__", "tendon__", "muscle__"))]
union = join_bms([built[k].copy() for k in solid_keys])
bpy.ops.wm.read_homefile(use_empty=True)       # fresh scene for modifier evaluation
ob = bm_to_object(union, "skin_src")
m = ob.modifiers.new("r1", "REMESH"); m.mode = "VOXEL"; m.voxel_size = 0.0025
m = ob.modifiers.new("s1", "SMOOTH"); m.factor = 1.0; m.iterations = 8
m = ob.modifiers.new("d", "DISPLACE"); m.strength = 0.0035; m.mid_level = 0; m.direction = "NORMAL"
m = ob.modifiers.new("r2", "REMESH"); m.mode = "VOXEL"; m.voxel_size = 0.002
m = ob.modifiers.new("s2", "SMOOTH"); m.factor = 1.0; m.iterations = 6
m = ob.modifiers.new("dec", "DECIMATE"); m.ratio = 0.5
skin = evaluated_bm(ob)
print("skin:", len(skin.verts), "verts", len(skin.faces), "faces")
built["skin__hand"] = skin

# ---- export ----
objects = []
for k, bm in built.items():
    v, t = to_arrays(bm)
    objects.append({"name": k, "layer": k.split("__")[0], "verts": v, "tris": t})
meta = {"palmar": list(PALMAR), "distal": list(DISTAL), "radial": list(RADIAL), "unit": "m", "attribution": ATTR}
export_all(objects, meta, "wrist_step5a")
render_views(STD_VIEWS, "s5a_skin", alpha={"skin": 0.35})
render_views({"palmar": STD_VIEWS["palmar"], "oblique": STD_VIEWS["oblique"]}, "s5a_noskin", hide_layers=("skin",))
