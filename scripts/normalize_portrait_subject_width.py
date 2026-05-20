from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw


CANVAS_SIZE = (768, 1024)


def alpha_bbox(image: Image.Image) -> tuple[int, int, int, int] | None:
    return image.getchannel("A").getbbox()


def body_bbox(image: Image.Image, threshold_alpha: int = 24) -> tuple[int, int, int, int]:
    """Estimate the body mass bbox while ignoring thin props and wispy edges."""
    alpha = image.getchannel("A")
    pix = alpha.load()
    width, height = image.size

    column_counts: list[int] = []
    row_counts: list[int] = []
    for x in range(width):
      column_counts.append(sum(1 for y in range(height) if pix[x, y] > threshold_alpha))
    for y in range(height):
      row_counts.append(sum(1 for x in range(width) if pix[x, y] > threshold_alpha))

    max_col = max(column_counts) or 1
    max_row = max(row_counts) or 1

    def smooth(values: list[int], radius: int) -> list[float]:
        out: list[float] = []
        for idx in range(len(values)):
            lo = max(0, idx - radius)
            hi = min(len(values), idx + radius + 1)
            out.append(sum(values[lo:hi]) / (hi - lo))
        return out

    smooth_cols = smooth(column_counts, 4)
    smooth_rows = smooth(row_counts, 4)
    col_threshold = max(18, max_col * 0.18)
    row_threshold = max(18, max_row * 0.10)

    xs = [idx for idx, value in enumerate(smooth_cols) if value >= col_threshold]
    ys = [idx for idx, value in enumerate(smooth_rows) if value >= row_threshold]
    full = alpha_bbox(image)
    if not full:
        return (0, 0, width, height)
    if not xs:
        xs = list(range(full[0], full[2]))
    if not ys:
        ys = list(range(full[1], full[3]))
    return (min(xs), min(ys), max(xs) + 1, max(ys) + 1)


def normalize_portrait(
    image: Image.Image,
    target_body_width: int,
    target_full_height: int,
    body_right: int,
    bottom: int,
    min_x_scale: float,
    max_x_scale: float,
) -> Image.Image:
    image = image.convert("RGBA")
    full = alpha_bbox(image)
    if not full:
        return Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))

    body = body_bbox(image)
    crop = image.crop(full)
    rel_body = (
        body[0] - full[0],
        body[1] - full[1],
        body[2] - full[0],
        body[3] - full[1],
    )

    crop_w, crop_h = crop.size
    body_w = max(1, rel_body[2] - rel_body[0])
    y_scale = min(1.0, target_full_height / crop_h)
    x_scale = target_body_width / (body_w * y_scale)
    x_scale = max(min_x_scale, min(max_x_scale, x_scale))

    new_w = max(1, round(crop_w * y_scale * x_scale))
    new_h = max(1, round(crop_h * y_scale))
    resized = crop.resize((new_w, new_h), Image.Resampling.LANCZOS)

    scaled_body_left = round(rel_body[0] * y_scale * x_scale)
    scaled_body_right = round(rel_body[2] * y_scale * x_scale)
    scaled_full_right_offset = new_w - scaled_body_right

    x = body_right - scaled_body_right
    y = bottom - new_h

    # Keep the whole visible subject on-canvas while preserving the body-right line when possible.
    if x < 0:
        x = 0
    if x + new_w > CANVAS_SIZE[0]:
        x = max(0, CANVAS_SIZE[0] - new_w)
    if y < 0:
        y = 0
    if y + new_h > CANVAS_SIZE[1]:
        y = max(0, CANVAS_SIZE[1] - new_h)

    out = Image.new("RGBA", CANVAS_SIZE, (0, 0, 0, 0))
    out.alpha_composite(resized, (x, y))
    return out


def make_contact_sheet(paths: list[Path], out_path: Path) -> None:
    thumb_w, thumb_h, cols = 220, 300, 5
    rows = (len(paths) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * thumb_w, rows * thumb_h), (18, 24, 34, 255))
    draw = ImageDraw.Draw(sheet)
    for idx, path in enumerate(paths):
        image = Image.open(path).convert("RGBA")
        bbox = alpha_bbox(image)
        if bbox:
            crop = image.crop(bbox)
            scale = min((thumb_w - 20) / crop.width, (thumb_h - 48) / crop.height)
            crop = crop.resize((round(crop.width * scale), round(crop.height * scale)), Image.Resampling.LANCZOS)
            x = (idx % cols) * thumb_w + (thumb_w - crop.width) // 2
            y = (idx // cols) * thumb_h + thumb_h - 34 - crop.height
            sheet.alpha_composite(crop, (x, y))
        draw.text(
            ((idx % cols) * thumb_w + 10, (idx // cols) * thumb_h + thumb_h - 24),
            path.stem.replace("portrait_", ""),
            fill=(230, 235, 245, 255),
        )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, "PNG")


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize transparent portrait subject widths for UI slot alignment.")
    parser.add_argument("--root", type=Path, default=Path("desktop/public/assets/ui/portraits"))
    parser.add_argument("--review-out", type=Path, default=Path("desktop/review/portrait_subject_width_normalized.png"))
    parser.add_argument("--target-body-width", type=int, default=500)
    parser.add_argument("--target-full-height", type=int, default=940)
    parser.add_argument("--body-right", type=int, default=600)
    parser.add_argument("--bottom", type=int, default=1018)
    parser.add_argument("--min-x-scale", type=float, default=0.82)
    parser.add_argument("--max-x-scale", type=float, default=1.35)
    args = parser.parse_args()

    paths = sorted(
        list((args.root / "roles").glob("*.png"))
        + list((args.root / "extra").glob("*.png"))
        + list((args.root / "unknown").glob("*.png"))
    )

    for path in paths:
        image = Image.open(path).convert("RGBA")
        normalized = normalize_portrait(
            image,
            target_body_width=args.target_body_width,
            target_full_height=args.target_full_height,
            body_right=args.body_right,
            bottom=args.bottom,
            min_x_scale=args.min_x_scale,
            max_x_scale=args.max_x_scale,
        )
        normalized.save(path, "PNG")
        print(path)

    make_contact_sheet(paths, args.review_out)
    print(args.review_out)


if __name__ == "__main__":
    main()
