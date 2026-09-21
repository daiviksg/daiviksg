#!/usr/bin/env python3
"""
Convert source-prepped.png into a self-typing, monochrome ASCII-art SVG.

The prepped image is downsampled to a character grid (~100 columns), and
each pixel's brightness picks a glyph from a density ramp - sparse
characters for bright areas, dense ones for dark, with a leading space so
the (white) background maps to nothing at all.

For the animation, each row is wrapped in a horizontal clip that wipes
left-to-right (a small block "cursor" rides the wipe edge), staggered top
to bottom. The whole portrait prints once and freezes - no looping.
"""
import os
import sys

import numpy as np
from PIL import Image

IN_PATH = os.path.join(os.path.dirname(__file__), "..", "source-prepped.png")
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "avi-ascii.svg")

# GitHub serves repo-committed SVGs (raw.githubusercontent.com, and CDN
# mirrors like jsdelivr) with response headers that block SMIL/CSS
# animation for cross-origin <img>-embedded SVGs - which is exactly how a
# README references this file. So by default we skip the typing effect and
# render every row already fully printed - set ANIMATE=1 to get the
# self-typing version instead, for contexts that DO run it (opening the
# raw SVG file directly in a browser tab).
ANIMATE = os.environ.get("ANIMATE") == "1"

# bright (sparse) -> dark (dense); leading space clears the background.
RAMP = " .`:-=+*cs#%@"

COLS = 100
# Character cells are taller than wide, so we shrink the row count to keep
# the portrait's aspect ratio roughly correct once rendered as monospace text.
CHAR_ASPECT = 0.52

FILL = "#c9d1d9"
BG = "#0d1117"

CELL_W = 7.0
CELL_H = 13.5
FONT_SIZE = 12

ROW_WIPE_DURATION = 0.55
ROW_STAGGER = 0.045


def load_gray():
    img = Image.open(IN_PATH).convert("L")
    return img


def to_char_grid(img: Image.Image):
    w, h = img.size
    rows = max(1, round(COLS * (h / w) * CHAR_ASPECT))
    small = img.resize((COLS, rows), Image.LANCZOS)
    arr = np.array(small, dtype=np.float64) / 255.0  # 0=black .. 1=white

    ramp_len = len(RAMP)
    # brightness 1.0 (white) -> index 0 (space); 0.0 (black) -> last glyph.
    idx = np.clip(((1.0 - arr) * (ramp_len - 1)).round().astype(int), 0, ramp_len - 1)

    lines = []
    for row in idx:
        lines.append("".join(RAMP[i] for i in row))
    return lines


def esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def render(lines):
    n_rows = len(lines)
    n_cols = max(len(l) for l in lines) if lines else 0

    width = n_cols * CELL_W + 20
    height = n_rows * CELL_H + 20

    total_anim = (n_rows - 1) * ROW_STAGGER + ROW_WIPE_DURATION if n_rows else 0

    style = f'''
    text {{
      font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
      font-size: {FONT_SIZE}px;
      fill: {FILL};
      white-space: pre;
    }}
    .row-clip rect {{ fill: white; }}
    .cursor {{
      fill: {FILL};
      opacity: 0.85;
    }}
  '''

    defs = []
    rows_svg = []
    for r, line in enumerate(lines):
        stripped_len = len(line.rstrip())
        if stripped_len == 0:
            continue  # fully blank row - nothing to wipe in
        y = 10 + r * CELL_H + FONT_SIZE
        delay = r * ROW_STAGGER
        clip_id = f"clip{r}"
        row_width_full = stripped_len * CELL_W

        if ANIMATE:
            # Clip rect animates from width 0 -> full, revealing the row's text.
            defs.append(
                f'<clipPath id="{clip_id}"><rect x="0" y="{10 + r * CELL_H - 2}" '
                f'width="0" height="{CELL_H + 4}">'
                f'<animate attributeName="width" from="0" to="{row_width_full}" '
                f'begin="{delay}s" dur="{ROW_WIPE_DURATION}s" fill="freeze" '
                f'calcMode="spline" keySplines="0.2 0 0.2 1" /></rect></clipPath>'
            )
        else:
            # No animation dependency: clip rect is already full width.
            defs.append(
                f'<clipPath id="{clip_id}"><rect x="0" y="{10 + r * CELL_H - 2}" '
                f'width="{row_width_full}" height="{CELL_H + 4}" /></clipPath>'
            )

        rows_svg.append(
            f'<g clip-path="url(#{clip_id})">'
            f'<text x="10" y="{y}" xml:space="preserve">{esc(line)}</text>'
            f'</g>'
        )

        if ANIMATE:
            # A small cursor block that rides the wipe edge, then disappears.
            cursor_h = CELL_H - 3
            rows_svg.append(
                f'<rect class="cursor" x="0" y="{10 + r * CELL_H - 2 + 1.5}" '
                f'width="{CELL_W * 0.85}" height="{cursor_h}">'
                f'<animate attributeName="x" from="0" to="{max(row_width_full - CELL_W, 0)}" '
                f'begin="{delay}s" dur="{ROW_WIPE_DURATION}s" fill="freeze" '
                f'calcMode="spline" keySplines="0.2 0 0.2 1" />'
                f'<animate attributeName="opacity" from="0.85" to="0" '
                f'begin="{delay + ROW_WIPE_DURATION}s" dur="0.15s" fill="freeze" />'
                f'</rect>'
            )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}"
     viewBox="0 0 {width:.0f} {height:.0f}">
  <style>{style}</style>
  <defs>
    {"".join(defs)}
  </defs>
  {"".join(rows_svg)}
</svg>
'''
    return svg


def main():
    if not os.path.exists(IN_PATH):
        print(f"[make_ascii_svg] missing {IN_PATH} - run prep_photo.py first", file=sys.stderr)
        sys.exit(1)

    img = load_gray()
    lines = to_char_grid(img)
    svg = render(lines)

    with open(OUT_PATH, "w") as f:
        f.write(svg)
    print(f"[make_ascii_svg] wrote {OUT_PATH} ({len(lines)} rows x {COLS} cols, {len(svg)} bytes)")


if __name__ == "__main__":
    main()
