#!/bin/bash
# Build CLAUDE as a Flash App (so it shows under [apps]) and the on-calculator
# installer for it. Outputs go to calculator/send-to-calculator/:
#   CLAPP0.8xv   the app, packed as an AppVar
#   CLINST.8xp   the installer (CE-Programming/app_tools), run once with arTIfiCE
set -e
REPO="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$HOME/CEdev/bin:$PATH"
OUT="$REPO/calculator/send-to-calculator"
cd "$REPO/calculator"
make APPLICATION=YES APPLICATION_DESCRIPTION='"Ask Claude"' BINDIR=bin/app OBJDIR=obj/app | grep -E "success|error"
convbin --iformat 8ek --input bin/app/CLAUDE.8ek --oformat 8xv-split --maxvarsize 65200 \
  --output bin/app/CLAPP.8xv --name CLAPP | grep success
cp bin/app/CLAPP.0.8xv "$OUT/CLAPP0.8xv"

WORK="${TMPDIR:-/tmp}/ti84-claude-app_tools"
rm -rf "$WORK"
git clone -q --depth 1 https://github.com/CE-Programming/app_tools "$WORK"
sed -i '' 's/^NAME = INSTALL/NAME = CLINST/; s/^APPVAR_PREFIX = "APP"/APPVAR_PREFIX = "CLAPP"/' "$WORK/installer/makefile"
make -C "$WORK/installer" | grep -E "success|error"
cp "$WORK/installer/bin/CLINST.8xp" "$OUT/CLINST.8xp"
echo "Built $OUT/CLAPP0.8xv and $OUT/CLINST.8xp"
