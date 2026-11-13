"""Render case/preview.png straight from make_case.py (needs matplotlib)."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

import make_case as mc


def triangles(part):
    mesh = part.to_mesh()
    verts = np.asarray(mesh.vert_properties)[:, :3]
    tris = verts[np.asarray(mesh.tri_verts)]
    normals = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-9)
    return tris, normals


def draw(ax, part, view, color):
    tris, normals = triangles(part)
    facing = normals @ view > 0  # matplotlib can't sort depth well, so drop hidden faces
    tris, normals = tris[facing], normals[facing]
    light = np.clip(normals @ view, 0.2, 1)
    base = np.array(matplotlib.colors.to_rgb(color))
    ax.add_collection3d(Poly3DCollection(tris, facecolors=np.outer(light, base) * 0.85 + 0.1, edgecolor="none"))


def lid_in_place(lid, x0, x1, y0, y1, z, lift):
    # Undo the print orientation (mirrored, upside down) and move it onto its compartment.
    return lid.mirror((1, 0, 0)).mirror((0, 0, 1)).translate(((x0 + x1) / 2, (y0 + y1) / 2, z + mc.LID_THICKNESS + lift))


body = mc.door_body()
z_xiao = mc.DOOR_THICKNESS + mc.XIAO_H
z_batt = mc.DOOR_THICKNESS + mc.BATT_H
cam = lid_in_place(mc.lid_camera(), mc.LEFT_X, mc.SHARED_X + mc.WALL,
                   mc.TOP_Y - mc.XIAO_L - 2 * mc.WALL, mc.TOP_Y, z_xiao, 10)
bat = lid_in_place(mc.lid_battery(), mc.BATT_X, mc.RIGHT_X,
                   mc.TOP_Y - mc.BATT_L - 2 * mc.WALL, mc.TOP_Y, z_batt, 10)

fig = plt.figure(figsize=(13, 6), dpi=110)
for i, (elev, azim, title) in enumerate([(40, -65, "Outside (camera side), lids lifted"),
                                         (-40, -65, "Inside (calculator side)")]):
    ax = fig.add_subplot(1, 2, i + 1, projection="3d")
    e, a = np.radians(elev), np.radians(azim)
    view = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
    draw(ax, body, view, "#4a90d9")
    if i == 0:
        draw(ax, cam, view, "#e8a33d")
        draw(ax, bat, view, "#7bbf6a")
    ax.set_xlim(-34, 34); ax.set_ylim(-34, 34); ax.set_zlim(-20, 48)
    ax.set_box_aspect((68, 68, 68))
    ax.view_init(elev, azim)
    ax.set_title(title)
    ax.set_axis_off()
fig.text(0.5, 0.03, "Tall compartment: XIAO + camera (orange lid, lens window).  Low compartment: "
         "EEMB 402535 battery (green lid).  USB-C opening faces the calculator's screen end.", ha="center")
fig.savefig(__file__.replace("preview.py", "preview.png"), bbox_inches="tight")
