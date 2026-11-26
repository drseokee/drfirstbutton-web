# 어깨(견관절·회전근개) 팩 — 1단계: 추출 · 팔꿈치 90° 굽힘 · 리그 가중치 · 극상근 병리 속성
# 원본: LluisV/Z-Anatomy FBX (Z-Anatomy CC BY-SA 4.0 / BodyParts3D) → imp.py 로 za_all.blend 를 먼저 만든다.
# 좌표: Z-Anatomy 축 그대로 (오른쪽 = -x, 앞 = -y, 위 = +z), 원점 = 상완골두 중심(구 맞춤), 미터.
import bpy, bmesh, json, math, os, sys
from mathutils import Vector, Matrix, Quaternion
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
sys.path.insert(0, os.path.dirname(__file__))
import zana
from zana import world_bm, cut_plane, cut_z, join_bms, bm_from_arrays

OUTS = "/home/claude/out_shoulder"; os.makedirs(OUTS, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath="/home/claude/sh/za_all.blend", load_ui=False); zana.refresh()
objs = bpy.data.objects
def get(n): return world_bm(n)
def verts(bm): return [v.co.copy() for v in bm.verts]

# ---------- frame: humeral head sphere ----------
hum = get("Humerus.r"); hv = verts(hum); ztop = max(v.z for v in hv)
head = [v for v in hv if v.z > ztop - 0.045 and v.x > -0.20]          # proximal 4.5 cm, medial-facing part of the head (articular)
def fit_sphere(P):
    import numpy as np
    A = np.array([[2*p.x, 2*p.y, 2*p.z, 1] for p in P]); b = np.array([p.dot(p) for p in P])
    s = np.linalg.lstsq(A, b, rcond=None)[0]; c = Vector(s[:3]); return c, math.sqrt(s[3] + c.dot(c))
# the articular surface faces medial-up-back: keep head points far from the shaft axis on the medial side
c0, r0 = fit_sphere(head)
for _ in range(3):
    pts = [p for p in head if abs((p - c0).length - r0) < 0.004 and (p - c0).x > -0.006]
    c0, r0 = fit_sphere(pts)
C = c0; R_HEAD = r0
print("head centre", [round(c, 4) for c in C], "radius mm", round(R_HEAD * 1e3, 1))

# ---------- objects ----------
B = {}
B["bone__humerus"] = hum
B["bone__scapula"] = get("Scapula.r")
B["bone__clavicle"] = get("Clavicle.r")
# forearm bent 90° at the elbow (forearm points forward) so humeral rotation reads clearly
ulna, rad = get("Ulna.r"), get("Radius.r")
dist = [v for v in hv if v.z < min(v.z for v in hv) + 0.02]
EL_C = sum(dist, Vector()) / len(dist); EL_C.z += 0.004
xs = sorted(dist, key=lambda v: v.x); EL_AX = (xs[-1] - xs[0]); EL_AX.z = 0; EL_AX.normalize()
def bend(bm, ang):
    R = Matrix.Rotation(ang, 4, EL_AX)
    for v in bm.verts: v.co = EL_C + (R @ (v.co - EL_C))
# sign: forearm (below the elbow, -z) must swing to anterior (-y)
test = Matrix.Rotation(math.radians(90), 3, EL_AX) @ Vector((0, 0, -1))
ANG = math.radians(90) if test.y < 0 else math.radians(-90)
for bm in (ulna, rad): bend(bm, ANG)
for bm in (ulna, rad):                                                  # forearm cut mid-way (no hand): 13 cm from the elbow
    fwd = Matrix.Rotation(ANG, 3, EL_AX) @ Vector((0, 0, -1))
    cut_plane(bm, EL_C + fwd * 0.13, fwd, remove="outer", cap=True)
B["bone__ulna"] = ulna; B["bone__radius"] = rad
# context (thorax): ribs 1–6, costal cartilages, sternum, T1–T6 — dimmed in the viewer
for n, k in [("First rib.r", "rib1"), ("Second rib.r", "rib2"), ("Third rib.r", "rib3"), ("Fourth rib.r", "rib4"), ("Fifth rib.r", "rib5"), ("Sixth rib.r", "rib6"),
             ("Manubrium of sternum", "manubrium"), ("Body of sternum", "sternum")] + [(f"Vertebra T{i}", f"t{i}") for i in range(1, 7)] + [(f"Costal cartilage of {w} rib.r", f"cc{i}") for i, w in enumerate(["first", "second", "third", "fourth", "fifth", "sixth"], 1)]:
    if n in objs: B["ctx__" + k] = get(n)
# muscles (whole) + their origin/insertion patches
MUS = {"ssp": "Supraspinatus muscle", "isp": "Infraspinatus muscle", "tm": "Teres minor muscle", "ssc": "Subscapularis muscle",
       "delt_a": "Clavicular part of deltoid muscle", "delt_m": "Acromial part of deltoid muscle", "delt_p": "Scapular spinal part of deltoid muscle",
       "lhb": "Long head of biceps brachii", "shb": "Short head of biceps brachii", "cb": "Coracobrachialis muscle", "tmaj": "Teres major muscle"}
PATCH = {}
for k, n in MUS.items():
    B["muscle__" + k] = get(n + ".r")
    for suf in ("or", "er"):
        if n + "." + suf in objs: PATCH[(k, suf)] = verts(get(n + "." + suf))
# deltoid insertion patch is shared ("Deltoid muscle.er")
for k in ("delt_a", "delt_m", "delt_p"): PATCH[(k, "er")] = verts(get("Deltoid muscle.er"))
PATCH[("shb", "er")] = PATCH.get(("lhb", "er"), [])
# supraspinatus: one subdivision (its tear edges and retraction need a finer mesh than the 717-vertex original)
_b = B["muscle__ssp"]; bmesh.ops.subdivide_edges(_b, edges=_b.edges[:], cuts=1, use_grid_fill=True); bmesh.ops.triangulate(_b, faces=_b.faces[:])
# biceps / coracobrachialis: cut above the elbow (the elbow is bent in this model) — keep the upper 17 cm
for k in ("lhb", "shb"): cut_z(B["muscle__" + k], C.z - 0.17, keep="above", cap=True)
# ligaments / capsule / labrum / bursae
for n, k in [("Articular capsule of glenohumeral joint.r", "lig__capsule"), ("Glenoid labrum.r", "lig__labrum"), ("Coracohumeral ligament.r", "lig__chl"),
             ("Transverse humeral ligament.r", "lig__thl"), ("Articular capsule of acromioclavicular joint.r", "lig__ac"), ("Trapezoid ligament.r", "lig__trapezoid"), ("Conoid ligament.r", "lig__conoid"),
             ("Subacromial bursa.r", "bursa__subacromial"), ("Subdeltoid bursa.r", "bursa__subdeltoid")]:
    if n in objs: B[k] = get(n)
for k, bm in B.items(): print(f"{k:24} {len(bm.verts):6} v")

# ---------- landmarks ----------
sv = verts(B["bone__scapula"])
acro = [v for v in sv if v.z > C.z + 0.015 and v.x < C.x + 0.012]       # acromion: above the head, lateral of a plane 12 mm medial of its centre
ACRO_TIP = min(acro, key=lambda v: v.x)                                    # most lateral point
ACRO_ANT = max(acro, key=lambda v: -v.y - 0.6 * v.x)                       # anterolateral corner
ACRO_POST = max(acro, key=lambda v: v.y - 0.6 * v.x)                       # posterolateral corner (injection landmark)
ACRO_UNDER = sum((v for v in acro if v.z < C.z + 0.028), Vector()) / max(1, len([v for v in acro if v.z < C.z + 0.028]))   # undersurface centre
cor = [v for v in sv if v.y < C.y - 0.015 and v.z > C.z - 0.01 and v.x > C.x + 0.015]
COR_TIP = min(cor, key=lambda v: v.y) if cor else None                    # coracoid tip: most anterior scapular point near the head
glen = [v for v in sv if (v - C).length < R_HEAD + 0.009 and (v - C).x > 0]
GLEN_C = sum(glen, Vector()) / max(1, len(glen))
print("acro tip", ACRO_TIP - C, "acro ant", ACRO_ANT - C, "acro post", ACRO_POST - C, "coracoid", COR_TIP - C, "glenoid", GLEN_C - C)
# coracoacromial ligament: flat band coracoid tip → anterior-inferior acromion (not in the FBX)
def band(p0, p1, w0, w1, th, n=10, m=6, sag=0.0):
    bm = bmesh.new(); ax = (p1 - p0); L = ax.length; ax.normalize(); side = ax.cross(Vector((0, 0, 1))).normalized(); nrm = side.cross(ax).normalized()
    rows = []
    for i in range(n + 1):
        u = i / n; c = p0.lerp(p1, u) + nrm * (sag * 4 * u * (1 - u)); w = w0 + (w1 - w0) * u
        rows.append([[bm.verts.new(c + side * (w * (j / m - 0.5)) + nrm * (s * th / 2)) for j in range(m + 1)] for s in (1, -1)])
    for i in range(n):
        for s in range(2):
            for j in range(m):
                a, b_, c_, d_ = rows[i][s][j], rows[i][s][j + 1], rows[i + 1][s][j + 1], rows[i + 1][s][j]
                bm.faces.new((a, b_, c_, d_) if s == 0 else (d_, c_, b_, a))
    for i in range(n):
        for j in (0, m):
            a, b_, c_, d_ = rows[i][0][j], rows[i + 1][0][j], rows[i + 1][1][j], rows[i][1][j]
            bm.faces.new((a, b_, c_, d_) if j == 0 else (d_, c_, b_, a))
    for i in (0, n):
        for j in range(m):
            a, b_, c_, d_ = rows[i][0][j], rows[i][0][j + 1], rows[i][1][j + 1], rows[i][1][j]
            bm.faces.new((a, b_, c_, d_) if i == n else (d_, c_, b_, a))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bmesh.ops.triangulate(bm, faces=bm.faces); return bm
B["lig__cal"] = band(COR_TIP + Vector((0.004, 0.006, 0.004)), ACRO_ANT + Vector((0.006, 0.004, -0.003)), 0.016, 0.012, 0.0018, sag=0.003)

# ---------- rig weights: w = 0 → scapula, 1 → humerus (muscles blend by origin/insertion distance) ----------
def kd(P):
    t = KDTree(len(P))
    for i, p in enumerate(P): t.insert(p, i)
    t.balance(); return t
W = {}
for k in MUS:
    bm = B["muscle__" + k]; o, e = PATCH.get((k, "or")), PATCH.get((k, "er"))
    if k in ("lhb", "shb", "cb"):        # biceps / coracobrachialis: origin = supraglenoid tubercle / coracoid; runs along the humerus
        ko = kd(o) if o else None; ws = []
        for v in bm.verts:
            d0 = ko.find(v.co)[2] if ko else 0.05
            ws.append(min(1.0, max(0.0, (d0 - 0.008) / 0.045)))
        W["muscle__" + k] = ws; continue
    if not o: o = [v.co for v in B["bone__scapula"].verts]
    if not e: e = [v.co for v in B["bone__humerus"].verts if v.co.z < C.z - 0.03]
    ko, ke = kd(o), kd(e); ws = []
    for v in bm.verts:
        do, de = ko.find(v.co)[2], ke.find(v.co)[2]; t = do / max(1e-6, do + de)
        t = min(1, max(0, (t - 0.25) / 0.6)); ws.append(t * t * (3 - 2 * t))
    W["muscle__" + k] = ws
# capsule / CHL / labrum / bursa: by distance to the head centre side (capsule humeral half follows the humerus)
for k in ("lig__capsule", "lig__chl", "lig__thl", "bursa__subdeltoid"):
    if k not in B: continue
    ws = []
    for v in B[k].verts:
        d = v.co - C; lat = -d.x                                           # lateral = -x (right side)
        ws.append(min(1, max(0, (lat + 0.004) / 0.014)) if k != "lig__thl" else 1.0)
    W[k] = ws

# ---------- supraspinatus tendon attributes (for tendinopathy / tears / retraction / atrophy) ----------
ssp = B["muscle__ssp"]; ke = kd(PATCH[("ssp", "er")]); ko = kd(PATCH[("ssp", "or")])
FOOT = PATCH[("ssp", "er")]; FOOT_C = sum(FOOT, Vector()) / len(FOOT)
fo = sum(PATCH[("ssp", "or")], Vector()) / len(PATCH[("ssp", "or")])
LINE = (fo - FOOT_C).normalized()                                          # insertion → origin (medial)
# footprint AP axis: principal horizontal spread of the footprint
import numpy as np
F = np.array([list(p - FOOT_C) for p in FOOT]); u, s, vt = np.linalg.svd(F, full_matrices=False)
AP = Vector(vt[0]); AP = (AP - LINE * AP.dot(LINE)).normalized()
if AP.y > 0: AP = -AP                                                      # +AP = anterior
attr = {"tend": [], "art": [], "ap": [], "belly": []}
for v in ssp.verts:
    p = v.co; de = ke.find(p)[2]; do = ko.find(p)[2]
    along = (p - FOOT_C).dot(LINE)                                         # mm medial of the footprint centre
    attr["tend"].append(round(along, 4))
    attr["art"].append(round((p - C).length - R_HEAD, 4))                  # height above the head surface (articular side ≈ 0)
    attr["ap"].append(round((p - FOOT_C).dot(AP), 4))
    attr["belly"].append(round(do, 4))
print("ssp along range mm", round(min(attr["tend"]) * 1e3), round(max(attr["tend"]) * 1e3), "ap", round(min(attr["ap"]) * 1e3), round(max(attr["ap"]) * 1e3))
# atrophy morph: the belly in the fossa sinks toward the scapular floor (Goutallier/Thomazeau-like look): nearest scapula point + 45 % of the gap
sbvh = BVHTree.FromBMesh(B["bone__scapula"])
atro = []
for v, al in zip(ssp.verts, attr["tend"]):
    k_ = min(1, max(0, (al - 0.035) / 0.03))                               # only the belly, > 3.5 cm medial of the footprint
    loc, nrm, idx, dd = sbvh.find_nearest(v.co)
    tgt = loc + (v.co - loc) * 0.45 if loc is not None else v.co
    d = (tgt - v.co) * k_; atro += [d.x, d.y, d.z]
# retraction morph: torn tendon end pulled medially along the muscle line (up to 2.5 cm at the stump, fading into the belly)
retr = []
for v, al in zip(ssp.verts, attr["tend"]):
    k_ = 1 - min(1, max(0, (al - 0.0) / 0.06)); d = LINE * 0.022 * k_
    # keep the stump riding on the head: push out radially if it would sink in
    q = v.co + d; r = (q - C).length
    if r < R_HEAD + 0.002: q = C + (q - C).normalized() * (R_HEAD + 0.002); d = q - v.co
    retr += [d.x, d.y, d.z]
# swelling morph (tendinopathy): tendon part thickens 1.5 mm along its normal
ssp.normal_update(); swell = []
for v, al in zip(ssp.verts, attr["tend"]):
    k_ = 1 - min(1, max(0, (al - 0.01) / 0.025)); d = v.normal * 0.0015 * k_; swell += [d.x, d.y, d.z]
MORPH = {"muscle__ssp": {"swell": swell, "retract": retr, "atrophy": atro}}

DE = {}
for k in MUS:
    e = PATCH.get((k, "er"))
    if not e or k in ("lhb", "shb", "cb"): continue
    t = kd(e); DE["muscle__" + k] = [round(t.find(v.co)[2], 4) for v in B["muscle__" + k].verts]
# scapular plane normal (PCA of the blade), AC and SC joint centres
P_ = np.array([list(v) for v in sv]); P0 = P_.mean(0); _, _, vt_ = np.linalg.svd(P_ - P0, full_matrices=False)
SN = Vector(vt_[2]); SN = SN if SN.y < 0 else -SN                          # normal pointing anterior (-y)
acv = verts(B["lig__ac"]); AC = sum(acv, Vector()) / len(acv)
cv = verts(B["bone__clavicle"]); SC = max(cv, key=lambda v: v.x)           # most medial clavicle point
SC = sum([v for v in cv if v.x > SC.x - 0.012], Vector()) / len([v for v in cv if v.x > SC.x - 0.012])
print("scap normal", SN, "AC", AC - C, "SC", SC - C)
# fibre attachments for the line-of-action deformation in the viewer: per muscle, sub-sampled origin / insertion patches + each vertex's nearest point on each
FIB = {}
for k in MUS:
    if k in ("lhb", "shb", "cb"): continue
    o = PATCH.get((k, "or")) or [v.co for v in B["bone__scapula"].verts]
    e = PATCH.get((k, "er")) or [v.co for v in B["bone__humerus"].verts if v.co.z < C.z - 0.03]
    o = o[::max(1, len(o) // 220)]; e = e[::max(1, len(e) // 220)]
    ko_, ke_ = kd(o), kd(e); bm = B["muscle__" + k]
    FIB["muscle__" + k] = {"po": [round(c, 5) for p in o for c in (p - C)], "pi": [round(c, 5) for p in e for c in (p - C)],
                           "oi": [ko_.find(v.co)[1] for v in bm.verts], "ii": [ke_.find(v.co)[1] for v in bm.verts]}
# ---------- export ----------
LAYER = lambda k: k.split("__")[0]
out = []
for k, bm in B.items():
    bm.verts.ensure_lookup_table(); bm.verts.index_update()
    o = {"name": k, "layer": LAYER(k), "verts": [round(c, 5) for v in bm.verts for c in (v.co - C)], "tris": [v.index for f in bm.faces for v in f.verts]}
    if k in W: o["wh"] = [round(x, 3) for x in W[k]]
    if k in MORPH: o["morphs"] = {mk: [round(x, 5) for x in mv] for mk, mv in MORPH[k].items()}
    if k == "muscle__ssp": o["attr"] = attr
    if k in DE: o["de"] = DE[k]
    if k in FIB: o["fib"] = FIB[k]
    out.append(o)
rel = lambda p: [round(c, 5) for c in (p - C)]
meta = {"attribution": zana.ATTR, "frame": "Z-Anatomy axes (right=-x, anterior=-y, up=+z), origin = humeral head centre", "R_head": round(R_HEAD, 5),
        "land": {"acro_tip": rel(ACRO_TIP), "acro_ant": rel(ACRO_ANT), "acro_post": rel(ACRO_POST), "acro_under": rel(ACRO_UNDER), "coracoid": rel(COR_TIP), "glenoid": rel(GLEN_C),
                 "ssp_foot": rel(FOOT_C), "ssp_line": [round(c, 4) for c in LINE], "ssp_ap": [round(c, 4) for c in AP], "elbow": rel(EL_C), "ac": rel(AC), "sc": rel(SC), "scap_n": [round(c, 4) for c in SN], "elbow_axis": [round(c, 4) for c in EL_AX]},
        "foot": {k: [rel(p) for p in PATCH[(k, "er")][::max(1, len(PATCH[(k, "er")]) // 60)]] for k in ("ssp", "isp", "tm", "ssc")}}
json.dump({"meta": meta, "objects": out}, open(f"{OUTS}/shoulder_a.json", "w"), separators=(",", ":"))
print("wrote", f"{OUTS}/shoulder_a.json", sum(len(o["verts"]) // 3 for o in out), "verts")
