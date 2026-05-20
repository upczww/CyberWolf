"""Split desktop/public/assets/ui/portraits/extra/landing_roles.png into two
transparent PNGs (left + right figure), each cropped to its alpha bounding box.

Outputs:
  desktop/public/assets/ui/portraits/extra/landing_role_personal.png
  desktop/public/assets/ui/portraits/extra/landing_role_god.png
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ALPHA_THRESHOLD = 16

SRC = Path(__file__).resolve().parent.parent / "desktop" / "public" / "assets" / "ui" / "portraits" / "extra" / "landing_roles.png"
OUT_DIR = SRC.parent


def alpha_columns_active(alpha) -> list[bool]:
    """Return per-column booleans: True if any pixel in that column has alpha >= threshold."""
    width, height = alpha.size
    active = [False] * width
    px = alpha.load()
    for x in range(width):
        col_active = False
        for y in range(height):
            if px[x, y] >= ALPHA_THRESHOLD:
                col_active = True
                break
        active[x] = col_active
    return active


def find_split_column(active: list[bool]) -> int:
    """Locate the widest run of inactive columns between the two figures."""
    width = len(active)
    runs: list[tuple[int, int]] = []  # (start, length)
    start = None
    for i, a in enumerate(active):
        if not a:
            if start is None:
                start = i
        else:
            if start is not None:
                runs.append((start, i - start))
                start = None
    if start is not None:
        runs.append((start, width - start))
    # Exclude leading and trailing runs; pick the longest interior gap.
    interior = [r for r in runs if r[0] > 0 and r[0] + r[1] < width]
    if not interior:
        raise RuntimeError("could not find a transparent gap between figures")
    interior.sort(key=lambda r: r[1], reverse=True)
    start, length = interior[0]
    return start + length // 2


def crop_to_alpha_bbox(img: Image.Image) -> Image.Image | None:
    alpha = img.split()[-1]
    width, height = alpha.size
    px = alpha.load()
    min_x, min_y, max_x, max_y = width, height, -1, -1
    for y in range(height):
        for x in range(width):
            if px[x, y] >= ALPHA_THRESHOLD:
                if x < min_x: min_x = x
                if x > max_x: max_x = x
                if y < min_y: min_y = y
                if y > max_y: max_y = y
    if max_x < 0:
        return None
    return img.crop((min_x, min_y, max_x + 1, max_y + 1))


def main() -> int:
    if not SRC.exists():
        print(f"missing: {SRC}", file=sys.stderr)
        return 1
    img = Image.open(SRC).convert("RGBA")
    width, height = img.size
    print(f"loaded {SRC.name}  {width}x{height} RGBA")

    alpha = img.split()[-1]
    active = alpha_columns_active(alpha)
    split = find_split_column(active)
    print(f"split column: {split}")

    left = img.crop((0, 0, split, height))
    right = img.crop((split, 0, width, height))

    left_cropped = crop_to_alpha_bbox(left)
    right_cropped = crop_to_alpha_bbox(right)
    if left_cropped is None or right_cropped is None:
        print("one of the halves was empty", file=sys.stderr)
        return 2

    out_personal = OUT_DIR / "landing_role_personal.png"
    out_god = OUT_DIR / "landing_role_god.png"
    left_cropped.save(out_personal, optimize=True)
    right_cropped.save(out_god, optimize=True)
    print(f"saved  {out_personal.name}  {left_cropped.size}")
    print(f"saved  {out_god.name}  {right_cropped.size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
