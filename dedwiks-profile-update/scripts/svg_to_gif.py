#!/usr/bin/env python3
"""
Render an animated SVG's timeline to a sequence of screenshots (via a
headless browser, so real SMIL/CSS animation plays exactly as it would in
any browser) and assemble them into an animated GIF.

Why: GitHub sanitizes repo-served SVGs before they reach an <img>-embedded
README, which strips SMIL/CSS animation - confirmed by the animated SVGs
rendering as frozen static images on the live profile. A GIF has no such
restriction (it's a raster format, nothing to sanitize), so baking the
animation down to a GIF is the reliable way to get real motion on GitHub.

Usage:
    python scripts/svg_to_gif.py IN.svg OUT.gif --duration 2.9 --fps 24
"""
import argparse
import os
import re
import sys
import tempfile
import time

from PIL import Image
from playwright.sync_api import sync_playwright

# This sandbox has Chromium pre-installed at a fixed path; CI (and anyone
# else running this) installs its own via `playwright install chromium` and
# should just let Playwright find it, so only override when the env var is
# set (see .github/workflows/update-profile-art.yml, which doesn't set it).
CHROMIUM_PATH = os.environ.get("PLAYWRIGHT_CHROMIUM_PATH", "/opt/pw-browsers/chromium")
_LAUNCH_KWARGS = {"executable_path": CHROMIUM_PATH} if os.path.exists(CHROMIUM_PATH) else {}


def _make_wrapper_html(svg_path, bg):
    """Some of these SVGs are intentionally transparent (designed to sit on
    GitHub's own dark README background), so navigating to the raw .svg
    file directly renders them on the browser's default white page
    background - invisible text. Inline the SVG markup into a small HTML
    wrapper with the right dark backdrop instead. Inlining (not <img>)
    keeps this a same-document embed, so SMIL/CSS animation runs exactly
    as it would standalone - this isn't the cross-origin <img> path that
    GitHub itself blocks."""
    with open(svg_path) as f:
        svg_markup = f.read()
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<style>html,body{{margin:0;padding:0;background:{bg};}}</style>
</head><body>{svg_markup}</body></html>"""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False)
    tmp.write(html)
    tmp.close()
    return tmp.name


def _svg_dims(svg_path):
    with open(svg_path) as f:
        head = f.read(600)
    w = re.search(r'width="(\d+)', head)
    h = re.search(r'height="(\d+)', head)
    return int(w.group(1)), int(h.group(1))


def capture_frames(svg_path, duration, fps, scale=2, bg="#0d1117"):
    n_frames = max(2, round(duration * fps))
    interval = duration / n_frames

    wrapper_path = _make_wrapper_html(svg_path, bg)
    width, height = _svg_dims(svg_path)

    # page.screenshot() itself takes real wall-clock time (PNG encoding of a
    # 2x-scaled capture can run 100-300ms), and the CSS/SMIL clock keeps
    # ticking during that. A naive fixed wait_for_timeout() between shots
    # compounds that overhead and the animation silently races ahead of the
    # frame count, undersampling it. So schedule against a wall-clock
    # target per frame and only wait the remainder, not a fixed interval.
    frames = []
    with sync_playwright() as p:
        browser = p.chromium.launch(**_LAUNCH_KWARGS)
        page = browser.new_page(
            device_scale_factor=scale, viewport={"width": width, "height": height}
        )
        page.goto(f"file://{os.path.abspath(wrapper_path)}")
        page.wait_for_timeout(30)  # let first paint settle

        t0 = time.monotonic()
        for i in range(n_frames):
            target = i * interval
            remaining = target - (time.monotonic() - t0)
            if remaining > 0:
                page.wait_for_timeout(remaining * 1000)
            frames.append(page.screenshot())

        # a couple of extra copies of the final, fully-settled frame so the
        # GIF holds on it instead of cutting off right as motion ends.
        page.wait_for_timeout(150)
        hold_frame = page.screenshot()
        browser.close()

    return frames, hold_frame


def build_gif(frames, hold_frame, out_path, fps, hold_ms=1200):
    import io

    pil_frames = [Image.open(io.BytesIO(f)).convert("RGB") for f in frames]
    pil_frames.append(Image.open(io.BytesIO(hold_frame)).convert("RGB"))

    frame_ms = round(1000 / fps)
    durations = [frame_ms] * (len(pil_frames) - 1) + [hold_ms]

    pil_frames[0].save(
        out_path,
        save_all=True,
        append_images=pil_frames[1:],
        duration=durations,
        loop=1,  # play once, then hold on the last frame (no repeat)
        optimize=True,
        disposal=2,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("svg_path")
    ap.add_argument("out_path")
    ap.add_argument("--duration", type=float, required=True, help="seconds of animation to capture")
    ap.add_argument("--fps", type=float, default=24)
    ap.add_argument("--scale", type=float, default=2, help="device scale factor (sharpness)")
    ap.add_argument("--bg", default="#0d1117", help="page background behind a transparent SVG")
    args = ap.parse_args()

    if not os.path.exists(args.svg_path):
        print(f"missing {args.svg_path}", file=sys.stderr)
        sys.exit(1)

    frames, hold_frame = capture_frames(args.svg_path, args.duration, args.fps, args.scale, args.bg)
    build_gif(frames, hold_frame, args.out_path, args.fps)
    size_kb = os.path.getsize(args.out_path) / 1024
    print(f"[svg_to_gif] wrote {args.out_path} ({len(frames)+1} frames, {size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
