import bpy, bmesh, json, math, bisect
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from zana import *

Z0 = Vector((0, 0, 0))
Z_SEC, Z_TUBE_END = 0.008, -0.023
TCL_PROX, TCL_DIST = 0.0065, -0.0085
FLAT, R, R_N = 0.78, 0.00145, 0.0018
FLAT_N = 0.62
GAP_ROOF, GAP_NERVE, GAP_FLOOR, GAP_ROW = 0.0008, 0.0010, 0.0008, 0.0024
GAP_ROW_F, GAP_FLOOR_F = 0.0022, 0.0026      # a little more air in the fingers (curved paths)
def smooth01(t): t = max(0.0, min(1.0, t)); return t * t * (3 - 2 * t)

bpy.ops.wm.open_mainfile(filepath=f"{OUT}/wrist_step5a.blend")
O = bpy.data.objects
def verts(n): return [v.co for v in O[n].data.vertices]

# ---- ligament deep surface (ray-cast from the dorsal side) ----
tcl = build_tcl(O)
tcl_bvh = BVHTree.FromBMesh(tcl)
def tcl_deep(x, z):
    hit = tcl_bvh.ray_cast(Vector((x, -0.001, z)), Vector((0, -1, 0)))   # from inside the tunnel toward the palm: first hit = deep surface
    return hit[0].y if hit[0] is not None else None
def roof_at(x, z, hw=0.0):
    ds = [tcl_deep(x + dx, z) for dx in (-hw, 0.0, hw)]
    ds = [d for d in ds if d is not None]
    return max(ds) if ds else -0.030

# ---- nerve trunk profile along z (unshifted Z-Anatomy) ----
NV = verts("nerve__median")
def nerve_slice(z, w=0.0009):
    for k in (1, 3, 8, 20):
        s = [p for p in NV if abs(p.z - z) < w * k]
        if s: return s
    zn = min(NV, key=lambda p: abs(p.z - z)).z
    return [p for p in NV if abs(p.z - zn) < w]
def nerve_x(z): s = nerve_slice(z); return sum(p.x for p in s) / len(s)
def nerve_top(z): return min(p.y for p in nerve_slice(z))
def nerve_bottom(z): return max(p.y for p in nerve_slice(z))
def band_w(z): return smooth01((z - (TCL_DIST - 0.009)) / 0.009) * smooth01(((TCL_PROX + 0.006) - z) / 0.006)
NERVE_D = 0.0036
# nerve tube: 3.6 mm wide, 2.2 mm thick inside the tunnel
H_N = R_N * FLAT_N
def roof(z):
    d = tcl_deep(nerve_x(z), z)
    return d if d is not None else nerve_top(z) - GAP_ROOF
def nerve_centre_za(z):
    s = nerve_slice(z, 0.002); return Vector((sum(p.x for p in s) / len(s), sum(p.y for p in s) / len(s), z))
NERVE_END = min(p.z for p in NV) + 0.0005                        # where the Z-Anatomy trunk ends and the digital branches begin
NX0 = -0.0025                                          # tunnel x reference (radial of Z-Anatomy's nerve centroid, which sits too close to the hook)
def zr(z): return max(-0.0075, min(0.0055, z))             # roof lookups clamp to where the band exists
def tuck_y(z): return roof_at(NX0, zr(z), R_N) + GAP_ROOF + H_N
def nerve_c(z):
    """centreline of the section-variant nerve tube: Z-Anatomy path proximally (forearm), straight and tucked under the
    roof through the band, then a straight run to where the Z-Anatomy trunk ends and the digital branches begin"""
    if z >= 0.016:                                       # forearm: blend from the Z-Anatomy line into the tunnel line by z=16 mm
        za = nerve_centre_za(z); t = smooth01((z - 0.016) / 0.012)
        tun = Vector((NX0, tuck_y(0.010), z))
        return tun * (1 - t) + za * t
    if z >= -0.013:                                      # band
        return Vector((NX0, tuck_y(z), z))
    end = nerve_centre_za(NERVE_END); t = smooth01((-0.013 - z) / (-0.013 - NERVE_END))
    band_end = Vector((NX0, tuck_y(-0.012), -0.013))
    return band_end * (1 - t) + end * t
def nerve_shift(z): return 0.0      # (kept for compatibility; the nerve is now generated, not shifted)
for z in (0.014, 0.011, 0.008, 0.004, 0.0, -0.004, -0.008, -0.012, -0.016):
    print(f"z {z*1e3:+5.1f}: roof {roof(z)*1e3:+.1f}  nerve tube centre y {nerve_c(z).y*1e3:+.1f} (top {(nerve_c(z).y-H_N)*1e3:+.1f})")

# ---- bone floor: ray-cast from the palm side against all carpal + metacarpal bones ----
FLOOR_BONES = ("bone__capitate", "bone__hamate", "bone__trapezoid", "bone__trapezium", "bone__lunate", "bone__scaphoid", "bone__triquetrum", "bone__pisiform", "bone__mc1", "bone__mc2", "bone__mc3", "bone__mc4", "bone__mc5") + tuple(n for n in O.keys() if n.startswith(("bone__pp", "bone__mp", "bone__dp")))
_fb = bmesh.new()
for n in FLOOR_BONES:
    _m = O[n].data.copy(); _fb.from_mesh(_m); bpy.data.meshes.remove(_m)
floor_bvh = BVHTree.FromBMesh(_fb)
def floor_y(x, z, hw=None):
    hw = R + 0.0006 if hw is None else hw
    ys = []
    for dx in (-hw, -hw / 2, 0.0, hw / 2, hw):
        hit = floor_bvh.ray_cast(Vector((x + dx, -0.040, z)), Vector((0, 1, 0)))
        if hit[0] is not None: ys.append(hit[0].y)
    return min(ys) if ys else -0.030

# ---- tunnel layout: offsets relative to the nerve (x: radial -, ulnar +); rows are stacked UNDER the nerve everywhere ----
layout = {   # absolute x at the section plane -> stored as offset from the nerve
    "tendon__fdp2": (-0.0070, "deep"), "tendon__fdp3": (-0.0038, "deep"), "tendon__fdp4": (-0.0006, "deep"), "tendon__fdp5": (0.0024, "deep"),
    "tendon__fds2": (-0.0068, "sup"),  "tendon__fds3": (-0.0036, "sup"),  "tendon__fds4": (-0.0004, "sup"),  "tendon__fds5": (0.0026, "sup"),
    "tendon__fpl1": (-0.0101, "fpl"),   # thumb: "fpl1" so it never collides with the Z-Anatomy FPL object
}
H_MIN = 0.0007
_fcr = bmesh.new(); _fcr.from_mesh(O["Flexor carpi radialis.r"].data) if "Flexor carpi radialis.r" in O else None
_fcr_bvh = None
try:
    _m = O["tendon__fcr"].data.copy(); _fb2 = bmesh.new(); _fb2.from_mesh(_m); bpy.data.meshes.remove(_m); _fcr_bvh = BVHTree.FromBMesh(_fb2)
except KeyError: pass
def fcr_deep(x, z):
    """dorsal surface of the FCR tendon above (x,z), or None"""
    if _fcr_bvh is None: return None
    ys = []
    for dx in (-R, 0.0, R):
        hit = _fcr_bvh.ray_cast(Vector((x + dx, 0.02, z)), Vector((0, -1, 0)))
        if hit[0] is not None: ys.append(hit[0].y)
    return max(ys) if ys else None
_pl_bvh = None
try:
    _m = O["tendon__pl"].data.copy(); _pb = bmesh.new(); _pb.from_mesh(_m); bpy.data.meshes.remove(_m)
    cut_z(_pb, -0.044, keep="above", cap=True)                 # same trim as the exported section-set PL (distal fan dropped)
    _pl_bvh = BVHTree.FromBMesh(_pb)
except KeyError: pass
def pl_deep(x, z):
    if _pl_bvh is None: return None
    ys = [h[0].y for h in (_pl_bvh.ray_cast(Vector((x + dx, 0.03, z)), Vector((0, -1, 0))) for dx in (-R, 0.0, R)) if h[0] is not None]
    return max(ys) if ys else None
def tube_x(k, z):
    x = nerve_c(z).x + DX[k]
    if k == "tendon__fpl1": x -= 0.0030 * smooth01((-0.010 - z) / 0.008)   # FPL drifts to the radial corner through the distal tunnel
    return x
DX = {k: x - NX0 for k, (x, row) in layout.items()}
def fit(k, z, h):
    """(y, h) for tube k at level z. Stack: roof > nerve > FDS row > FDP row > floor. Rows are placed top-down from the
    nerve; if the floor is too close the whole stack shrinks (thinner ovals) instead of any row being pushed into another."""
    row = layout[k][1]; x = tube_x(k, z); w = band_w(z)
    slope = abs(nerve_c(z + 0.001).y - nerve_c(z - 0.001).y) / 0.002      # the tunnel line descends/ascends: vertical spacing must grow by 1/cos
    inv_cos = (1 + slope * slope) ** 0.5
    nb = nerve_c(z).y + H_N * inv_cos                         # nerve's dorsal surface
    top = nb + GAP_NERVE * inv_cos                            # top of the FDS row
    if z <= 0.016:
        rf = roof_at(x, zr(z), R) if w > 0.01 else -0.030; fl = floor_y(x, z)
        top = max(top, rf + GAP_ROOF)                         # far from the nerve the roof may hang lower than the nerve does
        fd = fcr_deep(x, z)
        if fd is not None: top = max(top, fd + 0.0005)                 # stay deep to the FCR tendon where it crosses
        pd = pl_deep(x, z)
        if pd is not None: top = max(top, pd + 0.0005)                 # and deep to palmaris longus / the palmar aponeurosis
        S = (fl - GAP_FLOOR) - top                            # room for two rows
        h = min(h, max(H_MIN, (S - GAP_ROW) / 4))
    y_sup = top + h * inv_cos
    y_deep = y_sup + (2 * h + GAP_ROW) * inv_cos
    wf = smooth01((TCL_DIST + 0.002 - z) / 0.010)             # 0 inside the tunnel .. 1 well past the ligament: rows go from nerve-stacked to floor-resting
    if wf > 0:
        fl2 = floor_y(x, z); yd2 = fl2 - GAP_FLOOR - h * inv_cos; ys2 = yd2 - (2 * h + GAP_ROW) * inv_cos
        for ceil in (pl_deep(x, z), fcr_deep(x, z)):
            if ceil is not None and ys2 - h < ceil + 0.0006:      # a superficial structure in the way: shrink the stack rather than sink into bone
                h = max(H_MIN, h - ((ceil + 0.0006) - (ys2 - h)) / 4); yd2 = fl2 - GAP_FLOOR - h * inv_cos; ys2 = yd2 - (2 * h + GAP_ROW) * inv_cos
        y_deep = y_deep * (1 - wf) + yd2 * wf; y_sup = y_sup * (1 - wf) + ys2 * wf
    y = {"deep": y_deep, "sup": y_sup, "fpl": y_sup + h * 0.6}[row]   # FPL rides just below the FDS level, radial of the row
    if z <= 0.016:
        lim = floor_y(x, z) - GAP_FLOOR - h                  # hard floor: never inside bone
        if y > lim:
            print(f"  ! tight at z {z*1e3:+.0f} for {k}: {row} row exceeds floor by {(y - lim)*1e3:.2f} mm")
            y = lim
            if row == "sup": y = min(y, lim - 2 * h - 0.0016)   # keep the FDS row clear of the (also clamped) FDP row
    return y, h
BAND_Z = (0.014, 0.012, 0.009, 0.006, 0.003, 0.0, -0.003, -0.006, -0.009, -0.012, -0.015, -0.018, -0.021)
tube_h = {}
for k in layout:
    h = R * FLAT
    for _ in range(3):
        h = min(fit(k, z, h)[1] for z in BAND_Z)
    tube_h[k] = h
tunnel_xy = {k: (tube_x(k, Z_SEC), fit(k, Z_SEC, tube_h[k])[0], R) for k in layout}
for k, (x, y, r) in tunnel_xy.items(): print(f"{k}: x {x*1e3:+.1f} y {y*1e3:+.1f}  thickness {tube_h[k]*2e3:.1f} mm (at section plane)")

PATH_ZS = [0.075, 0.062, 0.050, 0.040, 0.030, 0.022, 0.016, 0.012, 0.0095, 0.008, 0.0065, 0.003, 0.0, -0.003, -0.006, -0.009, -0.012]
FINGER = {"tendon__fdp2": 2, "tendon__fds2": 2, "tendon__fdp3": 3, "tendon__fds3": 3, "tendon__fdp4": 4, "tendon__fds4": 4, "tendon__fdp5": 5, "tendon__fds5": 5, "tendon__fpl1": 1}
def bcentre(n):
    vs = [v.co for v in O[n].data.vertices]; return sum(vs, Vector()) / len(vs)
def bz(n):
    zs = [v.co.z for v in O[n].data.vertices]; return min(zs), max(zs)
def finger_chain(f):
    """bone-centre polyline down the finger (proximal -> distal) with per-bone axis; used to place tendons on the palmar side"""
    names = ([f"bone__mc{f}", f"bone__pp{f}", f"bone__mp{f}", f"bone__dp{f}"] if f != 1
             else ["bone__trapezium", "bone__mc1", "bone__pp1", "bone__dp1"])   # thumb column starts at the trapezium so the FPL curves, not corners
    pts = []
    for n in names:
        vs = [v.co for v in O[n].data.vertices]; c0 = sum(vs, Vector()) / len(vs)
        # principal axis of the bone from the vertex spread along the bone
        far = max(vs, key=lambda v: (v - c0).length); a = (far - c0).normalized()
        if a.z > 0: a = -a                                                  # axis points distally (-z)
        pts.append((c0, a, n))
    return pts, names
def chain_point(chain, s):
    """point + axis at arc-length s along the chain of bone centres"""
    seg = [(chain[i][0], chain[i + 1][0]) for i in range(len(chain) - 1)]
    acc = 0
    for i, (p, q) in enumerate(seg):
        L = (q - p).length
        if s <= acc + L: t = (s - acc) / L; return p + (q - p) * t, (q - p).normalized()
        acc += L
    p, q = seg[-1]; return q + (q - p).normalized() * (s - acc), (q - p).normalized()
def chain_len(chain, upto):
    return sum((chain[i + 1][0] - chain[i][0]).length for i in range(upto))
FINGER_TAPER = 0.85     # tendon radius in the fingers relative to the tunnel radius
def path(k):
    """returns list of (point, radius_scale)"""
    h = tube_h[k]; pts = []; row = layout[k][1]
    for z in PATH_ZS:
        y, _ = fit(k, z, h); pts.append((Vector((tube_x(k, z), y, z)), 1.0, 1.0))
    f = FINGER[k]; chain, names = finger_chain(f)
    x0, z0 = tube_x(k, -0.012), -0.012
    s_end = chain_len(chain, len(chain) - 1) - (0.007 if f != 1 else 0.013)          # FDP/FPL stop short of the distal tuft
    if row == "sup": s_end = chain_len(chain, len(chain) - 2) + 0.001               # FDS ends at the middle phalanx
    start = chain[0][0] - chain[0][1] * 0.012
    n_app = 3 if f != 1 else 0
    s_begin = 0.0
    if f == 1:   # thumb: leave the tunnel and pick up the trapezium->metacarpal column where it passes z = -18 mm
        pex = Vector((x0, min(pts[-1][0].y, floor_y(x0, z0 - 0.003, hw=0.0035) - GAP_FLOOR - h), z0 - 0.003))
        pts.append((pex, 1.0, 1.0))
        s_begin = 0.0
        while s_begin < 0.08 and chain_point(chain, s_begin)[0].z > -0.024: s_begin += 0.001
        cp0, a0 = chain_point(chain, s_begin)
        npal0 = (Vector((0, -1, 0)) - a0 * a0.y).normalized()
        tgt = cp0 + npal0 * 0.009                                                  # roughly where the column run will start (refined by the solver)
        # smooth arc from the tunnel direction into the thumb column: quadratic Bezier whose control point continues the tunnel line
        T0 = Vector((0, 0, -1)); L = (tgt - pex).length
        ctrl = pex + T0 * (L * 0.45)
        for j in range(1, 6):
            t = j / 6; q = pex * (1 - t) ** 2 + ctrl * 2 * (1 - t) * t + tgt * t ** 2
            pts.append((Vector((q.x, min(q.y, floor_y(q.x, q.z, hw=0.0035) - GAP_FLOOR - h), q.z)), 1.0, 1.0))
    if f != 1:   # fingers: keep the tunnel column straight for 6 mm past the ligament before drifting to the finger's own line
        pex = Vector((x0, 0, z0 - 0.006)); fl = floor_y(pex.x, pex.z)
        y_deep = fl - GAP_FLOOR - h
        for ceil in (pl_deep(pex.x, pex.z), fcr_deep(pex.x, pex.z)):
            if ceil is not None: y_deep = max(y_deep, ceil + 0.0006 + h + (2 * h + GAP_ROW if row == "sup" else 0))
        pts.append((Vector((pex.x, y_deep if row != "sup" else y_deep - 2 * h - GAP_ROW, pex.z)), 1.0, 1.0)); x0, z0 = pex.x, pex.z
    for i in range(1, n_app + 1):                                                  # palm approach: tunnel exit -> metacarpal
        t = i / n_app
        p = Vector((x0, 0, z0)) * (1 - t) + start * t
        fl = floor_y(p.x, p.z, hw=0.0035); y_deep = fl - GAP_FLOOR - h
        for ceil in (pl_deep(p.x, p.z), fcr_deep(p.x, p.z)):
            if ceil is not None: y_deep = max(y_deep, ceil + 0.0006 + h + (2 * h + GAP_ROW if row == "sup" else 0))
        y_row = y_deep if row != "sup" else y_deep - 2 * h - GAP_ROW
        if f == 1: y_row = y_row + (pts[-1][0].y - y_row) * (1 - min(1, t / 0.35)) if i == 1 else y_row   # thumb: leave the tunnel at its own level
        pts.append((Vector((p.x, y_row, p.z)), 1.0, 1.0))
    raw = []; s = s_begin
    while s < s_end: raw.append(chain_point(chain, s)[0]); s += 0.002
    # round the joint corners: Gaussian-smooth the centreline so palmar offset curves never cross on the inside of a bend
    sm = []
    for i in range(len(raw)):
        acc = Vector(); wsum = 0.0
        for j in range(max(0, i - 5), min(len(raw), i + 6)):
            w = math.exp(-((j - i) * 2.0) ** 2 / (2 * 4.0 ** 2)); acc += raw[j] * w; wsum += w
        sm.append(acc / wsum)
    FB = [v.co for n in names for v in O[n].data.vertices]                          # this finger's bone vertices
    depth = []
    frames = []
    for i, cp in enumerate(sm):
        a = (sm[min(i + 1, len(sm) - 1)] - sm[max(i - 1, 0)]).normalized()
        npal = (Vector((0, -1, 0)) - a * a.y).normalized() if abs(a.y) < 0.99 else Vector((0, -1, 0))
        side = a.cross(npal).normalized(); frames.append((a, npal, side))
        # palmar extent of the bone around this station: vertex-based, so it works inside, outside and at the joints
        ds = [(v - cp).dot(npal) for v in FB if abs((v - cp).dot(a)) < 0.0025 and abs((v - cp).dot(side)) < 0.0045]
        depth.append(max(ds) if ds else None)
    for i in range(len(depth)):                                                       # fill gaps from neighbours
        if depth[i] is None:
            nb = [depth[j] for j in range(max(0, i - 3), min(len(depth), i + 4)) if depth[j] is not None]
            depth[i] = max(nb) if nb else 0.006
    depth = [max(depth[max(0, i - 6):i + 7]) for i in range(len(depth))]              # dilation: joint heads win over shaft dips
    depth = [sum(depth[j] * math.exp(-((j - i) / 2.5) ** 2) for j in range(max(0, i - 6), min(len(depth), i + 7))) /
             sum(math.exp(-((j - i) / 2.5) ** 2) for j in range(max(0, i - 6), min(len(depth), i + 7))) for i in range(len(depth))]   # then smooth
    def bone_at(s):
        seg = [(chain[j][0], chain[j + 1][0]) for j in range(len(chain) - 1)]; acc = 0
        for j, (p, q) in enumerate(seg):
            L = (q - p).length
            if s <= acc + L: return names[j] if (s - acc) / L < 0.5 else names[j + 1]
            acc += L
        return names[-1]
    for i, cp in enumerate(sm):
        a, npal, side = frames[i]; s = s_begin + i * 0.002
        surf = cp + npal * depth[i]
        taper = 1.0 - (1.0 - FINGER_TAPER) * smooth01(s / 0.030)
        hf = h * taper
        base = surf + npal * (GAP_FLOOR_F + hf)
        sup = base + npal * (2 * hf + GAP_ROW_F)
        pd = pl_deep(sup.x, sup.z)
        if pd is not None and sup.y - hf < pd + 0.0006:                             # aponeurosis in the way: lift the whole stack (both rows) dorsally
            lift = (pd + 0.0006 + hf) - (sup.y - hf); base = base + Vector((0, lift, 0)); sup = sup + Vector((0, lift, 0))
        pts.append((base if row != "sup" else sup, taper, 1.0 - i / max(1, len(sm) - 1), bone_at(s)))   # station rides on this bone
    return pts

NERVE_ZS = [0.075, 0.062, 0.050, 0.040, 0.030, 0.022, 0.016, 0.011, 0.007, 0.003, -0.001, -0.005, -0.009, -0.013, -0.017, -0.021, -0.025]
def nerve_path(): return [(nerve_c(z), 1.0, 0.0) for z in NERVE_ZS if z > NERVE_END] + [(nerve_c(NERVE_END), 1.0, 0.0)]
sc = bpy.context.scene
tubes = {}
SPECS = {k: (path(k), R * (0.82 if k == 'tendon__fpl1' else 0.86 if k.endswith('5') else 1.0), tube_h[k] / R, tube_h[k] / R) for k in layout}   # FPL and the little-finger tendons are the slimmer ones (they also sit beside walls)
SPECS["nerve__median"] = (nerve_path(), R_N, FLAT_N, 1.0)
# ---- explicit sweep: rings placed exactly on the computed path (no spline overshoot), oval = (width w, height h) ----
def resample(ctrl, step=0.001):
    """Catmull-Rom through control points, ~step spacing; returns list of (point, scale, slide_weight)"""
    P = [c_[0] for c_ in ctrl]; S = [c_[1] for c_ in ctrl]; W = [c_[2] if len(c_) > 2 else 1.0 for c_ in ctrl]
    out = []
    for i in range(len(P) - 1):
        p0, p1, p2, p3 = P[max(i - 1, 0)], P[i], P[i + 1], P[min(i + 2, len(P) - 1)]
        s1, s2, w1, w2 = S[i], S[i + 1], W[i], W[i + 1]
        n = max(1, int((p2 - p1).length / step))
        for j in range(n):
            t = j / n; t2, t3 = t * t, t * t * t
            q = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
            out.append((q, s1 + (s2 - s1) * t, w1 + (w2 - w1) * t))
    out.append((P[-1], S[-1], W[-1]))
    return out
def sweep(ctrl, w_of, h_of, segs=14, excursion=0.0):
    """tube mesh along ctrl; w_of(z, scale) / h_of(z, scale) give the lateral and palmar half-axes at each station.
    excursion > 0 also stores, per vertex, the displacement to the tube's 'glided' state: every ring re-placed at
    arc-length s - excursion*weight along the SAME path, so the tube slides through its channel without buckling."""
    st = resample(ctrl)
    PAL = Vector((0, -1, 0))
    # arc-length table and frames along the path
    S = [0.0]
    for i in range(1, len(st)): S.append(S[-1] + (st[i][0] - st[i - 1][0]).length)
    def frame_at(s):
        """position, tangent, normal, side at arc-length s (extrapolates beyond the ends)"""
        if s <= 0: i, u = 0, 0.0
        elif s >= S[-1]: i, u = len(st) - 2, 1.0
        else:
            i = bisect.bisect_right(S, s) - 1; u = (s - S[i]) / max(1e-9, S[i + 1] - S[i])
        p0, p1 = st[i][0], st[i + 1][0]
        t = (st[min(i + 2, len(st) - 1)][0] - st[max(i - 1, 0)][0]).normalized()
        p = p0 + (p1 - p0) * u + (t * s if s < 0 else (t * (s - S[-1]) if s > S[-1] else Vector()))
        npal = (PAL - t * t.dot(PAL)).normalized(); side = t.cross(npal).normalized()
        return p, t, npal, side
    bm = bmesh.new(); rings = []
    GL = bm.verts.layers.float_vector.new("glide")
    for i, (p, s, wgt) in enumerate(st):
        _, t, npal, side = frame_at(S[i])
        w, h = w_of(p.z, s), h_of(p.z, s)
        p2, t2, npal2, side2 = frame_at(S[i] - excursion * wgt)
        ring = []
        for k in range(segs):
            cs, sn = math.cos(2 * math.pi * k / segs), math.sin(2 * math.pi * k / segs)
            v = bm.verts.new(p + side * (w * cs) + npal * (h * sn))
            v[GL] = (p2 + side2 * (w * cs) + npal2 * (h * sn)) - v.co
            ring.append(v)
        rings.append(ring)
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(segs):
            try: bm.faces.new((r0[k], r0[(k + 1) % segs], r1[(k + 1) % segs], r1[k]))
            except ValueError: pass
    for ring, rev in ((rings[0], True), (rings[-1], False)):          # end caps
        c0 = bm.verts.new(sum((v.co for v in ring), Vector()) / segs); c0[GL] = sum((v[GL] for v in ring), Vector()) / segs
        for k in range(segs):
            tri = (ring[k], ring[(k + 1) % segs], c0) if not rev else (ring[(k + 1) % segs], ring[k], c0)
            try: bm.faces.new(tri)
            except ValueError: pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    return bm
# ---- build in dependency order, resolving residual contacts station by station (palm & fingers only) ----
CLEAR = 0.0005
def obstacles_for(k, built_tubes):
    """(bvh, name) list a tube must stay clear of: all bones, previously built tubes (FDP before FDS before FPL), FCR/PL"""
    obs = [(floor_bvh, "bones")]
    obs += [(bvh_, n) for n, bvh_ in built_tubes.items() if n != k]
    if _fcr_bvh is not None: obs.append((_fcr_bvh, "fcr"))
    if _pl_bvh is not None: obs.append((_pl_bvh, "pl"))
    return obs        # the ligament is handled by fit() (roof); its oblique edges must not shove tubes around
def ring_points(p, t, w, h, segs=10):
    PAL = Vector((0, -1, 0)); npal = (PAL - t * t.dot(PAL)).normalized(); side = t.cross(npal).normalized()
    return [p + side * (w * math.cos(2 * math.pi * k / segs)) + npal * (h * math.sin(2 * math.pi * k / segs)) for k in range(segs)], npal
def penetration(pt, bvh_):
    """(depth, location) — how far pt must move to be CLEAR of this obstacle, and the obstacle point"""
    loc, nrm, idx, dist = bvh_.find_nearest(pt, 0.004)
    if loc is None: return 0.0, None
    inside = (pt - loc).dot(nrm) < 0
    return ((dist + CLEAR) if inside else max(0.0, CLEAR - dist)), loc
def resolve(ctrl, rad, f_band, f_out, obs):
    import os
    if os.environ.get("NO_RESOLVE"): return [(c_[0].copy(), c_[1], (c_[2] if len(c_) > 2 else 1.0)) + tuple(c_[3:]) for c_ in ctrl], 0
    """move stations along the local palmar normal until their rings clear every obstacle: away from bones (palmar),
    away from superficial structures (dorsal). Skips the forearm; inside the band it only reacts to other tubes/ligament."""
    ctrl = [(c_[0].copy(), c_[1], (c_[2] if len(c_) > 2 else 1.0)) + tuple(c_[3:]) for c_ in ctrl]; moved = 0
    for it in range(14):
        changed = False
        for i, st_ in enumerate(ctrl):
            p, s, wgt = st_[0], st_[1], st_[2]
            if p.z > 0.014: continue
            t = (ctrl[min(i + 1, len(ctrl) - 1)][0] - ctrl[max(i - 1, 0)][0]).normalized()
            f = f_out + (f_band - f_out) * band_w(p.z)
            pts_, npal = ring_points(p, t, rad * s, rad * s * f, segs=14)
            push = 0.0
            for b_, n_ in obs:
                if p.z > -0.010 and n_ in ("bones", "pl", "fcr"): continue          # in the band the fit() stack already handles these
                for q in pts_:
                    d, loc = penetration(q, b_)
                    if d > 0:
                        sign = -1.0 if (loc - p).dot(npal) > 0 else 1.0                # obstacle palmar of us -> go dorsal, else palmar
                        if abs(d * sign) > abs(push): push = d * sign
            if push != 0.0:
                ctrl[i] = (p + npal * (push + 0.0002 * (1 if push > 0 else -1)), s, wgt) + tuple(st_[3:]); changed = True; moved += 1
        if not changed: break
    return ctrl, moved
built_tubes = {}; TENDON_RIGS = {}
order = [k for k in SPECS if k.startswith("tendon__fdp")] + [k for k in SPECS if k.startswith("tendon__fds")] + ["tendon__fpl1", "nerve__median"]
for k in order:
    pts, rad, f_band, f_out = SPECS[k]
    if k != "nerve__median":
        pts, moved = resolve(pts, rad, f_band, f_out, obstacles_for(k, built_tubes))
        if moved: print(f"  {k}: {moved} station adjustments to clear neighbours")
    def w_of(z, s, rad=rad): return rad * s
    def h_of(z, s, rad=rad, f_band=f_band, f_out=f_out):
        f = f_out + (f_band - f_out) * band_w(z); return rad * s * f
    if k != "nerve__median":
        TENDON_RIGS[k] = {"name": k + "__cut", "kind": ("fdp" if k.startswith("tendon__fdp") else "fds" if k.startswith("tendon__fds") else "fpl"),
                          "r": rad, "f_band": f_band, "f_out": f_out, "band": [TCL_DIST - 0.009, TCL_PROX + 0.006], "plane_z": Z_SEC,
                          "stations": [{"p": [round(x, 5) for x in p], "s": round(sc_, 3), "bone": (st[3] if len(st) > 3 else "root").replace("bone__", "")}
                                       for st in pts for p, sc_ in [(st[0], st[1])]]}
    EXC = {"fdp": 0.014, "fds": 0.011, "fpl": 0.004}
    exc = EXC["fdp"] if k.startswith("tendon__fdp") else EXC["fds"] if k.startswith("tendon__fds") else EXC["fpl"] if k.startswith("tendon__fpl") else 0.0
    bm = sweep(pts, w_of, h_of, excursion=exc)
    if k != "nerve__median": built_tubes[k] = BVHTree.FromBMesh(bm)
    zj = (hash(k) % 11 - 5) * 0.00003
    b2 = bm.copy(); cut_z(b2, Z_SEC + zj, keep="below", cap=True)
    tubes[k + "__cut"] = b2
    print("tube", k, len(b2.verts), "verts")

# ---- assemble ----
prev = json.load(open(f"{OUT}/wrist_step5b.json"))   # always start from step 5b's output, never from our own
objects = [o for o in prev["objects"] if o["name"] not in ("nerve__median__cut", "tendon__fds__cut", "tendon__fdp__cut", "tendon__fpl__cut")]   # generated tubes replace the Z-Anatomy trunk and tendon fans in the section set
for o in objects:
    if o["name"] == "tendon__pl__cut":         # keep palmaris longus through the wrist and proximal palm only (its distal fan crowds the tendons)
        bm = bm_from_arrays([tuple(o["verts"][i:i+3]) for i in range(0, len(o["verts"]), 3)], [tuple(o["tris"][i:i+3]) for i in range(0, len(o["tris"]), 3)])
        cut_z(bm, -0.044, keep="above", cap=True)
        o["verts"], o["tris"] = to_arrays(bm, center=Z0)
for o in objects:
    if o["name"] == "tendon__pl__cut":         # palmaris longus runs OVER the ligament: lift any vertex that sits inside or touches it
        v = o["verts"]; moved = 0; CLEAR_PL = 0.0032
        for _pass in range(8):
            for i in range(0, len(v), 3):
                p = Vector(v[i:i + 3])
                hit = tcl_bvh.ray_cast(Vector((p.x, -0.06, p.z)), Vector((0, 1, 0)))
                if hit[0] is not None and p.y > hit[0].y - CLEAR_PL:
                    v[i + 1] = round(hit[0].y - CLEAR_PL, 5); moved += 1; continue
                loc, nrm, idx, dist = tcl_bvh.find_nearest(p, CLEAR_PL)
                if loc is not None:                      # near an edge face: push palmar until clear
                    v[i + 1] = round(p.y - (CLEAR_PL - dist) - 0.0002, 5); moved += 1
        print("PL lifted over the ligament:", moved, "vertex moves")
for k, bm in tubes.items():
    v, t = to_arrays(bm, center=Z0)
    o = {"name": k, "layer": k.split("__")[0], "verts": v, "tris": t}
    GL = bm.verts.layers.float_vector.get("glide")
    if GL is not None and k != "nerve__median__cut":
        bm.verts.ensure_lookup_table(); o["morphs"] = {"glide": [round(c_, 5) for vv in bm.verts for c_ in vv[GL]]}
    objects.append(o)
meta = prev["meta"]; meta["tunnel_layout"] = {k: [round(x * 1e3, 2), round(y * 1e3, 2), round(r * 1e3, 2)] for k, (x, y, r) in tunnel_xy.items()}
meta["tendon_rigs"] = list(TENDON_RIGS.values())
export_all(objects, meta, "wrist_step5")
