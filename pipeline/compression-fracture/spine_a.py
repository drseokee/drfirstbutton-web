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
for d in ["T12-L1", "L1-L2", "L2-L3", "L3-L4", "L4-L5", "L5-S1"]:
    built[f"disc__{d.lower().replace('-', '_')}"] = get(f"Intervertebral disc {d}", clipz=False)
built["nerve__dural_sac"] = get("Spinal dura")
for k, n in {"lig__pll": "Posterior longitudinal ligament", "lig__flava": "Ligamenta flava"}.items():
    if n in objs: built[k] = get(n)

STRUCT_CUT_Z = Z_TOP
# ---- Z-Anatomy's cauda is one trunk with branches: build an anatomical bundle instead ----
# conus ends at L1-L2; below it the roots run as separate strands inside the sac and each leaves at its own level
# canal centreline from the bones themselves: a ray through each body at mid-height finds the posterior wall (2nd hit) and, where present, the lamina (3rd hit);
# the canal centre is their midpoint, or posterior wall + 9 mm (typical AP canal radius) where the lamina lies at another height
CANAL = []
for lv in ["T12", "L1", "L2", "L3", "L4", "L5"]:
    bm_ = built[f"bone__{lv.lower()}"]; vs = [v.co for v in bm_.verts]; bvh_ = BVHTree.FromBMesh(bm_)
    ymin = min(v.y for v in vs); ymax = max(v.y for v in vs); yp = ymin + (ymax - ymin) * 0.42
    body_ = [v for v in vs if v.y < yp]; zmid = (min(v.z for v in body_) + max(v.z for v in body_)) / 2
    ys_h = []
    for x0 in (-0.003, 0.0, 0.003):
        p = Vector((x0, ymin - 0.01, zmid)); hits = []
        for _ in range(8):
            loc, nrm, idx, dist = bvh_.ray_cast(p, Vector((0, 1, 0)), 0.15)
            if loc is None: break
            hits.append(loc.y); p = loc + Vector((0, 0.0002, 0))
        if len(hits) >= 4: ys_h.append((hits[1] + hits[2]) / 2)
        elif len(hits) >= 2: ys_h.append(hits[1] + 0.009)
    if ys_h: CANAL.append((zmid, sum(ys_h) / len(ys_h)))
vs = [v.co for v in built["bone__sacrum"].verts]; s_top = max(v.z for v in vs); s_z = s_top - 0.02
sac_bvh = BVHTree.FromBMesh(built["bone__sacrum"]); p = Vector((0, min(v.y for v in vs) - 0.01, s_z)); hits = []
for _ in range(8):
    loc, nrm, idx, dist = sac_bvh.ray_cast(p, Vector((0, 1, 0)), 0.15)
    if loc is None: break
    hits.append(loc.y); p = loc + Vector((0, 0.0002, 0))
CANAL.append((s_z, (hits[1] + hits[2]) / 2 if len(hits) >= 4 else (hits[1] + 0.007 if len(hits) >= 2 else CANAL[-1][1] + 0.01)))
CANAL.append((Z_BOT, CANAL[-1][1] + 0.006)); CANAL.sort(key=lambda t: -t[0])
print("canal centres (z, y mm):", [(round(z_*1e3), round(y_*1e3, 1)) for z_, y_ in CANAL])
def sac_centre(z, dz=None):
    for (z0, y0), (z1, y1) in zip(CANAL, CANAL[1:]):
        if z1 <= z <= z0: u = (z0 - z) / max(1e-6, z0 - z1); return Vector((0, y0 + (y1 - y0) * u, z))
    return Vector((0, CANAL[0][1] if z > CANAL[0][0] else CANAL[-1][1], z))
def disc_z(name):
    vs = [v.co for v in built[name].verts]; return sum(v.z for v in vs) / len(vs)
CONUS_END = disc_z("disc__l1_l2") + 0.006
def tube_along(points, radius, segs=10):
    bm = bmesh.new(); rings = []
    for i, p in enumerate(points):
        t = (points[min(i + 1, len(points) - 1)] - points[max(i - 1, 0)]).normalized()
        a_ = Vector((1, 0, 0)) if abs(t.x) < 0.9 else Vector((0, 1, 0)); u = t.cross(a_).normalized(); w = t.cross(u)
        rings.append([bm.verts.new(p + u * (radius * math.cos(2 * math.pi * k / segs)) + w * (radius * math.sin(2 * math.pi * k / segs))) for k in range(segs)])
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(segs): bm.faces.new((r0[k], r0[(k + 1) % segs], r1[(k + 1) % segs], r1[k]))
    for ring, rev in ((rings[0], True), (rings[-1], False)):
        c0 = bm.verts.new(sum((v.co for v in ring), Vector()) / segs)
        for k in range(segs): bm.faces.new((ring[(k + 1) % segs], ring[k], c0) if rev else (ring[k], ring[(k + 1) % segs], c0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bmesh.ops.triangulate(bm, faces=bm.faces); return bm
def tube_along_r(points, radii, segs=14):
    bm = bmesh.new(); rings = []
    for i, p in enumerate(points):
        t = (points[min(i + 1, len(points) - 1)] - points[max(i - 1, 0)]).normalized()
        a_ = Vector((1, 0, 0)) if abs(t.x) < 0.9 else Vector((0, 1, 0)); u = t.cross(a_).normalized(); w = t.cross(u); r = radii[i]
        rings.append([bm.verts.new(p + u * (r * math.cos(2 * math.pi * k / segs)) + w * (r * 0.8 * math.sin(2 * math.pi * k / segs))) for k in range(segs)])
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(segs): bm.faces.new((r0[k], r0[(k + 1) % segs], r1[(k + 1) % segs], r1[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bmesh.ops.triangulate(bm, faces=bm.faces); return bm
# dural sac: Z-Anatomy's stops at L3, so build it along the canal from the block top to S2, tapering into the sacral canal (open ends)
zs_d = []; z = Z_TOP - 0.002
while z > Z_BOT + 0.002: zs_d.append(z); z -= 0.005
built["nerve__dural_sac"] = tube_along_r([sac_centre(z) for z in zs_d], [0.0078 if z > Z_BOT + 0.045 else 0.0078 - (Z_BOT + 0.045 - z) / 0.043 * 0.0045 for z in zs_d])
zs = []; z = Z_TOP - 0.003
while z > CONUS_END: zs.append(z); z -= 0.004
cord_pts = [sac_centre(z) or Vector((0, 0, z)) for z in zs]
for i in range(len(cord_pts)):                                                   # taper into the conus over the last 2 cm
    pass
built["nerve__conus"] = tube_along_r(cord_pts, [0.0045 if i < len(cord_pts) - 5 else 0.0045 * (len(cord_pts) - i) / 5 for i in range(len(cord_pts))], segs=12)
EXITS = {"L1": disc_z("disc__l1_l2"), "L2": disc_z("disc__l2_l3"), "L3": disc_z("disc__l3_l4"), "L4": disc_z("disc__l4_l5"), "L5": disc_z("disc__l5_s1"), "S1": Z_BOT + 0.028, "S2": Z_BOT + 0.014, "S3": Z_BOT + 0.004}
for side in (-1, 1):
    for ri, (lv, zx) in enumerate(EXITS.items()):
        pts = []; z = CONUS_END + 0.004; ang = (ri / len(EXITS)) * math.pi * 0.85 + 0.2; rr = 0.0022 + 0.0016 * (ri % 3)
        while z > zx:
            c = sac_centre(z) or Vector((0, 0, z)); pts.append(c + Vector((side * rr * math.cos(ang), 0.001 + rr * 0.6 * math.sin(ang), 0))); z -= 0.004
        c = sac_centre(zx) or Vector((0, 0, zx))
        for j in range(1, 5):                                                    # out through the foramen: lateral, slightly down and forward
            u = j / 4; pts.append(c + Vector((side * (0.005 + 0.020 * u), -0.003 - 0.007 * u, -0.005 * u)))
        built[f"nerve__root_{lv.lower()}_{'r' if side < 0 else 'l'}"] = tube_along(pts, 0.0011)
SP_TIPS = []
# pedicle centres (right side, x < 0): the bridge between body and arch
PED = {}
for lv in ["T12", "L1", "L2", "L3", "L4", "L5"]:
    vs = [v.co for v in built[f"bone__{lv.lower()}"].verts]
    ymin = min(v.y for v in vs); ymax = max(v.y for v in vs); yp = ymin + (ymax - ymin) * 0.45
    body_ = [v for v in vs if v.y < yp]; zb, zt = min(v.z for v in body_), max(v.z for v in body_); zmid = (zb + zt) / 2
    cand = [v for v in vs if yp - 0.003 < v.y < yp + 0.012 and -0.017 < v.x < -0.005 and zmid - 0.002 < v.z < zt - 0.002]   # pedicles spring from the upper half of the body
    if cand: PED[lv] = sum(cand, Vector()) / len(cand)
print("pedicle centres (block frame):", {k: [round(c, 4) for c in (v - CENTER)] for k, v in PED.items()})
for k, bm in built.items(): print(f"{k:28} {len(bm.verts):6} v")

# ---- export: full set + midline section set ----
objects = []
for k, bm in built.items():
    v, t = to_arrays(bm, center=CENTER); objects.append({"name": k, "layer": k.split("__")[0], "verts": v, "tris": t})
    if k.startswith("bone__rib12") or k.endswith("_l"): continue
    c2 = bm.copy(); zj = (hash(k) % 11 - 5) * 0.00003
    cut_plane(c2, (zj, 0, 0), (1, 0, 0), remove="outer", cap=(k != "nerve__dural_sac"), ngon=True)   # keep the patient's right half; the sac stays open (hollow) so the roots inside show
    if len(c2.faces):
        v, t = to_arrays(c2, center=CENTER); objects.append({"name": k + "__cut", "layer": k.split("__")[0], "verts": v, "tris": t})
meta = {"frame": "L2-body-centred; right=-x, anterior=-y, up=+z", "unit": "m", "attribution": ATTR, "levels": ["T12", "L1", "L2", "L3", "L4", "L5", "S1-2"],
        "pedicle_r": {k: [round(c, 5) for c in (v - CENTER)] for k, v in PED.items()}, "spinous_tips": SP_TIPS}
json.dump({"meta": meta, "objects": objects}, open(f"{OUTS}/spine_a.json", "w"), separators=(",", ":"))
print("exported spine_a:", len(objects), "objects,", sum(len(o["verts"]) // 3 for o in objects), "verts,", os.path.getsize(f"{OUTS}/spine_a.json") // 1024, "KB")
POST, LAT, UPV = Vector((0, 1, 0)), Vector((1, 0, 0)), Vector((0, 0, 1))
def look2(cam, sun, pos, up):
    fwd = (-pos).normalized(); right = fwd.cross(up).normalized(); up2 = right.cross(fwd).normalized()
    m = Matrix((right, up2, -fwd)).transposed(); cam.location = pos; cam.rotation_quaternion = m.to_quaternion(); sun.rotation_quaternion = (m @ Matrix.Rotation(0.5, 3, 'X') @ Matrix.Rotation(-0.4, 3, 'Y')).to_quaternion()
zana.look = look2
rebuild_scene([o for o in objects if o["name"].endswith("__cut") and o["layer"] in ("bone", "disc", "nerve")], meta)
render_views({"section_nerves": (LAT + POST * 0.15, UPV)}, "spine_a", dist=0.42, res=800, samples=14)
