"""Bark BGM generator — API endpoints for generating and serving game BGM.

Uses suno/bark model with GPU acceleration.
Bark can generate music via special music prompts with ♪ notation.
"""
from __future__ import annotations

import logging
import asyncio
from pathlib import Path
from typing import Any

import numpy as np
import scipy.io.wavfile
from fastapi import APIRouter
from pydantic import BaseModel

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/music", tags=["music"])

# Output directory
BGM_DIR = Path(__file__).resolve().parents[1] / "desktop" / "public" / "assets" / "bgm"

# Lazy-loaded model
_model = None
_processor = None
_sample_rate = 24000


def _ensure_model():
    global _model, _processor, _sample_rate
    if _model is not None:
        return
    _log.info("Loading Bark model (first time, downloading ~5GB)...")
    import torch
    from transformers import AutoProcessor, BarkModel

    _processor = AutoProcessor.from_pretrained("suno/bark")
    _model = BarkModel.from_pretrained("suno/bark", torch_dtype=torch.float16)
    if torch.cuda.is_available():
        _model = _model.to("cuda")
        _log.info("Bark loaded on GPU (CUDA)")
    else:
        _log.info("Bark loaded on CPU (will be slow)")
    _model = _model.eval()
    _sample_rate = _model.generation_config.sample_rate
    _log.info("Bark model ready, sample_rate=%d", _sample_rate)


class GenerateRequest(BaseModel):
    prompt: str = "♪ dark mysterious ambient music with strings and piano ♪"
    filename: str = "bgm_custom"
    segments: int = 4


class BGMInfo(BaseModel):
    filename: str
    path: str
    size_kb: float


# Bark uses text prompts with ♪ markers for music generation.
# We generate multiple segments and concatenate for longer tracks.
PRESETS: dict[str, dict[str, Any]] = {
    "night": {
        "prompt": "♪ dark mysterious ambient orchestral music, slow tempo, haunting cello, minor key ♪",
        "filename": "bgm_night",
        "segments": 6,
    },
    "day": {
        "prompt": "♪ tense suspenseful acoustic music, moderate tempo, plucked strings, analytical mood ♪",
        "filename": "bgm_day",
        "segments": 6,
    },
    "vote": {
        "prompt": "♪ intense dramatic countdown music, fast tempo, driving rhythm, suspenseful strings ♪",
        "filename": "bgm_vote",
        "segments": 4,
    },
    "sheriff": {
        "prompt": "♪ dramatic bold brass fanfare music, moderate tempo, authoritative, competitive ♪",
        "filename": "bgm_sheriff",
        "segments": 6,
    },
    "victory_good": {
        "prompt": "♪ triumphant joyful orchestral fanfare, major key, heroic brass, celebration ♪",
        "filename": "bgm_victory_good",
        "segments": 3,
    },
    "victory_wolf": {
        "prompt": "♪ ominous dark orchestral music, sinister, minor key, thunderous, menacing ♪",
        "filename": "bgm_victory_wolf",
        "segments": 3,
    },
}


@router.get("/presets")
async def list_presets():
    return {
        name: {"prompt": p["prompt"], "filename": p["filename"], "segments": p["segments"]}
        for name, p in PRESETS.items()
    }


@router.get("/files")
async def list_files():
    BGM_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    for f in sorted(BGM_DIR.glob("*.wav")):
        files.append(BGMInfo(
            filename=f.name,
            path=f"/assets/bgm/{f.name}",
            size_kb=round(f.stat().st_size / 1024, 1),
        ))
    return files


@router.post("/generate")
async def generate_bgm(req: GenerateRequest):
    BGM_DIR.mkdir(parents=True, exist_ok=True)
    output_path = BGM_DIR / f"{req.filename}.wav"
    result = await asyncio.to_thread(_generate_sync, req.prompt, req.segments, output_path)
    return result


@router.post("/generate/{preset_name}")
async def generate_preset(preset_name: str):
    preset = PRESETS.get(preset_name)
    if not preset:
        return {"error": f"Unknown preset: {preset_name}", "available": list(PRESETS.keys())}
    BGM_DIR.mkdir(parents=True, exist_ok=True)
    output_path = BGM_DIR / f"{preset['filename']}.wav"
    result = await asyncio.to_thread(_generate_sync, preset["prompt"], preset["segments"], output_path)
    return result


def _generate_sync(prompt: str, segments: int, output_path: Path) -> dict[str, Any]:
    """Generate music by concatenating multiple Bark segments."""
    import torch

    _ensure_model()

    _log.info("Generating BGM: prompt=%s, segments=%d", prompt[:60], segments)

    all_audio = []

    for i in range(segments):
        _log.info("  Generating segment %d/%d...", i + 1, segments)
        inputs = _processor(prompt, return_tensors="pt")
        if torch.cuda.is_available():
            inputs = {k: v.to("cuda") for k, v in inputs.items()}

        with torch.no_grad():
            audio_values = _model.generate(
                **inputs,
                do_sample=True,
                fine_temperature=0.4,
                coarse_temperature=0.8,
            )

        audio_data = audio_values.cpu().numpy().squeeze()
        all_audio.append(audio_data)

    # Concatenate all segments with short crossfade
    combined = _crossfade_segments(all_audio, crossfade_samples=int(_sample_rate * 0.1))

    # Normalize
    if combined.max() > 0:
        combined = combined / np.max(np.abs(combined)) * 0.9

    # Convert to int16
    audio_int16 = (combined * 32767).astype(np.int16)

    # Save
    scipy.io.wavfile.write(str(output_path), _sample_rate, audio_int16)

    duration = len(audio_int16) / _sample_rate
    size_kb = round(output_path.stat().st_size / 1024, 1)
    _log.info("BGM saved: %s (%.1fs, %.1f KB)", output_path.name, duration, size_kb)

    return {
        "success": True,
        "filename": output_path.name,
        "path": f"/assets/bgm/{output_path.name}",
        "size_kb": size_kb,
        "duration_seconds": round(duration, 1),
        "prompt": prompt,
        "segments": segments,
        "sample_rate": _sample_rate,
    }


def _crossfade_segments(segments: list[np.ndarray], crossfade_samples: int = 2400) -> np.ndarray:
    """Concatenate audio segments with smooth crossfade to avoid clicks."""
    if not segments:
        return np.array([], dtype=np.float32)
    if len(segments) == 1:
        return segments[0]

    result = segments[0].copy()
    for seg in segments[1:]:
        if len(result) < crossfade_samples or len(seg) < crossfade_samples:
            result = np.concatenate([result, seg])
            continue
        # Crossfade region
        fade_out = np.linspace(1, 0, crossfade_samples)
        fade_in = np.linspace(0, 1, crossfade_samples)
        result[-crossfade_samples:] = result[-crossfade_samples:] * fade_out + seg[:crossfade_samples] * fade_in
        result = np.concatenate([result, seg[crossfade_samples:]])

    return result
