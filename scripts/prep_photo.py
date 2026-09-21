#!/usr/bin/env python3
"""
Prep a source photo for ASCII conversion. Run once per photo (not part of
the daily automation - only the portrait libraries below are needed here).

Three steps, in order:
  1. Remove the background with rembg so the subject is isolated.
  2. Boost local contrast with OpenCV's CLAHE (contrast-limited adaptive
     histogram equalization) - this is what gives a flat, evenly-lit face
     real highlights and shadows instead of converting to a dark blob.
  3. Composite onto pure white so the background maps to the blank end of
     the ASCII ramp (white -> spaces).

Usage:
    python scripts/prep_photo.py source-photo.jpg
Writes:
    source-prepped.png (grayscale, background-removed, contrast-boosted)
"""
import sys
import os

import numpy as np
import cv2
from PIL import Image
from rembg import remove, new_session

OUT_NAME = "source-prepped.png"

# u2net_human_seg is tuned for people and much lighter than rembg's newer
# default (bria-rmbg-2.0, ~1GB) - plenty of quality for a portrait crop.
REMBG_MODEL = os.environ.get("REMBG_MODEL", "u2net_human_seg")


def remove_background(src_path: str) -> Image.Image:
    with open(src_path, "rb") as f:
        input_bytes = f.read()
    session = new_session(REMBG_MODEL)
    output_bytes = remove(input_bytes, session=session)
    from io import BytesIO
    return Image.open(BytesIO(output_bytes)).convert("RGBA")


def boost_contrast(rgba: Image.Image) -> Image.Image:
    """Apply CLAHE on the luminance channel only, keep alpha untouched."""
    arr = np.array(rgba)
    rgb = arr[:, :, :3]
    alpha = arr[:, :, 3]

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    boosted = clahe.apply(gray)

    out = np.dstack([boosted, boosted, boosted, alpha])
    return Image.fromarray(out, mode="RGBA")


def composite_on_white(rgba: Image.Image) -> Image.Image:
    white_bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    composited = Image.alpha_composite(white_bg, rgba)
    return composited.convert("L")  # grayscale


def crop_to_subject(gray: Image.Image, alpha_mask: Image.Image, pad_frac=0.08) -> Image.Image:
    """Crop to the alpha channel's bounding box (the actual subject) plus a
    little padding, so the ASCII grid isn't mostly blank canvas."""
    bbox = alpha_mask.getbbox()
    if bbox is None:
        return gray
    left, top, right, bottom = bbox
    w, h = right - left, bottom - top
    pad_x, pad_y = int(w * pad_frac), int(h * pad_frac)
    left = max(0, left - pad_x)
    top = max(0, top - pad_y)
    right = min(gray.width, right + pad_x)
    bottom = min(gray.height, bottom + pad_y)
    return gray.crop((left, top, right, bottom))


def main():
    if len(sys.argv) < 2:
        print("usage: prep_photo.py <source-photo>", file=sys.stderr)
        sys.exit(1)

    src_path = sys.argv[1]
    if not os.path.exists(src_path):
        print(f"not found: {src_path}", file=sys.stderr)
        sys.exit(1)

    print("[prep_photo] removing background...")
    no_bg = remove_background(src_path)

    print("[prep_photo] boosting local contrast (CLAHE)...")
    contrasty = boost_contrast(no_bg)

    print("[prep_photo] compositing onto white...")
    final = composite_on_white(contrasty)

    print("[prep_photo] cropping to subject...")
    alpha_mask = contrasty.split()[-1]
    final = crop_to_subject(final, alpha_mask)

    out_path = os.path.join(os.path.dirname(__file__), "..", OUT_NAME)
    final.save(out_path)
    print(f"[prep_photo] wrote {out_path} ({final.size[0]}x{final.size[1]})")


if __name__ == "__main__":
    main()
