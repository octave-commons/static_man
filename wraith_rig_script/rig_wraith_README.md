# Wraith auto-rig + idle animation (Blender)

This script imports an OBJ, builds a simple armature (root/spine/head + arms), parents the mesh with **Automatic Weights**, creates a looping **idle float** animation, and exports a **GLB** (and optionally FBX / BLEND).

## Run from terminal

```bash
blender --background --python rig_wraith_blender.py -- \
  --in wraith_clean_from_edited_smooth.obj \
  --out_glb wraith_rigged_idle.glb \
  --out_blend wraith_rigged_idle.blend
```

Optional FBX:

```bash
blender --background --python rig_wraith_blender.py -- \
  --in wraith_clean_from_edited_smooth.obj \
  --out_glb wraith_rigged_idle.glb \
  --out_fbx wraith_rigged_idle.fbx
```

If Automatic Weights fails (common on non-manifold meshes), enable voxel remesh:

```bash
blender --background --python rig_wraith_blender.py -- \
  --in wraith_clean_from_edited_smooth.obj \
  --out_glb wraith_rigged_idle.glb \
  --remesh_voxel 0.02
```

## What you get
- A basic deform rig
- A looping idle animation (60 frames at 30fps)
- Exported `.glb` (and optional `.fbx` / `.blend`)

## Notes
- This is a *proxy* rig meant for posing / quick tests.
- For production rigs: use Rigify or Mixamo, then repaint weights.
