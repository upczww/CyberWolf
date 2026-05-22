"""Process individually generated portrait sources into transparent UI PNGs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from scipy import ndimage


ROOT = Path(__file__).resolve().parents[1]
GENERATED_DIR = Path.home() / ".codex" / "generated_images" / "019e45a0-6adc-75c3-9e0c-215143615f7d"
PORTRAIT_ROOT = ROOT / "desktop" / "public" / "assets" / "ui" / "portraits"
CONTACT_SHEET = PORTRAIT_ROOT / "generated_portraits_contact_sheet.png"
REPORT = PORTRAIT_ROOT / "generated_portraits_report.json"

CANVAS_SIZE = (768, 1024)
TARGET_HEIGHT = 860
MAX_WIDTH = 720
SUBJECT_BOTTOM = 972


@dataclass(frozen=True)
class PortraitTarget:
    label: str
    rel_path: str


TARGETS = [
    PortraitTarget("elder_male", "extra/portrait_elder_male_01.png"),
    PortraitTarget("elder_female", "extra/portrait_elder_female_01.png"),
    PortraitTarget("villager_male", "roles/portrait_villager_male_01.png"),
    PortraitTarget("villager_female", "roles/portrait_villager_female_01.png"),
    PortraitTarget("boy", "extra/portrait_boy_01.png"),
    PortraitTarget("girl", "extra/portrait_girl_01.png"),
    PortraitTarget("seer", "roles/portrait_seer_01.png"),
    PortraitTarget("witch", "roles/portrait_witch_01.png"),
    PortraitTarget("hunter", "roles/portrait_hunter_01.png"),
    PortraitTarget("guard", "roles/portrait_guard_01.png"),
    PortraitTarget("werewolf_01", "roles/portrait_werewolf_01.png"),
    PortraitTarget("werewolf_02", "roles/portrait_werewolf_02.png"),
    PortraitTarget("werewolf_03", "roles/portrait_werewolf_03.png"),
    PortraitTarget("werewolf_04", "roles/portrait_werewolf_04.png"),
    PortraitTarget("werewolf_05", "roles/portrait_werewolf_05.png"),
    PortraitTarget("werewolf_06", "roles/portrait_werewolf_06.png"),
]


def generated_sources() -> list[Path]:
    files = sorted(GENERATED_DIR.glob("*.png"), key=lambda path: path.stat().st_mtime)
    if len(files) < len(TARGETS):
        raise RuntimeError(f"Expected at least {len(TARGETS)} generated PNGs, found {len(files)}")
    return files[-len(TARGETS):]


def remove_chroma_key(source: Image.Image) -> Image.Image:
    """Convert a flat chroma-key background to alpha without reshaping pixels."""
    rgb = source.convert("RGB")
    arr = np.asarray(rgb).astype(np.float32)
    corner_samples = np.array(
        [
            arr[0, 0],
            arr[0, -1],
            arr[-1, 0],
            arr[-1, -1],
            arr[0, arr.shape[1] // 2],
            arr[-1, arr.shape[1] // 2],
        ],
        dtype=np.float32,
    )

    green = (arr[..., 1] > 170) & (arr[..., 1] > arr[..., 0] * 1.8) & (arr[..., 1] > arr[..., 2] * 1.8)
    magenta = (arr[..., 0] > 170) & (arr[..., 2] > 170) & (arr[..., 1] < 95)
    key_mask = green | magenta

    if key_mask.mean() > 0.01:
        key = np.median(arr[key_mask], axis=0)
    else:
        key = np.median(corner_samples, axis=0)

    dist_to_key = np.sqrt(np.sum((arr - key) ** 2, axis=2))
    bg_candidate = key_mask | (dist_to_key < 92)

    # Only remove background connected to image borders. This keeps dark armor,
    # robes, hair, and fur intact even when they are color-similar to a corner.
    border_seed = np.zeros(bg_candidate.shape, dtype=bool)
    border_seed[0, :] = bg_candidate[0, :]
    border_seed[-1, :] = bg_candidate[-1, :]
    border_seed[:, 0] = bg_candidate[:, 0]
    border_seed[:, -1] = bg_candidate[:, -1]
    bg_connected = ndimage.binary_propagation(border_seed, mask=bg_candidate)

    transparent_at = 22.0
    opaque_at = 122.0
    alpha = np.full(arr.shape[:2], 255, dtype=np.float32)
    alpha[bg_connected | key_mask | (dist_to_key < 48)] = 0

    # Softly fade pixels that are key-colored but not part of the hard flood
    # mask, which reduces green/magenta halos around hair and fur.
    key_soft_alpha = np.clip((dist_to_key - transparent_at) / (opaque_at - transparent_at), 0, 1) * 255
    edge_zone = (ndimage.binary_dilation(bg_connected, iterations=4) & ~bg_connected) | ((dist_to_key < 150) & ~key_mask)
    alpha[edge_zone] = np.minimum(alpha[edge_zone], key_soft_alpha[edge_zone])

    alpha_img = Image.fromarray(alpha.astype(np.uint8), "L")
    alpha_img = alpha_img.filter(ImageFilter.GaussianBlur(0.45))

    # Despill chroma-key color from semi-transparent edge pixels.
    cleaned = arr.copy()
    if key[1] > key[0] and key[1] > key[2]:
        spill = dist_to_key < 170
        cleaned[..., 1][spill] = np.minimum(cleaned[..., 1][spill], np.maximum(cleaned[..., 0][spill], cleaned[..., 2][spill]) * 1.12)
    elif key[0] > 150 and key[2] > 150:
        spill = dist_to_key < 170
        cleaned[..., 0][spill] = np.minimum(cleaned[..., 0][spill], cleaned[..., 1][spill] * 1.18)
        cleaned[..., 2][spill] = np.minimum(cleaned[..., 2][spill], cleaned[..., 1][spill] * 1.18)

    out = Image.fromarray(np.clip(cleaned, 0, 255).astype(np.uint8), "RGB").convert("RGBA")
    out.putalpha(alpha_img)
    return out


def alpha_bbox(image: Image.Image, threshold: int = 16) -> tuple[int, int, int, int]:
    bbox = image.getchannel("A").point(lambda value: 255 if value > threshold else 0).getbbox()
    if bbox is None:
        raise RuntimeError("No visible subject after chroma-key removal")
    return bbox


def normalize(image: Image.Image) -> Image.Image:
    bbox = alpha_bbox(image)
    subject = image.crop(bbox)
    width, height = subject.size
    scale = TARGET_HEIGHT / height
    resized = subject.resize((round(width * scale), round(height * scale)), Image.Resampling.LANCZOS)
    if resized.width > MAX_WIDTH:
        left = (resized.width - MAX_WIDTH) // 2
        resized = resized.crop((left, 0, left + MAX_WIDTH, resized.height))

    canvas = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
    x = (CANVAS_SIZE[0] - resized.width) // 2
    y = SUBJECT_BOTTOM - resized.height
    canvas.alpha_composite(resized, (x, y))
    return canvas


def save_pair(image: Image.Image, rel_path: str) -> dict[str, object]:
    out = PORTRAIT_ROOT / rel_path
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)
    bust = out.with_name(f"{out.stem}_bust.png")
    image.save(bust)
    bbox = alpha_bbox(image)
    return {
        "path": str(out.relative_to(ROOT)),
        "bust_path": str(bust.relative_to(ROOT)),
        "size": image.size,
        "alpha_bbox": bbox,
        "alpha_width": bbox[2] - bbox[0],
        "alpha_height": bbox[3] - bbox[1],
        "transparent_corners": [
            image.getpixel((0, 0))[3],
            image.getpixel((CANVAS_SIZE[0] - 1, 0))[3],
            image.getpixel((0, CANVAS_SIZE[1] - 1))[3],
            image.getpixel((CANVAS_SIZE[0] - 1, CANVAS_SIZE[1] - 1))[3],
        ],
    }


def make_contact_sheet(paths: list[Path]) -> None:
    thumb_w, thumb_h = 150, 200
    cols = 4
    gap = 22
    label_h = 34
    rows = (len(paths) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * thumb_w + (cols + 1) * gap, rows * (thumb_h + label_h + gap) + gap), (27, 30, 36, 255))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 13)
    except OSError:
        font = ImageFont.load_default()

    checker = Image.new("RGBA", (thumb_w, thumb_h), (51, 56, 66, 255))
    cdraw = ImageDraw.Draw(checker)
    for y in range(0, thumb_h, 16):
        for x in range(0, thumb_w, 16):
            if (x // 16 + y // 16) % 2 == 0:
                cdraw.rectangle((x, y, x + 15, y + 15), fill=(70, 76, 88, 255))

    for index, path in enumerate(paths):
        image = Image.open(path).convert("RGBA")
        image.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
        col = index % cols
        row = index // cols
        x = gap + col * (thumb_w + gap)
        y = gap + row * (thumb_h + label_h + gap)
        sheet.alpha_composite(checker, (x, y))
        sheet.alpha_composite(image, (x + (thumb_w - image.width) // 2, y + (thumb_h - image.height) // 2))
        label = path.stem.replace("portrait_", "").replace("_01", "")
        draw.text((x, y + thumb_h + 7), label[:22], fill=(232, 229, 218, 255), font=font)
    sheet.save(CONTACT_SHEET)


def main() -> None:
    rows: list[dict[str, object]] = []
    output_paths: list[Path] = []
    for source, target in zip(generated_sources(), TARGETS, strict=True):
        final = normalize(remove_chroma_key(Image.open(source)))
        row = save_pair(final, target.rel_path)
        row["label"] = target.label
        row["source"] = str(source)
        rows.append(row)
        output_paths.append(PORTRAIT_ROOT / target.rel_path)

    make_contact_sheet(output_paths)
    REPORT.write_text(
        json.dumps(
            {
                "generated_dir": str(GENERATED_DIR),
                "canvas": CANVAS_SIZE,
                "target_height_without_distortion": TARGET_HEIGHT,
                "max_width_without_distortion": MAX_WIDTH,
                "processed": len(rows),
                "contact_sheet": str(CONTACT_SHEET.relative_to(ROOT)),
                "portraits": rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Processed {len(rows)} generated portraits.")
    print(f"Contact sheet: {CONTACT_SHEET}")
    print(f"Report: {REPORT}")


if __name__ == "__main__":
    main()
