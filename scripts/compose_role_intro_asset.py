from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

def trim_alpha(image: Image.Image) -> Image.Image:
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        return image
    return image.crop(bbox)


def fit_portrait(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    image = trim_alpha(image)
    src_w, src_h = image.size
    dst_w, dst_h = size
    scale = min(dst_w / src_w, dst_h / src_h)
    return image.resize((round(src_w * scale), round(src_h * scale)), Image.Resampling.LANCZOS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compose a role intro card from generated bitmap base and portrait.")
    parser.add_argument("--base", required=True, type=Path)
    parser.add_argument("--portrait", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    card = Image.open(args.base).convert("RGBA").resize((900, 1200), Image.Resampling.LANCZOS)
    if args.portrait:
        portrait = Image.open(args.portrait).convert("RGBA")
        portrait = fit_portrait(portrait, (470, 560))
        x = (900 - portrait.width) // 2
        y = 690 - portrait.height
        card.alpha_composite(portrait, (x, y))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    card.save(args.out, "PNG")
    print(args.out)


if __name__ == "__main__":
    main()
