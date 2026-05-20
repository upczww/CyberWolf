from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

import numpy as np
import soundfile as sf

from manifest_asset_utils import AssetResource, resources_by_type, validate_manifest_outputs

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_RATE = 24_000
NARRATOR_SEED = 2024
VOICE_TEXTS = {
    "voice_sys_dark_please_close_eyes": "天黑请闭眼。",
    "voice_sys_wolves_open_eyes": "狼人请睁眼。",
    "voice_sys_wolves_close_eyes": "狼人请闭眼。",
    "voice_sys_witch_open_eyes": "女巫请睁眼。",
    "voice_sys_witch_close_eyes": "女巫请闭眼。",
    "voice_sys_seer_open_eyes": "预言家请睁眼。",
    "voice_sys_seer_close_eyes": "预言家请闭眼。",
    "voice_sys_hunter_open_eyes": "猎人请睁眼。",
    "voice_sys_hunter_close_eyes": "猎人请闭眼。",
    "voice_sys_idiot_open_eyes": "白痴请睁眼。",
    "voice_sys_idiot_close_eyes": "白痴请闭眼。",
    "voice_sys_dawn": "天亮了，请睁眼。",
    "voice_sys_run_for_sheriff": "现在开始警长竞选。",
    "voice_sys_speech_start": "现在开始发言。",
    "voice_sys_vote_start": "现在开始投票。",
    "voice_sys_pk_start": "进入PK发言环节。",
    "voice_sys_night_direct": "当前流程结束，立即进入黑夜。",
    "voice_result_peace_night": "昨晚是平安夜，无人出局。",
    "voice_result_player_out": "昨晚，X号玩家出局。",
    "voice_result_player_exiled": "X号玩家被放逐出局。",
    "voice_result_sheriff_elected": "X号玩家当选警长。",
    "voice_result_no_sheriff": "本局没有警长。",
    "voice_result_tie_no_exile": "平票，本轮无人出局。",
    "voice_result_good_win": "好人阵营获胜。",
    "voice_result_wolf_win": "狼人阵营获胜。",
    "voice_skill_self_destruct": "X号玩家选择自爆。",
    "voice_role_intro_villager": "平民：无特殊技能，白天通过发言和投票帮助好人找出狼人。",
    "voice_role_intro_werewolf": "狼人：每晚共同击杀一名玩家，白天可以伪装身份并选择自爆。",
    "voice_role_intro_seer": "预言家：每晚查验一名玩家，得知其是好人还是狼人。",
    "voice_role_intro_witch": "女巫：拥有一瓶解药和一瓶毒药，每晚只能使用一瓶药。",
    "voice_role_intro_hunter": "猎人：出局时若可以开枪，可带走一名玩家。",
    "voice_role_intro_idiot": "白痴：被白天放逐时可以翻牌免于出局，但失去投票权。",
}


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


def text_from_prompt(resource: AssetResource) -> str:
    if resource.id in VOICE_TEXTS:
        return VOICE_TEXTS[resource.id]
    prompt = resource.prompt or ""
    match = re.search(r"[“\"](.+?)[”\"]", prompt)
    if match:
        return match.group(1)
    raise KeyError(f"Missing explicit voice text for {resource.id}")


def generate_voice_assets() -> None:
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

    for resource in resources_by_type("voice"):
        text = text_from_prompt(resource)
        wavs = chat.infer(
            [text],
            params_infer_code=params_infer,
            params_refine_text=params_refine,
        )
        if not wavs or wavs[0] is None:
            raise RuntimeError(f"ChatTTS returned no audio for {resource.id}: {text}")
        audio = np.asarray(wavs[0], dtype=np.float32).squeeze()
        audio = trim_and_normalize(audio)
        resource.output_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(resource.output_path, audio, SAMPLE_RATE, subtype="PCM_16")
        print(f"wrote {resource.full_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate manifest-aligned narrator voice assets from scratch.")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    generate_voice_assets()
    if args.verify:
        report = validate_manifest_outputs(["voice"])
        print(f"present={report['present_resources']} missing={report['missing_resources']}")
        if report["missing_resources"]:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
