from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def parse_size(value: str) -> tuple[int, int]:
    parts = value.lower().replace(" ", "").split("x")
    if len(parts) != 2:
        raise ValueError(f"Expected WIDTHxHEIGHT, got {value!r}")
    return int(parts[0]), int(parts[1])


def cover_resize(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    src_w, src_h = img.size
    dst_w, dst_h = size
    scale = max(dst_w / src_w, dst_h / src_h)
    new_size = (round(src_w * scale), round(src_h * scale))
    resized = img.resize(new_size, Image.Resampling.LANCZOS)
    left = max(0, (new_size[0] - dst_w) // 2)
    top = max(0, (new_size[1] - dst_h) // 2)
    return resized.crop((left, top, left + dst_w, top + dst_h))


def contain_resize(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    src_w, src_h = img.size
    dst_w, dst_h = size
    scale = min(dst_w / src_w, dst_h / src_h)
    new_size = (round(src_w * scale), round(src_h * scale))
    resized = img.resize(new_size, Image.Resampling.LANCZOS)
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    out.alpha_composite(resized, ((dst_w - new_size[0]) // 2, (dst_h - new_size[1]) // 2))
    return out


def stretch_resize(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    return img.resize(size, Image.Resampling.LANCZOS)


def remove_green_key(img: Image.Image) -> Image.Image:
    img = img.convert("RGBA")
    pixels = img.load()
    width, height = img.size
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            green_delta = g - max(r, b)
            if g > 150 and green_delta > 55:
                pixels[x, y] = (r, g, b, 0)
            elif g > 115 and green_delta > 32:
                alpha = max(0, min(255, 255 - green_delta * 4))
                pixels[x, y] = (r, min(g, max(r, b) + 8), b, min(a, alpha))
            else:
                pixels[x, y] = (r, g, b, a)
    return img


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare an image_gen output for a manifest asset path.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--size", required=True)
    parser.add_argument("--transparent", action="store_true")
    parser.add_argument("--fit", choices=("cover", "contain", "stretch"), default=None)
    args = parser.parse_args()

    size = parse_size(args.size)
    img = Image.open(args.input)
    fit = args.fit or ("contain" if args.transparent else "cover")
    if args.transparent:
        img = remove_green_key(img)
        if fit == "stretch":
            out = stretch_resize(img, size)
        elif fit == "cover":
            out = cover_resize(img, size)
        else:
            out = contain_resize(img, size)
    else:
        out = stretch_resize(img.convert("RGBA"), size) if fit == "stretch" else cover_resize(img.convert("RGBA"), size)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    out.save(args.out, "PNG")
    print(args.out)


if __name__ == "__main__":
    main()
