import bpy, bmesh, json, os
from mathutils import Vector

SRC = "/home/claude/Z-Anatomy/Startup.blend"
OUT = "/home/claude/out"; os.makedirs(OUT, exist_ok=True)
CUT_PROXIMAL = 0.065      # keep 6.5 cm proximal to carpal centre (radius/ulna/nerve trunk)
NERVE_R = {"trunk": 0.0018, "branch": 0.0009}   # tube radius in m

SELECT = {
    "bone__scaphoid":   "Scaphoid bone.r",   "bone__lunate":    "Lunate bone.r",
    "bone__triquetrum": "Triquetrum bone.r", "bone__pisiform":  "Pisiform bone.r",
    "bone__trapezium":  "Trapezium bone.r",  "bone__trapezoid": "Trapezoid bone.r",
    "bone__capitate":   "Capitate bone.r",   "bone__hamate":    "Hamate bone.r",
    "bone__radius_distal": "Radius.r",       "bone__ulna_distal":  "Ulna.r",
    "bone__mc1": "First metacarpal bone.r",  "bone__mc2": "Second metacarpal bone.r",
    "bone__mc3": "Third metacarpal bone.r",  "bone__mc4": "Fourth metacarpal bone.r",
    "bone__mc5": "Fifth metacarpal bone.r",
    "nerve__median":                 "Median nerve.r",
    "nerve__median_palmar_branch":   "Palmar branch of median nerve.r",
    "nerve__median_digital_common":  "Common palmar digital branches of median nerve.r",
    "nerve__median_digital_proper":  "Proper palmar digital branches of median nerve.r",
    "lig__tcl": "Flexor retinaculum of wrist.r",
}
CUT_THESE = {"bone__radius_distal", "bone__ulna_distal", "nerve__median", "nerve__median_palmar_branch"}
CARPALS = [k for k in SELECT if k.startswith("bone__") and "mc" not in k and "distal" not in k]

bpy.ops.wm.open_mainfile(filepath=SRC, load_ui=False)
objs = bpy.data.objects

# thicken nerve curves before evaluation
for key, name in SELECT.items():
    if key.startswith("nerve__"):
        c = objs[name].data
        c.bevel_depth = NERVE_R["trunk"] if key == "nerve__median" else NERVE_R["branch"]
        c.bevel_resolution = 6
        c.use_fill_caps = True
dg = bpy.context.evaluated_depsgraph_get(); dg.update()

def world_mesh(name):
    """evaluated (modifiers applied) mesh in world space -> (verts, tris)"""
    o = objs[name].evaluated_get(dg)
    me = o.to_mesh()
    me.transform(objs[name].matrix_world)
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    return bm

def bbox_center(bm):
    xs = [v.co for v in bm.verts]
    mn = Vector(map(min, zip(*xs))); mx = Vector(map(max, zip(*xs)))
    return (mn + mx) / 2

meshes = {k: world_mesh(n) for k, n in SELECT.items()}
center = sum((bbox_center(meshes[k]) for k in CARPALS), Vector()) / len(CARPALS)
cut_z = center.z + CUT_PROXIMAL
print("carpal centre", tuple(round(x, 4) for x in center), "cut z", round(cut_z, 4))

for k in CUT_THESE:
    bm = meshes[k]
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, cut_z), plane_no=(0, 0, 1),
                           clear_outer=True, clear_inner=False)
    boundary = [e for e in bm.edges if e.is_boundary]
    if boundary:
        bmesh.ops.holes_fill(bm, edges=boundary, sides=0)
        bmesh.ops.triangulate(bm, faces=bm.faces)
    print(f"cut {k}: {len(bm.verts)} verts")

# orientation helpers
# verified from bone positions: right hand in anatomical position, body faces -Y
palmar = Vector((0, -1, 0)); distal = Vector((0, 0, -1)); radial = Vector((-1, 0, 0))

# ---- JSON for the browser viewer (metres, centred) ----
out = {"meta": {"palmar": list(palmar), "distal": list(distal), "radial": list(radial), "unit": "m",
                "attribution": "Z-Anatomy CC BY-SA 4.0 / BodyParts3D CC BY-SA 2.1 JP"},
       "objects": []}
total_v = total_t = 0
for k, bm in meshes.items():
    bm.verts.ensure_lookup_table()
    idx = {v: i for i, v in enumerate(bm.verts)}
    verts = [round(c, 5) for v in bm.verts for c in (v.co - center)]
    tris = [idx[v] for f in bm.faces for v in f.verts]
    out["objects"].append({"name": k, "layer": k.split("__")[0], "verts": verts, "tris": tris})
    total_v += len(bm.verts); total_t += len(bm.faces)
json.dump(out, open(f"{OUT}/wrist.json", "w"), separators=(",", ":"))
print(f"json: {total_v} verts, {total_t} tris, {os.path.getsize(f'{OUT}/wrist.json')//1024} KB")

# ---- clean .blend + .glb (fresh file, only our objects, conventional names) ----
bpy.ops.wm.read_homefile(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"; scene.unit_settings.length_unit = "MILLIMETERS"
cols = {}
for o in out["objects"]:
    layer = o["layer"]
    if layer not in cols:
        cols[layer] = bpy.data.collections.new(layer); scene.collection.children.link(cols[layer])
    me = bpy.data.meshes.new(o["name"])
    v = o["verts"]; t = o["tris"]
    me.from_pydata([v[i:i+3] for i in range(0, len(v), 3)], [], [t[i:i+3] for i in range(0, len(t), 3)])
    me.update(); me.validate()
    for p in me.polygons: p.use_smooth = True
    ob = bpy.data.objects.new(o["name"], me); cols[layer].objects.link(ob)
    mat = bpy.data.materials.get(f"mat__{layer}") or bpy.data.materials.new(f"mat__{layer}")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = {"bone": (0.90, 0.86, 0.76, 1), "nerve": (0.95, 0.80, 0.25, 1), "lig": (0.85, 0.85, 0.80, 1)}[layer]
    me.materials.append(mat)
for k, v in out["meta"].items():
    scene[k] = str(v)
bpy.ops.wm.save_as_mainfile(filepath=f"{OUT}/carpal_tunnel_base.blend")
bpy.ops.export_scene.gltf(filepath=f"{OUT}/wrist.glb", export_format="GLB", export_apply=True)
print("saved blend + glb")

