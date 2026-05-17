"""MusicGen BGM generator — API endpoints for generating and serving game BGM.

Uses facebook/musicgen-small (300M) with GPU acceleration.
"""
from __future__ import annotations

import hashlib
import logging
import asyncio
from pathlib import Path
from typing import Any

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


def _ensure_model():
    global _model, _processor
    if _model is not None:
        return
    _log.info("Loading MusicGen model (first time, downloading ~500MB)...")
    from transformers import AutoProcessor, MusicgenForConditionalGeneration
    import torch

    _processor = AutoProcessor.from_pretrained("facebook/musicgen-small")
    _model = MusicgenForConditionalGeneration.from_pretrained("facebook/musicgen-small")
    if torch.cuda.is_available():
        _model = _model.to("cuda")
        _log.info("MusicGen loaded on GPU (CUDA)")
    else:
        _log.info("MusicGen loaded on CPU (will be slow)")


class GenerateRequest(BaseModel):
    prompt: str = "dark ambient orchestral, mysterious, cello drone, sparse piano, game night BGM"
    duration_seconds: float = 30.0
    filename: str = "bgm_custom"


class BGMInfo(BaseModel):
    filename: str
    path: str
    size_kb: float
    prompt: str | None = None


# Preset prompts for game phases
PRESETS: dict[str, dict[str, str]] = {
    "night": {
        "prompt": "dark ambient orchestral, 60 BPM, D minor, mysterious tense atmosphere, low cello drone, sparse haunting piano notes, subtle heartbeat rhythm, no vocals, seamless loop, game night phase background music, cinematic",
        "filename": "bgm_night",
    },
    "day": {
        "prompt": "tense acoustic thriller, 90 BPM, A minor, suspicious analytical mood, pizzicato strings, light frame drum, guzheng plucks, no vocals, seamless loop, game discussion phase background music, medieval tavern",
        "filename": "bgm_day",
    },
    "vote": {
        "prompt": "intense countdown tension, 110 BPM, E minor, driving string ostinato, ticking clock percussion, brass stabs, snare build, no vocals, seamless loop, game voting phase background music, suspenseful",
        "filename": "bgm_vote",
    },
    "sheriff": {
        "prompt": "dramatic competitive, 100 BPM, G minor, bold brass authority theme, military snare, competitive strings, no vocals, seamless loop, game campaign phase background music, medieval court",
        "filename": "bgm_sheriff",
    },
    "victory_good": {
        "prompt": "triumphant orchestral fanfare, 120 BPM, D major, heroic brass melody, soaring strings, warm cello harmony, joyful hopeful, no vocals, short victory theme, game win music, cinematic",
        "filename": "bgm_victory_good",
    },
    "victory_wolf": {
        "prompt": "ominous dark orchestral, 80 BPM, D minor, menacing brass doom chords, wolf howl motif, thunderous drums, sinister powerful, no vocals, short defeat theme, game dark victory music, cinematic",
        "filename": "bgm_victory_wolf",
    },
}


@router.get("/presets")
async def list_presets():
    """List available BGM presets."""
    return {
        name: {"prompt": p["prompt"], "filename": p["filename"]}
        for name, p in PRESETS.items()
    }


@router.get("/files")
async def list_files():
    """List generated BGM files."""
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
    """Generate BGM from text prompt using MusicGen."""
    BGM_DIR.mkdir(parents=True, exist_ok=True)
    output_path = BGM_DIR / f"{req.filename}.wav"

    # Run generation in thread to not block the event loop
    result = await asyncio.to_thread(_generate_sync, req.prompt, req.duration_seconds, output_path)
    return result


@router.post("/generate/{preset_name}")
async def generate_preset(preset_name: str):
    """Generate BGM from a preset."""
    preset = PRESETS.get(preset_name)
    if not preset:
        return {"error": f"Unknown preset: {preset_name}", "available": list(PRESETS.keys())}
    BGM_DIR.mkdir(parents=True, exist_ok=True)
    output_path = BGM_DIR / f"{preset['filename']}.wav"
    result = await asyncio.to_thread(_generate_sync, preset["prompt"], 30.0, output_path)
    return result


def _generate_sync(prompt: str, duration_seconds: float, output_path: Path) -> dict[str, Any]:
    """Synchronous generation (runs in thread)."""
    import torch

    _ensure_model()

    # Calculate tokens: ~50 tokens/second for musicgen
    max_tokens = int(duration_seconds * 50)
    max_tokens = min(max_tokens, 1500)  # Cap at ~30s

    _log.info("Generating BGM: prompt=%s, duration=%.1fs, tokens=%d", prompt[:60], duration_seconds, max_tokens)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    inputs = _processor(text=[prompt], padding=True, return_tensors="pt").to(device)

    with torch.no_grad():
        audio_values = _model.generate(**inputs, max_new_tokens=max_tokens)

    # Save as WAV
    sample_rate = _model.config.audio_encoder.sampling_rate
    audio_data = audio_values[0][0].cpu().numpy()
    scipy.io.wavfile.write(str(output_path), sample_rate, audio_data)

    size_kb = round(output_path.stat().st_size / 1024, 1)
    _log.info("BGM saved: %s (%.1f KB)", output_path.name, size_kb)

    return {
        "success": True,
        "filename": output_path.name,
        "path": f"/assets/bgm/{output_path.name}",
        "size_kb": size_kb,
        "duration_seconds": duration_seconds,
        "prompt": prompt,
        "sample_rate": sample_rate,
    }
