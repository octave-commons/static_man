# Blender auto-rig + simple idle animation for the Wraith OBJ.
# Usage (CLI):
#   blender --background --python rig_wraith_blender.py -- \
#     --in /path/to/wraith.obj \
#     --out_glb /path/to/wraith_rigged_idle.glb \
#     --out_blend /path/to/wraith_rigged_idle.blend
# Optional:
#     --out_fbx /path/to/wraith_rigged_idle.fbx
#     --remesh_voxel 0.02
#
# Notes:
# - Designed for “proxy” rigs (pose + basic animation), not production skinning.
# - Works best with a reasonably watertight, non-self-intersecting mesh.

import bpy
import sys
import math
import argparse


def parse_args(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="inp", required=True, help="Input OBJ path")
    p.add_argument("--out_glb", required=True, help="Output GLB path")
    p.add_argument("--out_blend", default="", help="Optional output .blend path")
    p.add_argument("--out_fbx", default="", help="Optional output FBX path")
    p.add_argument(
        "--remesh_voxel",
        type=float,
        default=0.0,
        help="If >0, applies Voxel Remesh with this voxel size (in Blender units) before rigging",
    )
    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--frames", type=int, default=60)
    return p.parse_args(argv)


def clean_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_obj(path):
    # Blender 4.x+ has new native OBJ importer operators (wm.obj_import).
    # Older versions typically use import_scene.obj (addon io_scene_obj).
    if hasattr(bpy.ops.wm, "obj_import"):
        bpy.ops.wm.obj_import(filepath=path)
    else:
        # Ensure addon is enabled if needed
        try:
            bpy.ops.preferences.addon_enable(module="io_scene_obj")
        except Exception:
            pass
        bpy.ops.import_scene.obj(filepath=path)

    # Return imported mesh objects
    return [o for o in bpy.context.scene.objects if o.type == "MESH"]


def join_meshes(meshes):
    if not meshes:
        raise RuntimeError("No mesh objects were imported.")

    bpy.ops.object.select_all(action='DESELECT')
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    return bpy.context.view_layer.objects.active


def apply_basic_cleanup(obj):
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

    # Recalculate normals
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode='OBJECT')


def move_to_ground(obj):
    # Put origin at geometry center, then move so min Z sits at 0
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')

    # Compute bbox in world space
    world = obj.matrix_world
    corners = [world @ v.co for v in obj.data.vertices]
    if not corners:
        return
    minz = min(v.z for v in corners)
    obj.location.z -= minz


def add_voxel_remesh(obj, voxel_size):
    # This can make auto-weighting more stable (watertight-ish), at the cost of detail.
    mod = obj.modifiers.new(name="VoxelRemesh", type='REMESH')
    mod.mode = 'VOXEL'
    mod.voxel_size = voxel_size
    mod.use_smooth_shade = True
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=mod.name)


def bbox_dims(obj):
    world = obj.matrix_world
    corners = [world @ v.co for v in obj.data.vertices]
    xs = [v.x for v in corners]
    ys = [v.y for v in corners]
    zs = [v.z for v in corners]
    return (max(xs)-min(xs), max(ys)-min(ys), max(zs)-min(zs))


def create_armature_for_bbox(width, depth, height):
    arm = bpy.data.armatures.new("WraithRig")
    arm_obj = bpy.data.objects.new("WraithRig", arm)
    bpy.context.collection.objects.link(arm_obj)

    bpy.context.view_layer.objects.active = arm_obj
    arm_obj.select_set(True)

    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.edit_bones

    # Heuristic proportions
    pelvis_z = height * 0.45
    chest_z  = height * 0.75
    neck_z   = height * 0.85
    head_z   = height * 0.95

    half_w = width * 0.5

    root = eb.new('root')
    root.head = (0.0, 0.0, 0.0)
    root.tail = (0.0, 0.0, height * 0.10)

    pelvis = eb.new('pelvis')
    pelvis.head = root.tail
    pelvis.tail = (0.0, 0.0, pelvis_z)
    pelvis.parent = root

    spine = eb.new('spine')
    spine.head = pelvis.tail
    spine.tail = (0.0, 0.0, chest_z)
    spine.parent = pelvis

    neck = eb.new('neck')
    neck.head = spine.tail
    neck.tail = (0.0, 0.0, neck_z)
    neck.parent = spine

    head = eb.new('head')
    head.head = neck.tail
    head.tail = (0.0, 0.0, head_z)
    head.parent = neck

    # Arms (T-pose)
    shoulder_x = half_w * 0.20
    elbow_x    = half_w * 0.55
    wrist_x    = half_w * 0.95

    l_u = eb.new('upper_arm.L')
    l_u.head = ( shoulder_x, 0.0, chest_z)
    l_u.tail = (   elbow_x, 0.0, chest_z)
    l_u.parent = spine

    l_f = eb.new('forearm.L')
    l_f.head = l_u.tail
    l_f.tail = (   wrist_x, 0.0, chest_z)
    l_f.parent = l_u

    l_h = eb.new('hand.L')
    l_h.head = l_f.tail
    l_h.tail = ( wrist_x + half_w*0.08, 0.0, chest_z)
    l_h.parent = l_f

    r_u = eb.new('upper_arm.R')
    r_u.head = (-shoulder_x, 0.0, chest_z)
    r_u.tail = (  -elbow_x, 0.0, chest_z)
    r_u.parent = spine

    r_f = eb.new('forearm.R')
    r_f.head = r_u.tail
    r_f.tail = (  -wrist_x, 0.0, chest_z)
    r_f.parent = r_u

    r_h = eb.new('hand.R')
    r_h.head = r_f.tail
    r_h.tail = (-wrist_x - half_w*0.08, 0.0, chest_z)
    r_h.parent = r_f

    bpy.ops.object.mode_set(mode='OBJECT')
    return arm_obj


def parent_with_auto_weights(mesh_obj, arm_obj):
    bpy.ops.object.select_all(action='DESELECT')
    mesh_obj.select_set(True)
    arm_obj.select_set(True)
    bpy.context.view_layer.objects.active = arm_obj
    # Parent mesh to armature with automatic weights
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')


def add_idle_animation(arm_obj, fps=30, frames=60):
    scene = bpy.context.scene
    scene.render.fps = fps
    scene.frame_start = 1
    scene.frame_end = frames

    if arm_obj.animation_data is None:
        arm_obj.animation_data_create()

    action = bpy.data.actions.new("Idle")
    arm_obj.animation_data.action = action

    pb_root = arm_obj.pose.bones.get('root')
    pb_spine = arm_obj.pose.bones.get('spine')
    pb_chest = arm_obj.pose.bones.get('spine')  # keep simple

    # Ensure Euler
    arm_obj.rotation_mode = 'XYZ'
    for pb in [pb_root, pb_spine, pb_chest]:
        if pb:
            pb.rotation_mode = 'XYZ'

    # Small float + sway loop
    h = 0.08  # bob amplitude (in Blender units; tweak later)

    def kf(frame, z, sway_y, sway_z):
        scene.frame_set(frame)
        if pb_root:
            pb_root.location = (0.0, 0.0, z)
            pb_root.keyframe_insert(data_path="location")
        if pb_spine:
            pb_spine.rotation_euler = (0.0, sway_y, sway_z)
            pb_spine.keyframe_insert(data_path="rotation_euler")

    kf(1,   0.00,  0.00,  0.00)
    kf(frames//4,  h,     0.04, -0.02)
    kf(frames//2,  0.00,  0.00,  0.00)
    kf(3*frames//4,h,    -0.04,  0.02)
    kf(frames,     0.00,  0.00,  0.00)

    # Make curves linear-ish then add cyclic modifier for looping
    for fcu in action.fcurves:
        for kp in fcu.keyframe_points:
            kp.interpolation = 'BEZIER'
        try:
            mod = fcu.modifiers.new(type='CYCLES')
            mod.mode_before = 'REPEAT'
            mod.mode_after = 'REPEAT'
        except Exception:
            pass


def export_outputs(glb_path, fbx_path="", blend_path=""):
    # GLB
    bpy.ops.export_scene.gltf(
        filepath=glb_path,
        export_format='GLB',
        export_yup=True,
        export_apply=True,
        export_animations=True,
    )

    if fbx_path:
        bpy.ops.export_scene.fbx(
            filepath=fbx_path,
            apply_scale_options='FBX_SCALE_ALL',
            bake_anim=True,
            add_leaf_bones=False,
            use_armature_deform_only=True,
        )

    if blend_path:
        bpy.ops.wm.save_as_mainfile(filepath=blend_path)


def main():
    args = parse_args(sys.argv)
    clean_scene()

    meshes = import_obj(args.inp)
    mesh = join_meshes(meshes)

    # Basic cleanup + ground
    apply_basic_cleanup(mesh)
    move_to_ground(mesh)

    if args.remesh_voxel and args.remesh_voxel > 0:
        add_voxel_remesh(mesh, args.remesh_voxel)
        apply_basic_cleanup(mesh)

    w, d, h = bbox_dims(mesh)
    rig = create_armature_for_bbox(w, d, h)

    parent_with_auto_weights(mesh, rig)
    add_idle_animation(rig, fps=args.fps, frames=args.frames)

    export_outputs(args.out_glb, fbx_path=args.out_fbx, blend_path=args.out_blend)


if __name__ == "__main__":
    main()
