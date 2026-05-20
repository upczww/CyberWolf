"""Generate procedural friendly-gothic storybook audio assets for LycanTUI.

The source prompts live in desktop/prompts_copy_ready_gothic_storybook_audio.md.
This script creates deterministic 44.1 kHz stereo WAV assets for the SFX and BGM
listed there. It intentionally avoids external encoders so it can run in a plain
Python environment without ffmpeg. The sound palette should feel mysterious and
storybook-like, not horror-heavy or hostile to players.
"""
from __future__ import annotations

from pathlib import Path
import math

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, lfilter

SR = 44_100
ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = ROOT / "desktop" / "public" / "assets"
SFX_DIR = ASSET_ROOT / "sfx"
BGM_DIR = ASSET_ROOT / "bgm"


def t(duration: float) -> np.ndarray:
    return np.linspace(0.0, duration, int(SR * duration), endpoint=False)


def stereo(mono: np.ndarray, pan: float = 0.0) -> np.ndarray:
    pan = float(np.clip(pan, -1.0, 1.0))
    left = mono * math.cos((pan + 1) * math.pi / 4)
    right = mono * math.sin((pan + 1) * math.pi / 4)
    return np.column_stack([left, right])


def sine(freq: float, duration: float, amp: float = 1.0, phase: float = 0.0) -> np.ndarray:
    x = t(duration)
    return amp * np.sin(2 * np.pi * freq * x + phase)


def noise(duration: float, amp: float = 1.0, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return amp * rng.normal(0.0, 1.0, int(SR * duration))


def adsr(duration: float, attack=0.01, decay=0.08, sustain=0.55, release=0.12) -> np.ndarray:
    n = int(SR * duration)
    env = np.ones(n) * sustain
    a = min(n, int(SR * attack))
    d = min(max(0, n - a), int(SR * decay))
    r = min(n, int(SR * release))
    if a:
        env[:a] = np.linspace(0, 1, a)
    if d:
        env[a:a+d] = np.linspace(1, sustain, d)
    if r:
        env[-r:] *= np.linspace(1, 0, r)
    return env


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


def lowpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    b, a = butter(3, cutoff / (SR / 2), btype="low")
    return lfilter(b, a, x)


def highpass(x: np.ndarray, cutoff: float) -> np.ndarray:
    b, a = butter(2, cutoff / (SR / 2), btype="high")
    return lfilter(b, a, x)


def add(dst: np.ndarray, src: np.ndarray, start: float) -> None:
    i = int(start * SR)
    if i >= len(dst):
        return
    src2 = src[: len(dst) - i]
    dst[i:i+len(src2)] += src2


def normalize(audio: np.ndarray, peak=0.92) -> np.ndarray:
    m = float(np.max(np.abs(audio))) if len(audio) else 0
    if m > 0:
        audio = audio / m * peak
    return np.clip(audio, -1, 1)


def write(path: Path, audio: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    audio = normalize(fade(audio, 0.01, 0.05))
    wavfile.write(path, SR, (audio * 32767).astype(np.int16))


def bell(freq: float, duration: float, amp: float = 0.5, pan=0.0) -> np.ndarray:
    x = t(duration)
    mono = np.zeros_like(x)
    for mul, gain in [(1, 1.0), (2.01, 0.42), (3.02, 0.22), (4.15, 0.12)]:
        mono += np.sin(2 * np.pi * freq * mul * x) * gain
    mono *= amp * np.exp(-x * 3.4)
    return stereo(mono, pan)


def drum(freq: float, duration: float, amp: float = 0.7, pan=0.0) -> np.ndarray:
    x = t(duration)
    pitch = freq * (1 + 3.5 * np.exp(-x * 34))
    phase = np.cumsum(pitch) / SR * 2 * np.pi
    mono = np.sin(phase) * np.exp(-x * 9.0) * amp
    mono += lowpass(noise(duration, 0.08, 44), 160) * np.exp(-x * 14)
    return stereo(mono, pan)


def wind(duration: float, amp=0.22, seed=1) -> np.ndarray:
    x = t(duration)
    mono = lowpass(highpass(noise(duration, 1, seed), 260), 1900)
    mono *= amp * (0.45 + 0.55 * np.sin(2 * np.pi * 0.12 * x + 0.7) ** 2)
    return stereo(mono, -0.2) + stereo(np.roll(mono, int(0.017 * SR)) * 0.6, 0.35)


def howl(duration: float, amp=0.45, base=360, pan=0.0) -> np.ndarray:
    x = t(duration)
    freq = base + 80 * np.sin(np.pi * x / duration) + 18 * np.sin(2 * np.pi * 4.3 * x)
    phase = np.cumsum(freq) / SR * 2 * np.pi
    mono = np.sin(phase) + 0.35 * np.sin(phase * 0.5)
    mono *= amp * np.sin(np.pi * x / duration) ** 0.8
    return stereo(mono, pan)


def shimmer(duration: float, root=880, amp=0.22, seed=2) -> np.ndarray:
    out = np.zeros((int(SR * duration), 2))
    notes = [root, root * 1.25, root * 1.5, root * 2.0]
    for i, f in enumerate(notes):
        start = i * duration / (len(notes) + 1)
        add(out, bell(f, duration - start, amp / (i + 1), pan=-0.4 + i * 0.25), start)
    mono = highpass(noise(duration, amp * 0.18, seed), 2500)
    out += stereo(mono * adsr(duration, 0.02, 0.2, 0.25, 0.8), 0.1)
    return out


def chord(freqs: list[float], duration: float, amp=0.2, pan=0.0, tremolo=0.0) -> np.ndarray:
    x = t(duration)
    mono = np.zeros_like(x)
    for f in freqs:
        mono += sine(f, duration, 1.0)
        mono += sine(f * 2, duration, 0.22)
    mono /= max(1, len(freqs))
    if tremolo:
        mono *= 0.72 + 0.28 * np.sin(2 * np.pi * tremolo * x)
    mono *= amp * adsr(duration, 0.08, 0.4, 0.72, 0.55)
    return stereo(mono, pan)


def pluck(freq: float, duration: float, amp=0.28, pan=0.0) -> np.ndarray:
    x = t(duration)
    mono = (np.sin(2*np.pi*freq*x) + 0.45*np.sin(2*np.pi*freq*2*x)) * np.exp(-x * 5.5)
    mono += lowpass(noise(duration, 0.04, int(freq)), 2400) * np.exp(-x * 12)
    return stereo(mono * amp, pan)


def sfx_phase_night() -> np.ndarray:
    out = wind(3.0, 0.075, 10)
    for st, f, pan in [(0.28, 523, -0.35), (0.72, 659, 0.25), (1.18, 784, -0.1), (1.68, 659, 0.32)]:
        add(out, bell(f, 1.1, 0.1, pan), st)
    add(out, chord([110.0, 146.8, 220.0], 1.8, 0.22, 0.0, tremolo=0.9), 0.72)
    add(out, shimmer(1.15, 740, 0.11), 1.65)
    return out


def sfx_phase_dawn() -> np.ndarray:
    out = wind(3.0, 0.11, 11)
    add(out, howl(0.65, 0.12, 420, -0.45), 0.0)
    for st, f in [(0.45, 720), (0.72, 910), (1.05, 1050), (1.25, 840)]:
        add(out, bell(f, 0.5, 0.12, 0.45), st)
    add(out, bell(440, 1.6, 0.36, -0.2), 1.25)
    add(out, shimmer(1.2, 880, 0.18), 1.7)
    return out


def sfx_wolf_kill() -> np.ndarray:
    out = np.zeros((int(SR*1.5), 2))
    for i, st in enumerate([0.18, 0.32, 0.47]):
        slash = highpass(noise(0.22, 0.24, 20+i), 1200) * np.linspace(1, 0, int(SR*0.22))
        add(out, stereo(slash, -0.6 + i*0.55), st)
    add(out, pluck(196, 0.72, 0.2, -0.15), 0.12)
    add(out, drum(82, 0.48, 0.42, 0.0), 0.62)
    add(out, bell(294, 0.7, 0.1, 0.2), 0.82)
    return out


def sfx_seer_check() -> np.ndarray:
    out = np.zeros((int(SR*2.0), 2))
    add(out, bell(1320, 1.0, 0.36, -0.25), 0.05)
    add(out, chord([146.8, 220.0, 293.7], 1.6, 0.28, 0.1, tremolo=5.5), 0.25)
    for i in range(9):
        add(out, bell(880 + i*70, 0.28, 0.08, -0.8 + i*0.2), 0.55 + i*0.11)
    add(out, shimmer(0.7, 1240, 0.3), 1.25)
    return out


def sfx_antidote() -> np.ndarray:
    out = np.zeros((int(SR*2.0), 2))
    add(out, drum(180, 0.16, 0.25, -0.15), 0.05)
    pour = highpass(lowpass(noise(0.75, 0.22, 30), 2700), 800) * adsr(0.75, 0.04, 0.12, 0.75, 0.28)
    add(out, stereo(pour, 0.15), 0.25)
    for i, f in enumerate([523, 659, 784, 1046]):
        add(out, bell(f, 0.9, 0.16, -0.3 + i*0.2), 0.55 + i*0.18)
    add(out, chord([130.8, 196.0, 261.6], 0.9, 0.22, 0.0), 1.05)
    return out


def sfx_poison() -> np.ndarray:
    out = np.zeros((int(SR*2.0), 2))
    add(out, drum(128, 0.18, 0.18, 0.1), 0.03)
    bubble = lowpass(noise(0.9, 0.18, 35), 520) * (0.55 + 0.45*np.sin(2*np.pi*13*t(0.9))**2)
    add(out, stereo(bubble, -0.15), 0.22)
    add(out, chord([196, 247, 330], 1.2, 0.18, 0.15, tremolo=3), 0.45)
    down = sine(260, 0.7, 0.12) * np.linspace(1, 0.2, int(SR*0.7))
    add(out, stereo(down, 0.0), 1.05)
    add(out, bell(392, 0.7, 0.12, 0.0), 1.35)
    return out


def sfx_hunter_shoot() -> np.ndarray:
    out = np.zeros((int(SR*1.5), 2))
    twang = sine(130, 0.35, 0.5) * adsr(0.35, 0.002, 0.03, 0.45, 0.2)
    add(out, stereo(twang, -0.45), 0.05)
    whoosh = highpass(noise(0.42, 0.42, 40), 1300) * np.linspace(1, 0, int(SR*0.42))
    add(out, stereo(whoosh, 0.42), 0.18)
    add(out, drum(120, 0.5, 0.72, 0.2), 0.62)
    add(out, bell(210, 0.8, 0.16, 0.0), 0.72)
    return out


def sfx_self_destruct() -> np.ndarray:
    out = np.zeros((int(SR*2.0), 2))
    add(out, chord([73.4, 110, 146.8], 0.9, 0.32, -0.1, tremolo=3), 0.0)
    cracks = highpass(noise(0.42, 0.24, 50), 1400) * adsr(0.42, 0.002, 0.04, 0.4, 0.18)
    add(out, stereo(cracks, 0.3), 0.55)
    add(out, drum(58, 0.72, 0.56, 0), 0.85)
    add(out, shimmer(0.8, 640, 0.22), 0.9)
    return out


def sfx_vote_result() -> np.ndarray:
    out = np.zeros((int(SR*1.5), 2))
    paper = highpass(noise(0.45, 0.22, 60), 2200) * adsr(0.45, 0.01, 0.04, 0.5, 0.08)
    add(out, stereo(paper, -0.1), 0.05)
    add(out, drum(82, 0.7, 0.9, 0), 0.68)
    gasp = lowpass(noise(0.45, 0.12, 61), 900) * adsr(0.45, 0.04, 0.08, 0.5, 0.2)
    add(out, stereo(gasp, 0.2), 0.92)
    return out


def sfx_exile() -> np.ndarray:
    out = np.zeros((int(SR*2.0), 2))
    add(out, chord([82.4, 123.5, 164.8], 0.8, 0.28, 0.0), 0.0)
    chains = highpass(noise(0.5, 0.14, 70), 1600) * adsr(0.5, 0.005, 0.05, 0.45, 0.15)
    add(out, stereo(chains, -0.4), 0.28)
    creak = sine(132, 0.8, 0.12) * (1 + 0.25*np.sin(2*np.pi*7*t(0.8))) * adsr(0.8, 0.05, 0.2, 0.6, 0.2)
    add(out, stereo(creak, 0.2), 0.65)
    add(out, drum(76, 0.58, 0.46, 0), 1.18)
    add(out, bell(294, 1.0, 0.15, 0), 1.4)
    return out


def sfx_sheriff() -> np.ndarray:
    out = np.zeros((int(SR*2.0), 2))
    for i, f in enumerate([392, 494, 587]):
        add(out, chord([f, f*1.5], 0.45, 0.24, -0.2 + i*0.2), 0.1 + i*0.22)
    add(out, bell(1568, 0.55, 0.22, 0.25), 0.86)
    for st in [1.05, 1.18, 1.32]:
        clap = highpass(noise(0.08, 0.18, int(st*100)), 900) * adsr(0.08, 0.002, 0.01, 0.5, 0.03)
        add(out, stereo(clap, -0.3 + st-1.05), st)
    add(out, drum(160, 0.25, 0.34, 0), 1.55)
    return out


def sfx_victory_good() -> np.ndarray:
    out = np.zeros((int(SR*4.0), 2))
    for st, freqs in [(0, [293.7, 370, 440]), (0.55, [370, 440, 587]), (1.1, [440, 554, 659])]:
        add(out, chord(freqs, 1.1, 0.38, 0, tremolo=3), st)
    for st in [0.4, 1.0, 1.6, 2.2]:
        add(out, bell(660, 1.2, 0.22, -0.3), st)
    add(out, shimmer(1.4, 1046, 0.24), 2.35)
    return out


def sfx_victory_wolf() -> np.ndarray:
    out = np.zeros((int(SR*4.0), 2))
    add(out, chord([73.4, 110, 146.8], 1.3, 0.34, 0, tremolo=2.5), 0)
    add(out, drum(70, 0.7, 0.42, 0), 0.25)
    for st, f in [(0.82, 294), (1.25, 370), (1.72, 440)]:
        add(out, bell(f, 1.0, 0.16, -0.25 + st * 0.2), st)
    add(out, shimmer(1.5, 587, 0.15), 2.0)
    add(out, wind(1.25, 0.06, 91), 2.35)
    return out


def bgm_loop(duration: float, bpm: int, key: str, mode: str) -> np.ndarray:
    out = np.zeros((int(SR*duration), 2))
    beat = 60.0 / bpm
    if key == "Dmin":
        root, fifth, minor = 73.4, 110.0, 146.8
    elif key == "Amin":
        root, fifth, minor = 55.0, 82.4, 110.0
    elif key == "Emin":
        root, fifth, minor = 82.4, 123.5, 164.8
    else:
        root, fifth, minor = 98.0, 146.8, 196.0

    out += chord([root, fifth, minor], duration, 0.13 if mode != "vote" else 0.18, 0, tremolo=0.7)
    total_beats = int(duration / beat)
    for b in range(total_beats):
        st = b * beat
        if mode == "night":
            if b % 4 == 0:
                add(out, drum(root/2, 0.35, 0.18, -0.2), st)
            if b % 8 in [2, 6]:
                add(out, bell(minor*4, 1.2, 0.11, 0.35), st)
        elif mode == "day":
            add(out, pluck([root*4, minor*3, fifth*3, minor*2][b % 4], 0.55, 0.16, -0.25 + (b % 3)*0.25), st)
            if b % 3 == 0:
                add(out, drum(110, 0.18, 0.16, 0.2), st)
        elif mode == "vote":
            add(out, pluck(root*2, 0.25, 0.16, -0.15), st)
            if b % 2 == 0:
                add(out, drum(70, 0.22, 0.23, 0), st)
            tick = highpass(noise(0.04, 0.08, b), 3000) * adsr(0.04, 0.001, 0.004, 0.6, 0.01)
            add(out, stereo(tick, 0.35), st + beat/2)
        elif mode == "sheriff":
            if b % 4 in [0, 2]:
                add(out, chord([root*3, minor*3, fifth*3], 0.45, 0.17, 0.1), st)
            add(out, drum(135, 0.12, 0.11, -0.2), st + beat/2)
    if mode == "night":
        for st in np.arange(3.0, duration, 6.0):
            add(out, bell(740, 1.2, 0.07, 0.28), float(st))
        out += wind(duration, 0.035, 120)
    if mode == "day":
        out += stereo(lowpass(noise(duration, 0.035, 130), 1300), 0.1)
    if mode == "vote":
        out += stereo(highpass(noise(duration, 0.025, 140), 2500), -0.1)
    if mode == "sheriff":
        for st in np.arange(2, duration, 6):
            add(out, bell(880, 0.8, 0.09, 0.25), float(st))
    return out


def bgm_victory_good() -> np.ndarray:
    out = np.zeros((int(SR*15), 2))
    for st, freqs in [(0, [293.7, 370, 440]), (1.2, [370, 440, 587]), (2.4, [440, 554, 659]), (3.6, [587, 740, 880])]:
        add(out, chord(freqs, 2.2, 0.32, 0, tremolo=2.5), st)
    melody = [587, 659, 740, 659, 587, 494, 440, 587]
    for i, f in enumerate(melody):
        add(out, pluck(f, 1.1, 0.18, -0.15), 5 + i*0.62)
    for st in [10, 11.4, 12.8]:
        add(out, bell(1046, 1.4, 0.16, 0.35), st)
    add(out, shimmer(4, 1046, 0.18), 10.8)
    return out


def bgm_victory_wolf() -> np.ndarray:
    out = np.zeros((int(SR*15), 2))
    add(out, chord([73.4, 110, 146.8], 4.5, 0.32, 0, tremolo=2.5), 0)
    add(out, drum(72, 1.2, 0.44, 0), 0.3)
    melody = [294, 330, 370, 330, 294, 247, 220, 294]
    for i, f in enumerate(melody):
        add(out, pluck(f, 0.95, 0.16, -0.2 + (i % 3) * 0.2), 4.3 + i * 0.62)
    for st in [9.8, 11.0, 12.2]:
        add(out, bell(587, 1.1, 0.13, 0.25), st)
    add(out, wind(4.4, 0.055, 150), 10.2)
    return out


def main() -> None:
    sfx = {
        "phase_night.wav": sfx_phase_night(),
        "phase_dawn.wav": sfx_phase_dawn(),
        "skill_wolf_kill.wav": sfx_wolf_kill(),
        "skill_seer_check.wav": sfx_seer_check(),
        "skill_antidote.wav": sfx_antidote(),
        "skill_poison.wav": sfx_poison(),
        "skill_hunter_shoot.wav": sfx_hunter_shoot(),
        "skill_self_destruct.wav": sfx_self_destruct(),
        "vote_result.wav": sfx_vote_result(),
        "exile.wav": sfx_exile(),
        "sheriff_elected.wav": sfx_sheriff(),
        "victory_good.wav": sfx_victory_good(),
        "victory_wolf.wav": sfx_victory_wolf(),
    }
    bgm = {
        "night_loop.wav": bgm_loop(30, 60, "Dmin", "night"),
        "day_discussion.wav": bgm_loop(30, 90, "Amin", "day"),
        "vote_tension.wav": bgm_loop(20, 120, "Emin", "vote"),
        "sheriff_campaign.wav": bgm_loop(30, 100, "Gmin", "sheriff"),
        "victory_good.wav": bgm_victory_good(),
        "victory_wolf.wav": bgm_victory_wolf(),
    }
    for name, audio in sfx.items():
        write(SFX_DIR / name, audio)
        print("wrote", SFX_DIR / name)
    for name, audio in bgm.items():
        write(BGM_DIR / name, audio)
        print("wrote", BGM_DIR / name)


if __name__ == "__main__":
    main()
