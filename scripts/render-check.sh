#!/usr/bin/env bash
# Headless renders of a page at desktop and phone width with scroll-reveals forced visible.
# Usage: bash scripts/render-check.sh portfolio.html  → writes /tmp/render/<page>-{1440,390}.png
set -euo pipefail
page="${1:-portfolio.html}"; here="$(cd "$(dirname "$0")/.." && pwd)"
tmp=/tmp/render; mkdir -p "$tmp"; rm -f "$tmp/${page%.html}"-*.png; ln -sfn "$here/assets" "$tmp/assets"
# drop the 'js' class bootstrap so .reveal never hides content; gallery.js still runs
sed "s#<script>document.documentElement.classList.add('js')</script>##" "$here/$page" > "$tmp/$page"
# pin vh-based heroes to a fixed height so the tall capture window doesn't stretch them
sed -i '' 's#</head>#<style>.hero{min-height:820px!important}@media(max-width:900px){.hero{min-height:700px!important}}</style></head>#' "$tmp/$page"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
for w in 1440 390; do
  out="$tmp/${page%.html}-$w.png"
  if [ "$w" -ge 500 ]; then h=16000; else h=14000; fi   # portfolio is ~11000 tall at 1440; both must fit the footer
  if [ "$w" -ge 500 ]; then
    "$CHROME" --headless=new --disable-gpu --hide-scrollbars --virtual-time-budget=4000 \
      --window-size=${w},$h --screenshot="$out" "file://$tmp/$page" 2>/dev/null
  else
    # headless Chrome clamps windows to >= 500px wide, so a 390 window lays out at 500 and the
    # screenshot silently crops it. Render inside an iframe of the exact width, then crop to it.
    printf '<!doctype html><style>html,body{margin:0}iframe{display:block;border:0;width:%spx;height:%spx}</style><iframe src="%s"></iframe>' \
      "$w" "$h" "$page" > "$tmp/frame-$w.html"
    "$CHROME" --headless=new --disable-gpu --hide-scrollbars --virtual-time-budget=4000 \
      --window-size=500,$h --screenshot="$out" "file://$tmp/frame-$w.html" 2>/dev/null
    python3 -c "import sys;from PIL import Image;p=sys.argv[1];Image.open(p).crop((0,0,int(sys.argv[2]),int(sys.argv[3]))).save(p)" "$out" "$w" "$h"
  fi
  echo "wrote $out"
done
