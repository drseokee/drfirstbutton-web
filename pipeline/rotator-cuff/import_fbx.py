import bpy, re
F="/home/user/lluisv/z-anatomy/Resources/Models/FBX/"
bpy.ops.wm.read_factory_settings(use_empty=True)
for f in ["SkeletalSystem100","MuscularSystem100","Joints100","NervousSystem100","CardioVascular41"]:
    bpy.ops.import_scene.fbx(filepath=F+f+".fbx")
bpy.context.view_layer.update()
mw={o.name:o.matrix_world.copy() for o in bpy.data.objects}
for o in bpy.data.objects:
    o.parent=None
for o in bpy.data.objects: o.matrix_world=mw[o.name]
for o in list(bpy.data.objects):
    if o.type!="MESH" or re.search(r"\.[ijst]\d*$",o.name) or len(o.data.vertices)<=8: bpy.data.objects.remove(o)
bpy.ops.wm.save_as_mainfile(filepath="/home/claude/sh/za_all.blend")
print("saved", len(bpy.data.objects))
