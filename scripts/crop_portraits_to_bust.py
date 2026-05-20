"""Crop all role portraits to bust (head + chest) using their alpha bbox.

Input:  desktop/public/assets/ui/portraits/roles/portrait_*_01.png
        desktop/public/assets/ui/portraits/extra/portrait_*_01.png
        desktop/public/assets/ui/portraits/unknown/portrait_*_01.png
Output: same folder, *_bust.png

Algorithm: find the subject's alpha bounding box, then keep top +
BUST_RATIO * subject_height. Default 0.55 → roughly head + chest.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PORTRAIT_DIRS = [
    ROOT / "desktop" / "public" / "assets" / "ui" / "portraits" / "roles",
    ROOT / "desktop" / "public" / "assets" / "ui" / "portraits" / "extra",
    ROOT / "desktop" / "public" / "assets" / "ui" / "portraits" / "unknown",
]

ALPHA_THRESHOLD = 16
BUST_RATIO = 0.55  # top fraction of subject to keep (head + chest)


def alpha_bbox(img: Image.Image) -> tuple[int, int, int, int] | None:
    """Tight bounding box of non-transparent pixels."""
    alpha = img.split()[-1]
    width, height = alpha.size
    px = alpha.load()
    min_x, min_y, max_x, max_y = width, height, -1, -1
    for y in range(height):
        row_has = False
        for x in range(width):
            if px[x, y] >= ALPHA_THRESHOLD:
                if x < min_x: min_x = x
                if x > max_x: max_x = x
                row_has = True
        if row_has:
            if y < min_y: min_y = y
            if y > max_y: max_y = y
    if max_x < 0:
        return None
    return (min_x, min_y, max_x + 1, max_y + 1)


def crop_to_bust(src: Path, dst: Path) -> tuple[int, int] | None:
    img = Image.open(src).convert("RGBA")
    bbox = alpha_bbox(img)
    if bbox is None:
        return None
    left, top, right, bottom = bbox
    subject_h = bottom - top
    new_bottom = top + int(round(subject_h * BUST_RATIO))
    # Crop tighter and trim residual transparent margin (re-check alpha bbox).
    cropped = img.crop((left, top, right, new_bottom))
    bbox2 = alpha_bbox(cropped)
    if bbox2 is not None:
        cropped = cropped.crop(bbox2)
    cropped.save(dst, optimize=True)
    return cropped.size


def main() -> int:
    targets: list[Path] = []
    for dir_ in PORTRAIT_DIRS:
        if not dir_.exists():
            continue
        for p in sorted(dir_.glob("portrait_*_01.png")):
            if p.stem.endswith("_bust"):
                continue
            targets.append(p)
    if not targets:
        print("no source portraits found", file=sys.stderr)
        return 1
    for src in targets:
        dst = src.with_name(src.stem + "_bust.png")
        size = crop_to_bust(src, dst)
        if size is None:
            print(f"skip (empty alpha): {src.name}")
        else:
            print(f"{src.parent.name}/{src.name}  →  {dst.name}  {size[0]}x{size[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
