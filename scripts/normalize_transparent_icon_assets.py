from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "desktop" / "werewolf_asset_manifest_v5.json"
ASSET_ROOT = ROOT / "desktop" / "public"


def parse_size(value: str | None) -> tuple[int, int] | None:
    if not value:
        return None
    import re

    nums = [int(item) for item in re.findall(r"\d+", value)]
    if len(nums) < 2:
        return None
    return nums[0], nums[1]


def bbox_from_alpha(img: Image.Image, threshold: int) -> tuple[int, int, int, int] | None:
    alpha = img.getchannel("A")
    mask = alpha.point(lambda value: 255 if value > threshold else 0)
    return mask.getbbox()


def clean_alpha_and_despill(img: Image.Image, threshold: int) -> Image.Image:
    img = img.convert("RGBA")
    pixels = img.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = pixels[x, y]
            if g > 145 and r < 95 and b < 120 and g > r + 45 and g > b + 35:
                pixels[x, y] = (0, 0, 0, 0)
                continue
            if a <= threshold:
                pixels[x, y] = (0, 0, 0, 0)
                continue

            green_delta = g - max(r, b)
            if g > 110 and green_delta > 24:
                g = min(g, max(r, b) + 6)
            pixels[x, y] = (r, g, b, a)
    return img


def remove_stray_components(img: Image.Image, threshold: int, min_ratio: float) -> Image.Image:
    alpha = img.getchannel("A")
    pixels = alpha.load()
    width, height = img.size
    seen: set[tuple[int, int]] = set()
    components: list[list[tuple[int, int]]] = []

    for y in range(height):
        for x in range(width):
            if (x, y) in seen or pixels[x, y] <= threshold:
                continue
            stack = [(x, y)]
            seen.add((x, y))
            component = []
            while stack:
                cx, cy = stack.pop()
                component.append((cx, cy))
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < width and 0 <= ny < height and (nx, ny) not in seen and pixels[nx, ny] > threshold:
                        seen.add((nx, ny))
                        stack.append((nx, ny))
            components.append(component)

    if not components:
        return img

    largest = max(len(component) for component in components)
    keep: set[tuple[int, int]] = set()
    for component in components:
        if len(component) >= largest * min_ratio:
            keep.update(component)

    out = img.copy()
    out_pixels = out.load()
    for y in range(height):
        for x in range(width):
            if pixels[x, y] > threshold and (x, y) not in keep:
                out_pixels[x, y] = (0, 0, 0, 0)
    return out


def normalize_icon(
    path: Path,
    size: tuple[int, int],
    padding_ratio: float,
    threshold: int,
    min_component_ratio: float,
) -> dict[str, object]:
    img = Image.open(path).convert("RGBA")
    img = clean_alpha_and_despill(img, threshold)
    img = remove_stray_components(img, threshold, min_component_ratio)
    bbox = bbox_from_alpha(img, threshold)
    if bbox is None:
        return {"path": str(path), "changed": False, "reason": "empty-alpha"}

    crop = img.crop(bbox)
    target_w = max(1, round(size[0] * (1 - padding_ratio * 2)))
    target_h = max(1, round(size[1] * (1 - padding_ratio * 2)))
    scale = min(target_w / crop.width, target_h / crop.height)
    resized = crop.resize(
        (max(1, round(crop.width * scale)), max(1, round(crop.height * scale))),
        Image.Resampling.LANCZOS,
    )

    out = Image.new("RGBA", size, (0, 0, 0, 0))
    x = (size[0] - resized.width) // 2
    y = (size[1] - resized.height) // 2
    out.alpha_composite(resized, (x, y))
    out.save(path, "PNG")

    after = bbox_from_alpha(out, threshold)
    return {
        "path": str(path),
        "changed": True,
        "before_bbox": bbox,
        "after_bbox": after,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Trim, center, and rescale transparent icon-like manifest assets.")
    parser.add_argument("--type", default="icon", help="Manifest resource type to normalize.")
    parser.add_argument("--padding-ratio", type=float, default=0.08)
    parser.add_argument("--alpha-threshold", type=int, default=18)
    parser.add_argument("--min-component-ratio", type=float, default=0.015)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    results = []
    for resource in manifest["resources"]:
        if resource.get("type") != args.type or resource.get("transparent") is not True:
            continue
        size = parse_size(resource.get("size"))
        path = ASSET_ROOT / resource["full_path"]
        if not path.exists():
            continue
        if size is None:
            size = Image.open(path).size
        results.append(
            normalize_icon(
                path,
                size,
                args.padding_ratio,
                args.alpha_threshold,
                args.min_component_ratio,
            )
        )

    summary = {
        "type": args.type,
        "processed": len(results),
        "changed": sum(1 for item in results if item.get("changed")),
        "results": results,
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("type", "processed", "changed")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
