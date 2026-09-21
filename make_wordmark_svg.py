#!/usr/bin/env python3
"""
Render a short personal wordmark (default "DVK") as a flat, bold ASCII-art
SVG card - the companion piece to the ASCII portrait card, in the same
terminal-card chrome (title bar, rounded border, dark gradient background)
as the reference profile's wordmark.sh card. Same downsampling technique
as make_ascii_svg.py (brightness -> character-ramp) but the source image
is synthetic: bold text rendered once, no drop-shadow/extrusion layer.

python scripts/make_wordmark_svg.py   # writes wordmark.svg
"""
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "wordmark.svg")

WORD = os.environ.get("WORDMARK_TEXT", "DVK")
PROMPT = os.environ.get("WORDMARK_PROMPT", "dedwiks@github: ~$ ./wordmark.sh --3d")
ANIMATE = os.environ.get("ANIMATE", "1") == "1"

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

# bright (sparse) -> dark (dense); leading space clears the background.
RAMP = " .`:-=+*cs#%@"

COLS = 90
CHAR_ASPECT = 0.52

# Same cool gray as the portrait and the reference's own wordmark (checked
# its committed SVG directly: fill="#c9d1d9" throughout, not an accent
# color) - keeps the whole card set monochrome and consistent.
FILL = "#c9d1d9"

CELL_W = 7.6
CELL_H = 13.5
FONT_SIZE = 12

# Matches the reference wordmark's own timing exactly (checked its SVG:
# a single 1.60s wipe reveal with a translucent cursor bar riding the edge).
WIPE_DURATION = 1.6

# After the reveal, the reference keeps going: ~20 duplicate text groups
# with indefinite discrete opacity toggles, each flashing an alternate
# (slightly shifted) glyph in and out - the "constant change of characters,
# creation and deletion" look. Reproduced here as overlay layers, each
# showing a randomized subset of characters nudged along the ramp, flickering
# on briefly on its own independent cycle.
FLICKER_LAYERS = 14
FLICKER_MIN_DUR = 2.6
FLICKER_MAX_DUR = 4.8
FLICKER_ON_FRACTION = 0.05
GLITCH_DENSITY = 0.07

# height/width the card should target, regardless of the word's own natural
# text aspect ratio - matches the reference wordmark.svg's own proportion
# (387/486 = 0.796), so the DVK card reads as roughly as tall as the
# portrait card instead of a flat strip.
TARGET_ASPECT = 0.8

# Card chrome - matches the reference card's palette/geometry.
PAD_X = 18
TITLEBAR_H = 28
PAD_BOTTOM = 18
CORNER_R = 12
BORDER = "#30363d"
TITLE_TEXT_COLOR = "#7d8590"


def _load_font(size):
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def render_flat_text(text: str) -> Image.Image:
    """Bold text, single flat layer, composited on white (so it feeds the
    same ramp logic as prep_photo.py's output: white background -> blank
    ASCII)."""
    scale = 4  # supersample for clean downsampling later
    font_size = 120 * scale
    font = _load_font(font_size)

    tmp = Image.new("L", (10, 10), 255)
    measure = ImageDraw.Draw(tmp)
    bbox = measure.textbbox((0, 0), text, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]

    pad = 40 * scale
    canvas_w = text_w + pad * 2
    canvas_h = text_h + pad * 2

    img = Image.new("L", (canvas_w, canvas_h), 255)
    draw = ImageDraw.Draw(img)

    origin_x, origin_y = pad - bbox[0], pad - bbox[1]
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


def trim_blank_rows(lines):
    """Drop fully-blank leading/trailing rows. render_svg() sizes the card
    height from len(lines) * CELL_H, so blank rows left in from the source
    image's own padding show up as visible dead space below (or above) the
    glyphs - this is what was causing the oversized DVK card."""
    start = 0
    end = len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return lines[start:end]


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def glitch_line(line: str, rng: random.Random, density: float) -> str:
    """Return a variant of `line` with a random subset of non-space glyphs
    nudged along RAMP - used as a briefly-flashed overlay layer so the base
    text appears to flicker/change at a few positions at a time."""
    ramp_len = len(RAMP)
    chars = list(line)
    for i, ch in enumerate(chars):
        if ch == " " or rng.random() >= density:
            continue
        idx = RAMP.index(ch)
        shift = rng.choice([-3, -2, -1, 1, 2, 3])
        chars[i] = RAMP[max(0, min(ramp_len - 1, idx + shift))]
    return "".join(chars)


def render_svg(lines):
    n_rows = len(lines)
    n_cols = max((len(l.rstrip()) for l in lines), default=0)

    content_w = n_cols * CELL_W
    content_h = n_rows * CELL_H
    width = content_w + PAD_X * 2

    # A short word like "DVK" is naturally wide-and-flat, so shrink-wrapping
    # the card height to the text (old behavior) made it look tiny next to
    # the portrait card. The reference's own wordmark.svg (checked via the
    # GitHub API) isn't shrink-wrapped either - it's a fixed, near-square
    # canvas (486x387, h/w ~= 0.8) with the ASCII content vertically
    # centered inside a generous top/bottom gap. Match that proportion here
    # instead of hugging the text tightly.
    natural_height = content_h + TITLEBAR_H + PAD_BOTTOM
    target_height = width * TARGET_ASPECT
    height = max(natural_height, target_height)
    top = TITLEBAR_H + (height - TITLEBAR_H - content_h) / 2

    text_lines = []
    for r, line in enumerate(lines):
        if not line.strip():
            continue
        y = top + r * CELL_H + FONT_SIZE
        text_lines.append(f'<text x="{PAD_X}" y="{y:.1f}" xml:space="preserve">{esc(line)}</text>')

    clip_style = ""
    clip_def = ""
    cursor_svg = ""
    group_open, group_close = "<g>", "</g>"
    if ANIMATE:
        clip_def = (
            f'<clipPath id="wipe"><rect x="{PAD_X}" y="{top - 2:.1f}" '
            f'height="{content_h + 4:.1f}" width="0">'
            f'<animate attributeName="width" from="0" to="{content_w:.1f}" '
            f'begin="0s" dur="{WIPE_DURATION}s" fill="freeze" '
            f'calcMode="spline" keySplines="0.2 0 0.2 1" /></rect></clipPath>'
        )
        group_open, group_close = '<g clip-path="url(#wipe)">', "</g>"
        # A faint vertical bar rides the wipe edge left-to-right, then
        # disappears once the reveal finishes - same technique as the
        # reference's own wordmark cursor.
        cursor_svg = (
            f'<rect x="{PAD_X}" y="{top - 2:.1f}" width="14.4" height="{content_h + 4:.1f}" '
            f'fill="{FILL}" opacity="0.16">'
            f'<animate attributeName="x" from="{PAD_X}" to="{PAD_X + content_w:.1f}" '
            f'begin="0s" dur="{WIPE_DURATION}s" fill="freeze" />'
            f'<animate attributeName="opacity" from="0.16" to="0" '
            f'begin="{WIPE_DURATION}s" dur="0.15s" fill="freeze" />'
            f'</rect>'
        )

    flicker_svg = ""
    if ANIMATE:
        rng = random.Random(sum(ord(c) for c in "".join(lines)) or 1)
        layers = []
        for _ in range(FLICKER_LAYERS):
            layer_text = []
            for r, line in enumerate(lines):
                glitched = glitch_line(line, rng, GLITCH_DENSITY)
                if not glitched.strip():
                    continue
                y = top + r * CELL_H + FONT_SIZE
                layer_text.append(
                    f'<text x="{PAD_X}" y="{y:.1f}" xml:space="preserve">{esc(glitched)}</text>'
                )
            dur = round(rng.uniform(FLICKER_MIN_DUR, FLICKER_MAX_DUR), 2)
            begin = round(WIPE_DURATION + rng.uniform(0, dur), 2)
            on_key = round(FLICKER_ON_FRACTION + rng.uniform(-0.015, 0.015), 3)
            layers.append(
                f'<g opacity="0">{"".join(layer_text)}'
                f'<animate attributeName="opacity" calcMode="discrete" '
                f'values="0;1;0" keyTimes="0;{on_key};1" dur="{dur}s" '
                f'begin="{begin}s" repeatCount="indefinite" /></g>'
            )
        flicker_svg = "".join(layers)

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}"
     viewBox="0 0 {width:.0f} {height:.0f}" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">
  <defs>
    <linearGradient id="wbg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#111722"/>
      <stop offset="1" stop-color="#0d1117"/>
    </linearGradient>
    {clip_def}
  </defs>
  <style>
    text {{
      font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
      font-size: {FONT_SIZE}px;
      fill: {FILL};
      white-space: pre;
    }}
    {clip_style}
  </style>
  <rect width="{width:.0f}" height="{height:.0f}" rx="{CORNER_R}" fill="url(#wbg)"/>
  <rect x="0.5" y="0.5" width="{width - 1:.0f}" height="{height - 1:.0f}" rx="{CORNER_R}" fill="none" stroke="{BORDER}" stroke-width="1"/>
  <line x1="0" y1="{TITLEBAR_H}" x2="{width:.0f}" y2="{TITLEBAR_H}" stroke="{BORDER}"/>
  <circle cx="18" cy="14" r="4.5" fill="#ff5f56"/>
  <circle cx="33" cy="14" r="4.5" fill="#ffbd2e"/>
  <circle cx="48" cy="14" r="4.5" fill="#27c93f"/>
  <text x="{width / 2:.1f}" y="18" fill="{TITLE_TEXT_COLOR}" font-size="11.5" text-anchor="middle">{esc(PROMPT)}</text>
  {group_open}{"".join(text_lines)}{group_close}
  {cursor_svg}
  {flicker_svg}
</svg>
'''
    return svg


def main():
    img = render_flat_text(WORD)
    lines = trim_blank_rows(to_char_grid(img))
    svg = render_svg(lines)
    with open(OUT_PATH, "w") as f:
        f.write(svg)
    print(f"[make_wordmark_svg] wrote {OUT_PATH} ({len(lines)} rows x {COLS} cols, word={WORD!r}, animate={ANIMATE})")


if __name__ == "__main__":
    main()
