#!/bin/sh
# Renders the plugin pages with the real OPNsense theme and takes screenshots
# against a mocked API (sample data with documentation IP ranges).
# usage: sh tools/preview/run.sh /path/to/opnsense/core [output_dir]
# needs: python3, playwright (pip install playwright) and a Chrome/Chromium
set -e
CORE=$(cd "$1" && pwd)
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
OUT=${2:-$ROOT/docs/screenshots}
APP="$ROOT/multihome-ddns/src/opnsense/mvc/app"
SITE=$(mktemp -d)
trap 'rm -rf "$SITE"' EXIT
# own tree with links to the core assets, so nothing is written into the core checkout
mkdir -p "$SITE/ui" "$OUT"
for entry in "$CORE"/src/opnsense/www/*; do
    ln -s "$entry" "$SITE/ui/$(basename "$entry")"
done
python3 "$HERE/render.py" "$APP" "$SITE/ui/multihomeddns"
python3 "$HERE/shoot.py" "$SITE" "$APP/models/OPNsense/MultihomeDDNS/MultihomeDDNS.xml" "$OUT"
