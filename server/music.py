"""ACE-Step 1.5 BGM generator — API endpoints for generating and serving game BGM.

Uses ACE-Step 1.5 model for high-quality instrumental music generation.
Install: pip install git+https://github.com/ace-step/ACE-Step-1.5.git
Model auto-downloads from HuggingFace on first use.
"""
from __future__ import annotations

import logging
import asyncio
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/music", tags=["music"])

# Output directory
BGM_DIR = Path(__file__).resolve().parents[1] / "desktop" / "public" / "assets" / "bgm"

# Lazy-loaded pipeline
_pipeline = None


def _ensure_model():
    global _pipeline
    if _pipeline is not None:
        return
    _log.info("Loading ACE-Step 1.5 model (first time, auto-downloading)...")
    try:
        from acestep import ACEStepPipeline
        _pipeline = ACEStepPipeline()
        _log.info("ACE-Step 1.5 loaded successfully")
    except ImportError:
        _log.error(
            "ACE-Step not installed. Run: pip install git+https://github.com/ace-step/ACE-Step-1.5.git"
        )
        raise


class GenerateRequest(BaseModel):
    tags: str = "ambient, orchestral, dark, mysterious, instrumental"
    lyrics: str = "[instrumental]"
    filename: str = "bgm_custom"
    duration: int = 30
    steps: int = 32


class BGMInfo(BaseModel):
    filename: str
    path: str
    size_kb: float


# Preset prompts — tags describe style, lyrics = [instrumental] for pure music
PRESETS: dict[str, dict[str, Any]] = {
    "night": {
        "tags": "ambient, orchestral, dark, mysterious, haunting, cello, piano, minor key, slow tempo, 60 bpm, cinematic, game soundtrack",
        "lyrics": "[instrumental]",
        "filename": "bgm_night",
        "duration": 30,
    },
    "day": {
        "tags": "acoustic, tense, suspenseful, pizzicato strings, light percussion, medieval, analytical, moderate tempo, 90 bpm, game soundtrack",
        "lyrics": "[instrumental]",
        "filename": "bgm_day",
        "duration": 30,
    },
    "vote": {
        "tags": "intense, dramatic, countdown, driving strings, ticking rhythm, brass stabs, suspenseful, fast tempo, 110 bpm, game soundtrack",
        "lyrics": "[instrumental]",
        "filename": "bgm_vote",
        "duration": 20,
    },
    "sheriff": {
        "tags": "dramatic, bold, brass fanfare, military snare, competitive, authoritative, moderate tempo, 100 bpm, game soundtrack",
        "lyrics": "[instrumental]",
        "filename": "bgm_sheriff",
        "duration": 30,
    },
    "victory_good": {
        "tags": "triumphant, joyful, orchestral, heroic brass, soaring strings, major key, celebration, uplifting, 120 bpm, game soundtrack",
        "lyrics": "[instrumental]",
        "filename": "bgm_victory_good",
        "duration": 15,
    },
    "victory_wolf": {
        "tags": "ominous, dark, orchestral, sinister brass, menacing, thunderous drums, minor key, powerful, 80 bpm, game soundtrack",
        "lyrics": "[instrumental]",
        "filename": "bgm_victory_wolf",
        "duration": 15,
    },
}


@router.get("/presets")
async def list_presets():
    return {
        name: {"tags": p["tags"], "filename": p["filename"], "duration": p["duration"]}
        for name, p in PRESETS.items()
    }


@router.get("/files")
async def list_files():
    BGM_DIR.mkdir(parents=True, exist_ok=True)
    files = []
    for ext in ("*.wav", "*.flac", "*.mp3"):
        for f in sorted(BGM_DIR.glob(ext)):
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
    result = await asyncio.to_thread(
        _generate_sync, req.tags, req.lyrics, req.duration, req.steps, output_path,
    )
    return result


@router.post("/generate/{preset_name}")
async def generate_preset(preset_name: str):
    preset = PRESETS.get(preset_name)
    if not preset:
        return {"error": f"Unknown preset: {preset_name}", "available": list(PRESETS.keys())}
    BGM_DIR.mkdir(parents=True, exist_ok=True)
    output_path = BGM_DIR / f"{preset['filename']}.wav"
    result = await asyncio.to_thread(
        _generate_sync, preset["tags"], preset["lyrics"], preset["duration"], 32, output_path,
    )
    return result


def _generate_sync(
    tags: str, lyrics: str, duration: int, steps: int, output_path: Path,
) -> dict[str, Any]:
    """Synchronous generation (runs in thread)."""
    _ensure_model()

    _log.info("Generating BGM: tags=%s, duration=%ds, steps=%d", tags[:60], duration, steps)

    result = _pipeline(
        tags=tags,
        lyrics=lyrics,
        duration=duration,
        infer_step=steps,
        save_path=str(output_path),
    )

    size_kb = round(output_path.stat().st_size / 1024, 1) if output_path.exists() else 0
    _log.info("BGM saved: %s (%.1f KB)", output_path.name, size_kb)

    return {
        "success": True,
        "filename": output_path.name,
        "path": f"/assets/bgm/{output_path.name}",
        "size_kb": size_kb,
        "duration_seconds": duration,
        "tags": tags,
    }
