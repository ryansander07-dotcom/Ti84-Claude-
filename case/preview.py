"""Render case/preview.png straight from make_case.py (needs matplotlib)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

import make_case as mc

WHITE, BLUE, ORANGE, DARK = "#e9ecef", "#4a90d9", "#e8a33d", "#3b4652"


def draw(ax, part, view, color):
    mesh = part.to_mesh()
    tris = np.asarray(mesh.vert_properties)[:, :3][np.asarray(mesh.tri_verts)]
    normals = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-9)
    facing = normals @ view > 0  # matplotlib can't sort depth well, so drop hidden faces
    light = np.clip(normals[facing] @ view, 0.25, 1)
    base = np.array(matplotlib.colors.to_rgb(color))
    ax.add_collection3d(Poly3DCollection(tris[facing], facecolors=np.outer(light, base) * 0.8 + 0.12,
                                         edgecolor="none"))


def seated(cover, height, z, lift=0.0):
    return cover.translate((0, 0, -height)).mirror((0, 0, 1)).translate((0, 0, z + lift))


cover_h = mc.COVER_H
scenes = [
    ("Always-on: door + cover (cover lifted)", (-36, 36, -36, 40, -5, 40), [
        (mc.always_on_base(), BLUE), (seated(mc.cover(), cover_h, mc.DOOR_THICKNESS, 14), WHITE)]),
    ("Always-on: assembled", (-36, 36, -36, 40, -5, 40), [
        (mc.always_on_base(), BLUE), (seated(mc.cover(), cover_h, mc.DOOR_THICKNESS), WHITE)]),
    ("Clip-on: door with magnet bosses", (-36, 36, -36, 40, -5, 40), [
        (mc.clip_door(), BLUE)]),
    ("Clip-on: pod lifting off", (-36, 36, -36, 40, -5, 40), [
        (mc.clip_door(), BLUE),
        (mc.pod_base().translate((0, 0, mc.DOOR_THICKNESS + 10)), ORANGE),
        (seated(mc.cover(), cover_h, mc.DOOR_THICKNESS + mc.POD_FLOOR + 10), WHITE)]),
    ("Mini (no camera), cover lifted", (-18, 18, -18, 20, -4, 26), [
        (mc.mini_base(), DARK), (seated(mc.mini_cover(), mc.MINI_INNER_H + mc.COVER_TOP, mc.MINI_FLOOR, 8), WHITE)]),
    ("Mini, assembled", (-18, 18, -18, 20, -4, 26), [
        (mc.mini_base(), DARK), (seated(mc.mini_cover(), mc.MINI_INNER_H + mc.COVER_TOP, mc.MINI_FLOOR), WHITE)]),
]

fig = plt.figure(figsize=(15, 14), dpi=90)
elev, azim = 34, -60
e, a = np.radians(elev), np.radians(azim)
view = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
for i, (title, lim, items) in enumerate(scenes):
    ax = fig.add_subplot(3, 2, i + 1, projection="3d")
    for part, color in items:
        draw(ax, part, view, color)
    ax.set_xlim(lim[0], lim[1]); ax.set_ylim(lim[2], lim[3]); ax.set_zlim(lim[4], lim[5])
    ax.set_box_aspect((lim[1] - lim[0], lim[3] - lim[2], lim[5] - lim[4]))
    ax.view_init(elev, azim)
    ax.set_title(title)
    ax.set_axis_off()
fig.text(0.5, 0.01, "The far end of each door is the screen end, where the USB cable leaves. "
         "The mini is shown larger than the doors.", ha="center")
fig.savefig(__file__.replace("preview.py", "preview.png"), bbox_inches="tight")
