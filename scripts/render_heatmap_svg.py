#!/usr/bin/env python3
"""
Render data/contributions.json as a 53-week x 7-day contribution heatmap SVG.

Design:
  - Rounded boxes in a GitHub-ish green ramp (PALETTE below).
  - A diagonal, line-after-line slide-down reveal via CSS keyframes that
    plays once on load and freezes (no infinite "glow" looping).
  - A Less -> More legend and a stats footer line.
  - Pure SVG + <style> (CSS keyframes) - no JS, no external assets, so it
    plays fine embedded via <img> on a GitHub README.
"""
import json
import os
from datetime import date, timedelta

# Confirmed live on GitHub (same as the other cards) that CSS/SMIL
# animation in an <img>-embedded README SVG does play - the earlier
# assumption that GitHub strips it was wrong. Animates by default; set
# ANIMATE=0 for a static fallback if ever needed.
ANIMATE = os.environ.get("ANIMATE", "1") == "1"

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "contributions.json")
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "contrib-heatmap.svg")

# none -> brightest (level 5 is a neon top end reserved for standout days)
PALETTE = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353", "#69f0a0"]

BOX = 12
GAP = 3
PITCH = BOX + GAP
LEFT_PAD = 32       # room for Mon/Wed/Fri labels
TOP_PAD = 20         # room for month labels
RIGHT_PAD = 33       # sized so total width lands on 860 (matches the README's two-column width)
BOTTOM_PAD = 34       # room for legend + stats footer
WEEKS = 53
DAYS = 7

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DAY_LABELS = {1: "Mon", 3: "Wed", 5: "Fri"}  # row index -> label (Sun=0)


def load_data():
    with open(DATA_PATH) as f:
        return json.load(f)


def build_grid(days):
    """Bucket days into a 53-week x 7-day grid aligned like GitHub (weeks
    start Sunday). Returns {(col, row): day_dict}."""
    if not days:
        return {}, None

    parsed = [
        {**d, "_date": date.fromisoformat(d["date"])}
        for d in days
    ]
    parsed.sort(key=lambda x: x["_date"])
    last_date = parsed[-1]["_date"]

    # Grid ends on the Saturday of the week containing last_date, and spans
    # WEEKS columns backwards from there (53 weeks ~ 371 days, matches the
    # blog's 53-week x 7-day layout).
    end_dow = (last_date.weekday() + 1) % 7  # convert Mon=0..Sun=6 -> Sun=0..Sat=6
    grid_end = last_date + timedelta(days=(6 - end_dow))
    grid_start = grid_end - timedelta(days=WEEKS * DAYS - 1)

    by_date = {d["_date"]: d for d in parsed}

    grid = {}
    d = grid_start
    col = 0
    while d <= grid_end:
        row = (d.weekday() + 1) % 7  # Sun=0 .. Sat=6
        entry = by_date.get(d)
        grid[(col, row)] = entry  # may be None for days outside our data range
        if row == 6:
            col += 1
        d += timedelta(days=1)

    return grid, grid_start


def neon_threshold(days):
    counts = sorted((d["count"] for d in days if d["count"] > 0), reverse=True)
    if not counts:
        return None
    top_n = max(1, len(counts) // 20)  # top ~5%
    return counts[top_n - 1]


def level_for(entry, threshold):
    if entry is None or entry["count"] == 0:
        return 0
    lvl = min(entry.get("level", 0), 4)
    if threshold is not None and entry["count"] >= threshold and lvl >= 4:
        return 5
    return max(lvl, 1)


def month_label_positions(grid, grid_start):
    """Return {col: 'Mon'} for the first column where a new month starts."""
    labels = {}
    seen_months = set()
    for col in range(WEEKS):
        d = grid.get((col, 0))
        day_date = date.fromisoformat(d["date"]) if d else (
            grid_start + timedelta(days=col * DAYS)
        )
        key = (day_date.year, day_date.month)
        if key not in seen_months:
            seen_months.add(key)
            labels[col] = MONTHS[day_date.month - 1]
    return labels


def render(payload):
    days = payload["days"]
    stats = payload["stats"]
    grid, grid_start = build_grid(days)
    threshold = neon_threshold(days)

    width = LEFT_PAD + WEEKS * PITCH + RIGHT_PAD
    height = TOP_PAD + DAYS * PITCH + BOTTOM_PAD

    month_labels = month_label_positions(grid, grid_start) if grid_start else {}

    month_svg = "\n".join(
        f'<text x="{LEFT_PAD + col * PITCH}" y="{TOP_PAD - 7}" '
        f'class="month-label">{label}</text>'
        for col, label in month_labels.items()
    )

    day_svg = "\n".join(
        f'<text x="{LEFT_PAD - 6}" y="{TOP_PAD + row * PITCH + BOX - 1}" '
        f'class="day-label" text-anchor="end">{label}</text>'
        for row, label in DAY_LABELS.items()
    )

    # Diagonal stagger: cell delay depends on (col + row); we approximate
    # per-cell timing with 40 CSS animation-delay buckets so file size stays
    # small (one @keyframes block, N tiny delay rules) rather than 371
    # inline styles.
    max_diag = (WEEKS - 1) + (DAYS - 1)
    bucket_count = 40
    delay_rules = []
    for b in range(bucket_count):
        diag_frac = b / bucket_count
        delay = round(diag_frac * 1.6, 3)  # total sweep ~1.6s across the grid
        delay_rules.append(f".d{b} {{ animation-delay: {delay}s; }}")

    # Each cell's animation-delay bucket comes from its diagonal position
    # (col + row), so the reveal sweeps top-left -> bottom-right.
    cells = []
    for col in range(WEEKS):
        for row in range(DAYS):
            entry = grid.get((col, row))
            lvl = level_for(entry, threshold)
            x = LEFT_PAD + col * PITCH
            y = TOP_PAD + row * PITCH
            fill = PALETTE[lvl]
            diag = col + row
            bucket = int((diag / max_diag) * (bucket_count - 1)) if max_diag else 0
            title = ""
            if entry:
                title = f"{entry['count']} contributions on {entry['date']}"
            cells.append(
                f'<rect class="cell d{bucket}" x="{x}" y="{y}" width="{BOX}" height="{BOX}" '
                f'rx="2" ry="2" fill="{fill}"><title>{title}</title></rect>'
            )

    legend_x = width - RIGHT_PAD - (5 * (BOX + 4)) - 34
    legend_y = TOP_PAD + DAYS * PITCH + 16
    legend_swatches = "\n".join(
        f'<rect x="{legend_x + 30 + i * (BOX + 4)}" y="{legend_y - BOX + 2}" '
        f'width="{BOX}" height="{BOX}" rx="2" ry="2" fill="{PALETTE[i]}" />'
        for i in range(5)
    )

    total = stats.get("total", 0)
    current_streak = stats.get("current_streak", 0)
    longest_streak = stats.get("longest_streak", 0)
    footer = (
        f"{total:,} contributions in the last year  ·  "
        f"current streak {current_streak}d  ·  longest streak {longest_streak}d"
    )

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"
     viewBox="0 0 {width} {height}" font-family="'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace">
  <style>
    text {{ fill: #8b949e; font-size: 10px; }}
    .month-label {{ fill: #8b949e; }}
    .day-label {{ fill: #8b949e; }}
    .legend-label {{ fill: #8b949e; font-size: 10px; }}
    .footer {{ fill: #8b949e; font-size: 11px; }}
    {"" if not ANIMATE else """
    .cell {
      opacity: 0;
      transform: translateY(-6px);
      transform-box: fill-box;
      transform-origin: center;
      animation: reveal 0.5s ease-out forwards;
    }
    @keyframes reveal {
      to { opacity: 1; transform: translateY(0); }
    }
    """}
    {" ".join(delay_rules) if ANIMATE else ""}
  </style>
  <rect x="0" y="0" width="{width}" height="{height}" fill="#0d1117" />
  {month_svg}
  {day_svg}
  {"".join(cells)}
  <text x="{legend_x}" y="{legend_y + 3}" class="legend-label">Less</text>
  {legend_swatches}
  <text x="{legend_x + 30 + 5 * (BOX + 4) + 6}" y="{legend_y + 3}" class="legend-label">More</text>
  <text x="{LEFT_PAD}" y="{height - 8}" class="footer">{footer}</text>
</svg>
'''
    return svg


def main():
    payload = load_data()
    svg = render(payload)
    with open(OUT_PATH, "w") as f:
        f.write(svg)
    print(f"[render_heatmap_svg] wrote {OUT_PATH} ({len(svg)} bytes)")


if __name__ == "__main__":
    main()
