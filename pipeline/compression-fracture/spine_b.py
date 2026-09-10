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
for nm in ("bone__l2",):
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
from mathutils import Matrix as _M
AXIS = Vector((-1, 0, 0))
R_full = _M.Rotation(math.radians(wedge_angle), 3, AXIS)
probe = Vector((0, y_ant, z_top + 0.03)); moved = R_full @ (probe - hinge) + hinge
if moved.z > probe.z: AXIS = -AXIS; R_full = _M.Rotation(math.radians(wedge_angle), 3, AXIS)   # forward tilt = the front drops
print("hinge axis", tuple(AXIS), "front point z", round(probe.z*1e3, 1), "->", round((R_full @ (probe - hinge) + hinge).z*1e3, 1))
def top_disp(p):  return R_full @ (p - hinge) + hinge - p
for nm in ("disc__l1_l2",):
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
GRP = {"static": [n for n in objs if n.startswith(("bone__", "disc__")) and n not in MOVING],
       "moving": [n for n in MOVING if n in objs]}
GBVH = {g: BVHTree.FromBMesh(join_bms([bm_of(objs[n]) for n in names])) for g, names in GRP.items()}
for o in d["objects"]:
    base = o["name"].replace("__cut", "")
    if base.startswith(("bone__", "disc__")): continue
    w = []
    for i in range(nverts(o)):
        p = V(o, i); ds = []
        for g in ("static", "moving"):
            loc, nrm, idx, dist = GBVH[g].find_nearest(p); ds.append(dist if loc is not None else 1.0)
        if p.z > hinge.z + 0.03: ww = [0.0, 1.0]
        elif p.z < hinge.z - 0.03: ww = [1.0, 0.0]
        else:
            inv = [1.0 / (dd + 0.004) ** 2 for dd in ds]; tot = sum(inv); ww = [inv[0] / tot, inv[1] / tot]
        w += [round(x, 2) for x in ww]
    o["w"] = w
meta = dict(d["meta"])
meta["rig"] = {"hinge": {"point": [round(x, 5) for x in hinge], "axis": [round(x, 3) for x in AXIS], "moves": GRP["moving"], "angle_at_full": round(wedge_angle, 2)},
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
sel = [o for o in d["objects"] if o["layer"] in ("bone", "disc", "nerve", "lig")]
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
