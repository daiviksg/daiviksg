#!/usr/bin/env python3
"""
Fetch a GitHub user's public contribution calendar without a token.

GitHub serves the calendar as an HTML fragment at:
    https://github.com/users/<username>/contributions
(the same fragment the profile page itself embeds). We parse the day
cells with BeautifulSoup and write out raw days plus a few derived
stats (current streak, longest streak, best day, monthly totals).
"""
import json
import os
import sys
from datetime import datetime, date

import requests
from bs4 import BeautifulSoup

USERNAME = os.environ.get("GITHUB_PROFILE_USERNAME", "dedwiks")
URL = f"https://github.com/users/{USERNAME}/contributions"
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "contributions.json")

HEADERS = {
    # A normal browser UA avoids GitHub serving a stripped-down response.
    "User-Agent": (
        "Mozilla/5.0 (compatible; profile-readme-bot/1.0; "
        "+https://github.com/{u})".format(u=USERNAME)
    )
}


def fetch_html(username: str) -> str:
    resp = requests.get(
        f"https://github.com/users/{username}/contributions",
        headers=HEADERS,
        timeout=20,
    )
    resp.raise_for_status()
    return resp.text


def parse_days(html: str):
    soup = BeautifulSoup(html, "html.parser")
    days = []

    # GitHub has shipped a couple of markup variants over the years:
    # older: <td class="ContributionCalendar-day" data-date="..." data-level="...">
    # newer: <table>...<tool-tip>; cells are <td> with data-date + data-level attrs.
    cells = soup.select("td.ContributionCalendar-day[data-date]")
    if not cells:
        # Fallback: any element carrying a data-date + data-level pair.
        cells = soup.select("[data-date][data-level]")

    for cell in cells:
        d = cell.get("data-date")
        level_raw = cell.get("data-level")
        if d is None or level_raw is None:
            continue
        try:
            level = int(level_raw)
        except ValueError:
            continue

        # Contribution count is usually in the accessible tooltip text
        # ("5 contributions on Monday, ..."), referenced via aria-label
        # on newer markup or a linked <tool-tip> element on older markup.
        count = 0
        aria = cell.get("aria-label", "")
        tooltip_id = cell.get("id")
        tooltip_text = aria
        if not tooltip_text and tooltip_id:
            tt = soup.find(attrs={"for": tooltip_id})
            if tt:
                tooltip_text = tt.get_text(strip=True)
        if tooltip_text:
            head = tooltip_text.split()[0].replace(",", "")
            if head.isdigit():
                count = int(head)
            elif "No contributions" in tooltip_text:
                count = 0

        days.append({"date": d, "level": level, "count": count})

    days.sort(key=lambda x: x["date"])
    return days


def compute_stats(days):
    if not days:
        return {
            "total": 0,
            "current_streak": 0,
            "longest_streak": 0,
            "best_day": None,
            "monthly": {},
        }

    total = sum(d["count"] for d in days)

    # Streaks (consecutive days with count > 0), walking chronologically.
    longest = 0
    current = 0
    running = 0
    today = date.today()
    for i, d in enumerate(days):
        if d["count"] > 0:
            running += 1
            longest = max(longest, running)
        else:
            running = 0

    # Current streak: walk backwards from the most recent day.
    for d in reversed(days):
        if d["count"] > 0:
            current += 1
        else:
            break

    best_day = max(days, key=lambda x: x["count"])
    if best_day["count"] == 0:
        best_day = None

    monthly = {}
    for d in days:
        month_key = d["date"][:7]  # YYYY-MM
        monthly[month_key] = monthly.get(month_key, 0) + d["count"]

    return {
        "total": total,
        "current_streak": current,
        "longest_streak": longest,
        "best_day": best_day,
        "monthly": monthly,
    }


def main():
    username = USERNAME
    if len(sys.argv) > 1:
        username = sys.argv[1]

    try:
        html = fetch_html(username)
        days = parse_days(html)
    except Exception as exc:
        print(f"[fetch_contributions] failed to fetch/parse: {exc}", file=sys.stderr)
        days = []

    if not days:
        print(
            "[fetch_contributions] no contribution cells parsed - "
            "writing empty calendar so downstream rendering still succeeds",
            file=sys.stderr,
        )

    stats = compute_stats(days)

    payload = {
        "username": username,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "days": days,
        "stats": stats,
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"[fetch_contributions] wrote {len(days)} days -> {OUT_PATH}")
    print(f"[fetch_contributions] total={stats['total']} "
          f"current_streak={stats['current_streak']} "
          f"longest_streak={stats['longest_streak']}")


if __name__ == "__main__":
    main()
