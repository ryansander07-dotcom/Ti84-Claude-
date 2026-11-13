#!/bin/bash
# Build the "Claude Calculator" folder on the Desktop: everything needed to set up
# a calculator, flash the dongle, and print the cases, sorted into numbered folders.
# Run it again any time to refresh the folder from this repo.
set -e
REPO="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$HOME/Desktop/Claude Calculator"
mkdir -p "$OUT"
rm -rf "$OUT/1 - Calculator files" "$OUT/2 - Dongle" "$OUT/3 - Test without the OTG cable" "$OUT/4 - 3D print files" "$OUT/5 - Wiring and parts"

# 1: the three calculator files and a send helper
C="$OUT/1 - Calculator files"
mkdir -p "$C"
cp "$REPO/calculator/send-to-calculator/arTIfiCE_v2.1.8xp" "$REPO/calculator/send-to-calculator/clibs.8xg" "$C/"
cp "$REPO/calculator/bin/CLAUDE.8xp" "$C/"
cat > "$C/Send to Calculator.command" <<'CMD'
#!/bin/bash
cd "$(dirname "$0")"
clear
echo "Sending CLAUDE to a TI-84 Plus CE"
echo
echo "1. Plug the calculator into this Mac with its USB cable and turn it on."
echo "2. TI Connect CE and a Finder window with the three files are opening now."
echo "3. Press Cmd+A in the Finder window, then drag the files onto the calculator"
echo "   listed in TI Connect CE, and click SEND."
echo
echo "First time only, on the calculator: [2nd] [+] > 2: Mem Management > Prgm,"
echo "move to A and press [enter] so its * goes away (arTIfiCE must be in RAM)."
echo "Then [prgm] > A > [enter], pick CLAUDE."
open -a "TI Connect CE"
open -R "arTIfiCE_v2.1.8xp"
CMD
chmod +x "$C/Send to Calculator.command"

# The apps-menu version: the app plus its one-time installer.
A="$C/Apps menu version"
mkdir -p "$A"
cp "$REPO/calculator/send-to-calculator/CLAPP0.8xv" "$REPO/calculator/send-to-calculator/CLINST.8xp" "$A/"
cat > "$A/How to install as an app.txt" <<'TXT'
Put CLAUDE under [apps] instead of [prgm]

You need clibs.8xg and arTIfiCE_v2.1.8xp on the calculator already
(the files one folder up). Then:

1. Send CLAPP0.8xv and CLINST.8xp to the calculator (drag them onto it in
   TI Connect CE, like the other files).
2. On the calculator: [prgm] > A > [enter]. In the arTIfiCE list pick CLINST.
3. It says "Installing: CLAUDE ... Do not reset!" Wait, and don't remove the
   batteries or press [on] until it finishes (a few seconds). It writes the app
   into the calculator's archive, so interrupting it can corrupt the archive.
4. When it asks "Delete installer files?", say yes.
5. Press [apps] and pick CLAUDE.

If it says "Out of archive space": [2nd] [+] > 2: Mem Management, or run the
GarbageCollect command from [2nd] [0] (catalog), then try again.
If it says "Already installed": delete the CLAUDE app in [2nd] [+] > 2 > Apps
first, then run CLINST again (that's how you update it).

The app still uses the C libraries (clibs). The old CLAUDE program can stay or be
deleted; they don't interfere.
TXT

# 2: the dongle
D="$OUT/2 - Dongle"
mkdir -p "$D"
cat > "$D/Update Dongle.command" <<CMD
#!/bin/bash
"$REPO/tools/flash_dongle.sh"
echo
read -n 1 -s -r -p "Press any key to close."
CMD
cat > "$D/Test Dongle.command" <<CMD
#!/bin/bash
cd "$REPO"
.venv/bin/python esp32/tools/test_dongle.py "What is 12*12?"
echo
read -n 1 -s -r -p "Press any key to close. (That question used about a third of a cent.)"
CMD
chmod +x "$D"/*.command

# 3: relay, for using the dongle through the Mac
R="$OUT/3 - Test without the OTG cable"
mkdir -p "$R"
cat > "$R/Start Relay.command" <<CMD
#!/bin/bash
cd "$REPO"
echo "Plug the calculator (running CLAUDE) and the dongle into this Mac."
echo "Close this window to stop."
.venv/bin/python esp32/tools/relay.py
CMD
chmod +x "$R/Start Relay.command"

# 4: print files
P="$OUT/4 - 3D print files"
mkdir -p "$P/No-camera box" "$P/Camera back plate" "$P/Pictures"
cp "$REPO/case/mini_box.3mf" "$REPO/case/mini_box_print_notes.txt" "$P/No-camera box/"
cp "$REPO/case/camera_plate_fit_test.3mf" "$REPO/case/camera_plate.3mf" "$REPO/case/camera_plate_print_notes.txt" "$P/Camera back plate/"
cp "$REPO"/case/renders/camera_plate-*.png "$P/Pictures/"

# 5: wiring and parts
W="$OUT/5 - Wiring and parts"
mkdir -p "$W"
cp "$REPO/case/README.md" "$W/Cases, parts and wiring.md"
cp "$REPO/README.md" "$W/Full project README.md"

cp "$REPO/tools/START HERE.txt" "$OUT/START HERE.txt"
echo "Made $OUT"
