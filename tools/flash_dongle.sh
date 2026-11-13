#!/bin/bash
# Build the dongle firmware and upload it to a Meshnology W11 plugged into this Mac.
# Needs arduino-cli with the esp32 core and ArduinoJson, and esp32/ti84_dongle/secrets.h.
set -e
REPO="$(cd "$(dirname "$0")/.." && pwd)"
SKETCH="$REPO/esp32/ti84_dongle"
BUILD="${TMPDIR:-/tmp}/ti84-claude-dongle-build"
FQBN="esp32:esp32:esp32s3:USBMode=default,CDCOnBoot=default,PSRAM=opi,FlashSize=16M,PartitionScheme=app3M_fat9M_16MB"

if [ ! -f "$SKETCH/secrets.h" ]; then
  echo "Missing $SKETCH/secrets.h. Copy secrets.example.h to secrets.h and put your API key in it."
  exit 1
fi
# Arduino's sketch scanner (ctags) is Intel-only; this sketch doesn't need it.
mkdir -p "$BUILD"
printf '#!/bin/sh\nexit 0\n' > "$BUILD/noctags" && chmod +x "$BUILD/noctags"

echo "Building the dongle firmware..."
arduino-cli compile -b "$FQBN" --build-path "$BUILD/out" \
  --build-property "tools.ctags.path=$BUILD" --build-property "tools.ctags.cmd.path=$BUILD/noctags" \
  "$SKETCH" | grep -E "Sketch uses|error" || true

find_dongle() { "$REPO/.venv/bin/python" -c "import sys; sys.path.insert(0, '$REPO/esp32/tools'); import relay; print(relay.ports_now()[1] or '')"; }
PORT=$(find_dongle)
if [ -z "$PORT" ]; then
  echo "No dongle found. Plug it into this Mac with a USB-C data cable."
  exit 1
fi
# If the firmware is running, a 1200-baud touch restarts the board into its loader.
"$REPO/.venv/bin/python" - "$PORT" <<'PY' || true
import sys, time, serial
try:
    s = serial.Serial(sys.argv[1], 1200); time.sleep(0.2); s.close()
except Exception:
    pass
PY
sleep 3
UPLOAD=$(find_dongle)
echo "Uploading to $UPLOAD..."
arduino-cli upload -p "$UPLOAD" -b "$FQBN" --input-dir "$BUILD/out" "$SKETCH" | grep -E "Hash of data verified|rror" | tail -1
echo "Done. The dongle restarts by itself."
