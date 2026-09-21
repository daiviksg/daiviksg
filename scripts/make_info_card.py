#!/usr/bin/env python3
"""
Hand-author a neofetch-style info card SVG: a title bar, then colored
key/value rows that fade + slide in on a short stagger, like the panel is
printing next to the ASCII portrait.

Content lives in ROWS below - edit it directly whenever role/stack/goals
change.

IMPORTANT: GitHub serves repo-committed SVGs (raw.githubusercontent.com,
and CDN mirrors like jsdelivr) with response headers that block SMIL/CSS
animation for cross-origin <img>-embedded SVGs - which is exactly how a
README references these files. So the README embed always shows the
*first* animation frame, frozen. Renders fully-visible by default so the
README looks correct; set ANIMATE=1 to get the fade-in version instead,
for contexts that DO run it (opening the raw SVG file directly in a
browser tab, or embedding it same-origin).
"""
import os

OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "info-card.svg")

WIDTH = 490
PROMPT = "dedwiks@github"

# (label, value) rows - the neofetch-style content. Keep this to the
# "story numbers can't tell" - the heatmap already covers raw GitHub stats.
ROWS = [
    ("Role", "Software Development Engineer"),
    ("Base", "Bengaluru, IN"),
    ("Stack", "Python · ML · Web · UI/Design · Automation"),
    ("Focus", "Freelance clients + remote FTE roles"),
    ("Style", "Full-stack · production-first · self-directed"),
]

# Neofetch-ish accent palette: label color cycles through these.
ACCENTS = ["#39d353", "#58a6ff", "#e3b341", "#bc8cff", "#f78166", "#39d353"]

FG = "#c9d1d9"
MUTED = "#8b949e"
BG = "#0d1117"
PANEL = "#010409"
BORDER = "#30363d"

ROW_HEIGHT = 30
TOP_PAD = 90          # title bar + prompt line + divider + gap
BOTTOM_PAD = 26
LEFT_PAD = 26
LABEL_WIDTH = 90

ANIMATE = os.environ.get("ANIMATE") == "1"


def esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def render():
    height = TOP_PAD + len(ROWS) * ROW_HEIGHT + BOTTOM_PAD

    style_extra = ""
    if not ANIMATE:
        # Default: skip the animation, render the final state directly.
        # (See module docstring - GitHub won't play it in the README anyway.)
        style_extra = ".line { opacity: 1 !important; transform: none !important; }"

    rows_svg = []
    for i, (label, value) in enumerate(ROWS):
        y = TOP_PAD + i * ROW_HEIGHT
        accent = ACCENTS[i % len(ACCENTS)]
        delay = round(0.15 + i * 0.14, 3)
        rows_svg.append(
            f'<g class="line" style="animation-delay:{delay}s">'
            f'<text x="{LEFT_PAD}" y="{y}" fill="{accent}" font-weight="600">{esc(label)}</text>'
            f'<text x="{LEFT_PAD + LABEL_WIDTH}" y="{y}" fill="{FG}">{esc(value)}</text>'
            f'</g>'
        )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}"
     viewBox="0 0 {WIDTH} {height}"
     font-family="'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace" font-size="13">
  <style>
    .line {{
      opacity: 0;
      transform: translateX(-8px);
      animation: line-in 0.4s ease-out forwards;
    }}
    @keyframes line-in {{
      to {{ opacity: 1; transform: translateX(0); }}
    }}
    .title {{ fill: {FG}; font-weight: 600; }}
    .prompt-muted {{ fill: {MUTED}; }}
    {style_extra}
  </style>

  <rect x="0" y="0" width="{WIDTH}" height="{height}" rx="8" ry="8" fill="{PANEL}" stroke="{BORDER}" />

  <!-- title bar -->
  <rect x="0" y="0" width="{WIDTH}" height="34" rx="8" ry="8" fill="{BG}" />
  <rect x="0" y="20" width="{WIDTH}" height="14" fill="{BG}" />
  <circle cx="20" cy="17" r="5" fill="#ff5f56" />
  <circle cx="38" cy="17" r="5" fill="#ffbd2e" />
  <circle cx="56" cy="17" r="5" fill="#27c93f" />
  <text x="{WIDTH / 2}" y="21" text-anchor="middle" class="prompt-muted">neofetch</text>

  <text x="{LEFT_PAD}" y="52" class="title">{esc(PROMPT)}</text>
  <line x1="{LEFT_PAD}" y1="64" x2="{WIDTH - LEFT_PAD}" y2="64" stroke="{BORDER}" stroke-width="1" />

  {"".join(rows_svg)}
</svg>
'''
    return svg


def main():
    svg = render()
    with open(OUT_PATH, "w") as f:
        f.write(svg)
    print(f"[make_info_card] wrote {OUT_PATH} ({len(svg)} bytes, animate={ANIMATE})")


if __name__ == "__main__":
    main()
