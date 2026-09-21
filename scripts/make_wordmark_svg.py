#!/usr/bin/env python3
"""
Render a short personal wordmark (e.g. "DAIVIK") as a pseudo-3D, extruded
ASCII-art SVG card - the companion piece to the ASCII portrait card. Same
technique as make_ascii_svg.py (brightness -> character-ramp downsampling)
but the source image is synthetic: bold text with a stepped drop-shadow to
fake a 3D-block extrusion, instead of a photo.

python scripts/make_wordmark_svg.py   # writes wordmark.svg
"""
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "wordmark.svg")

WORD = os.environ.get("WORDMARK_TEXT", "DAIVIK")
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

# bright (sparse) -> dark (dense); leading space clears the background.
RAMP = " .`:-=+*cs#%@"

COLS = 90
CHAR_ASPECT = 0.52
EXTRUDE_DEPTH = 26  # px, at supersampled render resolution
EXTRUDE_STEPS = 2  # just back-shadow + front-face reads cleanest at ASCII res

# Warm accent (vs. the portrait's cool gray) so the two cards read as a set
# but stay visually distinct - matches the reference's peach wordmark tone.
FILL = "#e3a374"
BG = "#0d1117"

CELL_W = 7.6
CELL_H = 13.5
FONT_SIZE = 12


def _load_font(size):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def render_3d_text(text: str) -> Image.Image:
    """Bold text with a stepped bottom-right shadow to fake an extruded
    3D-block look, composited on white (so it feeds the same ramp logic
    as prep_photo.py's output: white background -> blank ASCII)."""
    scale = 4  # supersample for clean downsampling later
    font_size = 120 * scale
    font = _load_font(font_size)

    tmp = Image.new("L", (10, 10), 255)
    measure = ImageDraw.Draw(tmp)
    bbox = measure.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]

    depth = EXTRUDE_DEPTH * scale
    pad = 40 * scale
    canvas_w = text_w + pad * 2 + depth
    canvas_h = text_h + pad * 2 + depth

    img = Image.new("L", (canvas_w, canvas_h), 255)
    draw = ImageDraw.Draw(img)

    origin_x, origin_y = pad - bbox[0], pad - bbox[1]

    # Solid offset shadow (mid-gray) behind a solid black front face - two
    # flat layers read as a clean block-depth silhouette at ASCII
    # resolution, where a smooth gradient of steps just turns to noise.
    draw.text((origin_x + depth, origin_y + depth), text, font=font, fill=150)
    draw.text((origin_x, origin_y), text, font=font, fill=0)

    return img


def to_char_grid(img: Image.Image):
    w, h = img.size
    rows = max(1, round(COLS * (h / w) * CHAR_ASPECT))
    small = img.resize((COLS, rows), Image.LANCZOS)
    arr = np.array(small, dtype=np.float64) / 255.0

    ramp_len = len(RAMP)
    idx = np.clip(((1.0 - arr) * (ramp_len - 1)).round().astype(int), 0, ramp_len - 1)

    return ["".join(RAMP[i] for i in row) for row in idx]


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_svg(lines):
    n_rows = len(lines)
    n_cols = max((len(l.rstrip()) for l in lines), default=0)

    width = n_cols * CELL_W + 20
    height = n_rows * CELL_H + 20

    text_lines = []
    for r, line in enumerate(lines):
        if not line.strip():
            continue
        y = 10 + r * CELL_H + FONT_SIZE
        text_lines.append(f'<text x="10" y="{y:.1f}" xml:space="preserve">{esc(line)}</text>')

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}"
     viewBox="0 0 {width:.0f} {height:.0f}">
  <style>
    text {{
      font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
      font-size: {FONT_SIZE}px;
      fill: {FILL};
      white-space: pre;
    }}
  </style>
  {"".join(text_lines)}
</svg>
'''
    return svg


def main():
    img = render_3d_text(WORD)
    lines = to_char_grid(img)
    svg = render_svg(lines)
    with open(OUT_PATH, "w") as f:
        f.write(svg)
    print(f"[make_wordmark_svg] wrote {OUT_PATH} ({len(lines)} rows x {COLS} cols, word={WORD!r})")


if __name__ == "__main__":
    main()
