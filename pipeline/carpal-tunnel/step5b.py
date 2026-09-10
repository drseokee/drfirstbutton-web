import bpy, bmesh
from mathutils import Vector
from zana import *

Z0 = Vector((0, 0, 0))
bpy.ops.wm.open_mainfile(filepath=f"{OUT}/wrist_step5a.blend")
O = bpy.data.objects
def local_bm(name):
    bm = bmesh.new(); bm.from_mesh(O[name].data); bmesh.ops.triangulate(bm, faces=bm.faces); return bm

built = {o.name: local_bm(o.name) for o in O if o.type == "MESH" and o.name not in ("skin__hand",)}

# ---- 1. TCL: Z-Anatomy's retinaculum is a cuff with no roof over the tunnel midline -> build the band procedurally ----
built.pop("lig__tcl_raw")
built["lig__tcl"] = build_tcl(O)

# ---- 2. skin envelope from the union of everything ----
union = join_bms([bm.copy() for bm in built.values()])
bpy.ops.wm.read_homefile(use_empty=True)
# two envelopes: padded (subcutaneous closing) for the palm/wrist, lean (+3.2 mm) for the fingers — then welded at the MCP line
Z_SPLIT = -0.068                                                       # just proximal to the MCP joints: fingers distal of this get no padding
def envelope(padded):
    o = bm_to_object(union.copy(), "skin_src_" + ("pad" if padded else "lean"))
    chain = ([("REMESH", dict(mode="VOXEL", voxel_size=0.0018)), ("SMOOTH", dict(factor=1.0, iterations=3)),
              ("DISPLACE", dict(strength=0.0065, mid_level=0, direction="NORMAL")), ("REMESH", dict(mode="VOXEL", voxel_size=0.0018)), ("SMOOTH", dict(factor=1.0, iterations=6)),
              ("DISPLACE", dict(strength=-0.0033, mid_level=0, direction="NORMAL"))] if padded else
             [("REMESH", dict(mode="VOXEL", voxel_size=0.0018)), ("SMOOTH", dict(factor=1.0, iterations=4)), ("DISPLACE", dict(strength=0.0032, mid_level=0, direction="NORMAL"))])
    chain += [("REMESH", dict(mode="VOXEL", voxel_size=0.0016))]
    for kind, kw in chain:
        m = o.modifiers.new(kind.lower() + str(len(o.modifiers)), kind)
        for k, v in kw.items(): setattr(m, k, v)
    return evaluated_bm(o)
pad = envelope(True); cut_z(pad, Z_SPLIT, keep="above", cap=True)      # palm + wrist (z > split)
lean = envelope(False); cut_z(lean, Z_SPLIT, keep="below", cap=True)   # fingers (z < split)
ob = bm_to_object(join_bms([pad, lean]), "skin_src")
for kind, kw in [("REMESH", dict(mode="VOXEL", voxel_size=0.0016)), ("SMOOTH", dict(factor=1.0, iterations=5))]:   # weld the two halves and blur the step at the seam
    m = ob.modifiers.new(kind.lower() + "w", kind)
    for k, v in kw.items(): setattr(m, k, v)
# finger gaps: thin slabs between adjacent fingers, starting 6 mm distal to the proximal phalanx base (web stays)
from mathutils import Matrix
def smooth01(t): t = max(0.0, min(1.0, t)); return t * t * (3 - 2 * t)
def centre(k):
    mn, mx = bbox(built[k]); return (mn + mx) / 2
cutters = bmesh.new()
P = Vector((0, -1, 0))
for i in (2, 3, 4):
    axes = {}
    for f in (i, i + 1):
        pp, dp = centre(f"bone__pp{f}"), centre(f"bone__dp{f}")
        a = (dp - pp).normalized()
        base = pp - a * ((bbox(built[f"bone__pp{f}"])[1] - bbox(built[f"bone__pp{f}"])[0]).length / 2)
        axes[f] = (base, dp + a * 0.015)
    pb = (axes[i][0] + axes[i + 1][0]) / 2; p1 = (axes[i][1] + axes[i + 1][1]) / 2
    # the gap must begin distal to the digital-nerve fork in this web: walk along the web line until no nerve is within 2.2 mm
    NERVE_PTS = [v.co for k in ("nerve__median_digital_common", "nerve__median_digital_proper") for v in built[k].verts]
    dirw = (p1 - pb).normalized(); nw = dirw.cross(P).normalized(); s = 0.013
    p0 = pb + dirw * s
    # the digital nerves run right between the fingers: past the web, nudge each one to its own finger's side of the gap
    moved = 0
    for k in ("nerve__median_digital_common", "nerve__median_digital_proper"):
        for v in built[k].verts:
            d = v.co - pb; along = d.dot(dirw); dn = d.dot(nw)
            if along > s - 0.002 and abs(dn) < 0.0020:
                w = smooth01((along - (s - 0.002)) / 0.004)                 # ease in over 4 mm
                v.co += nw * ((0.0020 - abs(dn)) * (1 if dn >= 0 else -1) * w); moved += 1
    print(f"  web {i}-{i+1}: gap from {s*1e3:.0f} mm; {moved} nerve points eased to their finger")
    a = (p1 - p0).normalized(); n = a.cross(P).normalized(); p = n.cross(a).normalized()
    L = (p1 - p0).length
    box = bmesh.new(); bmesh.ops.create_cube(box, size=1.0)
    M = Matrix.Translation((p0 + p1) / 2) @ Matrix((n, p, a)).transposed().to_4x4() @ Matrix.Diagonal((0.0022, 0.05, L + 0.006, 1))
    bmesh.ops.transform(box, matrix=M, verts=box.verts[:])
    me = bpy.data.meshes.new("cut"); box.to_mesh(me); cutters.from_mesh(me); bpy.data.meshes.remove(me)
cob = bm_to_object(cutters, "finger_cutters")
m = ob.modifiers.new("gaps", "BOOLEAN"); m.operation = "DIFFERENCE"; m.solver = "EXACT"; m.object = cob; m.use_hole_tolerant = True
for kind, kw in [("REMESH", dict(mode="VOXEL", voxel_size=0.0015)), ("SMOOTH", dict(factor=1.0, iterations=6)), ("DECIMATE", dict(ratio=0.4))]:
    m = ob.modifiers.new(kind.lower() + "2", kind)
    for k, v in kw.items(): setattr(m, k, v)
skin = evaluated_bm(ob); print("skin:", len(skin.verts), "verts")
built["skin__hand"] = skin

# ---- 3. section variants at the hook of hamate: keep proximal side ----
def zjit(k): return (hash(k) % 11 - 5) * 0.00003   # ±0.15 mm per object so neighbouring cut faces are never coplanar (no z-fighting)
Z_HOOK = 0.008   # section plane: proximal part of the ligament band; the HAND side is kept, forearm removed
Z_TENDON = -0.020   # Z-Anatomy tendon fans are kept only distal to the ligament (tubes take over inside the tunnel)
cut = {}
for k, bm in list(built.items()):
    if k == "skin__hand":
        c = bm.copy(); cut_z(c, Z_HOOK, keep="below", cap=False)
    elif k in ("tendon__fds", "tendon__fdp", "tendon__fpl"):
        c = cut_z_bool(bm.copy(), Z_TENDON, keep="below")
    elif k.split("__")[0] in ("bone", "nerve", "lig"):      # clean closed meshes: plain bisect + cap is more reliable than boolean
        c = bm.copy(); cut_z(c, Z_HOOK + zjit(k), keep="below", cap=True, ngon=(k.startswith("lig")))   # ligament section is C-shaped
    else:
        c = cut_z_bool(bm.copy(), Z_HOOK + zjit(k), keep="below")
    if len(c.verts) > 0 and len(c.faces) > 0:
        cut[k + "__cut"] = c
    else:
        c.free()
print("cut variants:", len(cut), "of", len(built))
print("removed entirely (proximal):", [k for k in built if k + "__cut" not in cut])

# ---- 4. export ----
objects = []
for k, bm in list(built.items()) + list(cut.items()):
    v, t = to_arrays(bm, center=Z0)
    objects.append({"name": k, "layer": k.split("__")[0], "verts": v, "tris": t})
meta = {"palmar": list(PALMAR), "distal": list(DISTAL), "radial": list(RADIAL), "unit": "m",
        "section_plane_z": Z_HOOK, "section_label": "손목터널 단면 (인대 근위부 레벨, 손 쪽 보존)", "attribution": ATTR}
export_all(objects, meta, "wrist_step5b")

# ---- 5. previews ----
sc = bpy.context.scene
full = [o for o in sc.objects if o.type == "MESH" and not o.name.endswith("__cut")]
cutobjs = [o for o in sc.objects if o.type == "MESH" and o.name.endswith("__cut")]
for o in cutobjs: o.hide_render = True
render_views({"palmar": STD_VIEWS["palmar"], "oblique": STD_VIEWS["oblique"]}, "s5_full", dist=0.40, res=640, samples=16)
render_views({"palmar": STD_VIEWS["palmar"]}, "s5_noskin", hide_layers=("skin",), dist=0.30, res=720, samples=20)
for o in full: o.hide_render = True
for o in cutobjs: o.hide_render = o.name.startswith("skin")
render_views({"section_distal": (DISTAL + PALMAR * 0.25 + RADIAL * 0.15, PALMAR),
              "section_oblique": (DISTAL * 0.7 + PALMAR * 0.9 + RADIAL * 0.6, PALMAR)}, "s5_cut", dist=0.16, res=720, samples=24)
