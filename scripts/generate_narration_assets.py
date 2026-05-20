"""Pre-generate fixed referee narration for the desktop client.

Dynamic player speeches still use live ChatTTS. These short system prompts are
stable across games, so generating them once avoids runtime latency and keeps
the narrator voice consistent.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np
import soundfile as sf


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "desktop" / "public" / "assets" / "narration"
SAMPLE_RATE = 24_000
NARRATOR_SEED = 2024

NARRATION_LINES: dict[str, str] = {
    "setup_game": "准备开始。",
    "night_start": "天黑请闭眼。",
    "night_wolf": "狼人请睁眼。",
    "night_seer": "预言家请睁眼。",
    "night_witch": "女巫请睁眼。",
    "night_resolve": "天亮了。",
    "day_announce": "昨夜信息公布。",
    "sheriff_election": "现在开始警长竞选。",
    "day_speech": "请按顺序发言。",
    "day_vote": "发言结束，请投票。",
    "day_resolve": "投票结束，开始放逐结算。",
    "pending_skills": "技能结算开始。",
    "check_win": "正在检查胜负。",
    "game_over": "游戏结束。",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="overwrite existing files")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    chat = load_chattts()
    speaker = narrator_speaker(chat)

    params_infer = chat.InferCodeParams(
        spk_emb=speaker,
        temperature=0.22,
        top_P=0.7,
        top_K=20,
    )
    params_refine = chat.RefineTextParams(
        temperature=0.22,
        top_P=0.7,
        top_K=20,
    )

    for key, text in NARRATION_LINES.items():
        path = OUT_DIR / f"{key}.wav"
        if path.exists() and not args.force:
            print("skip", path)
            continue

        wavs = chat.infer(
            [text],
            params_infer_code=params_infer,
            params_refine_text=params_refine,
        )
        if not wavs or wavs[0] is None:
            raise RuntimeError(f"ChatTTS returned no audio for {key}: {text}")

        audio = np.asarray(wavs[0], dtype=np.float32).squeeze()
        audio = trim_and_normalize(audio)
        sf.write(path, audio, SAMPLE_RATE)
        print("wrote", path)


def load_chattts():
    import ChatTTS

    chat = ChatTTS.Chat()
    custom_path = resolve_chattts_path()
    if custom_path is not None:
        ok = chat.load(compile=False, source="custom", custom_path=str(custom_path))
    else:
        ok = chat.load(compile=False)
    if not ok:
        raise RuntimeError("ChatTTS.load() returned False")
    return chat


def narrator_speaker(chat):
    import torch

    torch.manual_seed(NARRATOR_SEED)
    return chat.sample_random_speaker()


def trim_and_normalize(audio: np.ndarray) -> np.ndarray:
    if audio.ndim > 1:
        audio = audio.reshape(-1)
    audio = np.nan_to_num(audio)
    if not len(audio):
        return audio

    threshold = max(0.006, float(np.max(np.abs(audio))) * 0.015)
    active = np.where(np.abs(audio) > threshold)[0]
    if len(active):
        pad = int(SAMPLE_RATE * 0.08)
        start = max(0, int(active[0]) - pad)
        end = min(len(audio), int(active[-1]) + pad)
        audio = audio[start:end]

    fade_len = min(len(audio) // 4, int(SAMPLE_RATE * 0.035))
    if fade_len > 0:
        audio[:fade_len] *= np.linspace(0, 1, fade_len, dtype=np.float32)
        audio[-fade_len:] *= np.linspace(1, 0, fade_len, dtype=np.float32)

    peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
    if peak > 0:
        audio = audio / peak * 0.88
    return np.clip(audio, -1.0, 1.0)


def resolve_chattts_path() -> Path | None:
    candidates: list[Path] = []
    explicit = os.environ.get("LYCAN_CHATTTS_PATH")
    if explicit:
        candidates.append(Path(explicit))

    home = Path.home()
    candidates.append(home / ".cache" / "modelscope" / "AI-ModelScope" / "ChatTTS")
    hf_root = home / ".cache" / "huggingface" / "hub" / "models--2Noise--ChatTTS" / "snapshots"
    if hf_root.exists():
        candidates.extend(sorted([p for p in hf_root.iterdir() if p.is_dir()], reverse=True))

    for candidate in candidates:
        if (candidate / "asset").exists() and (candidate / "config").exists():
            return candidate
    return None


if __name__ == "__main__":
    main()
