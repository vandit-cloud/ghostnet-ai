"""Prepare Tripo-generated GLBs for the GhostNet-AI hero scene.

Run headless:
    blender --background --python scripts/blender_prep_models.py

Or open Blender, Scripting tab, Open, Run. It processes both models and writes
them straight into app/frontend/public/models/.

What it fixes, in the order it matters:
  1. Decimates ~12-15x of redundant geometry (Tripo puts the real detail in the
     normal map, so the silhouette survives this).
  2. Scales to REAL METRES. Tripo normalises every model to 1.0 units on its
     longest axis, so without this the towfish ends up the size of the ship.
  3. Drops the origin to the waterline (vessel) / nose (towfish).
  4. Points the bow along +Y, the convention Vessel.tsx and Scene3D.tsx assume.
  5. Downsizes Tripo's 4096x4096 maps - at hero size the vessel is ~400 px
     tall, so 4K textures cost megabytes to resolve detail no one can see.
  6. Exports .glb with Draco.

BOW_IS_POSITIVE_Y is the one thing this script cannot work out for itself - a
bounding box is symmetric, so nothing in the file says which end is the bow.
Look at the model once and set it.
"""

import math
import os
import bpy
from mathutils import Matrix, Vector

# Tripo ships 4096x4096 basecolor/normal/roughness-metallic maps. 1024 is
# ample for a model that renders at a few hundred pixels, and it is the
# difference between a ~2 MB and a ~0.4 MB asset.
TEXTURE_SIZE = 1024

SRC = r"E:\models"
DST = r"E:\New folder\app\frontend\public\models"

MODELS = [
    {
        "src": "survey vessel 3d model.glb",
        "out": "vessel.glb",
        # Real length in metres, bow to transom.
        "length_m": 28.0,
        # Triangle budget after decimation.
        "target_tris": 30000,
        # Fraction of TOTAL HEIGHT that sits below the waterline. Set this by
        # looking at where the dark antifouling band ends on the hull. 0.10 is a
        # typical loaded draught for a vessel of this type.
        # Measured from the basecolor texture: the reddish antifouling band
        # runs from the keel up to ~7% of total height, where the navy topsides
        # start. That boundary IS the design waterline.
        "origin_drop": 0.07,
        # The hull tapers toward glTF +Z (half-width 0.176 -> 0.078) while the
        # -Z end stays full-width and low - so +Z is the bow and -Z is the
        # transom with the open aft deck. The importer maps glTF +Z to Blender
        # -Y, so the bow lands on -Y and needs the 180 turn.
        "bow_is_positive_y": False,
    },
    {
        "src": "side-scan towfish 3d model.glb",
        "out": "towfish.glb",
        "length_m": 1.3,
        "target_tris": 8000,
        # The towfish origin belongs at the nose tow-point, not the waterline,
        # so it is handled separately below and this value is unused.
        "origin_drop": 0.0,
        "bow_is_positive_y": True,
    },
]


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.images):
        for item in list(block):
            if item.users == 0:
                block.remove(item)


def join_imported():
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    for o in bpy.context.scene.objects:
        if o.type != "MESH":
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.object.select_all(action="DESELECT")
    for m in meshes:
        m.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    if len(meshes) > 1:
        bpy.ops.object.join()
    return bpy.context.view_layer.objects.active


def decimate(obj, target_tris):
    bpy.context.view_layer.objects.active = obj
    # Triangulate first: decimate's collapse mode is defined on triangles, and
    # Tripo ships FB_ngon_encoding, so the raw face count lies about the real
    # triangle count.
    tri = obj.modifiers.new("tri", "TRIANGULATE")
    bpy.ops.object.modifier_apply(modifier=tri.name)

    current = len(obj.data.polygons)
    if current <= target_tris:
        print(f"    already under budget ({current:,} tris)")
        return
    dec = obj.modifiers.new("dec", "DECIMATE")
    dec.decimate_type = "COLLAPSE"
    dec.ratio = target_tris / current
    bpy.ops.object.modifier_apply(modifier=dec.name)
    print(f"    {current:,} -> {len(obj.data.polygons):,} tris (ratio {dec.ratio:.3f})")


def set_origin_to(obj, location):
    """Move the object's origin to a world-space point without moving the mesh."""
    offset = obj.matrix_world.translation - location
    obj.data.transform(Matrix.Translation(offset))
    obj.matrix_world.translation = location


def prep(cfg):
    print(f"\n== {cfg['src']}")
    clear_scene()
    bpy.ops.import_scene.gltf(filepath=os.path.join(SRC, cfg["src"]))
    obj = join_imported()

    decimate(obj, cfg["target_tris"])

    # --- scale to real metres -------------------------------------------------
    # The importer maps glTF +Z to Blender -Y, so the long axis lands on Y.
    dims = obj.dimensions
    longest = max(dims.x, dims.y, dims.z)
    factor = cfg["length_m"] / longest
    obj.scale = (factor, factor, factor)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    print(f"    scaled x{factor:.2f} -> {tuple(round(d, 2) for d in obj.dimensions)} m")

    # --- point the bow at +Y --------------------------------------------------
    if not cfg["bow_is_positive_y"]:
        obj.rotation_euler[2] = math.radians(180)
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
        print("    rotated 180 deg so the bow faces +Y")

    # --- origin ---------------------------------------------------------------
    bbox = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    xs = [v.x for v in bbox]
    ys = [v.y for v in bbox]
    zs = [v.z for v in bbox]
    cx = (min(xs) + max(xs)) / 2
    height = max(zs) - min(zs)

    if cfg["out"] == "towfish.glb":
        # Nose tow-point: centred, mid-body height, at the +Y tip.
        target = Vector((cx, max(ys), (min(zs) + max(zs)) / 2))
    else:
        # Waterline: above the keel by the draught fraction, at the pivot point.
        target = Vector((cx, (min(ys) + max(ys)) / 2, min(zs) + height * cfg["origin_drop"]))
    set_origin_to(obj, target)
    obj.location = (0, 0, 0)
    print(f"    origin set, final dims {tuple(round(d, 2) for d in obj.dimensions)} m")

    # --- textures -------------------------------------------------------------
    for img in bpy.data.images:
        if img.size[0] > TEXTURE_SIZE or img.size[1] > TEXTURE_SIZE:
            was = tuple(img.size)
            img.scale(TEXTURE_SIZE, TEXTURE_SIZE)
            print(f"    texture {img.name}: {was[0]}x{was[1]} -> {TEXTURE_SIZE}")

    # --- export ---------------------------------------------------------------
    os.makedirs(DST, exist_ok=True)
    out = os.path.join(DST, cfg["out"])
    bpy.ops.export_scene.gltf(
        filepath=out,
        export_format="GLB",
        export_yup=True,
        export_draco_mesh_compression_enable=True,
        export_draco_mesh_compression_level=6,
        export_apply=True,
        export_cameras=False,
        export_lights=False,
        use_selection=False,
    )
    print(f"    wrote {out} ({os.path.getsize(out) / 1e6:.2f} MB)")


for cfg in MODELS:
    prep(cfg)

print("\nDone. Open /lab/hero to check them.")
