"""Build the 3D-printable cases for the TI-84 Plus CE dongle.

    .venv/bin/python case/make_case.py

Three cases. The two battery doors use the same smooth, low cover: one rounded
shell the size of the battery door with a round lens window. Inside, the XIAO
ESP32S3 Sense lies flat with its camera unfolded beside it (not stacked on top),
next to a flat LiPo. The door plate is the same thickness as the original, so it
sits flush with the calculator.

  stl/always_on/   Screw it on and leave it.
      door_base.stl     the door, with a rim the cover presses onto
      cover.stl         the smooth shell with the lens window

  stl/clip_on/     Screw the door on once; the dongle pod snaps on with magnets and
                   pulls straight off.
      door_magnets.stl  flat door with four low magnet bosses that locate the pod
      pod_base.stl      the pod's floor, with matching sockets and magnets
      cover.stl         the same smooth shell

  stl/mini/        No camera, no battery door: a small box for a plain XIAO ESP32S3
                   that hangs off the USB cable. Powered by the calculator.
      mini_base.stl, mini_cover.stl

  stl/fit_test.stl  Just the door plate. Print this first (about 10 minutes) and
                    check it fits before printing a door.

Every size is in millimeters. The DOOR_ values and the XIAO stack height are
estimates: measure yours and change them before printing (see case/README.md).

Axes: X runs across the calculator, Y runs along it (+Y points toward the screen
and the USB port), Z points out of the back of the calculator.
"""

import struct
from pathlib import Path

import numpy as np
from manifold3d import CrossSection, Manifold

# ---- the TI-84 Plus CE battery door ------------------------------------------
# Measured from a straight-on iFixit photo, scaled by the calculator's published
# 86.9 mm (3.42 in) width, so expect up to about 1 mm of error. Check with
# calipers or the fit test before printing a full case.
DOOR_WIDTH = 63.4         # across the calculator (X)
DOOR_LENGTH = 60.4        # along the calculator (Y)
DOOR_THICKNESS = 1.6      # the flat part of the door; keeps the door flush (estimate)
DOOR_CORNER_RADIUS = 3.8
EDGE_MARGIN = 1.0         # the cover stays this far inside the door edge
# Two captive Phillips screws at the top corners (the screen end).
SCREW_INSET = 6.6         # screw centers from the left and right edges
SCREW_FROM_TOP = 5.5      # screw centers from the top edge
SCREW_HOLE = 2.2          # fits the original screws
SCREW_HEAD = 4.6          # counterbore for the screw heads
# The bottom edge tucks under the case; the door lifts out from the screw end.
TAB_WIDTH = 20.0
TAB_LENGTH = 2.0          # how far the tongue sticks out past the bottom edge
TAB_THICKNESS = 0.9
# The calculator's two rubber feet sit in recesses near the door's bottom corners.
FOOT_DIAMETER = 7.2
FOOT_INSET = 6.3          # foot centers from the left and right edges
FOOT_FROM_BOTTOM = 7.8    # foot centers from the bottom edge
FOOT_RECESS = 0.8         # recess depth in the door
FOOT_HEIGHT = 2.0         # how far a foot stands up; the pod clears this

# ---- the XIAO ESP32S3 Sense, camera unfolded beside it -------------------------
BOARD_WIDTH = 17.8        # X
BOARD_LENGTH = 21.0       # Y; the USB-C port faces +Y
STACK_HEIGHT = 9.0        # XIAO + expansion board, without the camera on top (estimate)
CAMERA_SIZE = 8.5         # the square camera module
CAMERA_HEIGHT = 5.5       # module plus lens barrel
CAMERA_GAP = 3.0          # room for the folded ribbon between board and camera

# ---- the battery: EEMB 402535, 3.7 V 320 mAh ----------------------------------
BATTERY_WIDTH = 25.5      # X
BATTERY_LENGTH = 36.0     # Y, including the protection circuit at the wire end
BATTERY_THICKNESS = 4.3

# ---- cover ----------------------------------------------------------------------
CLEARANCE = 0.4           # around each part inside
COVER_WALL = 1.4
COVER_TOP = 1.4
COVER_RADIUS = 4.0        # rounding of the cover's corners and top edges
LIP_HEIGHT = 2.5          # rim on the base the cover presses over
LIP_WALL = 1.2
LIP_FIT = 0.15            # gap between the rim and the cover's inside wall
LOCATOR_HEIGHT = 1.5      # low ribs that keep the parts in place
LENS_WINDOW = 7.5         # hole over the lens
LENS_RING = 11.0          # shallow recessed ring around it, for looks
USB_OPENING_WIDTH = 12.5  # fits a USB-C plug with its plastic overmold

# ---- clip-on magnets: 6 x 2 mm N52 discs, four pairs ------------------------------
MAGNET_DIAMETER = 6.0
MAGNET_THICKNESS = 2.0
MAGNET_FIT = 0.15         # extra room in each pocket; a drop of glue holds them
BOSS_DIAMETER = 9.0       # bosses on the door that locate the pod
BOSS_HEIGHT = 1.4
BOSS_FIT = 0.2
MAGNET_INSET = 6.5        # boss centers from the cover's edges

# ---- mini: plain XIAO ESP32S3, no camera ------------------------------------------
MINI_BOARD_HEIGHT = 4.5   # board plus the USB-C port and shield on top
MINI_FLOOR = 1.2
MINI_TAPE = 0.5           # foam tape between the battery and the board

SEGMENTS = 64
OUT = Path(__file__).resolve().parent / "stl"


# ---- shapes -------------------------------------------------------------------

def rounded_rect(width, length, radius):
    radius = max(0.01, min(radius, width / 2 - 0.01, length / 2 - 0.01))
    corners = [
        CrossSection.circle(radius, SEGMENTS).translate((x, y))
        for x in (-width / 2 + radius, width / 2 - radius)
        for y in (-length / 2 + radius, length / 2 - radius)
    ]
    return CrossSection.batch_hull(corners)


def box(width, length, height, radius):
    return Manifold.extrude(rounded_rect(width, length, radius), height)


def cube(x0, x1, y0, y1, z0, z1):
    return Manifold.cube((x1 - x0, y1 - y0, z1 - z0)).translate((x0, y0, z0))


def cylinder(diameter, z0, z1, x=0.0, y=0.0):
    return Manifold.cylinder(z1 - z0, diameter / 2, diameter / 2, SEGMENTS).translate((x, y, z0))


def pillow(width, length, height, radius):
    """A box with a flat bottom and every top edge and corner rounded."""
    r = min(radius, height - 0.01, width / 2 - 0.01, length / 2 - 0.01)
    parts = []
    for x in (-width / 2 + r, width / 2 - r):
        for y in (-length / 2 + r, length / 2 - r):
            parts.append(Manifold.cylinder(height - r, r, r, SEGMENTS).translate((x, y, 0)))
            parts.append(Manifold.sphere(r, SEGMENTS).translate((x, y, height - r)))
    return Manifold.batch_hull(parts)


def shell(width, length, inner_h, radius):
    """Rounded cover, right way up, open at the bottom."""
    outer = pillow(width, length, inner_h + COVER_TOP, radius)
    inner = pillow(width - 2 * COVER_WALL, length - 2 * COVER_WALL, inner_h,
                   max(radius - COVER_WALL, 0.6)).translate((0, 0, -0.01))
    return outer - inner


def rim(inner_w, inner_l, radius):
    """The ring on a base that the cover presses over."""
    w, l = inner_w - 2 * LIP_FIT, inner_l - 2 * LIP_FIT
    r = max(radius - COVER_WALL, 0.6)
    return box(w, l, LIP_HEIGHT, r) - box(w - 2 * LIP_WALL, l - 2 * LIP_WALL, LIP_HEIGHT + 2,
                                          max(r - LIP_WALL, 0.3)).translate((0, 0, -1))


def print_top_down(part, height):
    """Flip a cover so its flat top is on the print bed."""
    return part.mirror((0, 0, 1)).translate((0, 0, height))


# ---- the door plate -----------------------------------------------------------

SCREW_Y = DOOR_LENGTH / 2 - SCREW_FROM_TOP
SCREWS = [(-DOOR_WIDTH / 2 + SCREW_INSET, SCREW_Y), (DOOR_WIDTH / 2 - SCREW_INSET, SCREW_Y)]
FOOT_Y = -DOOR_LENGTH / 2 + FOOT_FROM_BOTTOM
FEET = [(-DOOR_WIDTH / 2 + FOOT_INSET, FOOT_Y), (DOOR_WIDTH / 2 - FOOT_INSET, FOOT_Y)]


def door_plate():
    plate = box(DOOR_WIDTH, DOOR_LENGTH, DOOR_THICKNESS, DOOR_CORNER_RADIUS)
    plate += cube(-TAB_WIDTH / 2, TAB_WIDTH / 2, -DOOR_LENGTH / 2 - TAB_LENGTH, -DOOR_LENGTH / 2 + 1, 0, TAB_THICKNESS)
    for x, y in SCREWS:
        plate -= cylinder(SCREW_HOLE, -1, DOOR_THICKNESS + 1, x, y)
        plate -= cylinder(SCREW_HEAD, DOOR_THICKNESS / 2, DOOR_THICKNESS + 1, x, y)
    for x, y in FEET:
        plate -= cylinder(FOOT_DIAMETER + 0.3, DOOR_THICKNESS - FOOT_RECESS, DOOR_THICKNESS + 1, x, y)
    return plate


# ---- what goes inside the door cover ----------------------------------------------
# "Inside" coordinates: z = 0 is the floor the parts sit on.

COVER_W = DOOR_WIDTH - 2 * EDGE_MARGIN
COVER_L = DOOR_LENGTH - 2 * EDGE_MARGIN
INNER_W = COVER_W - 2 * COVER_WALL
INNER_L = COVER_L - 2 * COVER_WALL
INNER_H = max(STACK_HEIGHT, BATTERY_THICKNESS, CAMERA_HEIGHT) + CLEARANCE
COVER_H = INNER_H + COVER_TOP

# XIAO in the top-left corner (USB-C against the top wall), camera below it,
# battery on the right.
XIAO_W, XIAO_L = BOARD_WIDTH + 2 * CLEARANCE, BOARD_LENGTH + 2 * CLEARANCE
BATT_W, BATT_L = BATTERY_WIDTH + 2 * CLEARANCE, BATTERY_LENGTH + 2 * CLEARANCE
GAP = 2.0
GROUP_W = XIAO_W + GAP + BATT_W
XIAO_X0 = -GROUP_W / 2
XIAO_CX = XIAO_X0 + XIAO_W / 2
PARTS_TOP_Y = min(INNER_L / 2 - LIP_WALL, SCREW_Y - SCREW_HEAD / 2 - 0.8)
XIAO_CY = PARTS_TOP_Y - XIAO_L / 2
CAM_CX = XIAO_CX
CAM_CY = XIAO_CY - XIAO_L / 2 - CAMERA_GAP - CAMERA_SIZE / 2
BATT_CX = XIAO_X0 + XIAO_W + GAP + BATT_W / 2
BATT_CY = PARTS_TOP_Y - BATT_L / 2


def usb_cut(z0, z1, inner_l, outer_l, cx, reach=3.0):
    return cube(cx - USB_OPENING_WIDTH / 2, cx + USB_OPENING_WIDTH / 2, inner_l / 2 - reach, outer_l / 2 + 1, z0, z1)


USB_REACH = INNER_L / 2 - PARTS_TOP_Y + 1.0  # the plug reaches in past the screw heads


def cover():
    c = shell(COVER_W, COVER_L, INNER_H, COVER_RADIUS)
    # Lens window with a shallow recessed ring around it.
    c -= cylinder(LENS_WINDOW, -1, COVER_H + 1, CAM_CX, CAM_CY)
    c -= cylinder(LENS_RING, COVER_H - 0.6, COVER_H + 1, CAM_CX, CAM_CY)
    # USB-C opening in the top wall, up the height of the board stack.
    c -= usb_cut(-1, min(STACK_HEIGHT, INNER_H - 1), INNER_L, COVER_L, XIAO_CX)  # through the wall only
    # Vent slots over the XIAO; Wi-Fi makes it warm.
    for i in range(3):
        x = XIAO_CX - 4 + i * 4
        c -= cube(x - 0.6, x + 0.6, XIAO_CY - 5, XIAO_CY + 5, INNER_H - 1, COVER_H + 1)
    return print_top_down(c, COVER_H)


def corner_ribs(cx, cy, w, l):
    ribs = Manifold()
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = cx + sx * (w / 2 + 0.6), cy + sy * (l / 2 + 0.6)
            ribs += cube(min(x, x - sx * 5), max(x, x - sx * 5), y - 0.6, y + 0.6, 0, LOCATOR_HEIGHT)
            ribs += cube(x - 0.6, x + 0.6, min(y, y - sy * 5), max(y, y - sy * 5), 0, LOCATOR_HEIGHT)
    return ribs


def inside_features():
    """Rim, low ribs around the XIAO and battery, and the camera pedestal."""
    r = rim(INNER_W, INNER_L, COVER_RADIUS) - usb_cut(-1, LIP_HEIGHT + 1, INNER_L, COVER_L, XIAO_CX, USB_REACH)
    ribs = corner_ribs(XIAO_CX, XIAO_CY, XIAO_W, XIAO_L) + corner_ribs(BATT_CX, BATT_CY, BATT_W, BATT_L)
    # The camera sits on a pedestal so the lens reaches the window, in a shallow pocket.
    pedestal_h = INNER_H - CAMERA_HEIGHT - 0.2
    pocket = CAMERA_SIZE + 0.4
    pedestal = box(pocket + 2.4, pocket + 2.4, pedestal_h + 1.0, 0.8)
    pedestal -= box(pocket, pocket, 2, 0.3).translate((0, 0, pedestal_h))
    features = r + ribs + pedestal.translate((CAM_CX, CAM_CY, 0))
    for x, y in SCREWS:  # keep the screw heads reachable with a screwdriver
        features -= cylinder(SCREW_HEAD + 1.5, -1, INNER_H, x, y)
    return features


# ---- always-on door ----------------------------------------------------------------

def always_on_base():
    return door_plate() + inside_features().translate((0, 0, DOOR_THICKNESS))


# ---- clip-on door and pod ------------------------------------------------------------

MAGNET_POCKET = MAGNET_DIAMETER + 2 * MAGNET_FIT
MAGNET_DEPTH = MAGNET_THICKNESS + 0.1
SOCKET_DEPTH = BOSS_HEIGHT + BOSS_FIT
POD_FLOOR = SOCKET_DEPTH + MAGNET_DEPTH + 0.6


def magnet_spots():
    # Middle of each edge: the corners are taken by the screws (top) and feet (bottom).
    return [(0, COVER_L / 2 - MAGNET_INSET), (0, -COVER_L / 2 + MAGNET_INSET),
            (-COVER_W / 2 + MAGNET_INSET, 0), (COVER_W / 2 - MAGNET_INSET, 0)]


def clip_door():
    door = door_plate()
    top = DOOR_THICKNESS + BOSS_HEIGHT
    for x, y in magnet_spots():
        door += cylinder(BOSS_DIAMETER, DOOR_THICKNESS - 0.01, top, x, y)
    for x, y in magnet_spots():
        door -= cylinder(MAGNET_POCKET, top - MAGNET_DEPTH, top + 1, x, y)
    return door


def pod_base():
    """The pod's floor, printed bottom-down. The cover's edge lands on it."""
    floor = box(COVER_W, COVER_L, POD_FLOOR, COVER_RADIUS)
    for x, y in magnet_spots():
        floor -= cylinder(BOSS_DIAMETER + 2 * BOSS_FIT, -1, SOCKET_DEPTH, x, y)
        floor -= cylinder(MAGNET_POCKET, SOCKET_DEPTH - 0.01, SOCKET_DEPTH + MAGNET_DEPTH, x, y)
    for x, y in FEET:
        floor -= cylinder(FOOT_DIAMETER + 1.0, -1, FOOT_HEIGHT - FOOT_RECESS + 0.4, x, y)
    for x, y in SCREWS:
        floor -= cylinder(SCREW_HEAD + 1.0, -1, 1.0, x, y)
    return floor + inside_features().translate((0, 0, POD_FLOOR))


# ---- mini box: plain XIAO ESP32S3, no camera -------------------------------------------

# The battery lies flat on the floor; the board lies on it (on a layer of foam
# tape), USB-C at the +Y end. Guide rails hanging from the cover keep the board
# from sliding.
MINI_CAVITY_W = BATTERY_WIDTH + 2 * CLEARANCE
MINI_CAVITY_L = BATTERY_LENGTH + 2 * CLEARANCE
MINI_INNER_W = MINI_CAVITY_W + 2 * LIP_WALL + 2 * LIP_FIT
MINI_INNER_L = MINI_CAVITY_L + 2 * LIP_WALL + 2 * LIP_FIT
MINI_W = MINI_INNER_W + 2 * COVER_WALL
MINI_L = MINI_INNER_L + 2 * COVER_WALL
MINI_BOARD_Z = BATTERY_THICKNESS + MINI_TAPE         # bottom of the board, above the floor
MINI_INNER_H = MINI_BOARD_Z + MINI_BOARD_HEIGHT + CLEARANCE
MINI_BOARD_CY = MINI_CAVITY_L / 2 - BOARD_LENGTH / 2 - CLEARANCE
MINI_RADIUS = 3.0


def mini_base():
    base = box(MINI_W, MINI_L, MINI_FLOOR, MINI_RADIUS)
    r = rim(MINI_INNER_W, MINI_INNER_L, MINI_RADIUS)
    return base + r.translate((0, 0, MINI_FLOOR))


def mini_cover():
    c = shell(MINI_W, MINI_L, MINI_INNER_H, MINI_RADIUS)
    # USB-C notch in the +Y wall, open at the top, so the plug's plastic overmold
    # can pass the wall and the plug seats fully.
    c -= cube(-USB_OPENING_WIDTH / 2, USB_OPENING_WIDTH / 2, MINI_BOARD_CY + BOARD_LENGTH / 2 - 0.5, MINI_L / 2 + 1,
              MINI_BOARD_Z - 1.5, MINI_INNER_H + COVER_TOP + 1)
    # Rails down each long side of the board and a stop at its far end, hanging
    # from the top. They end above the battery.
    rail_z0 = MINI_BOARD_Z + 1.0
    y0, y1 = MINI_BOARD_CY - BOARD_LENGTH / 2, MINI_BOARD_CY + BOARD_LENGTH / 2
    for sx in (-1, 1):
        x = sx * (BOARD_WIDTH / 2 + CLEARANCE + 0.6)
        c += cube(x - 0.6, x + 0.6, y0 + 2, y1 - 2, rail_z0, MINI_INNER_H + 0.01)
    c += cube(-5, 5, y0 - CLEARANCE - 1.2, y0 - CLEARANCE, rail_z0, MINI_INNER_H + 0.01)
    # Vents over the board.
    for i in range(3):
        x = -4 + i * 4
        c -= cube(x - 0.6, x + 0.6, MINI_BOARD_CY - 5, MINI_BOARD_CY + 5, MINI_INNER_H - 1, MINI_INNER_H + COVER_TOP + 1)
    return print_top_down(c, MINI_INNER_H + COVER_TOP)


# ---- checks ---------------------------------------------------------------------

def check_fit():
    problems = []
    room_w = INNER_W - 2 * LIP_WALL
    if GROUP_W > room_w:
        problems.append(f"the XIAO and battery need {GROUP_W:.1f} mm across, the cover has {room_w:.1f} mm")
    need_l = max(XIAO_L + CAMERA_GAP + CAMERA_SIZE + 1.2, BATT_L)
    room_l = PARTS_TOP_Y + INNER_L / 2 - LIP_WALL
    if need_l > room_l:
        problems.append(f"the parts need {need_l:.1f} mm of length, the cover has {room_l:.1f} mm")
    for x, y in magnet_spots():
        for sx, sy in SCREWS + FEET:
            if (x - sx) ** 2 + (y - sy) ** 2 < ((BOSS_DIAMETER + FOOT_DIAMETER) / 2 + 1) ** 2:
                problems.append("a magnet boss would hit a screw or foot; change MAGNET_INSET")
    for fx, fy in FEET:
        if fy + FOOT_DIAMETER / 2 + 1.5 > min(CAM_CY - CAMERA_SIZE / 2 - 1.2, BATT_CY - BATT_L / 2) and \
                (abs(fx - BATT_CX) < BATT_W / 2 + 4 or abs(fx - CAM_CX) < CAMERA_SIZE / 2 + 4):
            problems.append("the parts reach down over a rubber foot")
    if problems:
        raise SystemExit("Doesn't fit: " + "; ".join(problems) +
                         ". Check the DOOR_ measurements, or pick a smaller battery.")


# ---- output ---------------------------------------------------------------------

def write_stl(manifold, path):
    mesh = manifold.to_mesh()
    verts = np.asarray(mesh.vert_properties)[:, :3].astype(np.float32)
    tris = np.asarray(mesh.tri_verts)
    a, b, c = verts[tris[:, 0]], verts[tris[:, 1]], verts[tris[:, 2]]
    normals = np.cross(b - a, c - a)
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = normals / np.where(lengths == 0, 1, lengths)
    with open(path, "wb") as f:
        f.write(b"ti84-claude dongle case".ljust(80, b" "))
        f.write(struct.pack("<I", len(tris)))
        record = np.zeros(len(tris), dtype=[("n", "<f4", 3), ("v", "<f4", 9), ("attr", "<u2")])
        record["n"] = normals
        record["v"] = np.hstack([a, b, c])
        f.write(record.tobytes())
    bb = manifold.bounding_box()
    size = " x ".join(f"{h - l:.1f}" for l, h in zip(bb[:3], bb[3:]))
    print(f"{str(path.relative_to(OUT)):28s} {size} mm")


def parts():
    return {
        "fit_test.stl": door_plate(),
        "always_on/door_base.stl": always_on_base(),
        "always_on/cover.stl": cover(),
        "clip_on/door_magnets.stl": clip_door(),
        "clip_on/pod_base.stl": pod_base(),
        "clip_on/cover.stl": cover(),
        "mini/mini_base.stl": mini_base(),
        "mini/mini_cover.stl": mini_cover(),
    }


def main():
    check_fit()
    for old in OUT.rglob("*.stl"):
        old.unlink()  # clear files from earlier layouts
    for name, part in parts().items():
        if part.status().name != "NoError" or part.is_empty() or len(part.decompose()) != 1:
            raise SystemExit(f"{name}: geometry problem ({part.status()}, {len(part.decompose())} pieces)")
        path = OUT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        write_stl(part, path)
    print(f"Always-on door: sticks out {COVER_H:.1f} mm from the calculator.")
    print(f"Clip-on door alone: {BOSS_HEIGHT:.1f} mm bosses; with the pod on: {POD_FLOOR + COVER_H:.1f} mm.")
    print(f"Mini box: {MINI_W:.1f} x {MINI_L:.1f} x {MINI_FLOOR + MINI_INNER_H + COVER_TOP:.1f} mm.")


if __name__ == "__main__":
    main()
