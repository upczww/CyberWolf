from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

from prepare_imagegen_asset import contain_resize, remove_green_key


def main() -> None:
    parser = argparse.ArgumentParser(description="Split an image_gen icon grid into transparent PNG assets.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--rows", required=True, type=int)
    parser.add_argument("--cols", required=True, type=int)
    parser.add_argument("--out", required=True, nargs="+")
    parser.add_argument("--size", default="256x256")
    parser.add_argument("--transparent", action="store_true")
    args = parser.parse_args()

    w, h = (int(part) for part in args.size.lower().split("x"))
    img = Image.open(args.input).convert("RGBA")
    if args.transparent:
        img = remove_green_key(img)

    cell_w = img.width / args.cols
    cell_h = img.height / args.rows
    for index, out_text in enumerate(args.out):
        row = index // args.cols
        col = index % args.cols
        if row >= args.rows:
            break
        box = (
            round(col * cell_w),
            round(row * cell_h),
            round((col + 1) * cell_w),
            round((row + 1) * cell_h),
        )
        cell = img.crop(box)
        final = contain_resize(cell, (w, h))
        out = Path(out_text)
        out.parent.mkdir(parents=True, exist_ok=True)
        final.save(out, "PNG")
        print(out)


if __name__ == "__main__":
    main()
