from __future__ import annotations

import argparse
import math
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from manifest_asset_utils import AssetResource, ensure_parent, resources_by_type, validate_manifest_outputs

SR = 44_100


def t(duration: float) -> np.ndarray:
    return np.linspace(0.0, duration, int(SR * duration), endpoint=False)


def stereo(mono: np.ndarray, pan: float = 0.0) -> np.ndarray:
    pan = float(np.clip(pan, -1.0, 1.0))
    left = mono * math.cos((pan + 1) * math.pi / 4)
    right = mono * math.sin((pan + 1) * math.pi / 4)
    return np.column_stack([left, right])


def sine(freq: float, duration: float, amp: float = 1.0, phase: float = 0.0) -> np.ndarray:
    return amp * np.sin(2 * np.pi * freq * t(duration) + phase)


def noise(duration: float, amp: float = 1.0, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return amp * rng.normal(0.0, 1.0, int(SR * duration))


def adsr(duration: float, attack=0.01, decay=0.08, sustain=0.55, release=0.12) -> np.ndarray:
    n = int(SR * duration)
    env = np.ones(n, dtype=np.float32) * sustain
    a = min(n, int(SR * attack))
    d = min(max(0, n - a), int(SR * decay))
    r = min(n, int(SR * release))
    if a:
        env[:a] = np.linspace(0.0, 1.0, a)
    if d:
        env[a : a + d] = np.linspace(1.0, sustain, d)
    if r:
        env[-r:] *= np.linspace(1.0, 0.0, r)
    return env


def lowpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    from scipy.signal import butter, lfilter

    b, a = butter(3, cutoff / (SR / 2), btype="low")
    return lfilter(b, a, x)


def highpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    from scipy.signal import butter, lfilter

    b, a = butter(2, cutoff / (SR / 2), btype="high")
    return lfilter(b, a, x)


def add(dst: np.ndarray, src: np.ndarray, start: float) -> None:
    i = int(start * SR)
    if i >= len(dst):
        return
    src2 = src[: len(dst) - i]
    dst[i : i + len(src2)] += src2


def mix(*parts: np.ndarray) -> np.ndarray:
    if not parts:
        return np.zeros((0, 2), dtype=np.float32)
    max_len = max(len(part) for part in parts)
    out = np.zeros((max_len, 2), dtype=np.float32)
    for part in parts:
        out[: len(part)] += part
    return out


def normalize(audio: np.ndarray, peak: float = 0.92) -> np.ndarray:
    m = float(np.max(np.abs(audio))) if audio.size else 0.0
    if m > 0:
        audio = audio / m * peak
    return np.clip(audio, -1.0, 1.0)


def fade(audio: np.ndarray, fade_in=0.02, fade_out=0.08) -> np.ndarray:
    out = audio.copy()
    n = len(out)
    fi = min(n, int(SR * fade_in))
    fo = min(n, int(SR * fade_out))
    if fi:
        out[:fi] *= np.linspace(0, 1, fi)[:, None] if out.ndim == 2 else np.linspace(0, 1, fi)
    if fo:
        out[-fo:] *= np.linspace(1, 0, fo)[:, None] if out.ndim == 2 else np.linspace(1, 0, fo)
    return out


def bell(freq: float, duration: float, amp: float = 0.4, pan=0.0) -> np.ndarray:
    x = t(duration)
    mono = np.zeros_like(x)
    for mul, gain in [(1.0, 1.0), (2.01, 0.42), (3.02, 0.22), (4.15, 0.12)]:
        mono += np.sin(2 * np.pi * freq * mul * x) * gain
    mono *= amp * np.exp(-x * 3.4)
    return stereo(mono, pan)


def drum(freq: float, duration: float, amp: float = 0.7, pan=0.0) -> np.ndarray:
    x = t(duration)
    pitch = freq * (1 + 3.3 * np.exp(-x * 34))
    phase = np.cumsum(pitch) / SR * 2 * np.pi
    mono = np.sin(phase) * np.exp(-x * 9.0) * amp
    mono += lowpass(noise(duration, 0.08, int(freq * 10)), 180) * np.exp(-x * 14)
    return stereo(mono, pan)


def chord(freqs: list[float], duration: float, amp=0.2, pan=0.0, tremolo=0.0) -> np.ndarray:
    x = t(duration)
    mono = np.zeros_like(x)
    for f in freqs:
        mono += sine(f, duration, 1.0)
        mono += sine(f * 2, duration, 0.18)
    mono /= max(1, len(freqs))
    if tremolo:
        mono *= 0.72 + 0.28 * np.sin(2 * np.pi * tremolo * x)
    mono *= amp * adsr(duration, 0.08, 0.35, 0.72, 0.45)
    return stereo(mono, pan)


def pluck(freq: float, duration: float, amp=0.18, pan=0.0) -> np.ndarray:
    x = t(duration)
    mono = (np.sin(2 * np.pi * freq * x) + 0.42 * np.sin(2 * np.pi * freq * 2 * x)) * np.exp(-x * 5.2)
    mono += lowpass(noise(duration, 0.03, int(freq)), 2500) * np.exp(-x * 11)
    return stereo(mono * amp, pan)


def shimmer(duration: float, root=880, amp=0.18, seed=2) -> np.ndarray:
    out = np.zeros((int(SR * duration), 2))
    notes = [root, root * 1.25, root * 1.5, root * 2.0]
    for i, f in enumerate(notes):
        start = i * duration / (len(notes) + 1)
        add(out, bell(f, duration - start, amp / (i + 1), pan=-0.4 + i * 0.24), start)
    mono = highpass(noise(duration, amp * 0.18, seed), 2500)
    out += stereo(mono * adsr(duration, 0.02, 0.2, 0.25, 0.8), 0.1)
    return out


def wind(duration: float, amp=0.15, seed=1) -> np.ndarray:
    x = t(duration)
    mono = lowpass(highpass(noise(duration, 1.0, seed), 260), 1900)
    mono *= amp * (0.45 + 0.55 * np.sin(2 * np.pi * 0.12 * x + 0.7) ** 2)
    return stereo(mono, -0.2) + stereo(np.roll(mono, int(0.017 * SR)) * 0.6, 0.35)


def soft_click(duration: float = 0.16, accent=1200, seed=5) -> np.ndarray:
    x = t(duration)
    tap = highpass(noise(duration, 0.07, seed), 2600) * np.exp(-x * 26)
    tone = sine(accent, duration, 0.14) * np.exp(-x * 18)
    return stereo(tap + tone, 0.0)


def swoosh(duration: float = 0.32, direction: int = 1, seed: int = 7) -> np.ndarray:
    x = t(duration)
    mono = highpass(noise(duration, 0.16, seed), 1800) * np.exp(-x * 7)
    tone = sine(420 if direction > 0 else 360, duration, 0.08) * np.exp(-x * 6)
    return stereo(mono + tone, 0.25 * direction)


def loop_theme(duration: float, bpm: int, key: tuple[float, float, float], mode: str, accent_seed: int) -> np.ndarray:
    out = np.zeros((int(SR * duration), 2))
    beat = 60.0 / bpm
    root, third, fifth = key
    out += chord([root, third, fifth], duration, 0.12 if mode != "vote" else 0.16, 0, tremolo=0.7)
    total_beats = int(duration / beat)
    for b in range(total_beats):
        st = b * beat
        if mode == "landing":
            if b % 4 == 0:
                add(out, bell(third * 4, 1.2, 0.08, -0.3), st)
            if b % 8 == 4:
                add(out, shimmer(1.2, int(fifth * 5), 0.08, accent_seed + b), st)
        elif mode == "lobby":
            add(out, pluck(root * (4 if b % 2 == 0 else 3), 0.5, 0.12, -0.25 + (b % 3) * 0.25), st)
            if b % 4 == 2:
                add(out, bell(fifth * 3, 0.8, 0.07, 0.25), st)
        elif mode == "day":
            add(out, pluck([root * 4, third * 3, fifth * 3, third * 2][b % 4], 0.48, 0.15, -0.25 + (b % 3) * 0.25), st)
            if b % 3 == 0:
                add(out, drum(110, 0.16, 0.12, 0.12), st)
        elif mode == "vote":
            add(out, pluck(root * 2, 0.25, 0.15, -0.1), st)
            if b % 2 == 0:
                add(out, drum(72, 0.22, 0.18, 0), st)
            tick = highpass(noise(0.04, 0.06, accent_seed + b), 3000) * adsr(0.04, 0.001, 0.004, 0.6, 0.01)
            add(out, stereo(tick, 0.35), st + beat / 2)
        elif mode == "pk":
            add(out, drum(78, 0.22, 0.22, 0), st)
            add(out, pluck(fifth * 2, 0.2, 0.13, 0.18), st + beat / 2)
        elif mode == "night":
            if b % 4 == 0:
                add(out, drum(root / 2, 0.32, 0.13, -0.2), st)
            if b % 8 in {2, 6}:
                add(out, bell(third * 4, 1.1, 0.07, 0.35), st)
        elif mode == "wolf":
            add(out, drum(68, 0.25, 0.2, 0), st)
            if b % 2 == 1:
                add(out, highpass(stereo(noise(0.1, 0.05, accent_seed + b), -0.2)[:, 0], 2000)[:, None], st)
        elif mode == "witch":
            if b % 4 == 0:
                add(out, bell(third * 5, 1.0, 0.07, -0.2), st)
            if b % 4 == 2:
                add(out, bell(fifth * 4, 1.2, 0.06, 0.2), st)
        elif mode == "seer":
            if b % 3 == 0:
                add(out, bell(fifth * 4, 0.9, 0.07, -0.2), st)
            if b % 6 == 3:
                add(out, shimmer(0.8, int(third * 6), 0.07, accent_seed + b), st)
        elif mode == "hunter":
            add(out, drum(82, 0.18, 0.15, 0), st)
            if b % 4 == 1:
                add(out, pluck(root * 2, 0.3, 0.12, 0.12), st)
        elif mode == "sheriff":
            if b % 4 in {0, 2}:
                add(out, chord([root * 3, third * 3, fifth * 3], 0.42, 0.15, 0.08), st)
            add(out, drum(135, 0.1, 0.1, -0.2), st + beat / 2)
        elif mode == "summary":
            add(out, pluck(third * 3, 0.42, 0.11, -0.15), st)
            if b % 4 == 2:
                add(out, shimmer(0.8, int(fifth * 5), 0.05, accent_seed + b), st)
    if mode in {"night", "wolf", "witch", "seer", "hunter"}:
        out += wind(duration, 0.03 if mode != "wolf" else 0.04, accent_seed)
    if mode in {"landing", "lobby", "day", "sheriff", "summary"}:
        out += stereo(lowpass(noise(duration, 0.025, accent_seed + 100), 1400), 0.1)
    if mode in {"vote", "pk"}:
        out += stereo(highpass(noise(duration, 0.018, accent_seed + 200), 2600), -0.08)
    return out


def result_theme(kind: str) -> np.ndarray:
    duration = 15
    out = np.zeros((int(SR * duration), 2))
    if kind == "good":
        chords = [
            [293.7, 370, 440],
            [370, 440, 587],
            [440, 554, 659],
            [587, 740, 880],
        ]
        for i, freqs in enumerate(chords):
            add(out, chord(freqs, 2.0, 0.3, 0.0, tremolo=2.3), i * 1.2)
        for st in [6.2, 7.0, 7.8, 9.6]:
            add(out, bell(1046, 1.1, 0.16, 0.25), st)
        add(out, shimmer(3.4, 1046, 0.15, 90), 10.2)
    else:
        add(out, chord([73.4, 110, 146.8], 4.2, 0.3, 0.0, tremolo=2.0), 0.0)
        for st in [0.5, 1.7, 2.9]:
            add(out, drum(72, 0.8, 0.32, 0), st)
        melody = [294, 330, 370, 330, 294, 247, 220]
        for i, f in enumerate(melody):
            add(out, pluck(f, 0.9, 0.15, -0.2 + (i % 3) * 0.2), 4.6 + i * 0.66)
        add(out, wind(4.0, 0.05, 104), 10.4)
    return out


def death_announcement_theme() -> np.ndarray:
    out = np.zeros((int(SR * 8.0), 2))
    add(out, chord([82.4, 123.5, 164.8], 3.6, 0.18, 0, tremolo=1.4), 0)
    add(out, bell(330, 1.4, 0.09, -0.2), 1.6)
    add(out, bell(247, 1.2, 0.08, 0.25), 3.1)
    add(out, wind(3.5, 0.03, 72), 4.0)
    return out


def render_bgm(resource: AssetResource) -> np.ndarray:
    rid = resource.id
    if "landing" in rid:
        return loop_theme(28, 70, (73.4, 110.0, 146.8), "landing", 10)
    if "room_lobby" in rid:
        return loop_theme(24, 78, (82.4, 123.5, 164.8), "lobby", 12)
    if "day_speech" in rid:
        return loop_theme(28, 78, (55.0, 82.4, 110.0), "day", 14)
    if "vote_tension" in rid:
        return loop_theme(20, 88, (82.4, 123.5, 164.8), "vote", 16)
    if "pk_duel" in rid:
        return loop_theme(18, 92, (73.4, 110.0, 146.8), "pk", 18)
    if "night_phase" in rid:
        return loop_theme(28, 65, (73.4, 110.0, 146.8), "night", 20)
    if "wolf_action" in rid:
        return loop_theme(22, 72, (73.4, 110.0, 146.8), "wolf", 22)
    if "witch_action" in rid:
        return loop_theme(22, 68, (73.4, 92.5, 138.6), "witch", 24)
    if "seer_action" in rid:
        return loop_theme(22, 70, (82.4, 123.5, 164.8), "seer", 26)
    if "hunter_action" in rid:
        return loop_theme(18, 80, (73.4, 110.0, 146.8), "hunter", 28)
    if "death_announcement" in rid:
        return death_announcement_theme()
    if "sheriff_election" in rid:
        return loop_theme(24, 76, (98.0, 146.8, 196.0), "sheriff", 30)
    if "ai_summary" in rid:
        return loop_theme(24, 68, (82.4, 123.5, 164.8), "summary", 32)
    if "goodwin" in rid:
        return result_theme("good")
    if "wolfwin" in rid:
        return result_theme("wolf")
    return loop_theme(18, 72, (73.4, 110.0, 146.8), "night", 99)


def write_ogg(path: Path, audio: np.ndarray) -> None:
    ensure_parent(path)
    audio = normalize(fade(audio, 0.02, 0.08)).astype(np.float32, copy=False)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        sf.write(tmp_path, audio, SR, subtype="PCM_16")
        from imageio_ffmpeg import get_ffmpeg_exe

        ffmpeg = get_ffmpeg_exe()
        subprocess.run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(tmp_path),
                "-c:a",
                "libvorbis",
                "-qscale:a",
                "5",
                str(path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    finally:
        tmp_path.unlink(missing_ok=True)


def write_wav(path: Path, audio: np.ndarray) -> None:
    ensure_parent(path)
    audio = normalize(fade(audio, 0.01, 0.05)).astype(np.float32, copy=False)
    sf.write(path, audio, SR, subtype="PCM_16")


def sfx_from_id(resource_id: str) -> np.ndarray:
    if resource_id == "sfx_app_start":
        out = np.zeros((int(SR * 1.8), 2))
        add(out, swoosh(0.45, 1, 41), 0.0)
        add(out, bell(392, 1.0, 0.12, -0.2), 0.24)
        add(out, wind(0.9, 0.025, 42), 0.6)
        return out
    if resource_id == "sfx_ui_click_soft":
        return soft_click(0.18, 1320, 43)
    if resource_id == "sfx_ui_confirm":
        out = np.zeros((int(SR * 0.45), 2))
        add(out, soft_click(0.15, 1180, 44), 0.0)
        add(out, bell(880, 0.35, 0.1, 0.2), 0.06)
        return out
    if resource_id == "sfx_ui_cancel":
        out = np.zeros((int(SR * 0.35), 2))
        x = t(0.35)
        mono = sine(520, 0.35, 0.12) * np.linspace(1, 0.2, len(x))
        return stereo(mono, 0.0)
    if resource_id == "sfx_ui_tab_switch":
        return mix(soft_click(0.14, 1500, 45), swoosh(0.18, 1, 46) * 0.35)
    if resource_id == "sfx_ui_drawer_open":
        return mix(swoosh(0.42, 1, 47), shimmer(0.3, 980, 0.08, 48))
    if resource_id == "sfx_ui_drawer_close":
        return swoosh(0.34, -1, 49)
    if resource_id == "sfx_landing_mode_hover":
        return bell(1180, 0.28, 0.09, -0.1)
    if resource_id == "sfx_landing_mode_select":
        out = np.zeros((int(SR * 0.65), 2))
        add(out, bell(784, 0.45, 0.12, -0.15), 0.0)
        add(out, soft_click(0.16, 1000, 50), 0.08)
        add(out, bell(1174, 0.38, 0.08, 0.2), 0.12)
        return out
    if resource_id == "sfx_landing_start_game":
        out = np.zeros((int(SR * 0.9), 2))
        add(out, drum(94, 0.4, 0.28, 0.0), 0.0)
        add(out, shimmer(0.55, 880, 0.14, 51), 0.16)
        return out
    if resource_id == "sfx_sound_toggle_on":
        return bell(1046, 0.24, 0.09, 0.15)
    if resource_id == "sfx_sound_toggle_off":
        x = t(0.24)
        return stereo(sine(720, 0.24, 0.08) * np.linspace(1, 0.1, len(x)), 0.0)
    if resource_id == "sfx_ai_autoplay_on":
        out = np.zeros((int(SR * 0.6), 2))
        add(out, shimmer(0.45, 1320, 0.12, 52), 0.0)
        add(out, soft_click(0.14, 1480, 53), 0.06)
        return out
    if resource_id == "sfx_ai_autoplay_off":
        x = t(0.42)
        mono = sine(900, 0.42, 0.1) * np.linspace(1, 0.05, len(x))
        return stereo(mono, 0.0)
    if resource_id == "sfx_ai_suggestion":
        out = np.zeros((int(SR * 0.4), 2))
        add(out, bell(1320, 0.25, 0.08, -0.15), 0.0)
        add(out, bell(1568, 0.25, 0.07, 0.2), 0.06)
        return out
    if resource_id == "sfx_role_intro_open":
        return mix(swoosh(0.28, 1, 54), shimmer(0.32, 900, 0.08, 55))
    if resource_id == "sfx_role_intro_close":
        return mix(swoosh(0.24, -1, 56), soft_click(0.12, 900, 57) * 0.4)
    if resource_id == "sfx_wolf_kill":
        out = np.zeros((int(SR * 0.8), 2))
        for i, st in enumerate([0.05, 0.12, 0.18]):
            slash = highpass(noise(0.18, 0.2, 58 + i), 1200) * np.linspace(1, 0, int(SR * 0.18))
            add(out, stereo(slash, -0.5 + i * 0.4), st)
        add(out, drum(82, 0.35, 0.34, 0), 0.28)
        return out
    if resource_id == "sfx_witch_heal":
        out = np.zeros((int(SR * 0.9), 2))
        add(out, bell(740, 0.55, 0.12, -0.15), 0.0)
        add(out, shimmer(0.5, 1046, 0.12, 60), 0.16)
        return out
    if resource_id == "sfx_witch_poison":
        out = np.zeros((int(SR * 0.9), 2))
        bubble = lowpass(noise(0.6, 0.12, 61), 520) * adsr(0.6, 0.03, 0.08, 0.7, 0.2)
        add(out, stereo(bubble, -0.15), 0.0)
        add(out, bell(392, 0.55, 0.1, 0.2), 0.18)
        return out
    if resource_id == "sfx_seer_check":
        out = np.zeros((int(SR * 0.95), 2))
        add(out, bell(1320, 0.8, 0.14, -0.18), 0.0)
        add(out, shimmer(0.45, 1240, 0.14, 62), 0.22)
        return out
    if resource_id == "sfx_hunter_shoot":
        out = np.zeros((int(SR * 0.9), 2))
        add(out, pluck(130, 0.2, 0.22, -0.25), 0.0)
        whoosh = highpass(noise(0.18, 0.18, 63), 1500) * np.linspace(1, 0, int(SR * 0.18))
        add(out, stereo(whoosh, 0.25), 0.12)
        add(out, drum(120, 0.38, 0.42, 0), 0.28)
        return out
    if resource_id == "sfx_idiot_reveal":
        out = np.zeros((int(SR * 0.7), 2))
        add(out, swoosh(0.22, 1, 64), 0.0)
        add(out, bell(988, 0.32, 0.08, 0.12), 0.14)
        return out
    if resource_id == "sfx_vote_cast":
        out = np.zeros((int(SR * 0.32), 2))
        add(out, soft_click(0.14, 980, 65), 0.0)
        add(out, drum(180, 0.12, 0.16, 0), 0.05)
        return out
    if resource_id == "sfx_vote_tally":
        out = np.zeros((int(SR * 1.1), 2))
        for i in range(6):
            add(out, soft_click(0.12, 1280 - i * 80, 66 + i), i * 0.14)
        return out
    if resource_id == "sfx_player_exiled":
        out = np.zeros((int(SR * 0.9), 2))
        add(out, drum(76, 0.4, 0.36, 0), 0.0)
        add(out, bell(294, 0.6, 0.09, 0.12), 0.16)
        return out
    if resource_id == "sfx_player_dead":
        out = np.zeros((int(SR * 0.85), 2))
        add(out, drum(68, 0.36, 0.3, 0), 0.0)
        x = t(0.5)
        add(out, stereo(sine(220, 0.5, 0.08) * np.linspace(1, 0.02, len(x)), -0.1), 0.18)
        return out
    if resource_id == "sfx_self_destruct":
        out = np.zeros((int(SR * 0.95), 2))
        add(out, chord([73.4, 110, 146.8], 0.45, 0.16, 0, tremolo=3), 0.0)
        add(out, drum(58, 0.45, 0.4, 0), 0.25)
        add(out, shimmer(0.28, 640, 0.08, 74), 0.4)
        return out
    if resource_id == "sfx_good_win":
        out = np.zeros((int(SR * 1.8), 2))
        add(out, bell(880, 0.8, 0.12, -0.2), 0.0)
        add(out, bell(1174, 0.8, 0.12, 0.2), 0.18)
        add(out, shimmer(0.9, 1320, 0.16, 75), 0.42)
        return out
    if resource_id == "sfx_wolf_win":
        out = np.zeros((int(SR * 1.8), 2))
        add(out, chord([73.4, 110, 146.8], 0.9, 0.18, 0, tremolo=2), 0.0)
        add(out, drum(72, 0.5, 0.34, 0), 0.24)
        add(out, wind(0.7, 0.03, 76), 0.9)
        return out
    return soft_click()


def generate_audio_assets(selected_types: list[str]) -> None:
    if "bgm" in selected_types:
        for resource in resources_by_type("bgm"):
            audio = render_bgm(resource)
            write_ogg(resource.output_path, audio)
            print(f"wrote {resource.full_path}")
    if "sfx" in selected_types:
        for resource in resources_by_type("sfx"):
            audio = sfx_from_id(resource.id)
            write_wav(resource.output_path, audio)
            print(f"wrote {resource.full_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate manifest-aligned BGM and SFX assets from scratch.")
    parser.add_argument("--types", nargs="*", default=["bgm", "sfx"])
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    generate_audio_assets(args.types)
    if args.verify:
        report = validate_manifest_outputs(args.types)
        print(f"present={report['present_resources']} missing={report['missing_resources']}")
        if report["missing_resources"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
