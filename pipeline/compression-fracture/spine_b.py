import bpy, bmesh, json, math, os
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from zana import *
import zana

OUTS = "/home/claude/out_spine"; zana.OUT = OUTS
d = json.load(open(f"{OUTS}/spine_a.json")); objs = {o["name"]: o for o in d["objects"]}
def bm_of(o): return bm_from_arrays([tuple(o["verts"][i:i+3]) for i in range(0, len(o["verts"]), 3)], [tuple(o["tris"][i:i+3]) for i in range(0, len(o["tris"]), 3)])
def V(o, i): return Vector(o["verts"][3*i:3*i+3])
def nverts(o): return len(o["verts"]) // 3
ANT = Vector((0, -1, 0)); UP = Vector((0, 0, 1))

# ---------- L1 body geometry: anterior wall / posterior wall / endplates from the vertebra mesh ----------
l1 = objs["bone__l2"]; pts = [V(l1, i) for i in range(nverts(l1))]   # fractured level: L2
# the body is the anterior mass: take vertices in front of the pedicle plane; find the plane by the histogram of y (body = wide, anterior)
ys = sorted(p.y for p in pts); y_min = ys[0]; y_max = ys[-1]
# body/canal boundary: the posterior wall of the body ~ where the dense anterior mass ends; estimated at 45 % of the AP extent
Y_POST = y_min + (y_max - y_min) * 0.42                       # posterior wall of the body (behind it: canal, pedicles, arch)
body = [p for p in pts if p.y < Y_POST]
z_top = max(p.z for p in body); z_bot = min(p.z for p in body); z_mid = (z_top + z_bot) / 2; H = z_top - z_bot
y_ant = min(p.y for p in body); DEPTH = Y_POST - y_ant
print(f"L2 body: height {H*1e3:.1f} mm, AP depth {DEPTH*1e3:.1f} mm, posterior wall y {Y_POST*1e3:+.1f}")
def smooth01(t): t = max(0.0, min(1.0, t)); return t * t * (3 - 2 * t)

def wedge_delta(p, loss=0.60, retro=0.0):
    """displacement of a vertebra vertex for an anterior wedge collapse (loss = fraction of anterior height lost) and posterior-wall retropulsion"""
    w_body = 1 - smooth01((p.y - (Y_POST - 0.004)) / 0.008)          # 1 in the body, fades to 0 across the pedicles
    if w_body <= 0: return Vector((0, 0, 0))
    a = 1 - smooth01((p.y - y_ant) / DEPTH)                          # 1 at the anterior wall, 0 at the posterior wall (posterior height kept)
    f = max(0.0, min(1.0, (p.z - z_bot) / H))                         # 0 bottom plate .. 1 top plate
    h = (p.z - z_mid) / (H / 2)
    dz = -f * H * loss * (0.10 + 0.90 * a)                            # the SUPERIOR plate collapses (inferior plate stays): anterior top drops by loss*H
    bulge = loss * 0.006 * (1 - h * h) * a                            # crushed bone spreads forward at mid-height
    d = Vector((0, -bulge, dz)) * w_body
    if retro > 0:                                                     # unstable: the posterior wall bows into the canal
        pw = smooth01((p.y - (Y_POST - 0.008)) / 0.008) * w_body     # posterior wall zone
        d += Vector((0, retro * 0.0045 * (1 - h * h) * pw, 0))
    return d
delta_w = []; delta_r = []
for p in pts:
    dw = wedge_delta(p, 0.60, 0.0); dr = wedge_delta(p, 0.60, 1.0) - dw
    delta_w += [round(dw.x, 5), round(dw.y, 5), round(dw.z, 5)]; delta_r += [round(dr.x, 5), round(dr.y, 5), round(dr.z, 5)]
for nm in ("bone__l2", "bone__l2__cut"):
    o = objs[nm]; dwl = []; drl = []
    for i in range(nverts(o)):
        p = V(o, i); dw = wedge_delta(p, 0.60, 0.0); dr = wedge_delta(p, 0.60, 1.0) - dw
        dwl += [round(dw.x, 5), round(dw.y, 5), round(dw.z, 5)]; drl += [round(dr.x, 5), round(dr.y, 5), round(dr.z, 5)]
    o["morphs"] = {"wedge": dwl, "retro": drl}
    o["fx"] = [round((1 - smooth01((V(o, i).y - (Y_POST - 0.004)) / 0.008)) * (0.35 + 0.65 * (1 - smooth01((V(o, i).y - y_ant) / DEPTH))), 2) for i in range(nverts(o))]
print("wedge morph: anterior loss 60 % =", round(0.60 * H * 1e3, 1), "mm; posterior wall bow 4.5 mm")

# ---------- kyphosis hinge: everything above the L1 superior plate tilts forward about the posterior-superior corner ----------
hinge = Vector((0, Y_POST, z_top)); axis = Vector((1, 0, 0))          # transverse axis at the posterior wall top
wedge_angle = math.degrees(math.atan2(0.60 * H, DEPTH))
print(f"kyphosis at 60 % loss: {wedge_angle:.1f} deg")
MOVING = ["bone__t12", "bone__l1", "disc__t12_l1", "bone__rib12_r", "bone__rib12_l"]
def centre_of(n): o = objs[n]; return sum((V(o, i) for i in range(nverts(o))), Vector()) / nverts(o)
# levels from the sacrum up: each vertebra (with the disc below it) pivots at that disc's centre; shares of the total kyphosis angle
LEVELS = [
    {"name": "sacrum", "members": ["bone__sacrum"], "pivot": None, "share": 0.0},
    {"name": "L5", "members": ["bone__l5", "disc__l5_s1"], "pivot": centre_of("disc__l5_s1"), "share": -0.05},
    {"name": "L4", "members": ["bone__l4", "disc__l4_l5"], "pivot": centre_of("disc__l4_l5"), "share": -0.07},
    {"name": "L3", "members": ["bone__l3", "disc__l3_l4"], "pivot": centre_of("disc__l3_l4"), "share": -0.09},
    {"name": "L2", "members": ["bone__l2", "disc__l2_l3", "disc__l1_l2"], "pivot": centre_of("disc__l2_l3"), "share": -0.06},   # fractured body (morphs) — small extension below the wedge
    {"name": "L1", "members": ["bone__l1", "disc__t12_l1"], "pivot": None, "share": 1.0},                                        # hinge at the L2 superior plate (set below)
    {"name": "T12", "members": ["bone__t12", "bone__rib12_r", "bone__rib12_l"], "pivot": centre_of("disc__t12_l1"), "share": 0.12},
]
from mathutils import Matrix as _M
AXIS = Vector((-1, 0, 0))
R_full = _M.Rotation(math.radians(wedge_angle), 3, AXIS)
probe = Vector((0, y_ant, z_top + 0.03)); moved = R_full @ (probe - hinge) + hinge
if moved.z > probe.z: AXIS = -AXIS; R_full = _M.Rotation(math.radians(wedge_angle), 3, AXIS)   # forward tilt = the front drops
print("hinge axis", tuple(AXIS), "front point z", round(probe.z*1e3, 1), "->", round((R_full @ (probe - hinge) + hinge).z*1e3, 1))
def top_disp(p):  return R_full @ (p - hinge) + hinge - p
for nm in ("disc__l1_l2", "disc__l1_l2__cut"):
    o = objs[nm]; zs = [V(o, i).z for i in range(nverts(o))]; zb, zt = min(zs), max(zs); dl = []
    for i in range(nverts(o)):
        p = V(o, i); fr = max(0.0, min(1.0, (p.z - zb) / max(1e-6, zt - zb)))
        db = wedge_delta(Vector((p.x, p.y, z_top)), 0.60, 0.0)         # what the plate under this point does
        dt = top_disp(p)                                                 # what T12 above this point does
        dd = db * (1 - fr) + dt * fr
        dl += [round(dd.x, 5), round(dd.y, 5), round(dd.z, 5)]
    o["morphs"] = {"wedge": dl}
print("disc L1-L2: deforms with the plate below and L1 above")
# skinning weights for soft structures: nearest bone group (static below vs moving above), blended near the hinge
LEVELS[5]["pivot"] = hinge
LBVH = [BVHTree.FromBMesh(join_bms([bm_of(objs[n]) for n in L["members"]])) for L in LEVELS]
for o in d["objects"]:
    base = o["name"].replace("__cut", "")
    if base.startswith(("bone__", "disc__")): continue
    w = []
    for i in range(nverts(o)):
        p = V(o, i); ds = []
        for bvh in LBVH:
            loc, nrm, idx, dist = bvh.find_nearest(p); ds.append(dist if loc is not None else 1.0)
        order = sorted(range(len(LEVELS)), key=lambda k: ds[k]); a, bb = order[0], order[1]
        if ds[bb] - ds[a] > 0.012: wa, wb = 1.0, 0.0                              # clear winner
        else: ia, ib = 1.0 / (ds[a] + 0.003) ** 2, 1.0 / (ds[bb] + 0.003) ** 2; wa, wb = ia / (ia + ib), ib / (ia + ib)
        w += [a, round(wa, 2), bb, round(wb, 2)]                                  # [levelA, weightA, levelB, weightB]
    o["w"] = w
meta = dict(d["meta"])
meta["rig"] = {"hinge": {"point": [round(x, 5) for x in hinge], "axis": [round(x, 3) for x in AXIS], "moves": MOVING, "angle_at_full": round(wedge_angle, 2)},
               "levels": [{"name": L["name"], "members": L["members"], "pivot": ([round(x, 5) for x in L["pivot"]] if L["pivot"] is not None else None), "share": L["share"]} for L in LEVELS],
               "level": "L2", "l2": {"height": round(H, 5), "depth": round(DEPTH, 5), "y_post": round(Y_POST, 5), "z_top": round(z_top, 5), "z_bot": round(z_bot, 5)}}
d["meta"] = meta; json.dump(d, open(f"{OUTS}/spine_b.json", "w"), separators=(",", ":"))
print("exported spine_b:", len(d["objects"]), "objects")

# ---------- preview: section, normal vs 60 % wedge (morph applied) ----------
from mathutils import Matrix
def look2(cam, sun, pos, up):
    fwd = (-pos).normalized(); right = fwd.cross(up).normalized(); up2 = right.cross(fwd).normalized()
    m = Matrix((right, up2, -fwd)).transposed(); cam.location = pos; cam.rotation_quaternion = m.to_quaternion(); sun.rotation_quaternion = (m @ Matrix.Rotation(0.5, 3, 'X') @ Matrix.Rotation(-0.4, 3, 'Y')).to_quaternion()
zana.look = look2
LAT = Vector((1, 0, 0)); POST = Vector((0, 1, 0))
sel = [o for o in d["objects"] if o["layer"] in ("bone", "disc", "nerve", "lig") and not o["name"].endswith("__cut")]
rebuild_scene(sel, meta)
sc = bpy.context.scene
for ob in sc.objects:
    if ob.type == "MESH": ob.location.z -= 0.0
render_views({"sec_normal": (LAT + POST * 0.1, UP)}, "spine_b", dist=0.42, res=700, samples=14)
# apply the 60 % wedge to the cut L1 and re-render
import copy
sel2 = copy.deepcopy(sel)
for o in sel2:
    if o["name"] == "bone__l2":
        m = o["morphs"]["wedge"]; o["verts"] = [round(v + m[i], 5) for i, v in enumerate(o["verts"])]
rebuild_scene(sel2, meta)
render_views({"sec_wedge60": (LAT + POST * 0.1, UP)}, "spine_b", dist=0.42, res=700, samples=14)
