"""Build the 3D-printable battery door that holds the dongle and its battery.

    .venv/bin/python case/make_case.py

Everything stays inside the outline of the original battery door. The door has two
raised compartments side by side: a tall one for the XIAO ESP32S3 Sense (its camera
looks out through the lid) and a low one for a flat EEMB 402535 LiPo.

Writes four STL files to case/stl/:

  fit_test.stl       Just the door plate. Print this first (about 10 minutes) and
                     check it fits the calculator before printing the rest.
  door_body.stl      The door with both compartments.
  lid_camera.stl     Closes the XIAO compartment; has the camera window.
  lid_battery.stl    Closes the battery compartment.

Every size is in millimeters. The DOOR_ values are estimates: measure your own
battery door with calipers and change them before printing (see case/README.md).

Axes: X runs across the calculator, Y runs along it (+Y points toward the screen
and the USB port), Z points out of the back of the calculator.
"""

import struct
from pathlib import Path

import numpy as np
from manifold3d import CrossSection, Manifold

# ---- measure these on your calculator's battery door ------------------------
DOOR_WIDTH = 62.0         # across the calculator (X)
DOOR_LENGTH = 52.0        # along the calculator (Y)
DOOR_THICKNESS = 1.6      # the flat part of the door
DOOR_CORNER_RADIUS = 2.0
EDGE_MARGIN = 1.5         # keep compartments this far inside the door edge
TAB_WIDTH = 20.0          # tongue on the top edge that slides under the case
TAB_LENGTH = 3.0          # how far it sticks out past the door edge
TAB_THICKNESS = 0.9
SCREW_FROM_BOTTOM = 4.0   # center of the screw hole, measured from the bottom edge
SCREW_X = 0.0             # 0 = centered left to right
SCREW_HOLE = 2.2          # fits the original screw
SCREW_HEAD = 4.6          # counterbore for the screw head

# ---- the XIAO ESP32S3 Sense -------------------------------------------------
BOARD_WIDTH = 17.8        # X
BOARD_LENGTH = 21.0       # Y; the USB-C port faces +Y
BOARD_HEIGHT = 15.0       # with the camera board stacked on, to the top of the lens
LENS_FROM_CENTER = 0.0    # where the lens sits along Y, from the board's center

# ---- the battery: EEMB 402535, 3.7 V 320 mAh ----------------------------------
BATTERY_WIDTH = 25.5      # X
BATTERY_LENGTH = 36.0     # Y, including the protection circuit at the wire end
BATTERY_THICKNESS = 4.3

# ---- walls and lids -----------------------------------------------------------
CLEARANCE = 0.3           # gap around the board and the battery on each side
WALL = 1.2
USB_OPENING_WIDTH = 12.5  # fits a USB-C plug with its plastic overmold
USB_OPENING_HEIGHT = 7.5
WIRE_SLOT = 4.0           # passage between the compartments for the battery wires
LENS_WINDOW = 10.0        # diameter; generous so the lens doesn't need to be exact
LID_THICKNESS = 1.2
LID_LIP = 1.6             # how far each lid's lip reaches into its compartment
LID_FIT = 0.15            # gap between a lip and the walls

SEGMENTS = 64
OUT = Path(__file__).resolve().parent / "stl"


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


# Compartment sizes. The XIAO compartment is on the left (-X), the battery
# compartment on the right, sharing one wall, both against the top (+Y) edge.
XIAO_W = BOARD_WIDTH + 2 * CLEARANCE
XIAO_L = BOARD_LENGTH + 2 * CLEARANCE
XIAO_H = BOARD_HEIGHT + 0.3 + LID_LIP  # the lid's lip stays above the board
BATT_W = BATTERY_WIDTH + 2 * CLEARANCE
BATT_L = BATTERY_LENGTH + 2 * CLEARANCE
BATT_H = BATTERY_THICKNESS + 0.3 + LID_LIP

TOTAL_W = XIAO_W + BATT_W + 3 * WALL
TOP_Y = DOOR_LENGTH / 2 - EDGE_MARGIN
LEFT_X = -TOTAL_W / 2
SHARED_X = LEFT_X + WALL + XIAO_W          # left face of the shared wall
BATT_X = SHARED_X + WALL                   # left face of the battery cavity
RIGHT_X = BATT_X + BATT_W + WALL

XIAO_CX = LEFT_X + WALL + XIAO_W / 2
XIAO_CY = TOP_Y - WALL - XIAO_L / 2
BATT_CX = BATT_X + BATT_W / 2
BATT_CY = TOP_Y - WALL - BATT_L / 2

SCREW_Y = -DOOR_LENGTH / 2 + SCREW_FROM_BOTTOM


def check_fit():
    problems = []
    if TOTAL_W > DOOR_WIDTH - 2 * EDGE_MARGIN:
        problems.append(f"the compartments are {TOTAL_W:.1f} mm wide but the door only has "
                        f"{DOOR_WIDTH - 2 * EDGE_MARGIN:.1f} mm")
    length = max(XIAO_L, BATT_L) + 2 * WALL
    if length > DOOR_LENGTH - 2 * EDGE_MARGIN:
        problems.append(f"the battery compartment is {length:.1f} mm long but the door only has "
                        f"{DOOR_LENGTH - 2 * EDGE_MARGIN:.1f} mm")
    bottom = TOP_Y - length
    if SCREW_Y + SCREW_HEAD / 2 > bottom and LEFT_X < SCREW_X + SCREW_HEAD / 2 and SCREW_X - SCREW_HEAD / 2 < RIGHT_X:
        problems.append("the compartments would cover the screw")
    if problems:
        raise SystemExit("Doesn't fit: " + "; ".join(problems) +
                         ". Check the DOOR_ measurements, or pick a smaller battery.")


def door_plate():
    plate = box(DOOR_WIDTH, DOOR_LENGTH, DOOR_THICKNESS, DOOR_CORNER_RADIUS)
    tab = cube(-TAB_WIDTH / 2, TAB_WIDTH / 2, DOOR_LENGTH / 2 - 1, DOOR_LENGTH / 2 + TAB_LENGTH, 0, TAB_THICKNESS)
    hole = cylinder(SCREW_HOLE, -1, DOOR_THICKNESS + 1, SCREW_X, SCREW_Y)
    head = cylinder(SCREW_HEAD, DOOR_THICKNESS / 2, DOOR_THICKNESS + 1, SCREW_X, SCREW_Y)
    return plate + tab - hole - head


def door_body():
    z0 = DOOR_THICKNESS
    xiao_outer = box(XIAO_W + 2 * WALL, XIAO_L + 2 * WALL, z0 + XIAO_H, 2.0).translate((XIAO_CX, XIAO_CY, 0))
    batt_outer = box(BATT_W + 2 * WALL, BATT_L + 2 * WALL, z0 + BATT_H, 2.0).translate((BATT_CX, BATT_CY, 0))
    xiao_cavity = box(XIAO_W, XIAO_L, XIAO_H + 1, 0.6).translate((XIAO_CX, XIAO_CY, z0))
    batt_cavity = box(BATT_W, BATT_L, BATT_H + 1, 0.6).translate((BATT_CX, BATT_CY, z0))

    # USB-C opening in the XIAO compartment's top (+Y) wall, from the floor up.
    usb = cube(XIAO_CX - USB_OPENING_WIDTH / 2, XIAO_CX + USB_OPENING_WIDTH / 2,
               TOP_Y - WALL - 1, TOP_Y + 1, z0, z0 + USB_OPENING_HEIGHT)
    # Battery wires pass through the shared wall at floor level, near the top end.
    wires = cube(SHARED_X - 1, BATT_X + 1, TOP_Y - WALL - 2 - WIRE_SLOT, TOP_Y - WALL - 2, z0, z0 + 3)
    # Vent slots on the outer side of the XIAO compartment; Wi-Fi makes it warm.
    vents = Manifold()
    for i in range(3):
        y = XIAO_CY - 5 + i * 5
        vents += cube(LEFT_X - 1, LEFT_X + WALL + 1, y - 0.6, y + 0.6, z0 + 5, z0 + XIAO_H - LID_LIP - 1.5)

    shell = (xiao_outer + batt_outer) - xiao_cavity - batt_cavity - usb - wires - vents
    return door_plate() + shell


def make_lid(x0, x1, y0, y1, cavity_w, cavity_l, cavity_cx, cavity_cy, window=None):
    """A lid covering [x0, x1] x [y0, y1], printed upside down: outer face on the
    bed (z = 0) and the lip pointing up."""
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    top = box(x1 - x0, y1 - y0, LID_THICKNESS, 1.5)
    lip_w, lip_l = cavity_w - 2 * LID_FIT, cavity_l - 2 * LID_FIT
    lip = box(lip_w, lip_l, LID_LIP, 0.5) - box(lip_w - 2.4, lip_l - 2.4, LID_LIP + 2, 0.3).translate((0, 0, -1))
    lid = top + lip.translate((cavity_cx - cx, cavity_cy - cy, LID_THICKNESS))
    if window is not None:
        lid -= cylinder(LENS_WINDOW, -1, LID_THICKNESS + LID_LIP + 1, window[0] - cx, window[1] - cy)
    # A small notch on the top (+Y) edge shows which way round the lid goes.
    lid -= cube(-1.5, 1.5, (y1 - y0) / 2 - 1, (y1 - y0) / 2 + 1, -1, 0.5)
    # Mirror in X because it prints upside down.
    return lid.mirror((1, 0, 0))


def lid_camera():
    return make_lid(LEFT_X, SHARED_X + WALL, TOP_Y - XIAO_L - 2 * WALL, TOP_Y,
                    XIAO_W, XIAO_L, XIAO_CX, XIAO_CY, window=(XIAO_CX, XIAO_CY + LENS_FROM_CENTER))


def lid_battery():
    # The shared wall belongs to the taller XIAO compartment, so this lid starts after it.
    return make_lid(BATT_X, RIGHT_X, TOP_Y - BATT_L - 2 * WALL, TOP_Y, BATT_W, BATT_L, BATT_CX, BATT_CY)


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
    lo, hi = manifold.bounding_box()[:3], manifold.bounding_box()[3:]
    size = " x ".join(f"{h - l:.1f}" for l, h in zip(lo, hi))
    print(f"{path.name:20s} {size} mm, {manifold.volume() / 1000:.1f} cm^3")


def main():
    OUT.mkdir(exist_ok=True)
    check_fit()
    parts = {"fit_test.stl": door_plate(), "door_body.stl": door_body(),
             "lid_camera.stl": lid_camera(), "lid_battery.stl": lid_battery()}
    for name, part in parts.items():
        if part.status().name != "NoError" or part.is_empty():
            raise SystemExit(f"{name}: geometry error {part.status()}")
        write_stl(part, OUT / name)


if __name__ == "__main__":
    main()
