import bpy, bmesh, json, math, os
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from zana import *
import zana

OUTS = "/home/claude/out_spine"; zana.OUT = OUTS
d = json.load(open(f"{OUTS}/spine_a.json")); objs = {o["name"]: o for o in d["objects"]}
def bm_of(o): return bm_from_arrays([tuple(o["verts"][i:i+3]) for i in range(0, len(o["verts"]), 3)], [tuple(o["tris"][i:i+3]) for i in range(0, len(o["tris"]), 3)])
def V(o, i): return Vector(o["verts"][3*i:3*i+3])
def nverts(o): return len(o["verts"]) // 3
def smooth01(t): t = max(0.0, min(1.0, t)); return t * t * (3 - 2 * t)
def centre_of(n): o = objs[n]; return sum((V(o, i) for i in range(nverts(o))), Vector()) / nverts(o)

LEVEL_NAMES = ["T12", "L1", "L2", "L3", "L4", "L5"]
DISC_ABOVE = {"T12": None, "L1": "disc__t12_l1", "L2": "disc__l1_l2", "L3": "disc__l2_l3", "L4": "disc__l3_l4", "L5": "disc__l4_l5"}
DISC_BELOW = {"T12": "disc__t12_l1", "L1": "disc__l1_l2", "L2": "disc__l2_l3", "L3": "disc__l3_l4", "L4": "disc__l4_l5", "L5": "disc__l5_s1"}
FX = {}
for lv in LEVEL_NAMES:
    bone = f"bone__{lv.lower()}"; o = objs[bone]; pts = [V(o, i) for i in range(nverts(o))]
    ys = [p.y for p in pts]; y_min, y_max = min(ys), max(ys)
    Y_POST = y_min + (y_max - y_min) * 0.42
    body = [p for p in pts if p.y < Y_POST]; z_top = max(p.z for p in body); z_bot = min(p.z for p in body); z_mid = (z_top + z_bot) / 2; H = z_top - z_bot
    y_ant = min(p.y for p in body); DEPTH = Y_POST - y_ant
    def wedge_delta(p, loss=0.60, retro=0.0, Y_POST=Y_POST, y_ant=y_ant, DEPTH=DEPTH, z_top=z_top, z_bot=z_bot, z_mid=z_mid, H=H):
        w_body = 1 - smooth01((p.y - (Y_POST - 0.004)) / 0.008)
        if w_body <= 0: return Vector((0, 0, 0))
        a = 1 - smooth01((p.y - y_ant) / DEPTH); f = max(0.0, min(1.0, (p.z - z_bot) / H)); h = (p.z - z_mid) / (H / 2)
        dz = -f * H * loss * (0.10 + 0.90 * a); bulge = loss * 0.006 * (1 - h * h) * a
        dd = Vector((0, -bulge, dz)) * w_body
        if retro > 0:                                                        # unstable: the posterior wall bursts back into the canal (7 mm) — enough to press the sac
            pw = smooth01((p.y - (Y_POST - 0.010)) / 0.010) * w_body; dd += Vector((0, retro * 0.007 * (1 - h * h * 0.5) * pw, 0))
        return dd
    for nm in (bone, bone + "__cut"):
        if nm not in objs: continue
        o2 = objs[nm]; dwl = []; drl = []; fx = []
        for i in range(nverts(o2)):
            p = V(o2, i); dw = wedge_delta(p); dr = wedge_delta(p, 0.60, 1.0) - dw
            dwl += [round(dw.x, 5), round(dw.y, 5), round(dw.z, 5)]; drl += [round(dr.x, 5), round(dr.y, 5), round(dr.z, 5)]
            fx.append(round((1 - smooth01((p.y - (Y_POST - 0.004)) / 0.008)) * (0.35 + 0.65 * (1 - smooth01((p.y - y_ant) / DEPTH))), 2))
        o2["morphs"] = {"wedge": dwl, "retro": drl}; o2["fx"] = fx
    hinge = Vector((0, Y_POST, z_top)); wedge_angle = math.degrees(math.atan2(0.60 * H, DEPTH))
    AXIS = Vector((-1, 0, 0)); R_full = Matrix.Rotation(math.radians(wedge_angle), 3, AXIS)
    probe = Vector((0, y_ant, z_top + 0.03))
    if (R_full @ (probe - hinge) + hinge).z > probe.z: AXIS = -AXIS; R_full = Matrix.Rotation(math.radians(wedge_angle), 3, AXIS)
    da = DISC_ABOVE[lv]
    if da:
        for nm in (da, da + "__cut"):
            if nm not in objs: continue
            o2 = objs[nm]; zs = [V(o2, i).z for i in range(nverts(o2))]; zb, zt = min(zs), max(zs); dl = []
            for i in range(nverts(o2)):
                p = V(o2, i); fr = max(0.0, min(1.0, (p.z - zb) / max(1e-6, zt - zb)))
                db = wedge_delta(Vector((p.x, p.y, z_top))); dt = R_full @ (p - hinge) + hinge - p; dd = db * (1 - fr) + dt * fr
                dl += [round(dd.x, 5), round(dd.y, 5), round(dd.z, 5)]
            o2.setdefault("morphs", {})[f"wedge_{lv.lower()}"] = dl
    for nm in ("lig__all", "lig__all__cut", "lig__pll", "lig__pll__cut"):
        if nm not in objs: continue
        o2 = objs[nm]; dwl = []; drl = []
        for i in range(nverts(o2)):
            p = V(o2, i)
            inz = smooth01((p.z - (z_bot - 0.002)) / 0.004) * (1 - smooth01((p.z - (z_top - 0.001)) / 0.004))   # only over this body's height
            q = Vector((p.x, max(p.y, y_ant + 0.0005) if nm.startswith("lig__all") else min(p.y, Y_POST - 0.0005), p.z))
            dw = wedge_delta(q) * inz; dr = (wedge_delta(q, 0.60, 1.0) - wedge_delta(q)) * inz
            if nm.startswith("lig__all"): dr = Vector((0, 0, 0))
            dwl += [round(dw.x, 5), round(dw.y, 5), round(dw.z, 5)]; drl += [round(dr.x, 5), round(dr.y, 5), round(dr.z, 5)]
        o2.setdefault("morphs", {})[f"wedge_{lv.lower()}"] = dwl
        if nm.startswith("lig__pll"): o2["morphs"][f"retro_{lv.lower()}"] = drl
    # cannula: straight through the pedicle centre along the pedicle axis (toward the body at the pedicle's height) → lands in the upper third
    ped = d["meta"].get("pedicle_r", {}).get(lv)
    if ped:
        pedv = Vector(ped); bodyc_ped_h = Vector((0, (y_ant + Y_POST) / 2, pedv.z))
        axis = (bodyc_ped_h - pedv); axis.z -= 0.003; axis.normalize()                     # slightly downward as it runs forward
        tip = pedv + axis * ((pedv - Vector((0, y_ant, pedv.z))).length * 0.72)              # to the anterior third
    # pedicle screw (right side; the left is mirrored in the viewer): trajectory = pedicle axis parallel to the superior plate,
    # entry = where that line, run backward from the pedicle centre, leaves the posterior bone surface (the transverse-process / superior-facet junction),
    # tip = 75 % of the AP depth of the body (anterior wall never breached), screw 6.5 x 45 mm
    screw = None
    if ped:
        CONV = {"T12": 8, "L1": 10, "L2": 12, "L3": 15, "L4": 18, "L5": 27}[lv]          # medial convergence (deg), literature values by level
        saxis = Vector((math.sin(math.radians(CONV)) * (1 if pedv.x < 0 else -1), -math.cos(math.radians(CONV)), 0)).normalized()   # anterior, converging toward the midline, parallel to the plate
        bvh_v = BVHTree.FromBMesh(bm_of(o))
        far = pedv - saxis * 0.06; hits = []
        loc, nrm, idx, dist = bvh_v.ray_cast(far, saxis, 0.06)                     # first bone surface met when coming from behind = the entry point
        entry_pt = loc if loc is not None else pedv - saxis * 0.018
        t_tip = (pedv.y - (Y_POST - 0.75 * DEPTH)) / max(1e-6, -saxis.y)              # along the axis until y reaches 75 % depth
        tip_pt = pedv + saxis * t_tip
        L = (tip_pt - entry_pt).length
        if L > 0.045: tip_pt = entry_pt + saxis * 0.045                                 # 45 mm screw
        screw = {"entry": [round(x, 5) for x in entry_pt], "tip": [round(x, 5) for x in tip_pt], "axis": [round(x, 4) for x in saxis],
                 "convergence_deg": round(math.degrees(math.atan2(abs(saxis.x), abs(saxis.y))), 1), "length_mm": round((tip_pt - entry_pt).length * 1e3, 1)}
        print(f"   {lv} screw: convergence {screw['convergence_deg']} deg, length {screw['length_mm']} mm")
    FX[lv] = {"hinge": [round(x, 5) for x in hinge], "pedicle_axis": ([round(x, 4) for x in axis] if ped else None), "cannula_tip": ([round(x, 5) for x in tip] if ped else None), "screw_r": screw, "axis": [round(x, 3) for x in AXIS], "angle_at_full": round(wedge_angle, 2), "height": round(H, 5), "depth": round(DEPTH, 5),
              "body_centre": [0, round((y_ant + Y_POST) / 2, 5), round(z_mid, 5)], "pedicle_r": d["meta"].get("pedicle_r", {}).get(lv)}
    print(f"{lv}: body {H*1e3:.1f} x {DEPTH*1e3:.1f} mm, kyphosis at 60 % {wedge_angle:.1f} deg")
# chain: sacrum → L5 → ... → T12; each level pivots at the disc below; shares are set in the viewer relative to the chosen fracture level
LEVELS = [{"name": "sacrum", "members": ["bone__sacrum"], "pivot": None}]
for lv in ["L5", "L4", "L3", "L2", "L1", "T12"]:
    mem = [f"bone__{lv.lower()}", DISC_BELOW[lv]]
    LEVELS.append({"name": lv, "members": mem, "pivot": [round(x, 5) for x in centre_of(DISC_BELOW[lv])]})
# soft structures follow the column by HEIGHT: between two vertebra centres the weight ramps linearly (monotonic → no crumpling
# where neighbouring vertices would otherwise pick different level pairs). Level centre heights from the sacrum top up to T12.
# body ranges (bottom, top plate) per level; a vertex over a body follows that level rigidly, across a disc space it ramps
BR = []
for L in LEVELS:
    bone = [n for n in L["members"] if n.startswith("bone__")][0]; o_ = objs[bone]
    pts_ = [V(o_, i) for i in range(nverts(o_))]
    if L["name"] == "sacrum": BR.append((min(p.z for p in pts_), max(p.z for p in pts_) - 0.004)); continue
    ys_ = [p.y for p in pts_]; yp_ = min(ys_) + (max(ys_) - min(ys_)) * 0.42; body_ = [p for p in pts_ if p.y < yp_]
    BR.append((min(p.z for p in body_), max(p.z for p in body_)))
for o in d["objects"]:
    base = o["name"].replace("__cut", "")
    if base.startswith(("bone__", "disc__")): continue
    w = []
    for i in range(nverts(o)):
        z = V(o, i).z
        if z <= BR[0][1]: w += [0, 1.0, 1, 0.0]; continue
        if z >= BR[-1][0]: w += [len(BR) - 1, 1.0, len(BR) - 2, 0.0]; continue
        k = max(j for j in range(len(BR) - 1) if BR[j][1] <= z)                     # the level whose top plate is below z
        if z < BR[k + 1][0]: t = (z - BR[k][1]) / max(1e-6, BR[k + 1][0] - BR[k][1]); t = t * t * (3 - 2 * t)   # in the disc space between k and k+1
        else: t = 1.0                                                                # over the body of k+1
        w += [k, round(1 - t, 2), k + 1, round(t, 2)]
    o["w"] = w
meta = dict(d["meta"]); meta["rig"] = {"levels": LEVELS, "fx": FX, "default_level": "L2"}
d["meta"] = meta
json.dump(d, open(f"{OUTS}/spine_b.json", "w"), separators=(",", ":"))
print("exported spine_b:", len(d["objects"]), "objects")
