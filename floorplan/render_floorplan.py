"""Render a privacy-safe example floorplan for a Home Assistant dashboard.

Usage (from the repo root):
    blender -b -P floorplan/render_floorplan.py            # Blender installed
    python floorplan/render_floorplan.py                   # or: pip install bpy

Options (after "--" when running through blender):
    --floor DEMO        render only the synthetic demo floor
    --samples 64        Cycles samples (default 48)
    --width 1600        image width in px (height follows the model)

Inputs : floorplan/models/*.obj (exported from a CAD tool, cm, Y-up)
Outputs: floorplan/output/<floor>_{day,night,<light>}.webp
         floorplan/positions.json  (light/room positions in % of the image,
                                    used for the picture-elements YAML)
"""

import argparse
import json
import math
import sys
from pathlib import Path

import bpy  # must come first: the bpy wheel provides bmesh/mathutils
import bmesh
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / "floorplan" / "models"
OUT = ROOT / "floorplan" / "output"
POSITIONS = ROOT / "floorplan" / "positions.json"

# ---------------------------------------------------------------------------
# Layout. Coordinates are "plan cm": x to the right, y DOWN (same orientation
# as the Grundrissplan PDF), origin = top-left of the plan.
# rot = degrees clockwise as seen on the plan, applied before the move.
# ---------------------------------------------------------------------------
FLOORS = {
    "DEMO": {
        "demo_room": {"rot": 0, "move": (0, 0)},
    },
}

# Everything above this height (cm) is cut off, dollhouse style.
CUT_HEIGHT = 120

# Lamps: plan cm (x, y) + height cm. One overlay image is rendered per lamp.
LIGHTS = {
    "demo_light": {"floor": "DEMO", "pos": (250, 250, 220), "power": 120},
}

# Optional demo furniture as boxes: plan cm x0, y0, x1, y1, height cm,
# colour key. Replace this with synthetic or user-owned example data.
FURNITURE = {
    "DEMO": [
        ("table", 150, 180, 350, 320, 75, "wood"),
        ("sofa", 420, 160, 700, 260, 80, "fabric"),
    ],
}

# Room label anchors (plan cm) -> positions.json only.
ROOMS = {
    "demo_room": {"floor": "DEMO", "pos": (500, 400)},
}

# Heights (cm) at which dashboard elements are projected onto the image:
# lamp/stairs icons at wall-cut height, room labels on the floor.
ICON_HEIGHT = 120
LABEL_HEIGHT = 0

# Stairs hotspot per floor (plan cm): tapping it switches to the other floor.
STAIRS = {"DEMO": (700, 450)}

# Velux roof windows (plan cm) -> cover icons on the dashboard.
COVERS = {
    "demo_cover": {"floor": "DEMO", "pos": (700, 80)},
}

LAMP_COLOR = (1.0, 0.72, 0.42)  # ~2700 K
# Camera per layout: desktop is landscape; mobile turns the flat 90 degrees so
# its long side runs down a portrait phone screen (images get an "_m" suffix).
CAMERAS = {
    "desktop": {"rot": (55, 0, 35), "suffix": ""},
    "mobile": {"rot": (30, 0, 80), "suffix": "_m"},
}

MAT_COLORS = {
    "wall": (0.82, 0.81, 0.78, 1),
    "floor": (0.42, 0.27, 0.15, 1),
    "cap": (0.12, 0.13, 0.15, 1),
    "default": (0.70, 0.70, 0.70, 1),
    # furniture
    "fabric": (0.38, 0.39, 0.41, 1),
    "fabric_light": (0.88, 0.86, 0.82, 1),
    "rug": (0.60, 0.52, 0.42, 1),
    "wood": (0.50, 0.33, 0.18, 1),
    "dark_wood": (0.30, 0.20, 0.13, 1),
    "white": (0.90, 0.90, 0.88, 1),
}


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    p = argparse.ArgumentParser()
    p.add_argument("--floor", choices=list(FLOORS))
    p.add_argument("--samples", type=int, default=48)
    p.add_argument("--width", type=int, default=1600, help="longer image side, px")
    p.add_argument("--mobile", action="store_true", help="portrait camera, *_m images")
    return p.parse_args(argv)


def plan_to_world(x, y, z=0.0):
    """plan cm (y down) -> Blender metres (Y up)."""
    return Vector((x / 100, -y / 100, z / 100))


# --------------------------------------------------------------------------- scene
def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.use_denoising = True
    scene.render.film_transparent = True
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Punchy"
    scene.render.image_settings.file_format = "WEBP"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.quality = 90
    world = bpy.data.worlds.new("World")
    world.use_nodes = True
    scene.world = world
    return scene


def material(name, rgba, emission=0.0):
    mat = bpy.data.materials.get(name)
    if mat:
        return mat
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = 0.8
    if emission:
        bsdf.inputs["Emission Color"].default_value = rgba
        bsdf.inputs["Emission Strength"].default_value = emission
    return mat


def pick_material(obj):
    """Fusion exports many materials with Kd 0 (textures); map by name instead."""
    name = obj.name.lower()
    src = obj.active_material.name.lower() if obj.active_material else ""
    if "floor" in name:
        return material("floor", MAT_COLORS["floor"])
    if "wall" in name or "powder_coat_-_rough_(white)" in src:
        return material("wall", MAT_COLORS["wall"])
    if obj.active_material:
        bsdf = obj.active_material.node_tree.nodes.get("Principled BSDF") if obj.active_material.node_tree else None
        if bsdf:
            col = tuple(bsdf.inputs["Base Color"].default_value)
            if sum(col[:3]) > 0.05:
                return material(f"furn_{src}", col)
    return material("default", MAT_COLORS["default"])


def import_room(name, rot, move):
    before = set(bpy.data.objects)
    bpy.ops.wm.obj_import(
        filepath=str(MODELS / f"{name}.obj"),
        up_axis="Y",
        forward_axis="NEGATIVE_Z",
        global_scale=0.01,
        use_split_groups=True,
    )
    objs = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    for o in objs:
        o.name = f"{name}:{o.name}"
        o.rotation_euler.z += math.radians(-rot)  # plan CW == Blender CW (negative)
        o.location = plan_to_world(*move)
        mat = pick_material(o)
        o.data.materials.clear()
        o.data.materials.append(mat)
    return objs


def add_furniture(floor):
    objs = []
    for name, x0, y0, x1, y1, h, colour in FURNITURE.get(floor, []):
        h = min(h, CUT_HEIGHT - 2)  # tall pieces end just under the wall cut
        size = Vector(((x1 - x0) / 100, (y1 - y0) / 100, h / 100))
        centre = plan_to_world((x0 + x1) / 2, (y0 + y1) / 2, h / 2)
        bpy.ops.mesh.primitive_cube_add(size=1, location=centre)
        box = bpy.context.active_object
        box.name = f"furniture:{name}"
        box.scale = size
        bevel = box.modifiers.new("bevel", "BEVEL")  # soft edges read better
        bevel.width = 0.015
        bevel.segments = 2
        bevel.affect = "EDGES"
        box.data.materials.append(material(colour, MAT_COLORS[colour]))
        objs.append(box)
    return objs


def cut_object(obj, height_m, cap_mat):
    """Remove geometry above height_m and cap the cut with a dark fill."""
    bpy.context.view_layer.update()
    mw = obj.matrix_world
    if max((mw @ v.co).z for v in obj.data.vertices) <= height_m + 1e-4:
        return
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.transform(mw)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    res = bmesh.ops.bisect_plane(
        bm, geom=geom, plane_co=(0, 0, height_m), plane_no=(0, 0, 1), clear_outer=True
    )
    cut_edges = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
    if cut_edges:
        if cap_mat.name not in me.materials:
            me.materials.append(cap_mat)
        cap_index = list(me.materials).index(cap_mat)
        filled = bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=True, edges=cut_edges)
        for f in filled["geom"]:
            if isinstance(f, bmesh.types.BMFace):
                f.material_index = cap_index
    bm.transform(mw.inverted())
    bm.to_mesh(me)
    bm.free()


def add_lamp(key, cfg):
    x, y, z = cfg["pos"]
    data = bpy.data.lights.new(f"lamp_{key}", "POINT")
    data.color = LAMP_COLOR
    data.energy = cfg["power"]
    data.shadow_soft_size = 0.15
    lamp = bpy.data.objects.new(f"lamp_{key}", data)
    lamp.location = plan_to_world(x, y, z)
    bpy.context.scene.collection.objects.link(lamp)
    return lamp


def set_world(strength, color):
    nodes = bpy.context.scene.world.node_tree.nodes
    bg = nodes["Background"]
    bg.inputs["Color"].default_value = (*color, 1)
    bg.inputs["Strength"].default_value = strength


def add_sun():
    data = bpy.data.lights.new("sun", "SUN")
    data.energy = 3.0
    data.angle = math.radians(8)
    sun = bpy.data.objects.new("sun", data)
    sun.rotation_euler = (math.radians(40), math.radians(15), math.radians(30))
    bpy.context.scene.collection.objects.link(sun)
    return sun


def frame_camera(objs, width_px, rot_deg):
    cam_data = bpy.data.cameras.new("cam")
    cam_data.type = "ORTHO"
    cam = bpy.data.objects.new("cam", cam_data)
    cam.rotation_euler = tuple(math.radians(a) for a in rot_deg)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    bpy.context.view_layer.update()

    rot = cam.matrix_world.to_3x3()
    inv = rot.inverted()
    pts = [inv @ (o.matrix_world @ Vector(c)) for o in objs for c in o.bound_box]
    xs, ys, zs = [p.x for p in pts], [p.y for p in pts], [p.z for p in pts]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    centre = Vector(((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, max(zs) + 20))
    cam.location = rot @ centre
    margin = 1.06
    cam_data.ortho_scale = max(w, h) * margin
    cam_data.clip_end = 200
    scene = bpy.context.scene
    scene.render.resolution_x = width_px
    scene.render.resolution_y = max(2, int(round(width_px * h / w)))
    scene.render.resolution_percentage = 100
    if h > w:  # ortho_scale applies to the longer side
        scene.render.resolution_y = width_px
        scene.render.resolution_x = max(2, int(round(width_px * w / h)))
    bpy.context.view_layer.update()
    return cam


def to_percent(cam, world_co):
    from bpy_extras.object_utils import world_to_camera_view

    v = world_to_camera_view(bpy.context.scene, cam, world_co)
    return {"left": round(v.x * 100, 1), "top": round((1 - v.y) * 100, 1)}


def render(path):
    bpy.context.scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    print("wrote", path)


# --------------------------------------------------------------------------- main
def render_floor(floor, args, positions):
    scene = reset_scene()
    scene.cycles.samples = args.samples
    cap = material("cap", MAT_COLORS["cap"])

    objs = []
    for room, cfg in FLOORS[floor].items():
        objs += import_room(room, cfg["rot"], cfg["move"])
    for o in objs:
        cut_object(o, CUT_HEIGHT / 100, cap)
    add_furniture(floor)

    layout = CAMERAS["mobile" if args.mobile else "desktop"]
    name = floor + layout["suffix"]  # e.g. UG or UG_m
    cam = frame_camera(objs, args.width, layout["rot"])
    lamps = {k: add_lamp(k, c) for k, c in LIGHTS.items() if c["floor"] == floor}

    def lamps_on(keys):
        for k, lamp in lamps.items():
            lamp.hide_render = k not in keys

    OUT.mkdir(parents=True, exist_ok=True)

    # day: sun + bright sky, lamps off
    sun = add_sun()
    set_world(0.6, (0.85, 0.9, 1.0))
    lamps_on(set())
    render(OUT / f"{name}_day.webp")

    # night base: faint blue moonlight, lamps off
    sun.hide_render = True
    set_world(0.15, (0.35, 0.45, 0.8))
    render(OUT / f"{name}_night.webp")

    # one image per lamp, same night ambient -> blended with "lighten" in HA
    for key in lamps:
        lamps_on({key})
        render(OUT / f"{name}_{key}.webp")

    positions[name] = {
        "image_size": [scene.render.resolution_x, scene.render.resolution_y],
        "lights": {
            k: to_percent(cam, plan_to_world(*LIGHTS[k]["pos"][:2], ICON_HEIGHT))
            for k in lamps
        },
        "rooms": {
            k: to_percent(cam, plan_to_world(*c["pos"], LABEL_HEIGHT))
            for k, c in ROOMS.items()
            if c["floor"] == floor
        },
        "stairs": to_percent(cam, plan_to_world(*STAIRS[floor], ICON_HEIGHT)),
        "covers": {
            k: to_percent(cam, plan_to_world(*c["pos"], ICON_HEIGHT))
            for k, c in COVERS.items()
            if c["floor"] == floor
        },
    }


def write_transparent_placeholder():
    """1x1 transparent image shown by picture-elements while a lamp is off."""
    img = bpy.data.images.new("transparent", 1, 1, alpha=True)
    img.pixels = [0.0, 0.0, 0.0, 0.0]
    img.filepath_raw = str(OUT / "transparent.webp")
    img.file_format = "WEBP"
    img.save()


def main():
    args = parse_args()
    positions = json.loads(POSITIONS.read_text()) if POSITIONS.exists() else {}
    for floor in [args.floor] if args.floor else FLOORS:
        render_floor(floor, args, positions)
    write_transparent_placeholder()
    POSITIONS.write_text(json.dumps(positions, indent=2))
    print(json.dumps(positions, indent=2))


if __name__ == "__main__":
    main()
