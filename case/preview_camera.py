"""Render case/preview_camera.png: both camera-box layouts, open and closed."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

import make_case as mc


def draw(ax, part, view, color):
    mesh = part.to_mesh()
    tris = np.asarray(mesh.vert_properties)[:, :3][np.asarray(mesh.tri_verts)]
    normals = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-9)
    facing = normals @ view > 0
    light = np.clip(normals[facing] @ view, 0.25, 1)
    base = np.array(matplotlib.colors.to_rgb(color))
    ax.add_collection3d(Poly3DCollection(tris[facing], facecolors=np.outer(light, base) * 0.8 + 0.12, edgecolor="none"))


def contents(c):
    z = mc.MINI_FLOOR
    bz = z + c.board_z
    parts = [
        (mc.cube(c.batt_cx - mc.BATTERY_WIDTH / 2, c.batt_cx + mc.BATTERY_WIDTH / 2, c.batt_cy - mc.BATTERY_LENGTH / 2,
                 c.batt_cy + mc.BATTERY_LENGTH / 2, z, z + mc.BATTERY_THICKNESS), "#7bbf6a"),
        (mc.cube(c.board_cx - mc.W11_WIDTH / 2, c.board_cx + mc.W11_WIDTH / 2, c.board_cy - mc.W11_LENGTH / 2,
                 c.board_cy + mc.W11_LENGTH / 2, bz, bz + mc.W11_STACK_HEIGHT - 5.5), "#3b4652"),
        (mc.cube(c.board_cx - 4.5, c.board_cx + 4.5, c.board_cy - 4.5, c.board_cy + 4.5,
                 bz + mc.W11_STACK_HEIGHT - 5.5, bz + mc.W11_STACK_HEIGHT - 3), "#4a90d9"),
        (mc.cylinder(7, bz + mc.W11_STACK_HEIGHT - 3, bz + mc.W11_STACK_HEIGHT, c.board_cx, c.board_cy), "#222222"),
    ]
    return parts


def seated(c, lift=0.0):
    H = c.inner_h + mc.COVER_TOP
    return c.cover().translate((0, 0, -H)).mirror((0, 0, 1)).translate((0, 0, mc.MINI_FLOOR + lift))


fig = plt.figure(figsize=(13, 11), dpi=95)
elev, azim = 30, -58
e, a = np.radians(elev), np.radians(azim)
view = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
scenes = []
for c, name in ((mc.CAM_STACKED, "Stacked"), (mc.CAM_SIDE, "Side by side")):
    scenes.append((f"{name}: open (battery green, board gray, camera blue)",
                   [(c.base(), "#9aa3ad")] + contents(c) + [(seated(c, 22), "#e9ecef")]))
    scenes.append((f"{name}: {c.w:.0f} x {c.l:.0f} x {c.h:.0f} mm", [(c.base(), "#9aa3ad"), (seated(c), "#e9ecef")]))
for i, (title, items) in enumerate(scenes):
    ax = fig.add_subplot(2, 2, i + 1, projection="3d")
    for part, color in items:
        draw(ax, part, view, color)
    ax.set_xlim(-30, 30); ax.set_ylim(-30, 30); ax.set_zlim(-2, 52)
    ax.set_box_aspect((60, 60, 54)); ax.view_init(elev, azim); ax.set_title(title); ax.set_axis_off()
fig.text(0.5, 0.02, "Both drawn at the same scale. The lens looks out of the top; the USB-C notch is at the far end.", ha="center")
fig.savefig(__file__.replace("preview_camera.py", "preview_camera.png"), bbox_inches="tight")
