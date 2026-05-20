from __future__ import annotations

import argparse
import math
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageFilter, ImageFont

from manifest_asset_utils import AssetResource, ensure_parent, parse_size, resources_by_type, validate_manifest_outputs

BG_DEEP = "#07111F"
BG_PANEL = "#0E1A2C"
GOLD = "#D6A75A"
GOLD_SOFT = "#F0D08A"
BLUE = "#4BA3FF"
RED = "#C64B4B"
GREEN = "#4DBA7A"
PURPLE = "#8E62D9"
GRAY = "#7C8494"
TEXT = "#F5E9D0"
TEXT_SUB = "#AEB9C9"

SCRIPT_TYPES = {"background", "icon", "share_card", "panel", "button", "portrait", "role_intro"}


def rgba(value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    r, g, b = ImageColor.getrgb(value)
    return r, g, b, alpha


def make_canvas(size: tuple[int, int], transparent: bool = False) -> Image.Image:
    color = (0, 0, 0, 0) if transparent else rgba(BG_DEEP)
    return Image.new("RGBA", size, color)


def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = []
    if bold:
        candidates.extend(
            [
                Path("C:/Windows/Fonts/msyhbd.ttc"),
                Path("C:/Windows/Fonts/simhei.ttf"),
                Path("C:/Windows/Fonts/STZHONGS.TTF"),
            ]
        )
    candidates.extend(
        [
            Path("C:/Windows/Fonts/msyh.ttc"),
            Path("C:/Windows/Fonts/simhei.ttf"),
            Path("C:/Windows/Fonts/STSONG.TTF"),
            Path("C:/Windows/Fonts/arial.ttf"),
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def vertical_gradient(size: tuple[int, int], top: str, bottom: str) -> Image.Image:
    w, h = size
    img = Image.new("RGBA", size)
    top_rgb = ImageColor.getrgb(top)
    bottom_rgb = ImageColor.getrgb(bottom)
    pixels = img.load()
    for y in range(h):
        t = y / max(1, h - 1)
        color = tuple(int(top_rgb[i] * (1 - t) + bottom_rgb[i] * t) for i in range(3)) + (255,)
        for x in range(w):
            pixels[x, y] = color
    return img


def add_soft_noise(img: Image.Image, alpha: int = 24, seed: int = 0) -> Image.Image:
    rnd = random.Random(seed)
    noise = Image.new("RGBA", img.size, (0, 0, 0, 0))
    pixels = noise.load()
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            v = rnd.randint(0, 255)
            pixels[x, y] = (v, v, v, alpha)
    noise = noise.filter(ImageFilter.GaussianBlur(0.8))
    return ImageChops.soft_light(img, noise)


def draw_moon(draw: ImageDraw.ImageDraw, center: tuple[float, float], radius: float, alpha: int = 255) -> None:
    x, y = center
    for ring in range(8, 0, -1):
        rr = radius * (1 + ring * 0.18)
        a = max(8, int(alpha * 0.05 * ring))
        draw.ellipse((x - rr, y - rr, x + rr, y + rr), fill=rgba(GOLD_SOFT, a))
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=rgba("#F7F2D9", alpha))


def draw_fog_layer(size: tuple[int, int], color: str, alpha: int, seed: int) -> Image.Image:
    rnd = random.Random(seed)
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    w, h = size
    for _ in range(18):
        cx = rnd.randint(-w // 6, w + w // 6)
        cy = rnd.randint(h // 3, h)
        rx = rnd.randint(w // 10, w // 3)
        ry = rnd.randint(h // 20, h // 8)
        draw.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=rgba(color, rnd.randint(alpha // 3, alpha)))
    return layer.filter(ImageFilter.GaussianBlur(radius=max(18, w // 50)))


def draw_village(draw: ImageDraw.ImageDraw, size: tuple[int, int], horizon: int, accent: str) -> None:
    w, h = size
    base = [
        (0, h),
        (0, horizon + 60),
        (w * 0.08, horizon + 24),
        (w * 0.16, horizon + 70),
        (w * 0.26, horizon - 2),
        (w * 0.34, horizon + 82),
        (w * 0.42, horizon + 40),
        (w * 0.54, horizon + 95),
        (w * 0.63, horizon + 18),
        (w * 0.72, horizon + 76),
        (w * 0.82, horizon + 26),
        (w, horizon + 84),
        (w, h),
    ]
    draw.polygon(base, fill=rgba("#08111D", 255))
    for x in range(0, w, max(80, w // 16)):
        roof_h = random.randint(40, 110)
        body_h = random.randint(90, 180)
        roof_w = random.randint(90, 170)
        left = x + random.randint(-12, 18)
        right = left + roof_w
        body_top = horizon + random.randint(30, 120)
        draw.polygon(
            [(left, body_top), ((left + right) / 2, body_top - roof_h), (right, body_top)],
            fill=rgba("#0B1322", 255),
        )
        draw.rectangle((left + 12, body_top, right - 12, body_top + body_h), fill=rgba("#101928", 255))
        if x % 2 == 0:
            chimney_x0 = left + roof_w * 0.68
            chimney_x1 = left + roof_w * 0.78
            chimney_y0 = body_top - roof_h - 50
            chimney_y1 = body_top - roof_h + 8
            draw.rectangle((chimney_x0, chimney_y0, chimney_x1, chimney_y1), fill=rgba("#0E1624", 255))
        for wx in range(left + 24, right - 20, 28):
            draw.rectangle((wx, body_top + 18, wx + 10, body_top + 30), fill=rgba(accent, 180))


def draw_forest(draw: ImageDraw.ImageDraw, size: tuple[int, int], horizon: int) -> None:
    w, h = size
    for x in range(-50, w + 50, max(44, w // 28)):
        trunk_h = random.randint(110, 230)
        crown_w = random.randint(70, 140)
        base_y = random.randint(horizon + 50, h - 20)
        draw.rectangle((x - 5, base_y - trunk_h, x + 5, base_y), fill=rgba("#0C1120", 255))
        draw.polygon(
            [
                (x, base_y - trunk_h - crown_w * 0.9),
                (x - crown_w * 0.55, base_y - trunk_h * 0.75),
                (x - crown_w * 0.2, base_y - trunk_h * 0.75),
                (x - crown_w * 0.72, base_y - trunk_h * 0.38),
                (x + crown_w * 0.72, base_y - trunk_h * 0.38),
                (x + crown_w * 0.2, base_y - trunk_h * 0.75),
                (x + crown_w * 0.55, base_y - trunk_h * 0.75),
            ],
            fill=rgba("#070C17", 245),
        )


def draw_hall(draw: ImageDraw.ImageDraw, size: tuple[int, int], accent: str) -> None:
    w, h = size
    floor_y = int(h * 0.73)
    draw.rectangle((0, floor_y, w, h), fill=rgba("#120E14"))
    for i in range(6):
        x = int((i + 0.5) * w / 6)
        col_w = w // 18
        draw.rectangle((x - col_w, h * 0.18, x + col_w, floor_y), fill=rgba("#17131C"))
        draw.rectangle((x - col_w * 1.2, h * 0.16, x + col_w * 1.2, h * 0.2), fill=rgba("#201828"))
        draw.rectangle((x - col_w * 1.2, floor_y - 12, x + col_w * 1.2, floor_y + 10), fill=rgba("#201828"))
        draw.ellipse((x - 14, h * 0.28, x + 14, h * 0.28 + 28), fill=rgba(accent, 170))
    draw.polygon([(w * 0.38, h * 0.72), (w * 0.5, h * 0.54), (w * 0.62, h * 0.72)], fill=rgba("#0B0A10"))
    draw.ellipse((w * 0.46, h * 0.48, w * 0.54, h * 0.56), fill=rgba(accent, 180))


def draw_background(resource: AssetResource) -> Image.Image:
    size = parse_size(resource.size, (1920, 1080))
    img = vertical_gradient(size, "#0A1830", BG_DEEP)
    img = add_soft_noise(img, alpha=20, seed=hash(resource.id) & 0xFFFF)
    draw = ImageDraw.Draw(img, "RGBA")
    w, h = size
    horizon = int(h * 0.56)
    accent = GOLD
    sky_top = "#0B1E38"
    sky_bottom = "#07111F"
    if "day" in resource.id:
        sky_top, sky_bottom, accent = "#495A75", "#182739", GOLD_SOFT
    elif "witch" in resource.id:
        sky_top, sky_bottom, accent = "#1A1E36", "#091320", GREEN
    elif "seer" in resource.id:
        sky_top, sky_bottom, accent = "#132546", "#07111F", BLUE
    elif "wolf" in resource.id:
        sky_top, sky_bottom, accent = "#231629", "#081018", RED
    elif "result" in resource.id and "wolfwin" in resource.id:
        sky_top, sky_bottom, accent = "#2B1620", "#090B12", RED
    elif "goodwin" in resource.id:
        sky_top, sky_bottom, accent = "#2B3040", "#0C1420", GOLD_SOFT
    img = vertical_gradient(size, sky_top, sky_bottom)
    img = add_soft_noise(img, alpha=16, seed=(hash(resource.id) + 99) & 0xFFFF)
    draw = ImageDraw.Draw(img, "RGBA")

    moon_y = h * (0.24 if "landing" in resource.id or "splash" in resource.id else 0.2)
    moon_x = w * (0.72 if "auth_login" in resource.id else 0.28 if "auth_register" in resource.id else 0.5)
    if "vote" in resource.id or "pk" in resource.id:
        moon_x = w * 0.78
    draw_moon(draw, (moon_x, moon_y), min(w, h) * 0.07, alpha=235)

    if "forest" in resource.id or "splash" in resource.id:
        draw_forest(draw, size, horizon)
    elif "result_hall" in resource.id or ("global_result" in resource.id):
        draw_hall(draw, size, accent)
    else:
        draw_village(draw, size, horizon, accent)
        if "global_day" in resource.id or "speech" in resource.id or "vote" in resource.id or "sheriff" in resource.id:
            draw.rectangle((0, h * 0.72, w, h), fill=rgba("#15111A", 255))
        if "hunter" in resource.id:
            draw.line((w * 0.2, h * 0.72, w * 0.35, h * 0.54), fill=rgba(GOLD, 180), width=max(2, w // 300))
        if "seer" in resource.id:
            draw.ellipse((w * 0.68, h * 0.32, w * 0.78, h * 0.42), outline=rgba(BLUE, 180), width=max(3, w // 260))
            draw.ellipse((w * 0.72, h * 0.35, w * 0.74, h * 0.39), fill=rgba(BLUE, 180))
        if "witch" in resource.id:
            draw.ellipse((w * 0.72, h * 0.65, w * 0.8, h * 0.78), outline=rgba(PURPLE, 200), width=max(3, w // 260))
            draw.rectangle((w * 0.74, h * 0.58, w * 0.78, h * 0.66), fill=rgba(GREEN, 150))
        if "wolf_action" in resource.id:
            draw.polygon(
                [
                    (w * 0.18, h * 0.72),
                    (w * 0.24, h * 0.52),
                    (w * 0.32, h * 0.66),
                    (w * 0.27, h * 0.42),
                    (w * 0.38, h * 0.62),
                ],
                fill=rgba(RED, 120),
            )
        if "idiot_reveal" in resource.id:
            draw.ellipse((w * 0.42, h * 0.46, w * 0.58, h * 0.64), outline=rgba(GOLD_SOFT, 180), width=max(3, w // 250))

    img.alpha_composite(draw_fog_layer(size, "#D7E0F0" if "day" in resource.id else "#D8E1EA", 38, seed=hash(resource.id) & 0xFFFF))
    img.alpha_composite(draw_fog_layer(size, accent, 16, seed=(hash(resource.id) >> 2) & 0xFFFF))
    if resource.id == "bg_landing_wolf":
        overlay = Image.new("RGBA", size, (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay, "RGBA")
        points = [
            (w * 0.55, h * 0.9),
            (w * 0.5, h * 0.7),
            (w * 0.52, h * 0.48),
            (w * 0.46, h * 0.34),
            (w * 0.48, h * 0.2),
            (w * 0.42, h * 0.1),
            (w * 0.51, h * 0.16),
            (w * 0.58, h * 0.08),
            (w * 0.67, h * 0.18),
            (w * 0.69, h * 0.34),
            (w * 0.64, h * 0.52),
            (w * 0.72, h * 0.74),
            (w * 0.67, h * 0.92),
        ]
        od.polygon(points, fill=rgba("#160A10", 160))
        overlay = overlay.filter(ImageFilter.GaussianBlur(4))
        return overlay
    return img


def panel_size(resource_id: str) -> tuple[int, int]:
    mapping = {
        "panel_main_dark_glass": (1320, 840),
        "panel_side_drawer": (680, 980),
        "panel_player_slot": (420, 220),
        "panel_vote_main": (960, 720),
        "panel_vote_card": (520, 180),
        "panel_night_phase": (900, 520),
        "panel_witch_action": (900, 620),
        "panel_seer_action": (900, 620),
        "panel_hunter_action": (900, 620),
        "panel_sheriff_election": (980, 680),
        "panel_death_announcement": (980, 540),
        "panel_speech_stage": (980, 540),
        "panel_pk_main": (980, 620),
        "panel_exile_result": (860, 520),
        "panel_game_over": (980, 640),
        "drawer_history_record": (680, 980),
        "card_history_chat": (560, 180),
        "card_history_skill": (560, 180),
        "panel_landing_mode_personal": (540, 720),
        "panel_landing_mode_god": (540, 720),
        "panel_auth_form": (720, 820),
        "panel_register_form": (760, 900),
        "panel_create_match": (1080, 820),
        "panel_match_list": (1180, 860),
        "card_match_record": (1040, 180),
        "panel_settings": (980, 760),
        "panel_ai_autoplay": (620, 300),
        "panel_ai_summary_main": (1180, 840),
        "card_summary_event": (1020, 180),
        "card_summary_player_score": (1020, 180),
        "panel_help_rules": (1160, 860),
        "panel_tutorial_tip": (620, 220),
        "dialog_delete_match": (720, 340),
        "dialog_pause_game": (720, 340),
        "dialog_stop_game": (720, 340),
        "dialog_exit_save": (720, 340),
        "dialog_generic_confirm": (720, 340),
        "overlay_dim_night": (1920, 1080),
        "overlay_focus_center": (1920, 1080),
        "overlay_wolf_focus": (1920, 1080),
        "loading_bar_gold": (512, 64),
        "toggle_on_gold": (160, 80),
        "toggle_off_gray": (160, 80),
        "slider_gold": (360, 64),
        "toast_success": (480, 96),
        "toast_warning": (480, 96),
        "toast_error": (480, 96),
        "toast_info": (480, 96),
        "card_self_role_base": (360, 520),
        "card_ai_unknown_base": (360, 520),
        "card_ai_unknown_dead": (360, 520),
        "card_ai_revealed_base": (360, 520),
        "card_god_villager": (360, 520),
        "card_god_werewolf": (360, 520),
        "card_god_seer": (360, 520),
        "card_god_witch": (360, 520),
        "card_god_hunter": (360, 520),
        "card_god_idiot": (360, 520),
    }
    return mapping.get(resource_id, (1024, 640))


def draw_gold_frame(draw: ImageDraw.ImageDraw, rect: tuple[int, int, int, int], accent: str, width: int) -> None:
    x0, y0, x1, y1 = rect
    for offset in range(width):
        draw.rounded_rectangle((x0 + offset, y0 + offset, x1 - offset, y1 - offset), radius=28, outline=rgba(accent, 180 - offset * 8), width=1)
    corner = 26
    for sx in (x0 + 30, x1 - 30):
        for sy in (y0 + 30, y1 - 30):
            draw.arc((sx - corner, sy - corner, sx + corner, sy + corner), 180, 270, fill=rgba(GOLD_SOFT, 200), width=3)


def draw_panel_surface(size: tuple[int, int], accent: str, solid: bool = False) -> Image.Image:
    w, h = size
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img, "RGBA")
    outer = (18, 18, w - 18, h - 18)
    fill_alpha = 210 if solid else 168
    draw.rounded_rectangle(outer, radius=32, fill=rgba(BG_PANEL, fill_alpha), outline=rgba(accent, 110), width=2)
    inner = (34, 34, w - 34, h - 34)
    draw.rounded_rectangle(inner, radius=24, outline=rgba(GOLD_SOFT, 54), width=1)
    band_bottom = max(52, int(h * 0.28))
    draw.rectangle((36, 36, w - 36, band_bottom), fill=rgba(accent, 18))
    draw_gold_frame(draw, outer, accent, width=3)
    return img


def draw_panel(resource: AssetResource) -> Image.Image:
    size = panel_size(resource.id)
    accent = GOLD
    if "wolf" in resource.id or "danger" in resource.id or "error" in resource.id:
        accent = RED
    elif "seer" in resource.id or "summary" in resource.id:
        accent = BLUE
    elif "witch" in resource.id:
        accent = GREEN
    elif "hunter" in resource.id:
        accent = GOLD_SOFT
    elif "warning" in resource.id:
        accent = "#E6B85C"
    elif "info" in resource.id:
        accent = BLUE
    elif "success" in resource.id:
        accent = GREEN
    elif "gray" in resource.id or "disabled" in resource.id:
        accent = GRAY

    if resource.id.startswith("overlay_"):
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img, "RGBA")
        draw.rectangle((0, 0, size[0], size[1]), fill=rgba("#03070D", 150 if "dim" in resource.id else 115))
        center = Image.new("L", size, 255)
        cd = ImageDraw.Draw(center)
        radius = min(size) * (0.22 if "center" in resource.id else 0.18)
        cx, cy = size[0] / 2, size[1] / 2
        cd.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=0)
        center = center.filter(ImageFilter.GaussianBlur(radius=96))
        img.putalpha(ImageChops.subtract(img.getchannel("A"), center))
        if "wolf" in resource.id:
            tint = Image.new("RGBA", size, rgba(RED, 28))
            img.alpha_composite(tint)
        return img

    if resource.id.startswith("loading_bar"):
        img = make_canvas(size, transparent=True)
        draw = ImageDraw.Draw(img, "RGBA")
        draw.rounded_rectangle((2, 14, size[0] - 2, size[1] - 14), radius=22, fill=rgba("#102030", 160), outline=rgba(GOLD, 120), width=2)
        draw.rounded_rectangle((12, 22, int(size[0] * 0.68), size[1] - 22), radius=16, fill=rgba(GOLD, 220))
        return img

    if resource.id.startswith("toggle_"):
        img = make_canvas(size, transparent=True)
        draw = ImageDraw.Draw(img, "RGBA")
        accent = GOLD if "on" in resource.id else GRAY
        draw.rounded_rectangle((4, 8, size[0] - 4, size[1] - 8), radius=32, fill=rgba(BG_PANEL, 180), outline=rgba(accent, 150), width=3)
        knob_x = size[0] * 0.68 if "on" in resource.id else size[0] * 0.32
        draw.ellipse((knob_x - 28, size[1] / 2 - 28, knob_x + 28, size[1] / 2 + 28), fill=rgba(accent, 235))
        return img

    if resource.id.startswith("slider_"):
        img = make_canvas(size, transparent=True)
        draw = ImageDraw.Draw(img, "RGBA")
        draw.rounded_rectangle((10, size[1] / 2 - 10, size[0] - 10, size[1] / 2 + 10), radius=12, fill=rgba("#152538", 170))
        draw.rounded_rectangle((10, size[1] / 2 - 10, int(size[0] * 0.62), size[1] / 2 + 10), radius=12, fill=rgba(GOLD, 220))
        draw.ellipse((size[0] * 0.62 - 18, size[1] / 2 - 18, size[0] * 0.62 + 18, size[1] / 2 + 18), fill=rgba(GOLD_SOFT, 245))
        return img

    img = draw_panel_surface(size, accent)
    draw = ImageDraw.Draw(img, "RGBA")
    if resource.id.startswith("toast_"):
        draw.rectangle((20, 20, 48, size[1] - 20), fill=rgba(accent, 220))
    if resource.id.startswith("card_") or resource.id.startswith("panel_landing_mode"):
        draw.rectangle((32, 64, size[0] - 32, size[1] - 32), outline=rgba(GOLD_SOFT, 48), width=1)
    if resource.id.startswith("card_god_") or resource.id.startswith("card_self_") or resource.id.startswith("card_ai_"):
        draw_card_symbol(draw, resource.id, size)
    return img


def draw_button(resource: AssetResource) -> Image.Image:
    size = parse_size(resource.size, (360, 96))
    img = make_canvas(size, transparent=True)
    draw = ImageDraw.Draw(img, "RGBA")
    accent = GOLD
    fill_1 = "#7B551D"
    fill_2 = "#C08A34"
    if "secondary" in resource.id or "guest" in resource.id:
        accent, fill_1, fill_2 = GRAY, "#162535", "#22364F"
    elif "danger" in resource.id or resource.id.endswith("_red"):
        accent, fill_1, fill_2 = RED, "#5F1C20", "#A7373F"
    elif "blue" in resource.id:
        accent, fill_1, fill_2 = BLUE, "#1C3960", "#3D78C6"
    elif "disabled" in resource.id:
        accent, fill_1, fill_2 = GRAY, "#2A3038", "#5C6673"
    base = vertical_gradient(size, fill_2, fill_1)
    img.alpha_composite(base)
    draw.rounded_rectangle((4, 4, size[0] - 4, size[1] - 4), radius=26, outline=rgba(accent, 180), width=3)
    draw.rounded_rectangle((12, 12, size[0] - 12, size[1] - 12), radius=20, outline=rgba(GOLD_SOFT, 45), width=1)
    return img


def draw_card_symbol(draw: ImageDraw.ImageDraw, resource_id: str, size: tuple[int, int]) -> None:
    w, h = size
    accent = GOLD
    label = "?"
    if "werewolf" in resource_id:
        accent, label = RED, "狼"
    elif "seer" in resource_id:
        accent, label = BLUE, "预"
    elif "witch" in resource_id:
        accent, label = GREEN, "巫"
    elif "hunter" in resource_id:
        accent, label = GOLD_SOFT, "猎"
    elif "idiot" in resource_id:
        accent, label = PURPLE, "愚"
    elif "villager" in resource_id:
        accent, label = GOLD, "民"
    elif "unknown" in resource_id:
        accent, label = GRAY, "?"
    elif "revealed" in resource_id:
        accent, label = GOLD_SOFT, "示"
    cx, cy = w / 2, h * 0.42
    draw.ellipse((cx - 92, cy - 92, cx + 92, cy + 92), outline=rgba(accent, 160), width=4)
    font = get_font(86, bold=True)
    bbox = draw.textbbox((0, 0), label, font=font)
    draw.text((cx - (bbox[2] - bbox[0]) / 2, cy - (bbox[3] - bbox[1]) / 2 - 4), label, font=font, fill=rgba(TEXT, 240))
    draw.rectangle((48, h * 0.72, w - 48, h * 0.82), fill=rgba(accent, 24))


def draw_logo(resource: AssetResource) -> Image.Image:
    size = parse_size(resource.size, (1024, 512))
    img = make_canvas(size, transparent=True)
    draw = ImageDraw.Draw(img, "RGBA")
    title = "狼人杀"
    subtitle = "LYCAN TUI"
    font = get_font(176, bold=True)
    sub_font = get_font(40, bold=False)
    bbox = draw.textbbox((0, 0), title, font=font)
    tx = (size[0] - (bbox[2] - bbox[0])) / 2
    ty = 84
    for offset, alpha in [(10, 36), (6, 52), (3, 80)]:
        draw.text((tx, ty + offset), title, font=font, fill=rgba("#23140E", alpha))
    draw.text((tx, ty), title, font=font, fill=rgba(GOLD_SOFT, 250), stroke_width=3, stroke_fill=rgba("#6C4A17", 240))
    sb = draw.textbbox((0, 0), subtitle, font=sub_font)
    draw.text(((size[0] - (sb[2] - sb[0])) / 2, ty + 218), subtitle, font=sub_font, fill=rgba(TEXT, 200))
    draw.line((size[0] * 0.26, ty + 258, size[0] * 0.74, ty + 258), fill=rgba(GOLD, 110), width=2)
    return img


def draw_sigil(draw: ImageDraw.ImageDraw, center: tuple[float, float], radius: float, accent: str, kind: str) -> None:
    cx, cy = center
    if kind == "wolf":
        pts = [(cx, cy - radius), (cx - radius * 0.5, cy + radius * 0.2), (cx - radius * 0.2, cy + radius), (cx, cy + radius * 0.62), (cx + radius * 0.2, cy + radius), (cx + radius * 0.5, cy + radius * 0.2)]
        draw.polygon(pts, fill=rgba(accent, 220))
    elif kind == "seer":
        draw.ellipse((cx - radius, cy - radius * 0.6, cx + radius, cy + radius * 0.6), outline=rgba(accent, 220), width=6)
        draw.ellipse((cx - radius * 0.2, cy - radius * 0.2, cx + radius * 0.2, cy + radius * 0.2), fill=rgba(accent, 220))
    elif kind == "witch":
        draw.ellipse((cx - radius * 0.35, cy - radius * 0.6, cx + radius * 0.35, cy + radius * 0.5), outline=rgba(accent, 220), width=6)
        draw.rectangle((cx - radius * 0.16, cy - radius * 0.88, cx + radius * 0.16, cy - radius * 0.4), fill=rgba(accent, 220))
    elif kind == "hunter":
        draw.line((cx - radius * 0.7, cy + radius * 0.55, cx + radius * 0.7, cy - radius * 0.55), fill=rgba(accent, 220), width=7)
        draw.polygon([(cx + radius * 0.7, cy - radius * 0.55), (cx + radius * 0.28, cy - radius * 0.22), (cx + radius * 0.4, cy - radius * 0.08)], fill=rgba(accent, 220))
    elif kind == "villager":
        draw.rectangle((cx - radius * 0.4, cy - radius * 0.2, cx + radius * 0.4, cy + radius * 0.6), outline=rgba(accent, 220), width=6)
        draw.polygon([(cx - radius * 0.54, cy - radius * 0.18), (cx, cy - radius * 0.62), (cx + radius * 0.54, cy - radius * 0.18)], fill=rgba(accent, 220))
    else:
        draw.ellipse((cx - radius * 0.15, cy - radius * 0.15, cx + radius * 0.15, cy + radius * 0.15), fill=rgba(accent, 220))


def draw_portrait(resource: AssetResource) -> Image.Image:
    size = parse_size(resource.size, (768, 1024))
    img = make_canvas(size, transparent=True)
    draw = ImageDraw.Draw(img, "RGBA")
    accent = GOLD
    base_fill = "#172335"
    skin = "#D3B092"
    hair = "#33221B"
    sigil = "villager"
    if "werewolf" in resource.id:
        accent, base_fill, skin, hair, sigil = RED, "#26171F", "#A58A7C", "#1B1111", "wolf"
    elif "seer" in resource.id:
        accent, base_fill, sigil = BLUE, "#16253A", "seer"
    elif "witch" in resource.id:
        accent, base_fill, sigil = GREEN, "#1C2136", "witch"
    elif "hunter" in resource.id:
        accent, base_fill, sigil = GOLD_SOFT, "#241C24", "hunter"
    elif "idiot" in resource.id:
        accent, base_fill, sigil = PURPLE, "#241D32", "neutral"
    elif "unknown" in resource.id:
        accent, base_fill, skin, hair, sigil = GRAY, "#131826", "#000000", "#000000", "neutral"
    bg = vertical_gradient(size, base_fill, "#09111C")
    mask = Image.new("L", size, 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((18, 18, size[0] - 18, size[1] - 18), radius=44, fill=255)
    bg.putalpha(mask)
    img.alpha_composite(bg)
    draw.rounded_rectangle((18, 18, size[0] - 18, size[1] - 18), radius=44, outline=rgba(accent, 170), width=4)
    draw.ellipse((size[0] * 0.28, size[1] * 0.22, size[0] * 0.72, size[1] * 0.66), fill=rgba("#0D131F", 160))
    if "unknown" in resource.id:
        draw.polygon(
            [
                (size[0] * 0.5, size[1] * 0.18),
                (size[0] * 0.28, size[1] * 0.55),
                (size[0] * 0.37, size[1] * 0.88),
                (size[0] * 0.63, size[1] * 0.88),
                (size[0] * 0.72, size[1] * 0.55),
            ],
            fill=rgba("#070B10", 235),
        )
    else:
        draw.ellipse((size[0] * 0.38, size[1] * 0.18, size[0] * 0.62, size[1] * 0.42), fill=rgba(skin, 255))
        draw.pieslice((size[0] * 0.34, size[1] * 0.14, size[0] * 0.66, size[1] * 0.44), 180, 360, fill=rgba(hair, 255))
        draw.rectangle((size[0] * 0.44, size[1] * 0.38, size[0] * 0.56, size[1] * 0.48), fill=rgba(skin, 255))
        robe = [(size[0] * 0.24, size[1] * 0.88), (size[0] * 0.34, size[1] * 0.48), (size[0] * 0.66, size[1] * 0.48), (size[0] * 0.76, size[1] * 0.88)]
        draw.polygon(robe, fill=rgba(base_fill, 240))
        draw.polygon([(size[0] * 0.5, size[1] * 0.5), (size[0] * 0.36, size[1] * 0.68), (size[0] * 0.64, size[1] * 0.68)], fill=rgba(accent, 72))
    draw_sigil(draw, (size[0] * 0.5, size[1] * 0.8), size[0] * 0.1, accent, sigil)
    return img


def draw_role_intro(resource: AssetResource) -> Image.Image:
    size = parse_size(resource.size, (900, 1200))
    if "base_" in resource.id:
        accent = GOLD if "good" in resource.id else RED if "wolf" in resource.id else PURPLE
        img = draw_panel_surface(size, accent, solid=True)
        draw = ImageDraw.Draw(img, "RGBA")
        draw.rectangle((72, 98, size[0] - 72, size[1] - 132), outline=rgba(GOLD_SOFT, 70), width=2)
        return img
    img = draw_panel_surface(size, GOLD, solid=True)
    draw = ImageDraw.Draw(img, "RGBA")
    portrait_name = "portrait_villager_male_01"
    title = "平民"
    accent = GOLD
    sigil = "villager"
    if "werewolf" in resource.id:
        portrait_name, title, accent, sigil = "portrait_werewolf_01", "狼人", RED, "wolf"
    elif "seer" in resource.id:
        portrait_name, title, accent, sigil = "portrait_seer_01", "预言家", BLUE, "seer"
    elif "witch" in resource.id:
        portrait_name, title, accent, sigil = "portrait_witch_01", "女巫", GREEN, "witch"
    elif "hunter" in resource.id:
        portrait_name, title, accent, sigil = "portrait_hunter_01", "猎人", GOLD_SOFT, "hunter"
    elif "idiot" in resource.id:
        portrait_name, title, accent, sigil = "portrait_idiot_01", "白痴", PURPLE, "neutral"
    portrait_resource = next(resource for resource in resources_by_type("portrait") if resource.id == portrait_name)
    portrait = draw_portrait(portrait_resource).resize((520, 700))
    img.alpha_composite(portrait, dest=(190, 170))
    draw.rectangle((130, 110, size[0] - 130, 152), fill=rgba(accent, 42))
    font = get_font(78, bold=True)
    draw.text((size[0] * 0.5, 98), title, font=font, fill=rgba(TEXT, 245), anchor="ma")
    draw_sigil(draw, (size[0] * 0.5, size[1] * 0.84), 66, accent, sigil)
    return img


def draw_share_card(resource: AssetResource) -> Image.Image:
    size = parse_size(resource.size, (1080, 1920))
    accent = GOLD_SOFT if "good" in resource.id else RED
    img = vertical_gradient(size, "#121E31" if "good" in resource.id else "#241520", BG_DEEP)
    draw = ImageDraw.Draw(img, "RGBA")
    draw_moon(draw, (size[0] * 0.5, size[1] * 0.22), size[0] * 0.12, alpha=230)
    draw_village(draw, size, int(size[1] * 0.62), accent)
    img.alpha_composite(draw_fog_layer(size, "#E0E6F0", 42, seed=33 if "good" in resource.id else 44))
    badge = "好人胜利" if "good" in resource.id else "狼人胜利"
    font = get_font(118, bold=True)
    sub = get_font(40, bold=False)
    draw.text((size[0] * 0.5, size[1] * 0.72), badge, font=font, fill=rgba(TEXT, 245), anchor="ma", stroke_width=3, stroke_fill=rgba("#2B1C13", 180))
    draw.text((size[0] * 0.5, size[1] * 0.79), "12 Player Gothic Werewolf", font=sub, fill=rgba(TEXT_SUB, 210), anchor="ma")
    draw_sigil(draw, (size[0] * 0.5, size[1] * 0.56), 110, accent, "villager" if "good" in resource.id else "wolf")
    return img


def symbol_from_id(resource_id: str) -> tuple[str, str]:
    mapping = {
        "sheriff": ("star", GOLD),
        "speaking": ("voice", BLUE),
        "voted": ("vote", GOLD),
        "knifed": ("claw", RED),
        "exiled": ("stamp", RED),
        "poisoned": ("drop", PURPLE),
        "saved": ("drop", GREEN),
        "dead": ("skull", GRAY),
        "shot": ("bolt", GOLD_SOFT),
        "last_words": ("scroll", GOLD),
        "pk": ("versus", RED),
        "self_destruct": ("burst", RED),
        "check_good": ("sun", GREEN),
        "check_wolf": ("moon", RED),
        "identity_hidden": ("mask", GRAY),
        "ai_player": ("chip", BLUE),
        "human_player": ("person", GOLD_SOFT),
        "ai_controlling": ("spark", BLUE),
        "on_stage": ("stage", GOLD),
        "versus": ("versus", RED),
        "good_win": ("sun", GOLD_SOFT),
        "wolf_win": ("moon", RED),
        "record": ("scroll", GOLD),
        "history": ("clock", GOLD),
        "settings": ("gear", GRAY),
        "chat": ("voice", BLUE),
        "vote": ("vote", GOLD),
        "skip": ("arrow", GRAY),
        "confirm": ("check", GREEN),
        "close": ("x", RED),
        "campaign": ("flag", GOLD),
        "explode": ("burst", RED),
        "token": ("coin", GOLD),
        "personal_mode": ("eye", BLUE),
        "god_mode": ("crown", GOLD),
        "sound_on": ("speaker", GOLD),
        "sound_off": ("mute", GRAY),
        "help": ("book", GOLD_SOFT),
        "match_records": ("stack", GOLD),
        "autoplay": ("spark", BLUE),
        "summary": ("chart", BLUE),
        "achievement": ("trophy", GOLD),
        "ranking": ("crown", GOLD_SOFT),
        "user": ("person", GOLD_SOFT),
        "password": ("lock", GRAY),
        "guest": ("door", GOLD),
        "difficulty": ("bars", RED),
        "rule_config": ("book", GOLD),
        "speed_config": ("speed", BLUE),
        "continue": ("arrow", GREEN),
        "delete": ("x", RED),
        "replay": ("replay", BLUE),
        "pause": ("pause", GRAY),
        "stop": ("stop", RED),
        "resume": ("play", GREEN),
        "save": ("coin", GOLD_SOFT),
        "suggestion": ("spark", BLUE),
        "next": ("arrow", GOLD),
        "timeline": ("clock", BLUE),
        "vote_chart": ("chart", GOLD),
        "comment": ("chat", BLUE),
        "wolf_kill": ("claw", RED),
        "wolf_confirm": ("check", RED),
        "witch_heal": ("drop", GREEN),
        "witch_poison": ("drop", PURPLE),
        "seer_check": ("eye", BLUE),
        "hunter_shoot": ("bolt", GOLD_SOFT),
        "idiot_reveal": ("burst", PURPLE),
        "result_good": ("sun", GREEN),
        "result_wolf": ("moon", RED),
        "hunter_target": ("target", GOLD_SOFT),
        "role_villager": ("person", GOLD),
        "role_werewolf": ("wolf", RED),
        "role_seer": ("eye", BLUE),
        "role_witch": ("drop", GREEN),
        "role_hunter": ("bolt", GOLD_SOFT),
        "role_idiot": ("mask", PURPLE),
        "empty_matches": ("stack", GOLD),
        "empty_history": ("clock", GOLD),
        "error_network": ("net", RED),
        "error_ai": ("chip", RED),
        "loading_wolf": ("wolf", RED),
    }
    for key, value in mapping.items():
        if key in resource_id:
            return value
    return "coin", GOLD


def draw_icon_shape(draw: ImageDraw.ImageDraw, size: tuple[int, int], kind: str, accent: str) -> None:
    w, h = size
    cx, cy = w / 2, h / 2
    pad = min(w, h) * 0.18
    stroke = max(4, int(min(w, h) * 0.04))
    if kind == "star":
        pts = []
        for i in range(10):
            angle = math.pi / 2 + i * math.pi / 5
            radius = min(w, h) * (0.32 if i % 2 == 0 else 0.14)
            pts.append((cx + math.cos(angle) * radius, cy - math.sin(angle) * radius))
        draw.polygon(pts, fill=rgba(accent, 230))
    elif kind in {"voice", "chat"}:
        draw.rounded_rectangle((pad, h * 0.28, w - pad, h * 0.68), radius=28, outline=rgba(accent, 230), width=stroke)
        draw.polygon([(w * 0.42, h * 0.68), (w * 0.5, h * 0.84), (w * 0.56, h * 0.68)], fill=rgba(accent, 230))
    elif kind == "vote":
        draw.rectangle((w * 0.28, h * 0.42, w * 0.72, h * 0.72), outline=rgba(accent, 230), width=stroke)
        draw.line((w * 0.34, h * 0.34, w * 0.66, h * 0.34), fill=rgba(accent, 230), width=stroke)
        draw.line((w * 0.4, h * 0.34, w * 0.52, h * 0.52), fill=rgba(accent, 230), width=stroke)
    elif kind == "claw":
        for x in [0.34, 0.48, 0.62]:
            draw.line((w * x, h * 0.25, w * (x - 0.1), h * 0.76), fill=rgba(accent, 235), width=stroke + 2)
    elif kind == "drop":
        draw.polygon([(cx, h * 0.2), (w * 0.3, h * 0.56), (w * 0.38, h * 0.78), (w * 0.62, h * 0.78), (w * 0.7, h * 0.56)], fill=rgba(accent, 220))
    elif kind == "skull":
        draw.ellipse((w * 0.27, h * 0.22, w * 0.73, h * 0.62), outline=rgba(accent, 230), width=stroke)
        draw.ellipse((w * 0.38, h * 0.38, w * 0.46, h * 0.48), fill=rgba(accent, 230))
        draw.ellipse((w * 0.54, h * 0.38, w * 0.62, h * 0.48), fill=rgba(accent, 230))
        draw.rectangle((w * 0.4, h * 0.62, w * 0.6, h * 0.76), outline=rgba(accent, 230), width=stroke)
    elif kind == "bolt":
        draw.polygon([(w * 0.58, h * 0.14), (w * 0.34, h * 0.56), (w * 0.5, h * 0.56), (w * 0.42, h * 0.86), (w * 0.7, h * 0.42), (w * 0.54, h * 0.42)], fill=rgba(accent, 230))
    elif kind == "scroll":
        draw.rounded_rectangle((w * 0.28, h * 0.24, w * 0.72, h * 0.76), radius=24, outline=rgba(accent, 230), width=stroke)
        draw.line((w * 0.36, h * 0.38, w * 0.64, h * 0.38), fill=rgba(accent, 230), width=stroke)
        draw.line((w * 0.36, h * 0.52, w * 0.6, h * 0.52), fill=rgba(accent, 230), width=stroke)
    elif kind == "versus":
        font = get_font(int(min(w, h) * 0.3), bold=True)
        draw.text((cx, cy), "VS", font=font, fill=rgba(accent, 235), anchor="mm")
    elif kind == "sun":
        draw.ellipse((w * 0.3, h * 0.3, w * 0.7, h * 0.7), fill=rgba(accent, 220))
        for i in range(8):
            angle = i * math.pi / 4
            draw.line((cx + math.cos(angle) * w * 0.24, cy + math.sin(angle) * h * 0.24, cx + math.cos(angle) * w * 0.38, cy + math.sin(angle) * h * 0.38), fill=rgba(accent, 220), width=stroke)
    elif kind == "moon":
        draw.ellipse((w * 0.28, h * 0.22, w * 0.74, h * 0.68), fill=rgba(accent, 220))
        draw.ellipse((w * 0.4, h * 0.18, w * 0.82, h * 0.68), fill=(0, 0, 0, 0))
    elif kind == "mask":
        draw.rounded_rectangle((w * 0.26, h * 0.34, w * 0.74, h * 0.58), radius=22, outline=rgba(accent, 230), width=stroke)
        draw.ellipse((w * 0.34, h * 0.4, w * 0.44, h * 0.48), fill=rgba(accent, 230))
        draw.ellipse((w * 0.56, h * 0.4, w * 0.66, h * 0.48), fill=rgba(accent, 230))
    elif kind == "chip":
        draw.rectangle((w * 0.3, h * 0.3, w * 0.7, h * 0.7), outline=rgba(accent, 230), width=stroke)
        for x in [0.24, 0.76]:
            for y in [0.36, 0.5, 0.64]:
                draw.line((w * x, h * y, w * (0.3 if x < 0.5 else 0.7), h * y), fill=rgba(accent, 230), width=stroke)
        for y in [0.24, 0.76]:
            for x in [0.36, 0.5, 0.64]:
                draw.line((w * x, h * y, w * x, h * (0.3 if y < 0.5 else 0.7)), fill=rgba(accent, 230), width=stroke)
    elif kind == "person":
        draw.ellipse((w * 0.38, h * 0.22, w * 0.62, h * 0.42), fill=rgba(accent, 230))
        draw.rounded_rectangle((w * 0.3, h * 0.44, w * 0.7, h * 0.78), radius=30, fill=rgba(accent, 230))
    elif kind == "stage":
        draw.line((w * 0.3, h * 0.72, w * 0.7, h * 0.72), fill=rgba(accent, 230), width=stroke)
        draw.rectangle((w * 0.34, h * 0.52, w * 0.66, h * 0.68), outline=rgba(accent, 230), width=stroke)
    elif kind == "coin":
        draw.ellipse((w * 0.28, h * 0.28, w * 0.72, h * 0.72), outline=rgba(accent, 230), width=stroke)
        draw.ellipse((w * 0.38, h * 0.38, w * 0.62, h * 0.62), outline=rgba(accent, 180), width=stroke)
    elif kind == "eye":
        draw_sigil(draw, (cx, cy), min(w, h) * 0.22, accent, "seer")
    elif kind == "crown":
        draw.polygon([(w * 0.24, h * 0.66), (w * 0.32, h * 0.36), (w * 0.46, h * 0.58), (w * 0.54, h * 0.28), (w * 0.62, h * 0.58), (w * 0.76, h * 0.36), (w * 0.82, h * 0.66)], fill=rgba(accent, 230))
        draw.rectangle((w * 0.28, h * 0.62, w * 0.78, h * 0.74), fill=rgba(accent, 230))
    elif kind == "gear":
        draw.ellipse((w * 0.34, h * 0.34, w * 0.66, h * 0.66), outline=rgba(accent, 230), width=stroke)
        for i in range(8):
            angle = i * math.pi / 4
            draw.line((cx + math.cos(angle) * w * 0.2, cy + math.sin(angle) * h * 0.2, cx + math.cos(angle) * w * 0.34, cy + math.sin(angle) * h * 0.34), fill=rgba(accent, 230), width=stroke)
    elif kind == "check":
        draw.line((w * 0.28, h * 0.54, w * 0.44, h * 0.72), fill=rgba(accent, 230), width=stroke)
        draw.line((w * 0.44, h * 0.72, w * 0.76, h * 0.3), fill=rgba(accent, 230), width=stroke)
    elif kind == "x":
        draw.line((w * 0.3, h * 0.3, w * 0.7, h * 0.7), fill=rgba(accent, 230), width=stroke)
        draw.line((w * 0.7, h * 0.3, w * 0.3, h * 0.7), fill=rgba(accent, 230), width=stroke)
    elif kind == "flag":
        draw.line((w * 0.34, h * 0.24, w * 0.34, h * 0.76), fill=rgba(accent, 230), width=stroke)
        draw.polygon([(w * 0.38, h * 0.28), (w * 0.68, h * 0.34), (w * 0.38, h * 0.48)], fill=rgba(accent, 230))
    elif kind == "burst":
        pts = []
        for i in range(16):
            angle = i * math.pi / 8
            radius = min(w, h) * (0.34 if i % 2 == 0 else 0.18)
            pts.append((cx + math.cos(angle) * radius, cy + math.sin(angle) * radius))
        draw.polygon(pts, fill=rgba(accent, 230))
    elif kind == "arrow":
        draw.line((w * 0.24, cy, w * 0.72, cy), fill=rgba(accent, 230), width=stroke)
        draw.polygon([(w * 0.72, cy), (w * 0.54, cy - h * 0.14), (w * 0.54, cy + h * 0.14)], fill=rgba(accent, 230))
    elif kind == "book":
        draw.rectangle((w * 0.28, h * 0.26, w * 0.68, h * 0.74), outline=rgba(accent, 230), width=stroke)
        draw.line((w * 0.48, h * 0.26, w * 0.48, h * 0.74), fill=rgba(accent, 230), width=stroke)
    elif kind == "stack":
        for off in [0.0, 0.06, 0.12]:
            draw.rounded_rectangle((w * (0.28 + off), h * (0.28 + off), w * (0.64 + off), h * (0.58 + off)), radius=18, outline=rgba(accent, 210), width=stroke)
    elif kind == "lock":
        draw.rounded_rectangle((w * 0.32, h * 0.44, w * 0.68, h * 0.76), radius=18, outline=rgba(accent, 230), width=stroke)
        draw.arc((w * 0.38, h * 0.2, w * 0.62, h * 0.52), 180, 360, fill=rgba(accent, 230), width=stroke)
    elif kind == "door":
        draw.rectangle((w * 0.34, h * 0.22, w * 0.66, h * 0.78), outline=rgba(accent, 230), width=stroke)
        draw.ellipse((w * 0.56, h * 0.48, w * 0.6, h * 0.52), fill=rgba(accent, 230))
    elif kind == "bars":
        for i, ht in enumerate([0.34, 0.48, 0.64, 0.78]):
            x0 = w * (0.24 + i * 0.14)
            draw.rounded_rectangle((x0, h * ht, x0 + w * 0.08, h * 0.82), radius=8, fill=rgba(accent, 230))
    elif kind == "speed":
        draw.arc((w * 0.24, h * 0.26, w * 0.76, h * 0.78), 200, 340, fill=rgba(accent, 230), width=stroke)
        draw.line((cx, cy, w * 0.68, h * 0.42), fill=rgba(accent, 230), width=stroke)
    elif kind == "play":
        draw.polygon([(w * 0.38, h * 0.28), (w * 0.72, cy), (w * 0.38, h * 0.72)], fill=rgba(accent, 230))
    elif kind == "speaker":
        draw.polygon([(w * 0.26, h * 0.44), (w * 0.4, h * 0.44), (w * 0.56, h * 0.28), (w * 0.56, h * 0.72), (w * 0.4, h * 0.56), (w * 0.26, h * 0.56)], fill=rgba(accent, 230))
        draw.arc((w * 0.5, h * 0.32, w * 0.82, h * 0.68), -45, 45, fill=rgba(accent, 230), width=stroke)
    elif kind == "mute":
        draw_icon_shape(draw, size, "speaker", accent)
        draw.line((w * 0.64, h * 0.34, w * 0.84, h * 0.66), fill=rgba(RED, 230), width=stroke)
    elif kind == "pause":
        draw.rounded_rectangle((w * 0.32, h * 0.24, w * 0.44, h * 0.76), radius=8, fill=rgba(accent, 230))
        draw.rounded_rectangle((w * 0.56, h * 0.24, w * 0.68, h * 0.76), radius=8, fill=rgba(accent, 230))
    elif kind == "stop":
        draw.rounded_rectangle((w * 0.3, h * 0.3, w * 0.7, h * 0.7), radius=12, fill=rgba(accent, 230))
    elif kind == "spark":
        for i in range(8):
            angle = i * math.pi / 4
            draw.line((cx, cy, cx + math.cos(angle) * w * 0.26, cy + math.sin(angle) * h * 0.26), fill=rgba(accent, 230), width=stroke)
        draw.ellipse((cx - w * 0.08, cy - h * 0.08, cx + w * 0.08, cy + h * 0.08), fill=rgba(accent, 230))
    elif kind == "chart":
        draw.line((w * 0.26, h * 0.72, w * 0.74, h * 0.72), fill=rgba(accent, 230), width=stroke)
        draw.line((w * 0.26, h * 0.72, w * 0.26, h * 0.28), fill=rgba(accent, 230), width=stroke)
        draw.line((w * 0.3, h * 0.62, w * 0.42, h * 0.52), fill=rgba(accent, 230), width=stroke)
        draw.line((w * 0.42, h * 0.52, w * 0.56, h * 0.58), fill=rgba(accent, 230), width=stroke)
        draw.line((w * 0.56, h * 0.58, w * 0.72, h * 0.36), fill=rgba(accent, 230), width=stroke)
    elif kind == "clock":
        draw.ellipse((w * 0.24, h * 0.24, w * 0.76, h * 0.76), outline=rgba(accent, 230), width=stroke)
        draw.line((cx, cy, cx, h * 0.38), fill=rgba(accent, 230), width=stroke)
        draw.line((cx, cy, w * 0.62, cy), fill=rgba(accent, 230), width=stroke)
    elif kind == "replay":
        draw.arc((w * 0.24, h * 0.24, w * 0.76, h * 0.76), 40, 300, fill=rgba(accent, 230), width=stroke)
        draw.polygon([(w * 0.26, h * 0.44), (w * 0.18, h * 0.3), (w * 0.34, h * 0.28)], fill=rgba(accent, 230))
    elif kind == "target":
        draw.ellipse((w * 0.24, h * 0.24, w * 0.76, h * 0.76), outline=rgba(accent, 230), width=stroke)
        draw.ellipse((w * 0.4, h * 0.4, w * 0.6, h * 0.6), outline=rgba(accent, 230), width=stroke)
        draw.line((cx, h * 0.14, cx, h * 0.34), fill=rgba(accent, 230), width=stroke)
        draw.line((cx, h * 0.66, cx, h * 0.86), fill=rgba(accent, 230), width=stroke)
    elif kind == "wolf":
        draw_sigil(draw, (cx, cy), min(w, h) * 0.3, accent, "wolf")
    elif kind == "net":
        draw.rectangle((w * 0.26, h * 0.3, w * 0.74, h * 0.7), outline=rgba(accent, 230), width=stroke)
        for frac in [0.38, 0.5, 0.62]:
            draw.line((w * frac, h * 0.3, w * frac, h * 0.7), fill=rgba(accent, 200), width=stroke - 1)
        for frac in [0.42, 0.58]:
            draw.line((w * 0.26, h * frac, w * 0.74, h * frac), fill=rgba(accent, 200), width=stroke - 1)
    else:
        draw.ellipse((w * 0.3, h * 0.3, w * 0.7, h * 0.7), fill=rgba(accent, 220))


def draw_icon(resource: AssetResource) -> Image.Image:
    default = (256, 256)
    size = parse_size(resource.size, default)
    img = make_canvas(size, transparent=True)
    draw = ImageDraw.Draw(img, "RGBA")
    kind, accent = symbol_from_id(resource.id)
    if resource.id == "logo_title":
        return draw_logo(resource)
    draw_icon_shape(draw, size, kind, accent)
    return img


def save_image(resource: AssetResource, image: Image.Image) -> None:
    ensure_parent(resource.output_path)
    image.save(resource.output_path)


def generate_resource(resource: AssetResource) -> None:
    if resource.type == "background":
        image = draw_background(resource)
    elif resource.type == "panel":
        image = draw_panel(resource)
    elif resource.type == "button":
        image = draw_button(resource)
    elif resource.type == "icon":
        image = draw_icon(resource)
    elif resource.type == "portrait":
        image = draw_portrait(resource)
    elif resource.type == "role_intro":
        image = draw_role_intro(resource)
    elif resource.type == "share_card":
        image = draw_share_card(resource)
    else:
        raise ValueError(f"Unsupported visual type: {resource.type}")
    save_image(resource, image)


def generate_visual_assets(selected_types: list[str] | None = None) -> None:
    wanted = set(selected_types or SCRIPT_TYPES)
    for asset_type in SCRIPT_TYPES:
        if asset_type not in wanted:
            continue
        for resource in resources_by_type(asset_type):
            generate_resource(resource)
            print(f"wrote {resource.full_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate manifest-aligned visual assets from scratch.")
    parser.add_argument("--types", nargs="*", help="Optional subset of visual asset types to generate.")
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Validate the selected visual types after generation.",
    )
    args = parser.parse_args()
    selected = args.types or list(SCRIPT_TYPES)
    generate_visual_assets(selected)
    if args.verify:
        report = validate_manifest_outputs(selected)
        print(f"present={report['present_resources']} missing={report['missing_resources']}")
        if report["missing_resources"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
