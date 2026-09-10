import bpy, bmesh, json, sys, itertools
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from zana import *
import zana

JSON = f"{OUT}/wrist_step6.json"
d = json.load(open(JSON)); objs = {o["name"]: o for o in d["objects"]}
def bm_of(o):
    return bm_from_arrays([tuple(o["verts"][i:i+3]) for i in range(0, len(o["verts"]), 3)], [tuple(o["tris"][i:i+3]) for i in range(0, len(o["tris"]), 3)])

cut = {k: o for k, o in objs.items() if k.endswith("__cut") and not k.startswith(("skin", "prop", "lig__tcl_released"))}
layer = lambda k: k.split("__")[0]
tube = lambda k: k.startswith(("tendon__fds", "tendon__fdp", "tendon__fpl")) and k not in ("tendon__fds__cut", "tendon__fdp__cut", "tendon__fpl__cut")
za_fan = lambda k: k in ("tendon__fds__cut", "tendon__fdp__cut", "tendon__fpl__cut")
def checked(a, b):
    """pairs where an overlap is a real defect (skip Z-Anatomy-internal contacts and intentional joins)"""
    la, lb = layer(a), layer(b)
    if la == "muscle" or lb == "muscle": return False                       # Z-Anatomy muscles overlap each other/bones by design
    if "skin" in (la, lb): return False
    if la == "bone" and lb == "bone": return False                          # joint surfaces touch in Z-Anatomy
    if {la, lb} == {"bone", "lig"}: return False                            # ligament bites into its attachments on purpose
    if (tube(a) and za_fan(b)) or (tube(b) and za_fan(a)): return False    # tubes dive into the tendon fans on purpose
    if za_fan(a) and za_fan(b): return False
    za = lambda k: za_fan(k) or k in ("tendon__pl__cut", "tendon__fcr__cut")
    if (la == "bone" and za(b)) or (lb == "bone" and za(a)): return False      # Z-Anatomy tendons vs Z-Anatomy bones: not ours to fix
    if {a, b} == {"lig__tcl__cut", "tendon__fcr__cut"}: return False           # FCR runs inside a split of the ligament
    if za(a) and za(b): return False
    if "nerve__median_digital" in a or "nerve__median_digital" in b or "palmar_branch" in a or "palmar_branch" in b: return False
    if (a == "nerve__median__cut" and za_fan(b)) or (b == "nerve__median__cut" and za_fan(a)): return False   # trunk end meets the fans
    return True

bvh = {k: BVHTree.FromBMesh(bm_of(o)) for k, o in cut.items()}
bad = []
tris = {k: [tuple(o["tris"][i:i+3]) for i in range(0, len(o["tris"]), 3)] for k, o in cut.items()}
def tri_z(k, ti): o = cut[k]; return sum(o["verts"][3 * v + 2] for v in tris[k][ti]) / 3
for a, b in itertools.combinations(sorted(cut), 2):
    if not checked(a, b): continue
    ov = bvh[a].overlap(bvh[b])
    if ov:
        zs = [tri_z(a, i) for i, _ in ov]
        bad.append((a, b, len(ov), min(zs), max(zs)))
print(f"QA overlap check: {len(cut)} objects, {len(bad)} overlapping pairs")
for a, b, n, z0, z1 in sorted(bad, key=lambda t: -t[2]): print(f"  OVERLAP {a:28} x {b:28} {n:5} tri pairs  z {z0*1e3:+6.1f}..{z1*1e3:+6.1f} mm")

# ---- slice renders through the band (section set only) ----
if "--render" in sys.argv:
    from mathutils import Matrix
    def look2(cam, sun, pos, up):
        fwd = (-pos).normalized(); right = fwd.cross(up).normalized(); up2 = right.cross(fwd).normalized()
        m = Matrix((right, up2, -fwd)).transposed(); cam.location = pos; cam.rotation_quaternion = m.to_quaternion(); sun.rotation_quaternion = m.to_quaternion()
    zana.look = look2
    for zc in (0.006, 0.002, -0.002, -0.006, -0.010):
        sl = []
        for k, o in cut.items():
            if layer(k) in ("muscle",): continue
            bm = bm_of(o); cut_z(bm, zc, keep="below", cap=True, ngon=layer(k) == "lig")
            if len(bm.faces): v, t = to_arrays(bm, center=Vector((0, 0, 0))); sl.append({"name": k, "layer": layer(k), "verts": v, "tris": t})
        rebuild_scene(sl, {})
        render_views({f"slice_{int(round(zc*1e3)):+03d}": (-DISTAL + PALMAR * 0.05, PALMAR)}, "qa", dist=0.075, res=520, samples=14, show=lambda ob: True)
sys.exit(1 if bad else 0)
