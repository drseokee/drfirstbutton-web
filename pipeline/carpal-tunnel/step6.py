import bpy, bmesh, json, math
from mathutils import Vector, Matrix
from zana import *

Z0 = Vector((0, 0, 0))
bpy.ops.wm.read_homefile(use_empty=True)
d = json.load(open(f"{OUT}/wrist_step5.json"))
objs = {o["name"]: o for o in d["objects"]}
def V(o, i): v = o["verts"]; return Vector((v[3*i], v[3*i+1], v[3*i+2]))
def nverts(o): return len(o["verts"]) // 3
def normals(o):
    bm = bm_from_arrays([tuple(o["verts"][i:i+3]) for i in range(0, len(o["verts"]), 3)], [tuple(o["tris"][i:i+3]) for i in range(0, len(o["tris"]), 3)])
    bm.verts.ensure_lookup_table(); bm.normal_update()
    return [v.normal.copy() for v in bm.verts], bm
def smooth01(t): t = max(0.0, min(1.0, t)); return t * t * (3 - 2 * t)

TCL_PROX, TCL_DIST = 0.0065, -0.0085

# ---- 0. tuck anything that pokes through the skin back inside (full-model variants only) ----
from mathutils.bvhtree import BVHTree
skin_o = objs["skin__hand"]
skin_bm = bm_from_arrays([tuple(skin_o["verts"][i:i+3]) for i in range(0, len(skin_o["verts"]), 3)], [tuple(skin_o["tris"][i:i+3]) for i in range(0, len(skin_o["tris"]), 3)])
skin_bm.normal_update(); bvh = BVHTree.FromBMesh(skin_bm)
INSIDE = 0.0010
for name, o in objs.items():
    if name.endswith("__cut") or o["layer"] in ("skin",): continue
    v = o["verts"]; moved = 0; worst = 0
    for i in range(0, len(v), 3):
        p = Vector(v[i:i+3]); loc, nrm, idx, dist = bvh.find_nearest(p)
        if loc is None: continue
        signed = (p - loc).dot(nrm)          # > 0 : outside the skin
        if signed > 0.0002:                  # only points truly outside the skin; move straight inward along the skin normal
            worst = max(worst, signed)
            q = p - nrm * (signed + 0.0008); v[i], v[i+1], v[i+2] = round(q.x, 5), round(q.y, 5), round(q.z, 5); moved += 1
    if moved: print(f"tucked {name:34} {moved:5} verts (max protrusion {worst*1e3:.1f} mm)")
skin_bm.free()
# ---- 1. TCL "thick" morph: deep surface bulges into the tunnel (+y = dorsal), outer surface slightly palmar ----
for name in ("lig__tcl", "lig__tcl__cut"):
    o = objs[name]; nrm, bm = normals(o); delta = []
    for i in range(nverts(o)):
        p = V(o, i); n = nrm[i]
        zc = 1 - abs((p.z - (TCL_PROX + TCL_DIST) / 2) / ((TCL_PROX - TCL_DIST) / 2)) * 0.5   # 1 at band centre, 0.5 at edges
        xc = 1 - min(1, abs(p.x) / 0.0185) * 0.6                                             # more in the middle of the arch
        w = zc * xc
        if n.y > 0.4:   dy = 0.0028 * w          # deep surface: into the tunnel
        elif n.y < -0.4: dy = -0.0008 * w        # outer surface: slight palmar bulge
        else: dy = 0.0010 * w                    # edges/caps: provisional
        delta += [0, round(dy, 5), 0]
    # cut faces and edge walls: their vertices coincide with deep/outer-surface vertices (split for shading) ->
    # copy the delta of the coincident surface vertex so the section face thickens together with the band
    key = lambda i: (round(V(o, i).x, 5), round(V(o, i).y, 5), round(V(o, i).z, 5))
    surf = {}
    for i in range(nverts(o)):
        if abs(nrm[i].y) > 0.4: surf.setdefault(key(i), delta[3 * i + 1])
    fixed = 0
    for i in range(nverts(o)):
        if abs(nrm[i].y) <= 0.4 and key(i) in surf:
            delta[3 * i + 1] = surf[key(i)]; fixed += 1
    print(f"{name}: {fixed} cap/edge vertices follow the surfaces")
    o["morphs"] = {"thick": delta}
    bm.free()
print("TCL morphs done")

# ---- 2. nerve "compressed" morph: flattened under the ligament, scaled about the dorsal (tendon-side) surface ----
for name in ("nerve__median", "nerve__median__cut"):
    o = objs[name]; n = nverts(o); pts = [V(o, i) for i in range(n)]; delta = []
    for i, p in enumerate(pts):
        w = smooth01((p.z - (TCL_DIST - 0.006)) / 0.006) * smooth01(((TCL_PROX + 0.006) - p.z) / 0.006)
        if w <= 0: delta += [0, 0, 0]; continue
        ring = [q for q in pts if abs(q.z - p.z) < 0.0012]
        cx = sum(q.x for q in ring) / len(ring); ymax = max(q.y for q in ring)
        dy = (p.y - ymax) * (0.30 - 1) * w        # top moves down toward the tendons, bottom stays
        dx = (p.x - cx) * 0.65 * w                # widens sideways
        delta += [round(dx, 5), round(dy, 5), 0]
    o["morphs"] = {"compressed": delta}
print("nerve morphs done")

# ---- 2b. tendon "swollen" morph: tenosynovial thickening — the 9 tunnel tendons enlarge inside the ligament band ----
for name in [k for k in objs if k.startswith(("tendon__fds", "tendon__fdp", "tendon__fpl1")) and k.endswith("__cut") and k not in ("tendon__fds__cut", "tendon__fdp__cut", "tendon__fpl__cut")]:
    o = objs[name]; n = nverts(o); pts = [V(o, i) for i in range(n)]; delta = []
    for p in pts:
        w = smooth01((p.z - (TCL_DIST - 0.008)) / 0.008) * smooth01(((TCL_PROX + 0.010) - p.z) / 0.008)
        if w <= 0: delta += [0, 0, 0]; continue
        ring = [q for q in pts if abs(q.z - p.z) < 0.0012]
        cx = sum(q.x for q in ring) / len(ring); cy = sum(q.y for q in ring) / len(ring)
        delta += [round((p.x - cx) * 0.30 * w, 5), round((p.y - cy) * 0.45 * w, 5), 0]   # +30 % wide, +45 % thick
    o.setdefault("morphs", {})["swollen"] = delta
# ---- 2c. PL / FCR react to the thickened ligament: PL (superficial) is lifted palmar, FCR (own compartment) is squeezed ----
for name, mode in (("tendon__pl__cut", "lift"), ("tendon__fcr__cut", "squeeze")):
    o = objs[name]; n = nverts(o); pts = [V(o, i) for i in range(n)]; delta = []
    for p in pts:
        w = smooth01((p.z - (TCL_DIST - 0.006)) / 0.006) * smooth01(((TCL_PROX + 0.008) - p.z) / 0.008)
        if w <= 0: delta += [0, 0, 0]; continue
        if mode == "lift": delta += [0, round(-0.0012 * w, 5), 0]
        else:
            ring = [q for q in pts if abs(q.z - p.z) < 0.0012]; cy = sum(q.y for q in ring) / len(ring); cx = sum(q.x for q in ring) / len(ring)
            delta += [round((p.x - cx) * 0.15 * w, 5), round((p.y - cy) * (-0.25) * w, 5), 0]
    o["morphs"] = {"patho": delta}
print("tendon morphs done")

# ---- 3. released halves: thick-state TCL split directly above the median nerve ----
_nvc = objs["nerve__median__cut"]; _nx = [V(_nvc, i).x for i in range(nverts(_nvc)) if abs(V(_nvc, i).z) < 0.003]
X_INC = sum(_nx) / len(_nx)
print(f"incision at x = {X_INC*1e3:+.1f} mm (over the nerve)")
o = objs["lig__tcl__cut"]; th = o["morphs"]["thick"]
verts = [(o["verts"][i] + th[i], o["verts"][i+1] + th[i+1], o["verts"][i+2] + th[i+2]) for i in range(0, len(o["verts"]), 3)]
tris = [tuple(o["tris"][i:i+3]) for i in range(0, len(o["tris"]), 3)]
from mathutils.bvhtree import BVHTree as _BVH
_thick_bm = bm_from_arrays(verts, tris); _thick_bvh = _BVH.FromBMesh(_thick_bm)
inc_pts = []
for zi in range(24):
    z = -0.0125 + (0.0075 + 0.0125) * zi / 23
    hit = _thick_bvh.ray_cast(Vector((X_INC, -0.06, z)), Vector((0, 1, 0)))
    if hit[0] is not None: inc_pts.append(Vector((X_INC, hit[0].y - 0.0002, z)))
_inc = bmesh.new()
for a, b in zip(inc_pts, inc_pts[1:]):      # thin rod segments along the outer surface
    seg = bmesh.new(); bmesh.ops.create_cone(seg, cap_ends=True, segments=8, radius1=0.00035, radius2=0.00035, depth=(b - a).length)
    M = Matrix.Translation((a + b) / 2) @ (b - a).normalized().to_track_quat("Z", "Y").to_matrix().to_4x4()
    bmesh.ops.transform(seg, matrix=M, verts=seg.verts[:]); me = bpy.data.meshes.new("s"); seg.to_mesh(me); _inc.from_mesh(me); bpy.data.meshes.remove(me)
bmesh.ops.triangulate(_inc, faces=_inc.faces)
v, tt = to_arrays(_inc, center=Z0)
objs["prop__incision__cut"] = {"name": "prop__incision__cut", "layer": "prop", "verts": v, "tris": tt, "hidden": True}
print("incision line:", len(inc_pts), "points")
for side, remove in (("radial", "outer"), ("ulnar", "inner")):
    bm = bm_from_arrays(verts, tris)
    cut_plane(bm, (X_INC, 0, 0), (1, 0, 0), remove=remove, cap=True, ngon=True)
    v, t = to_arrays(bm, center=Z0)
    objs[f"lig__tcl_released_{side}__cut"] = {"name": f"lig__tcl_released_{side}__cut", "layer": "lig", "verts": v, "tris": t, "hidden": True}
    print("released", side, len(v)//3, "verts")

# ---- 4. syringe prop (built at the inserted pose; viewer slides it along its axis) ----
# needle tip: beside the median nerve (ulnar side), at the nerve's own depth just under the ligament, above the tendon rows
_nv = objs["nerve__median__cut"]; _zt = 0.002
_ring = [V(_nv, i) for i in range(nverts(_nv)) if abs(V(_nv, i).z - _zt) < 0.0012]
_ncx = sum(p.x for p in _ring) / len(_ring); _ncy = sum(p.y for p in _ring) / len(_ring)
tip = Vector((_ncx + 0.0032, _ncy - 0.0003, _zt))
axis = Vector((0.0, 0.32, -1.0)).normalized()      # shallow entry: travels distally, only slightly dorsally, stays superficial to the tendons
print(f"needle tip at ({tip.x*1e3:+.1f}, {tip.y*1e3:+.1f}, {tip.z*1e3:+.1f}) mm; nerve centre ({_ncx*1e3:+.1f}, {_ncy*1e3:+.1f})")
def cyl(r, L, z0, segs=20):
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=r, radius2=r, depth=L)
    bmesh.ops.translate(bm, verts=bm.verts[:], vec=(0, 0, z0 + L / 2)); return bm
parts = [cyl(0.00045, 0.032, -0.032, 12), cyl(0.0025, 0.006, -0.038, 20), cyl(0.0045, 0.045, -0.083, 24), cyl(0.0012, 0.020, -0.103, 12), cyl(0.0055, 0.003, -0.106, 24)]
syr = join_bms(parts)
M = Matrix.Translation(tip) @ axis.to_track_quat("Z", "Y").to_matrix().to_4x4()   # local +Z -> axis, tip at origin
bmesh.ops.transform(syr, matrix=M, verts=syr.verts[:])
bmesh.ops.triangulate(syr, faces=syr.faces)
v, t = to_arrays(syr, center=Z0)
objs["prop__syringe__cut"] = {"name": "prop__syringe__cut", "layer": "prop", "verts": v, "tris": t, "hidden": True, "axis": list(axis), "tip": list(tip)}
print("syringe", len(v)//3, "verts")

# ---- 5. median-nerve skin territory mask on the full skin ----
skin = objs["skin__hand"]; nrm, bm = normals(skin)
def centre(name):
    o = objs[name]; xs = [V(o, i) for i in range(nverts(o))]
    return sum(xs, Vector()) / len(xs)
c_mc4, c_pp4, c_dp4 = centre("bone__mc4"), centre("bone__pp4"), centre("bone__dp4")
def x_split(z):    # ring-finger axis: median territory is radial (x smaller) to it
    if z > c_mc4.z: return c_mc4.x
    if z > c_pp4.z: t = (c_mc4.z - z) / (c_mc4.z - c_pp4.z); return c_mc4.x + (c_pp4.x - c_mc4.x) * t
    t = min(1, (c_pp4.z - z) / max(1e-6, (c_pp4.z - c_dp4.z))); return c_pp4.x + (c_dp4.x - c_pp4.x) * t
tips = [centre(f"bone__dp{i}") for i in (1, 2, 3)]
mask = []
for i in range(nverts(skin)):
    p = V(skin, i); n = nrm[i]
    palmar = n.y < -0.15
    in_area = p.z < 0.002 and p.x < x_split(p.z) + 0.001
    dorsal_tip = any((p - tp).length < 0.011 for tp in tips)
    m = 1.0 if (in_area and (palmar or dorsal_tip)) else 0.0
    if m and p.z > -0.008: m = smooth01((0.002 - p.z) / 0.010)   # fades in across the wrist crease
    mask.append(round(m, 2))
skin["overlay"] = {"median": mask}
print("skin mask: ", sum(1 for m in mask if m > 0.5), "of", len(mask), "verts")

d["objects"] = list(objs.values())
d["meta"]["stages"] = "see viewer"
json.dump(d, open(f"{OUT}/wrist_step6.json", "w"), separators=(",", ":"))
import os; print("json", os.path.getsize(f"{OUT}/wrist_step6.json") // 1024, "KB")
