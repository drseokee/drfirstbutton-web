import bpy, bmesh, json, os
from mathutils import Vector, Matrix

SRC = "/home/claude/Z-Anatomy/Startup.blend"
OUT = "/home/claude/out"; os.makedirs(OUT, exist_ok=True)
CARPAL_CENTER = Vector((-0.2609, -0.0218, 0.8463))     # from Step 4
PALMAR, DISTAL, RADIAL = Vector((0, -1, 0)), Vector((0, 0, -1)), Vector((-1, 0, 0))
ATTR = "Z-Anatomy CC BY-SA 4.0 / BodyParts3D CC BY-SA 2.1 JP"

_dg = None
def open_src():
    global _dg
    bpy.ops.wm.open_mainfile(filepath=SRC, load_ui=False)
    _dg = bpy.context.evaluated_depsgraph_get(); _dg.update()
    return bpy.data.objects

def refresh():
    global _dg
    _dg = bpy.context.evaluated_depsgraph_get(); _dg.update()

def world_bm(name, triangulate=True):
    o = bpy.data.objects[name]
    ev = o.evaluated_get(_dg)
    me = ev.to_mesh()
    me.transform(o.matrix_world)
    bm = bmesh.new(); bm.from_mesh(me)
    ev.to_mesh_clear()
    if triangulate: bmesh.ops.triangulate(bm, faces=bm.faces)
    return bm

def bm_from_arrays(verts, tris):
    bm = bmesh.new()
    vs = [bm.verts.new(v) for v in verts]
    bm.verts.ensure_lookup_table()
    for t in tris:
        try: bm.faces.new((vs[t[0]], vs[t[1]], vs[t[2]]))
        except ValueError: pass
    return bm

def cut_plane(bm, co, no, remove="outer", cap=True, ngon=False):
    """bisect; remove='outer' removes the side the normal points to.
    cap: fan from the loop centroid (robust for round/convex sections) or ngon=True (ear-clipped polygon, for C-shaped sections)."""
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no,
                           clear_outer=(remove == "outer"), clear_inner=(remove == "inner"))
    if cap:
        boundary = [e for e in bm.edges if e.is_boundary]
        if ngon:
            res = bmesh.ops.holes_fill(bm, edges=boundary, sides=0)
            bmesh.ops.triangulate(bm, faces=res["faces"], ngon_method="EAR_CLIP")
        else:
          for loop in edge_loops(boundary):          # fan-cap every loop from its centroid: never leaves holes on star-shaped sections
            vs = ordered_verts(loop)
            if len(vs) < 3: continue
            c = bm.verts.new(sum((v.co for v in vs), Vector()) / len(vs))
            for i in range(len(vs)):
                try: bm.faces.new((vs[i], vs[(i + 1) % len(vs)], c))
                except ValueError: pass
        if boundary:
            bmesh.ops.split_edges(bm, edges=[e for e in boundary if e.is_valid])   # hard edge cap/wall
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.triangulate(bm, faces=bm.faces)   # bisect leaves quads on the wall
    return bm

def edge_loops(edges):
    from collections import defaultdict
    adj = defaultdict(list)
    for e in edges:
        for v in e.verts: adj[v].append(e)
    seen, loops = set(), []
    for e in edges:
        if e in seen: continue
        loop = [e]; seen.add(e); start, cur = e.verts[0], e.verts[1]
        while cur is not start:
            nxt = [x for x in adj[cur] if x not in seen]
            if not nxt: break
            seen.add(nxt[0]); loop.append(nxt[0]); cur = nxt[0].other_vert(cur)
        loops.append(loop)
    return loops

def ordered_verts(loop):
    vs = [loop[0].verts[0]]
    for e in loop:
        vs.append(e.other_vert(vs[-1]))
    return vs[:-1] if vs[-1] is vs[0] else vs

def cut_z(bm, z, keep="below", cap=True, ngon=False):
    # keep='below' keeps z < plane (distal side), removes proximal (+z)
    return cut_plane(bm, (0, 0, z), (0, 0, 1), remove="outer" if keep == "below" else "inner", cap=cap, ngon=ngon)

def bbox(bm):
    xs = [v.co for v in bm.verts]
    mn = Vector(map(min, zip(*xs))); mx = Vector(map(max, zip(*xs)))
    return mn, mx

def join_bms(bms):
    out = bmesh.new()
    for bm in bms:
        me = bpy.data.meshes.new("tmp"); bm.to_mesh(me); out.from_mesh(me); bpy.data.meshes.remove(me)
    return out

def bm_to_object(bm, name, collection=None):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); me.update()
    ob = bpy.data.objects.new(name, me)
    (collection or bpy.context.scene.collection).objects.link(ob)
    return ob

def evaluated_bm(ob):
    """evaluate modifiers of a temp object in the current scene"""
    dg = bpy.context.evaluated_depsgraph_get(); dg.update()
    ev = ob.evaluated_get(dg); me = ev.to_mesh()
    bm = bmesh.new(); bm.from_mesh(me); ev.to_mesh_clear()
    bmesh.ops.triangulate(bm, faces=bm.faces)
    return bm

def to_arrays(bm, center=CARPAL_CENTER, nd=5):
    bm.verts.ensure_lookup_table()
    idx = {v: i for i, v in enumerate(bm.verts)}
    verts = [round(c, nd) for v in bm.verts for c in (v.co - center)]
    tris = [idx[v] for f in bm.faces for v in f.verts]
    return verts, tris

def smooth_shade(me):
    for p in me.polygons: p.use_smooth = True

# ---------- clean scene rebuild + export ----------
COLORS = {"bone": (0.90, 0.86, 0.76, 1), "nerve": (0.95, 0.80, 0.25, 1), "lig": (0.85, 0.85, 0.80, 1),
          "tendon": (0.93, 0.93, 0.90, 1), "muscle": (0.62, 0.22, 0.22, 1), "skin": (0.85, 0.62, 0.52, 1)}

def rebuild_scene(objects, meta):
    """objects: list of dicts {name, layer, verts, tris}; creates fresh scene"""
    bpy.ops.wm.read_homefile(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"; sc.unit_settings.length_unit = "MILLIMETERS"
    cols = {}
    for o in objects:
        layer = o["layer"]
        if layer not in cols:
            cols[layer] = bpy.data.collections.new(layer); sc.collection.children.link(cols[layer])
        me = bpy.data.meshes.new(o["name"]); v, t = o["verts"], o["tris"]
        me.from_pydata([v[i:i+3] for i in range(0, len(v), 3)], [], [t[i:i+3] for i in range(0, len(t), 3)])
        me.update(); me.validate(); smooth_shade(me)
        ob = bpy.data.objects.new(o["name"], me); cols[layer].objects.link(ob)
        mat = bpy.data.materials.get(f"mat__{layer}")
        if mat is None:
            mat = bpy.data.materials.new(f"mat__{layer}"); mat.use_nodes = True
            mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = COLORS.get(layer, (0.7, 0.7, 0.7, 1))
        me.materials.append(mat)
    for k, v in meta.items(): sc[k] = str(v)
    return sc

def export_all(objects, meta, stem):
    json.dump({"meta": meta, "objects": objects}, open(f"{OUT}/{stem}.json", "w"), separators=(",", ":"))
    rebuild_scene(objects, meta)
    bpy.ops.wm.save_as_mainfile(filepath=f"{OUT}/{stem}.blend")
    bpy.ops.export_scene.gltf(filepath=f"{OUT}/{stem}.glb", export_format="GLB", export_apply=True)
    print(f"exported {stem}: {sum(len(o['verts'])//3 for o in objects)} verts, json {os.path.getsize(f'{OUT}/{stem}.json')//1024} KB")

# ---------- preview renders (CPU Cycles) ----------
def look(cam, sun, pos, up):
    fwd = (-pos).normalized(); right = fwd.cross(up).normalized(); up2 = right.cross(fwd).normalized()
    m = Matrix((right, up2, -fwd)).transposed()
    cam.location = pos; cam.rotation_quaternion = m.to_quaternion()
    sun.rotation_quaternion = (m @ Matrix.Rotation(0.5, 3, 'X') @ Matrix.Rotation(-0.6, 3, 'Y')).to_quaternion()

def render_views(views, stem, hide_layers=(), res=720, samples=24, dist=0.24, alpha=None, show=lambda ob: True):
    """views: {name: (direction_vector, up_vector)}; run on the rebuilt scene"""
    sc = bpy.context.scene
    cam = bpy.data.objects.get("cam") or bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    if cam.name not in sc.collection.objects: sc.collection.objects.link(cam)
    sc.camera = cam; cam.data.lens = 50; cam.data.clip_start = 0.005; cam.rotation_mode = "QUATERNION"
    sun = bpy.data.objects.get("sun") or bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    if sun.name not in sc.collection.objects: sc.collection.objects.link(sun)
    sun.data.energy = 2.5; sun.rotation_mode = "QUATERNION"
    if sc.world is None:
        sc.world = bpy.data.worlds.new("w"); sc.world.use_nodes = True
        bg = sc.world.node_tree.nodes["Background"]; bg.inputs[0].default_value = (0.30, 0.33, 0.40, 1); bg.inputs[1].default_value = 1.0
    sc.render.engine = "CYCLES"; sc.cycles.device = "CPU"; sc.cycles.samples = samples; sc.cycles.use_denoising = False
    sc.render.resolution_x = res; sc.render.resolution_y = res
    for ob in sc.objects:
        if ob.type == "MESH": ob.hide_render = (ob.users_collection[0].name in hide_layers) or not show(ob)
    if alpha:
        for layer, a in alpha.items():
            mat = bpy.data.materials.get(f"mat__{layer}")
            if mat: mat.node_tree.nodes["Principled BSDF"].inputs["Alpha"].default_value = a
    for name, (d, up) in views.items():
        look(cam, sun, d.normalized() * dist, up)
        sc.render.filepath = f"{OUT}/{stem}_{name}.png"
        bpy.ops.render.render(write_still=True); print("rendered", stem, name)

STD_VIEWS = {"palmar": (PALMAR, DISTAL),
             "oblique": (PALMAR + RADIAL * 0.9 - DISTAL * 0.35, DISTAL),
             "proximal": (-DISTAL + PALMAR * 0.12, PALMAR)}

def cut_z_bool(bm, z, keep="above", split_angle=1.0):
    """robust half-space cut with capped faces via exact boolean; returns new bmesh"""
    ob = bm_to_object(bm, "_cut_tmp")
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, z - 0.5 if keep == "above" else z + 0.5))
    cube = bpy.context.active_object
    m = ob.modifiers.new("bool", "BOOLEAN"); m.operation = "DIFFERENCE"; m.solver = "EXACT"
    m.object = cube; m.use_self = True; m.use_hole_tolerant = True
    out = evaluated_bm(ob)
    bpy.data.objects.remove(cube); bpy.data.objects.remove(ob)
    sharp = [e for e in out.edges if not e.is_boundary and e.is_manifold and e.calc_face_angle(0) > split_angle]
    if sharp: bmesh.ops.split_edges(out, edges=sharp)
    bmesh.ops.triangulate(out, faces=out.faces)
    return out

def build_tcl(O, thickness=0.0016, z_prox=0.011, z_dist=-0.013, nz=13, nx=25, sag=0.0045, overlap=0.0015):
    """Procedural transverse carpal ligament: a solid arch band spanning scaphoid tubercle/trapezium ridge (radial)
    to pisiform/hook of hamate (ulnar), sagging palmarly by `sag` at the middle. Coordinates: carpal-centred frame."""
    def pal(n): vs = [v.co for v in O[n].data.vertices]; return min(vs, key=lambda v: v.y).copy()
    sca, trz, pis, ham = pal("bone__scaphoid"), pal("bone__trapezium"), pal("bone__pisiform"), pal("bone__hamate")
    def on_line(p, q, z):      # attachment edge: interpolate between the two landmarks, hold the landmark beyond them
        t = (p.z - z) / (p.z - q.z) if abs(p.z - q.z) > 1e-6 else 0.0
        t = max(0.0, min(1.0, t))
        r = p + (q - p) * t; r.z = z; return r
    outer, deep = [], []
    for i in range(nz):
        z = z_prox + (z_dist - z_prox) * i / (nz - 1)
        A, B = on_line(sca, trz, z), on_line(pis, ham, z)
        chord = (B - A); chord.z = 0; d = chord.normalized()
        A = A - d * overlap; B = B + d * overlap               # bite into the bones a little
        mid = (A + B) / 2; ctrl = mid + Vector((0, -2 * sag, 0))   # quadratic Bezier through mid - sag
        row_o, row_d = [], []
        for j in range(nx):
            t = j / (nx - 1)
            P = A * (1 - t) ** 2 + ctrl * 2 * (1 - t) * t + B * t ** 2
            T = (ctrl - A) * 2 * (1 - t) + (B - ctrl) * 2 * t; T.z = 0; T.normalize()
            n = Vector((-T.y, T.x, 0))
            if n.y < 0: n = -n                                   # normal pointing dorsally (into the tunnel)
            P.z = z
            row_o.append(P); row_d.append(P + n * thickness)
        outer.append(row_o); deep.append(row_d)
    bm = bmesh.new()
    vo = [[bm.verts.new(p) for p in row] for row in outer]
    vd = [[bm.verts.new(p) for p in row] for row in deep]
    def quad(a, b, c, d):
        try: bm.faces.new((a, b, c, d))
        except ValueError: pass
    for i in range(nz - 1):
        for j in range(nx - 1):
            quad(vo[i][j], vo[i][j + 1], vo[i + 1][j + 1], vo[i + 1][j])
            quad(vd[i][j], vd[i + 1][j], vd[i + 1][j + 1], vd[i][j + 1])
    for i in range(nz - 1):                                     # radial / ulnar edges
        quad(vo[i][0], vo[i + 1][0], vd[i + 1][0], vd[i][0])
        quad(vo[i][-1], vd[i][-1], vd[i + 1][-1], vo[i + 1][-1])
    for j in range(nx - 1):                                     # proximal / distal ends
        quad(vo[0][j], vd[0][j], vd[0][j + 1], vo[0][j + 1])
        quad(vo[-1][j], vo[-1][j + 1], vd[-1][j + 1], vd[-1][j])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    print(f"TCL built: radial {tuple(round(x*1e3,1) for x in sca)}->{tuple(round(x*1e3,1) for x in trz)}, ulnar {tuple(round(x*1e3,1) for x in pis)}->{tuple(round(x*1e3,1) for x in ham)}; {len(bm.verts)} verts")
    return bm
