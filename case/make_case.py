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
MINI_BOARD_HEIGHT = 4.5   # board plus the USB-C port and shield on top (W11: 4.5 mm)
MINI_FLOOR = 1.2
MINI_TAPE = 0.5           # foam tape between the battery and the board
# The no-camera box holds the Meshnology W11 main board (camera board left off).
# From Meshnology's drawing: 18.00 x 23.50 mm, 24.54 mm with the USB-C, 4.5 mm tall.
MINI_BOARD_WIDTH = 18.0
MINI_BOARD_LENGTH = 24.54
# Power switch on the side: an SS12D00-style mini slide switch, wired between the
# battery's red wire and the board's B+ pad. It lies with its top (the lever side)
# against the inside of the +X wall, lever out through a slot.
SWITCH_LENGTH = 8.6       # body, along the wall
SWITCH_WIDTH = 3.6        # body, top to bottom of the box
SWITCH_DEPTH = 3.5        # body, from the wall inward (the pins stick out further)
SWITCH_PINS = 3.0         # room for the pins and wires behind the body
SWITCH_LEVER = 1.5        # lever cross-section
SWITCH_TRAVEL = 2.0       # how far the lever slides

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
# tape), USB-C toward the -X side. Guide rails hanging from the cover keep the
# board from sliding.
MINI_CAVITY_W = BATTERY_WIDTH + 2 * CLEARANCE
MINI_CAVITY_L = BATTERY_LENGTH + 2 * CLEARANCE
MINI_INNER_W = MINI_CAVITY_W + 2 * LIP_WALL + 2 * LIP_FIT
MINI_INNER_L = MINI_CAVITY_L + 2 * LIP_WALL + 2 * LIP_FIT
MINI_W = MINI_INNER_W + 2 * COVER_WALL
MINI_L = MINI_INNER_L + 2 * COVER_WALL
MINI_BOARD_Z = BATTERY_THICKNESS + MINI_TAPE         # bottom of the board, above the floor
MINI_INNER_H = MINI_BOARD_Z + MINI_BOARD_HEIGHT + CLEARANCE
# The board lies crosswise at the +Y end, USB-C facing the -X wall, so the cable
# comes out of a long side. The switch is on the other long side (+X).
MINI_BOARD_CX = -MINI_CAVITY_W / 2 + MINI_BOARD_LENGTH / 2 + CLEARANCE
MINI_BOARD_CY = MINI_CAVITY_L / 2 - MINI_BOARD_WIDTH / 2 - CLEARANCE
MINI_USB_X = MINI_BOARD_CX - MINI_BOARD_LENGTH / 2  # face of the USB-C port
# The switch sits at the end away from the USB-C, above the battery, where the
# board doesn't reach.
SWITCH_CY = -MINI_CAVITY_L / 2 + 0.8 + SWITCH_LENGTH / 2
SWITCH_CZ = BATTERY_THICKNESS + 0.3 + SWITCH_WIDTH / 2  # center height above the floor, just over the battery
SWITCH_WALL_X = MINI_INNER_W / 2                    # inside face of the +X wall
MINI_RADIUS = 3.0


def mini_base():
    base = box(MINI_W, MINI_L, MINI_FLOOR, MINI_RADIUS)
    r = rim(MINI_INNER_W, MINI_INNER_L, MINI_RADIUS)
    return base + r.translate((0, 0, MINI_FLOOR))


def mini_cover():
    c = shell(MINI_W, MINI_L, MINI_INNER_H, MINI_RADIUS)
    # USB-C notch in the -X wall (a long side), open at the top, so the plug's
    # plastic overmold can pass the wall and the plug seats fully.
    c -= cube(-MINI_W / 2 - 1, MINI_USB_X + 0.5,
              MINI_BOARD_CY - USB_OPENING_WIDTH / 2, MINI_BOARD_CY + USB_OPENING_WIDTH / 2,
              MINI_BOARD_Z - 1.5, MINI_INNER_H + COVER_TOP + 1)
    # Rails along each long edge of the board and a stop at its far (+X) end,
    # hanging from the top. They end above the battery.
    rail_z0 = MINI_BOARD_Z + 1.0
    x0, x1 = MINI_USB_X, MINI_BOARD_CX + MINI_BOARD_LENGTH / 2
    for sy in (-1, 1):
        y = MINI_BOARD_CY + sy * (MINI_BOARD_WIDTH / 2 + CLEARANCE + 0.6)
        c += cube(x0 + 2, x1 - 2, y - 0.6, y + 0.6, rail_z0, MINI_INNER_H + 0.01)
    c += cube(x1 + CLEARANCE, x1 + CLEARANCE + 1.2, MINI_BOARD_CY - 5, MINI_BOARD_CY + 5, rail_z0, MINI_INNER_H + 0.01)
    # Vents over the board.
    for i in range(3):
        y = MINI_BOARD_CY - 4 + i * 4
        c -= cube(MINI_BOARD_CX - 5, MINI_BOARD_CX + 5, y - 0.6, y + 0.6, MINI_INNER_H - 1, MINI_INNER_H + COVER_TOP + 1)
    # Power switch: a slot for the lever in the +X wall, and two blocks hanging from
    # the lid that hold the switch body against the wall at both ends.
    slot_l = SWITCH_LEVER + SWITCH_TRAVEL + 0.8
    slot_h = SWITCH_LEVER + 0.8
    c -= cube(SWITCH_WALL_X - 1, MINI_W / 2 + 1, SWITCH_CY - slot_l / 2, SWITCH_CY + slot_l / 2,
              SWITCH_CZ - slot_h / 2, SWITCH_CZ + slot_h / 2)
    for sy in (-1, 1):
        y_in = SWITCH_CY + sy * (SWITCH_LENGTH / 2 + 0.2)
        c += cube(SWITCH_WALL_X - SWITCH_DEPTH, SWITCH_WALL_X + 0.01, min(y_in, y_in + sy * 1.2), max(y_in, y_in + sy * 1.2),
                  SWITCH_CZ - SWITCH_WIDTH / 2, MINI_INNER_H + 0.01)
    return print_top_down(c, MINI_INNER_H + COVER_TOP)


# ---- camera box: Meshnology W11 with its camera board snapped on ---------------------
# A standalone box on the end of the USB cable, lens looking out of the top like a
# phone camera. Two layouts: "stacked" (battery under the board: small footprint,
# taller) and "side" (battery beside the board: flatter, wider).
# W11 main board from Meshnology's drawing: 18.00 x 23.50 mm, USB-C overhangs to
# 24.54 mm. The stack height with the camera board and lens is an ESTIMATE.
W11_WIDTH = 18.0
W11_LENGTH = 24.54        # including the USB-C overhang; USB-C faces +Y
W11_STACK_HEIGHT = 13.0   # main board + camera board + lens (estimate; measure it)
W11_USB_HEIGHT = 1.6      # USB-C center above the bottom of the main board (estimate)
CAM_LENS_FROM_CENTER = 0.0  # lens position along Y from the board's center (estimate)
CAM_LENS_WINDOW = 9.0
CAM_LENS_RING = 13.0
CAM_RADIUS = 4.0
CAM_STANDOFF = 2.2        # side layout: board height above the floor, on two ledges


class CameraBox:
    def __init__(self, layout):
        self.layout = layout
        bw, bl = W11_WIDTH + 2 * CLEARANCE, W11_LENGTH + 2 * CLEARANCE
        tw, tl = BATTERY_WIDTH + 2 * CLEARANCE, BATTERY_LENGTH + 2 * CLEARANCE
        if layout == "stacked":
            self.cavity_w, self.cavity_l = max(bw, tw), max(bl, tl)
            self.board_z = BATTERY_THICKNESS + MINI_TAPE
            self.board_cx = 0.0
            self.batt_cx, self.batt_cy = 0.0, 0.0
            self.inner_h = self.board_z + W11_STACK_HEIGHT + CLEARANCE
        else:
            self.cavity_w, self.cavity_l = bw + 2.0 + tw, max(bl, tl)
            self.board_z = CAM_STANDOFF  # on ledges, so a USB plug's body clears the floor
            self.board_cx = -self.cavity_w / 2 + bw / 2
            self.batt_cx, self.batt_cy = self.cavity_w / 2 - tw / 2, 0.0
            self.inner_h = max(CAM_STANDOFF + W11_STACK_HEIGHT, BATTERY_THICKNESS) + CLEARANCE
        self.board_cy = self.cavity_l / 2 - bl / 2  # USB-C end against the +Y wall
        self.inner_w = self.cavity_w + 2 * LIP_WALL + 2 * LIP_FIT
        self.inner_l = self.cavity_l + 2 * LIP_WALL + 2 * LIP_FIT
        self.w = self.inner_w + 2 * COVER_WALL
        self.l = self.inner_l + 2 * COVER_WALL
        self.h = MINI_FLOOR + self.inner_h + COVER_TOP

    def base(self):
        base = box(self.w, self.l, MINI_FLOOR, CAM_RADIUS)
        inside = rim(self.inner_w, self.inner_l, CAM_RADIUS)
        if self.layout == "side":
            # Low ribs keep the board and the battery in their own spots.
            bw, bl = W11_WIDTH + 2 * CLEARANCE, W11_LENGTH + 2 * CLEARANCE
            ribs = corner_ribs(self.board_cx, self.board_cy, bw, bl)
            ribs += corner_ribs(self.batt_cx, self.batt_cy, BATTERY_WIDTH + 2 * CLEARANCE,
                                BATTERY_LENGTH + 2 * CLEARANCE)
            # Keep the ribs inside the rim, clear of the cover's rounded corners.
            inside += ribs ^ box(self.cavity_w - 0.05, self.cavity_l - 0.05, 10, max(CAM_RADIUS - COVER_WALL - LIP_WALL, 0.5))
            inside -= cube(-self.cavity_w / 2 + bw - 1, -self.cavity_w / 2 + bw + 3, -100, 100, -1, 10)  # wire gap
            for sx in (-1, 1):  # ledges under the board's long edges
                x = self.board_cx + sx * (W11_WIDTH / 2 - 1.0)
                inside += cube(x - 1.0, x + 1.0, self.board_cy - W11_LENGTH / 2 + 2, self.board_cy + W11_LENGTH / 2 - 3,
                               0, CAM_STANDOFF)
        # Gap in the rim where the USB plug's body goes.
        inside -= cube(self.board_cx - USB_OPENING_WIDTH / 2, self.board_cx + USB_OPENING_WIDTH / 2,
                       self.cavity_l / 2 - 1, self.l, -1, 10)
        return base + inside.translate((0, 0, MINI_FLOOR - 0.01))  # sunk into the floor so it's one piece

    def cover(self):
        c = shell(self.w, self.l, self.inner_h, CAM_RADIUS)
        lens_y = self.board_cy + CAM_LENS_FROM_CENTER
        c -= cylinder(CAM_LENS_WINDOW, -1, self.inner_h + COVER_TOP + 1, self.board_cx, lens_y)
        c -= cylinder(CAM_LENS_RING, self.inner_h + COVER_TOP - 0.6, self.inner_h + COVER_TOP + 1, self.board_cx, lens_y)
        # USB-C notch at the board's end, open at the top so a plug's overmold clears it.
        usb_z = self.board_z + W11_USB_HEIGHT
        c -= cube(self.board_cx - USB_OPENING_WIDTH / 2, self.board_cx + USB_OPENING_WIDTH / 2,
                  self.board_cy + W11_LENGTH / 2 - 0.5, self.l / 2 + 1, usb_z - 3.5, usb_z + 4.0)
        # Rails down the board's long sides and a stop at its far end, hanging from
        # the top so the board can't shift (they end above the battery).
        rail_z0 = self.board_z + 2.0
        y0, y1 = self.board_cy - W11_LENGTH / 2, self.board_cy + W11_LENGTH / 2
        for sx in (-1, 1):
            x = self.board_cx + sx * (W11_WIDTH / 2 + CLEARANCE + 0.6)
            c += cube(x - 0.6, x + 0.6, y0 + 3, y1 - 3, rail_z0, self.inner_h + 0.01)
        c += cube(self.board_cx - 4, self.board_cx + 4, y0 - CLEARANCE - 1.2, y0 - CLEARANCE, rail_z0, self.inner_h + 0.01)
        # Vents beside the lens over the board.
        for i in range(3):
            x = self.board_cx + (-1 if self.layout == "side" else 1) * 0 + (i - 1) * 3.0
            y = self.board_cy - W11_LENGTH / 2 + 3.0
            c -= cube(x - 0.6, x + 0.6, y - 2.5, y + 2.5, self.inner_h - 1, self.inner_h + COVER_TOP + 1)
        return print_top_down(c.translate((0, 0, 0)), self.inner_h + COVER_TOP)


CAM_STACKED = CameraBox("stacked")
CAM_SIDE = CameraBox("side")


# ---- thin back plate: covers the whole back of the calculator -----------------------
# A thin plate that grips the calculator's long edges (like TI's slide cover) with a
# low, smooth raised area at the top that holds everything laid out flat: the W11
# board, its camera unfolded beside it on the ribbon, and the battery. The raised
# area is open on the calculator side, so the parts sit right against the
# calculator's back and no wall is wasted there. ESTIMATES: the calculator size
# (TI's published 193 x 87 mm), the edge grip, and the W11 height without the camera.
CALC_WIDTH = 86.9
CALC_LENGTH = 192.8
CALC_CORNER = 9.0
PLATE_THICKNESS = 1.6     # everywhere except the raised area
GRIP_DEPTH = 4.0          # how far the side walls reach down the calculator's sides
GRIP_LIP = 1.0            # the small inward lip that hooks the edge
W11_FLAT_HEIGHT = 7.0     # W11 + expansion board with the camera unfolded off it (estimate)
BACK_FOAM = 1.0           # foam pad under the board; lifts the USB-C so the plug clears the calculator
USB_CENTER = 2.6          # USB-C center above the bottom of the W11 board
PLUG_HEIGHT = 6.5         # a USB-C plug's plastic overmold, top to bottom
CAM_COLLAR = 3.0          # square collar under the roof that holds the camera up at the window
POD_TOP = 0.8             # roof thickness of the raised area (4 layers at 0.2 mm)
BACK_HEADROOM = 0.2       # space between the tallest part and the roof
BACK_LOW_EXTRA = 0.6      # over the battery: room for the antenna sticker and tape
POD_FROM_TOP = 6.0        # gap between the calculator's top edge and the raised area
POD_RADIUS = 3.0
POD_EDGE = 2.0            # wall around the parts
BACK_SWITCH_CZ = 3.0      # switch center height above the calculator's back; the lever clears the plate


class BackPlate:
    """Raised area layout, looking at the back with the calculator's top edge up:
    top row: W11 board (USB-C pointing at the top edge), camera beside it, power
    switch against the right wall; bottom row: the battery, lying across, with the
    Wi-Fi antenna stuck under the roof above it. The raised area steps down over the
    battery, which is much thinner than the board stack."""

    def __init__(self):
        bw, bl = W11_WIDTH + 2 * CLEARANCE, W11_LENGTH + 2 * CLEARANCE
        cam = CAMERA_SIZE + 2 * CLEARANCE
        tw, tl = BATTERY_LENGTH + 2 * CLEARANCE, BATTERY_WIDTH + 2 * CLEARANCE  # battery lies across
        self.inner_h = max(BACK_FOAM + W11_FLAT_HEIGHT, CAMERA_HEIGHT) + BACK_HEADROOM
        self.h = self.inner_h + POD_TOP
        self.low_inner = BATTERY_THICKNESS + BACK_LOW_EXTRA
        self.low_h = self.low_inner + POD_TOP
        self.tall_inner_l = bl + 1.0  # the board row
        sw_room = 1.0 + SWITCH_DEPTH + SWITCH_PINS
        row1_w = bw + 3.0 + cam + sw_room
        self.inner_w = max(row1_w, tw)
        self.inner_l = bl + 2.0 + tl
        self.w = self.inner_w + 2 * POD_EDGE
        self.l = self.inner_l + 2 * POD_EDGE
        self.cy = CALC_LENGTH / 2 - POD_FROM_TOP - self.l / 2
        top = self.cy + self.inner_l / 2
        left = -self.inner_w / 2
        self.row1_y = top - bl / 2
        self.board = (left + bw / 2, self.row1_y)
        self.cam = (left + bw + 3.0 + cam / 2, self.row1_y)
        self.batt = (0.0, top - bl - 2.0 - tl / 2)
        self.switch_wall = self.inner_w / 2
        self.switch = (self.switch_wall - SWITCH_DEPTH / 2, self.row1_y, BACK_SWITCH_CZ)
        self.usb_z = BACK_FOAM + USB_CENTER
        self.board_top_y = top - CLEARANCE  # the USB-C end of the board
        self.tall_cy = top - self.tall_inner_l / 2

    def body(self):
        plate = box(CALC_WIDTH, CALC_LENGTH, PLATE_THICKNESS, CALC_CORNER)
        # Side walls with a small inward lip, down both long edges.
        for sx in (-1, 1):
            x_out = sx * (CALC_WIDTH / 2 + 1.2)
            x_in = sx * CALC_WIDTH / 2
            wall = cube(min(x_out, x_in), max(x_out, x_in), -CALC_LENGTH / 2 + CALC_CORNER, CALC_LENGTH / 2 - CALC_CORNER,
                        -GRIP_DEPTH, PLATE_THICKNESS)
            lip = cube(min(x_in, x_in - sx * GRIP_LIP), max(x_in, x_in - sx * GRIP_LIP),
                       -CALC_LENGTH / 2 + CALC_CORNER, CALC_LENGTH / 2 - CALC_CORNER, -GRIP_DEPTH, -GRIP_DEPTH + 0.8)
            plate += wall + lip
        # The raised area: a smooth low hump, hollow and open toward the calculator.
        # Low over the battery, full height only over the board row.
        pod = pillow(self.w, self.l, self.low_h, POD_RADIUS).translate((0, self.cy, 0))
        pod += pillow(self.w, self.tall_inner_l + 2 * POD_EDGE, self.h, POD_RADIUS).translate((0, self.tall_cy, 0))
        pocket = box(self.inner_w, self.inner_l, self.low_inner + 1, 1.0).translate((0, self.cy, -1))
        pocket += box(self.inner_w, self.tall_inner_l, self.inner_h + 1, 1.0).translate((0, self.tall_cy, -1))
        body = plate + pod - pocket
        ih = self.inner_h
        cx, cy = self.cam
        bx, by = self.board
        cam = CAMERA_SIZE + 2 * CLEARANCE
        # Collar under the roof that the camera presses up into, so the lens sits in the window.
        collar = box(cam + 1.6, cam + 1.6, CAM_COLLAR, 1.0) - box(cam, cam, CAM_COLLAR + 2, 0.5).translate((0, 0, -1))
        body += collar.translate((cx, cy, ih - CAM_COLLAR))
        # Lens window with a recessed ring, over the camera.
        body -= cylinder(CAM_LENS_WINDOW, -1, self.h + 1, cx, cy)
        body -= cylinder(CAM_LENS_RING, self.h - 0.3, self.h + 1, cx, cy)
        # Short stubs beside the board's corners, hanging from the roof, so it can't
        # slide sideways. The middle is left open for the camera ribbon.
        bw, bl = W11_WIDTH + 2 * CLEARANCE, W11_LENGTH + 2 * CLEARANCE
        x_r = bx + bw / 2
        for y in (by - bl / 2 + 1.0, by + bl / 2 - 5.0):
            body += cube(x_r, x_r + 1.2, y, y + 4.0, BACK_FOAM + 1.5, ih + 0.01)
        # USB-C opening in the top wall: a closed window the plug's overmold fits through.
        z0, z1 = self.usb_z - PLUG_HEIGHT / 2 - 0.4, self.usb_z + PLUG_HEIGHT / 2 + 0.4
        body -= cube(bx - USB_OPENING_WIDTH / 2, bx + USB_OPENING_WIDTH / 2, by, self.cy + self.l / 2 + 1, -1, z1)
        # Channel through the plate so the plug and cable run flat to the top edge.
        body -= cube(bx - USB_OPENING_WIDTH / 2, bx + USB_OPENING_WIDTH / 2, by, CALC_LENGTH / 2 + 1, -1, PLATE_THICKNESS + 1)
        # Vents in the roof over the board, where the ESP32 warms up.
        for i in range(4):
            y = by - 6.0 + i * 4.0
            body -= cube(bx - 5.0, bx + 5.0, y - 0.6, y + 0.6, ih - 1, self.h + 1)
        # Power switch: lever slot through the right wall, two blocks that hold the body.
        sx, sy, sz = self.switch
        wx = self.switch_wall
        slot_l = SWITCH_LEVER + SWITCH_TRAVEL + 0.8
        slot_h = SWITCH_LEVER + 0.8
        body -= cube(wx - 1, self.w / 2 + 1, sy - slot_l / 2, sy + slot_l / 2, sz - slot_h / 2, sz + slot_h / 2)
        for d in (-1, 1):
            y_in = sy + d * (SWITCH_LENGTH / 2 + 0.2)
            body += cube(wx - SWITCH_DEPTH, wx + 0.01, min(y_in, y_in + d * 1.2), max(y_in, y_in + d * 1.2),
                         sz - SWITCH_WIDTH / 2, ih + 0.01)
        return body


BACK = BackPlate()


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
        "camera_box/stacked_base.stl": CAM_STACKED.base(),
        "camera_box/stacked_cover.stl": CAM_STACKED.cover(),
        "camera_box/side_base.stl": CAM_SIDE.base(),
        "camera_box/side_cover.stl": CAM_SIDE.cover(),
        "back_plate/back_plate.stl": BACK.body().translate((0, 0, GRIP_DEPTH)),  # calculator side down
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
