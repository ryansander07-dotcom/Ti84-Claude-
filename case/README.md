# Dongle case (replaces the battery door)

A 3D-printed battery door with the dongle built in. Everything stays inside the
outline of the original door: a tall compartment for the XIAO ESP32S3 Sense and a low
one beside it for a flat LiPo battery. The camera looks out of the back of the
calculator, like a phone camera, so you hold the calculator over the problem to take
the picture.

![preview](preview.png)

## Parts

| Part | Notes |
|---|---|
| Seeed XIAO ESP32S3 Sense | 21 × 17.8 × 15 mm with the camera board |
| [EEMB 402535 LiPo, 3.7 V 320 mAh](https://www.amazon.com/EEMB-402535-Rechargeable-Connector-Certified/dp/B08215N9R8) | 25.5 × 36 × 4.3 mm, built-in protection circuit. [4-pack](https://www.amazon.com/EEMB-402535-Rechargeable-Connector-Certified/dp/B08HD1N273) |
| Right-angle USB-C to mini-USB **OTG** cable, short | Runs from the door to the calculator's USB port |
| The original battery door screw | Holds the new door on |

The XIAO charges the battery whenever the calculator powers it, so you never charge the
dongle separately. That charging comes out of the calculator's own battery.

## Measure first

The door sizes in `make_case.py` are estimates; nobody publishes exact dimensions for
the TI-84 Plus CE Python's door. Take the original door off (Phillips #00 screw) and
measure it with calipers:

| Setting in `make_case.py` | What to measure |
|---|---|
| `DOOR_WIDTH` | Across the calculator, edge to edge |
| `DOOR_LENGTH` | Along the calculator, edge to edge, not counting tabs |
| `DOOR_THICKNESS` | The flat part of the door |
| `TAB_WIDTH`, `TAB_LENGTH`, `TAB_THICKNESS` | The tongue that slides under the case at the top edge |
| `SCREW_FROM_BOTTOM`, `SCREW_X` | Where the screw hole's center is |
| `BOARD_HEIGHT` | Your XIAO with the camera board on, bottom to top of the lens |

Then rebuild the files:

```bash
.venv/bin/python case/make_case.py
```

If the parts don't fit inside the door, the script stops and says what's too big. If
your door has clips the script doesn't model, a photo of the inside of the door is
enough to add them.

## Print

1. **`stl/fit_test.stl` first.** It's only the door plate and takes about 10 minutes.
   It should drop into the recess and the screw should line up. Adjust the sizes and
   print again until it fits.
2. **`stl/door_body.stl`**: flat side down, no supports.
3. **`stl/lid_camera.stl`** and **`stl/lid_battery.stl`**: as exported (outer face
   down, lip up), no supports.

PLA or PETG, 0.2 mm layers, 3 walls, 20% infill. PETG holds up better in a hot car or
backpack.

## Assemble

1. **Battery wires.** Cut the battery's connector off and solder red to the **B+** pad
   and black to the **B−** pad on the underside of the XIAO. Do one wire at a time so
   the bare ends never touch. Leave about 4 cm of wire.
2. Lay the battery flat in the low compartment, wire end toward the top (the USB
   end), and feed the wires through the slot in the shared wall.
3. Put the XIAO in the tall compartment with its USB-C port facing the opening. A
   small square of double-sided foam tape under it stops rattling.
4. Press both lids on with their notches at the USB end. The camera lens sits in the
   round window. Check the preview on the calculator and adjust `LENS_FROM_CENTER` if
   the lens isn't centered.
5. Plug in the OTG cable, run it along the back to the calculator's USB port, and keep
   it flat with a small adhesive cable clip.
6. Swap the door onto the calculator and put the original screw back in.

The calculator's own battery stays in place underneath. Keep the original door so you
can put it back.
