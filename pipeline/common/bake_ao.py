import bpy, bmesh, json, sys, math, time
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from zana import bm_from_arrays, join_bms

src, dst = sys.argv[1], sys.argv[2]
RAYS = int(sys.argv[3]) if len(sys.argv) > 3 else 20
DIST = float(sys.argv[4]) if len(sys.argv) > 4 else 0.035        # occlusion reach: 3.5 cm
d = json.load(open(src))
def bm_of(o): return bm_from_arrays([tuple(o["verts"][i:i+3]) for i in range(0, len(o["verts"]), 3)], [tuple(o["tris"][i:i+3]) for i in range(0, len(o["tris"]), 3)])
# occluders: everything except skin (the skin would blacken the whole interior) and props
world = BVHTree.FromBMesh(join_bms([bm_of(o) for o in d["objects"] if o["layer"] not in ("skin", "prop")]))
dirs = []
for i in range(RAYS):                                             # fixed cosine-weighted hemisphere directions (local frame)
    u, v = (i + 0.5) / RAYS, ((i * 0.618033988) % 1.0)
    r = math.sqrt(u); th = 2 * math.pi * v
    dirs.append(Vector((r * math.cos(th), r * math.sin(th), math.sqrt(max(0.0, 1 - u)))))
t0 = time.time(); total = 0
for o in d["objects"]:
    if o["layer"] == "prop": continue
    bm = bm_of(o); bm.normal_update(); bm.verts.ensure_lookup_table()
    ao = []
    for v in bm.verts:
        n = v.normal
        if n.length < 0.5: ao.append(1.0); continue
        a = Vector((1, 0, 0)) if abs(n.x) < 0.9 else Vector((0, 1, 0))
        t = n.cross(a).normalized(); b = n.cross(t)
        origin = v.co + n * 0.0004; hit = 0.0
        for dv in dirs:
            w = t * dv.x + b * dv.y + n * dv.z
            loc, nrm, idx, dist = world.ray_cast(origin, w, DIST)
            if loc is not None: hit += 1 - (dist / DIST) * 0.6          # nearer occluders count more
        ao.append(round(max(0.0, 1 - hit / RAYS), 3))
    o["ao"] = ao; total += len(ao)
    print(f"ao {o['name']:34} {len(ao):6} v  mean {sum(ao)/max(1,len(ao)):.2f}  ({time.time()-t0:.0f}s)")
json.dump(d, open(dst, "w"), separators=(",", ":"))
print("wrote", dst, total, "verts", f"{time.time()-t0:.0f}s")
