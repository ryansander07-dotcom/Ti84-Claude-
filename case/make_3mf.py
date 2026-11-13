"""Pack case parts into one 3MF plate that Bambu Studio (or any slicer) opens ready
to slice.

    .venv/bin/python case/make_3mf.py

Writes case/mini_box.3mf: the mini box's base and cover side by side, both flat
on the plate, already in print orientation. The plate layout fits every Bambu Lab
printer, including the 180 mm A1 mini.
"""

import zipfile
from pathlib import Path

import numpy as np

import make_case as mc

HERE = Path(__file__).resolve().parent
PLATE_CENTER = (90.0, 90.0)  # inside the bed of every Bambu Lab printer
GAP = 8.0                    # space between parts on the plate

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
</Types>
"""

RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel0" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
"""


def mesh_xml(part):
    mesh = part.to_mesh()
    verts = np.asarray(mesh.vert_properties)[:, :3]
    tris = np.asarray(mesh.tri_verts)
    lo = verts.min(axis=0)
    hi = verts.max(axis=0)
    # Center each part on its own origin, sitting on z = 0.
    verts = verts - np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]])
    v = "\n".join(f'     <vertex x="{x:.4f}" y="{y:.4f}" z="{z:.4f}"/>' for x, y, z in verts)
    t = "\n".join(f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in tris)
    return f"    <mesh>\n     <vertices>\n{v}\n     </vertices>\n     <triangles>\n{t}\n     </triangles>\n    </mesh>", hi - lo


def write_3mf(path, parts, center=PLATE_CENTER, title="TI-84 Claude mini box"):
    objects, items, sizes = [], [], []
    for i, (name, part) in enumerate(parts, start=1):
        xml, size = mesh_xml(part)
        sizes.append(size)
        objects.append(f'  <object id="{i}" name="{name}" type="model">\n{xml}\n  </object>')
    # Lay the parts out left to right, centered on the plate.
    total = sum(s[0] for s in sizes) + GAP * (len(sizes) - 1)
    x = center[0] - total / 2
    for i, size in enumerate(sizes, start=1):
        cx = x + size[0] / 2
        items.append(f'  <item objectid="{i}" transform="1 0 0 0 1 0 0 0 1 {cx:.3f} {center[1]:.3f} 0"/>')
        x += size[0] + GAP
    model = ('<?xml version="1.0" encoding="UTF-8"?>\n'
             '<model unit="millimeter" xml:lang="en-US" '
             'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">\n'
             f' <metadata name="Title">{title}</metadata>\n'
             ' <resources>\n' + "\n".join(objects) + '\n </resources>\n'
             ' <build>\n' + "\n".join(items) + '\n </build>\n</model>\n')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("3D/3dmodel.model", model)
    print(f"Wrote {path.name}: {', '.join(n for n, _ in parts)}")


if __name__ == "__main__":
    write_3mf(HERE / "mini_box.3mf", [("mini_base", mc.mini_base()), ("mini_cover", mc.mini_cover())])
    # The camera back plate is 89 x 193 mm: it needs a 256 mm bed (X1, P1, A1; not the A1 mini).
    # Printed calculator side down, so the outside face comes out clean.
    write_3mf(HERE / "camera_plate.3mf", [("camera_back_plate", mc.BACK.body().translate((0, 0, mc.GRIP_DEPTH)))],
              center=(128.0, 128.0), title="TI-84 Claude camera back plate")
    # A 30 mm slice of the plate with both edge grips: checks the fit on the calculator first.
    strip = mc.BACK.body() ^ mc.cube(-60, 60, -15, 15, -10, 20)
    write_3mf(HERE / "camera_plate_fit_test.3mf", [("camera_plate_fit_test", strip.translate((0, 0, mc.GRIP_DEPTH)))],
              title="TI-84 Claude camera plate fit test")
