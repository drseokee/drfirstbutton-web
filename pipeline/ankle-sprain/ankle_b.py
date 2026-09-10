import bpy, bmesh, json, math, os
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from zana import *
import zana

OUTA = "/home/claude/out_ankle"; zana.OUT = OUTA
d = json.load(open(f"{OUTA}/ankle_a.json")); objs = {o["name"]: o for o in d["objects"]}
def bm_of(o): return bm_from_arrays([tuple(o["verts"][i:i+3]) for i in range(0, len(o["verts"]), 3)], [tuple(o["tris"][i:i+3]) for i in range(0, len(o["tris"]), 3)])
def verts_of(n): v = objs[n]["verts"]; return [Vector(v[i:i+3]) for i in range(0, len(v), 3)]
BVH = {n: BVHTree.FromBMesh(bm_of(objs[n])) for n in ("bone__fibula_distal", "bone__tibia_distal", "bone__talus", "bone__calcaneus")}
LAT, ANT, UP = Vector((-1, 0, 0)), Vector((0, -1, 0)), Vector((0, 0, 1))   # anatomical axes in this frame (right foot)

# ---------- landmarks ----------
fib = verts_of("bone__fibula_distal"); tib = verts_of("bone__tibia_distal"); tal = verts_of("bone__talus"); cal = verts_of("bone__calcaneus")
TIP_LAT = min(fib, key=lambda p: p.z)                                   # lateral malleolus tip
TIP_MED = min(tib, key=lambda p: p.z)                                   # medial malleolus tip
def nearest(bone, p):
    loc, nrm, idx, dist = BVH[bone].find_nearest(p); return loc, nrm
def fib_ring(z, dz=0.0015): return [p for p in fib if abs(p.z - z) < dz]
# ATFL fibular footprint: anterior border of the lateral malleolus, ~10 mm proximal to the tip
ring = fib_ring(TIP_LAT.z + 0.010); ATFL_F = min(ring, key=lambda p: p.y)            # most anterior point of that ring
ATFL_F, nF1 = nearest("bone__fibula_distal", ATFL_F)
# ATFL talar footprint: lateral talar body-neck junction — aim anteromedial-slightly-down from the origin, snap to the talus
ATFL_T, nT1 = nearest("bone__talus", ATFL_F + ANT * 0.017 - LAT * 0.006 - UP * 0.004)
# CFL: origin just anterior-inferior of the malleolar tip (~3 mm proximal, anterior surface), insertion on the lateral calcaneal surface
CFL_F, nF2 = nearest("bone__fibula_distal", TIP_LAT + UP * 0.003 + ANT * 0.003)
CFL_C, nC = nearest("bone__calcaneus", TIP_LAT - UP * 0.016 - ANT * 0.006 - LAT * 0.004)
# PTFL: origin in the malleolar fossa (posteromedial face of the malleolus, ~5 mm above the tip), insertion on the lateral tubercle of the posterior talar process
ring = fib_ring(TIP_LAT.z + 0.005); PTFL_F = max(ring, key=lambda p: p.y - 0.4 * p.x)   # posterior & medial
PTFL_F, nF3 = nearest("bone__fibula_distal", PTFL_F)
post = max([p for p in tal if p.z < 0.004], key=lambda p: p.y); PTFL_T, nT3 = nearest("bone__talus", post - LAT * 0.002)
LIGS = {
    "lig__atfl": dict(a=("fibula_distal", ATFL_F, nF1), b=("talus", ATFL_T, nT1), width=0.008, thick=0.0022, strands=5),
    "lig__cfl":  dict(a=("fibula_distal", CFL_F, nF2),  b=("calcaneus", CFL_C, nC),  width=0.0055, thick=0.0025, strands=4),
    "lig__ptfl": dict(a=("fibula_distal", PTFL_F, nF3), b=("talus", PTFL_T, nT3),   width=0.008, thick=0.003, strands=5),
}
for k, L in LIGS.items():
    print(f"{k}: {L['a'][0]} ({L['a'][1].x*1e3:+.1f},{L['a'][1].y*1e3:+.1f},{L['a'][1].z*1e3:+.1f}) -> {L['b'][0]} ({L['b'][1].x*1e3:+.1f},{L['b'][1].y*1e3:+.1f},{L['b'][1].z*1e3:+.1f})  length {(L['b'][1]-L['a'][1]).length*1e3:.1f} mm")

# ---------- static band meshes (for review; the viewer re-sweeps these at runtime) ----------
def band(a, b, na, nb, width, thick, bulge=0.0015, segs=16):
    """flat band a->b; the band's face normal follows the bone-surface normals; the middle lifts off the bones by `bulge`"""
    d = (b - a); L = d.length; t = d / L
    out = ((a + b) / 2).normalized()                       # outward from the ankle centre (origin): always points away from the joint
    nrm = (out - t * t.dot(out)).normalized(); side = t.cross(nrm).normalized()
    bm = bmesh.new(); rings = []
    for i in range(segs + 1):
        u = i / segs; c = a + d * u + nrm * (bulge * math.sin(math.pi * u))
        ring = []
        for (sx, sn) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            ring.append(bm.verts.new(c + side * (sx * width / 2) + nrm * (sn * thick / 2)))
        rings.append(ring)
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(4): bm.faces.new((r0[k], r0[(k + 1) % 4], r1[(k + 1) % 4], r1[k]))
    bm.faces.new(rings[0][::-1]); bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bmesh.ops.triangulate(bm, faces=bm.faces)
    return bm
objects = [o for o in d["objects"] if not o["name"].endswith("_ref")]        # drop the Z-Anatomy reference ligaments
for k, L in LIGS.items():
    bm = band(L["a"][1], L["b"][1], L["a"][2], L["b"][2], L["width"], L["thick"])
    v, t = to_arrays(bm, center=Vector((0, 0, 0)))
    objects.append({"name": k, "layer": "lig", "verts": v, "tris": t})

# ---------- joint axes ----------
ankle_axis_p = (TIP_LAT + TIP_MED) / 2 + UP * 0.004                          # talocrural axis: through the malleoli (slightly above the tips)
ankle_axis_d = (TIP_LAT - TIP_MED).normalized()
tal_c = sum(tal, Vector()) / len(tal); cal_c = sum(cal, Vector()) / len(cal)
cal_post_inf = min(cal, key=lambda p: -p.y + p.z * 1.5)                      # posterolateral-inferior calcaneus
sub_axis_p = cal_post_inf + Vector((-0.004, 0, 0))
sub_axis_d = (Vector((0, -1, 0)).rotation_difference(Vector((0, -1, 0))) @ Vector((0, -1, 0)))
# Inman's subtalar axis: ~42° up from the horizontal, ~20° medial to the foot's long axis (anterior = -y, medial = +x)
sub_axis_d = Vector((math.sin(math.radians(20)) * math.cos(math.radians(42)), -math.cos(math.radians(20)) * math.cos(math.radians(42)), math.sin(math.radians(42)))).normalized()
FOOT_BONES = [n for n in objs if n.startswith("bone__") and n not in ("bone__tibia_distal", "bone__fibula_distal", "bone__talus")]
# ---------- bone-hugging profile per ligament: offset along the outward normal that keeps the band 0.8 mm above the bone surface ----------
BONES_BVH = BVHTree.FromBMesh(join_bms([bm_of(objs[n]) for n in ("bone__fibula_distal", "bone__talus", "bone__calcaneus")]))
def profile(a, b, n=17):
    dd = b - a; t = dd.normalized(); out = ((a + b) / 2).normalized(); nrm = (out - t * t.dot(out)).normalized()
    prof = []
    for i in range(n):
        u = i / (n - 1); c = a + dd * u
        hit = BONES_BVH.ray_cast(c + nrm * 0.03, -nrm, 0.06)
        off = (hit[0] - c).dot(nrm) + 0.0008 if hit[0] is not None else 0.0
        prof.append(round(max(-0.009, min(0.004, off)), 5))
    prof[0] = prof[-1] = 0.0004                                   # attachments stay on their footprints
    return prof
for k, L in LIGS.items(): L["profile"] = profile(L["a"][1], L["b"][1])
rig = {
    "ankle":    {"point": [round(x, 5) for x in ankle_axis_p], "dir": [round(x, 5) for x in ankle_axis_d], "moves": ["bone__talus"] + FOOT_BONES, "note": "talocrural: plantar/dorsiflexion"},
    "subtalar": {"point": [round(x, 5) for x in sub_axis_p], "dir": [round(x, 5) for x in sub_axis_d], "moves": FOOT_BONES, "note": "Inman axis: inversion/eversion"},
    "ligaments": {k: {"a": {"bone": "bone__" + L["a"][0], "p": [round(x, 5) for x in L["a"][1]], "n": [round(x, 4) for x in L["a"][2]]},
                      "b": {"bone": "bone__" + L["b"][0], "p": [round(x, 5) for x in L["b"][1]], "n": [round(x, 4) for x in L["b"][2]]},
                      "width": L["width"], "thick": L["thick"], "strands": L["strands"], "rest": round((L["b"][1] - L["a"][1]).length, 5), "profile": L["profile"]} for k, L in LIGS.items()},
    "landmarks": {"lateral_malleolus_tip": [round(x, 5) for x in TIP_LAT], "medial_malleolus_tip": [round(x, 5) for x in TIP_MED]},
}
# ---------- skinning weights for soft structures: by nearest bone group (leg / talus / foot), so a retinaculum's fibular end
# stays with the fibula and its calcaneal end goes with the foot ----------
GROUPS = {"leg": ["bone__tibia_distal", "bone__fibula_distal"], "talus": ["bone__talus"], "foot": FOOT_BONES}
GBVH = {g: BVHTree.FromBMesh(join_bms([bm_of(objs[n]) for n in names])) for g, names in GROUPS.items()}
for o in objects:
    if o["layer"] == "bone" or o["name"] in LIGS: continue
    v = o["verts"]; w = []
    for i in range(0, len(v), 3):
        p = Vector(v[i:i+3]); ds = []
        for g in ("leg", "talus", "foot"):
            loc, nrm, idx, dist = GBVH[g].find_nearest(p); ds.append(dist if loc is not None else 1.0)
        inv = [1.0 / (dd + 0.003) ** 3 for dd in ds]; tot = sum(inv)
        ww = [x / tot for x in inv]
        # snap: a clear winner (closer by 10 mm than the runner-up) takes all -> no smearing far from joints
        srt = sorted(range(3), key=lambda k: ds[k])
        if ds[srt[1]] - ds[srt[0]] > 0.010: ww = [1.0 if k == srt[0] else 0.0 for k in range(3)]
        w += [round(x, 2) for x in ww]
    o["w"] = w
meta = dict(d["meta"]); meta["rig"] = rig
json.dump({"meta": meta, "objects": objects}, open(f"{OUTA}/ankle_b.json", "w"), separators=(",", ":"))
print("exported ankle_b:", len(objects), "objects; ankle axis", [round(x, 3) for x in ankle_axis_d], "subtalar axis", [round(x, 3) for x in sub_axis_d])

# ---------- preview: lateral close-up on the ligaments ----------
rebuild_scene([o for o in objects if o["layer"] in ("bone", "lig")], meta)
sc = bpy.context.scene
def look2(cam, sun, pos, up):
    fwd = (-pos).normalized(); right = fwd.cross(up).normalized(); up2 = right.cross(fwd).normalized()
    m = Matrix((right, up2, -fwd)).transposed(); cam.location = pos; cam.rotation_quaternion = m.to_quaternion(); sun.rotation_quaternion = (m @ Matrix.Rotation(0.5, 3, 'X') @ Matrix.Rotation(-0.4, 3, 'Y')).to_quaternion()
zana.look = look2
for o in sc.objects:
    if o.type == "MESH": o.location -= Vector((-0.02, 0.01, -0.005))            # centre the view on the lateral ankle
render_views({"lig_lateral": (LAT + ANT * 0.25, UP), "lig_anterolat": (LAT * 0.7 + ANT * 0.7 + UP * 0.15, UP), "lig_posterolat": (LAT * 0.7 - ANT * 0.7 + UP * 0.1, UP)}, "ankle_b", dist=0.16, res=700, samples=16)
