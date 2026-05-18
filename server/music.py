"""ACE-Step 1.5 BGM generator — API endpoints for generating game BGM.

Uses ACE-Step 1.5 (MIT license) for high-quality instrumental music.
Requires: pip install -e /path/to/ACE-Step-1.5
"""
from __future__ import annotations

import logging
import asyncio
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/music", tags=["music"])

BGM_DIR = Path(__file__).resolve().parents[1] / "desktop" / "public" / "assets" / "bgm"

# Add ACE-Step to path if installed elsewhere
_ACE_STEP_PATH = Path("/tmp/ace-step")
if _ACE_STEP_PATH.exists() and str(_ACE_STEP_PATH) not in sys.path:
    sys.path.insert(0, str(_ACE_STEP_PATH))

# Lazy-loaded handlers
_dit_handler = None
_llm_handler = None


def _ensure_model():
    global _dit_handler, _llm_handler
    if _dit_handler is not None:
        return
    _log.info("Loading ACE-Step 1.5 model...")
    # Use ACE-Step's venv if available
    ace_venv = _ACE_STEP_PATH / ".venv" / "lib"
    if ace_venv.exists():
        for p in ace_venv.glob("python*/site-packages"):
            if str(p) not in sys.path:
                sys.path.insert(0, str(p))

    from acestep.handler import AceStepHandler
    _dit_handler = AceStepHandler()
    status, enable = _dit_handler.initialize_service(
        project_root=str(_ACE_STEP_PATH),
        config_path="acestep-v15-turbo",
        device="cuda",
    )
    _log.info("ACE-Step init: %s", status)
    _llm_handler = None
    _log.info("ACE-Step 1.5 ready")


class GenerateRequest(BaseModel):
    caption: str = "dark ambient orchestral, mysterious, haunting cello, game soundtrack"
    lyrics: str = "[Instrumental]"
    filename: str = "bgm_custom"
    duration: int = 30
    bpm: int = 80
    infer_step: int = 60


class BGMInfo(BaseModel):
    filename: str
    path: str
    size_kb: float


PRESETS: dict[str, dict[str, Any]] = {
    "night": {
        "caption": "Dark ambient orchestral music, mysterious and tense atmosphere, low cello drone with sparse haunting piano notes, subtle heartbeat rhythm, cinematic game night phase soundtrack",
        "lyrics": "[Instrumental]",
        "filename": "bgm_night",
        "duration": 30,
        "bpm": 60,
    },
    "day": {
        "caption": "Tense acoustic thriller music, suspicious and analytical mood, pizzicato strings with light frame drum, medieval tavern atmosphere, game discussion phase soundtrack",
        "lyrics": "[Instrumental]",
        "filename": "bgm_day",
        "duration": 30,
        "bpm": 90,
    },
    "vote": {
        "caption": "Intense dramatic countdown music, driving string ostinato with ticking clock percussion, brass stabs and building snare, suspenseful game voting phase soundtrack",
        "lyrics": "[Instrumental]",
        "filename": "bgm_vote",
        "duration": 20,
        "bpm": 110,
    },
    "sheriff": {
        "caption": "Dramatic bold brass fanfare music, military snare pattern with competitive string runs, authoritative and commanding, game campaign phase soundtrack",
        "lyrics": "[Instrumental]",
        "filename": "bgm_sheriff",
        "duration": 30,
        "bpm": 100,
    },
    "victory_good": {
        "caption": "Triumphant joyful orchestral fanfare, heroic brass melody with soaring strings, warm hopeful celebration, game victory theme",
        "lyrics": "[Instrumental]",
        "filename": "bgm_victory_good",
        "duration": 15,
        "bpm": 120,
    },
    "victory_wolf": {
        "caption": "Ominous dark orchestral music, sinister brass doom chords with thunderous drums, menacing and powerful, game dark victory theme",
        "lyrics": "[Instrumental]",
        "filename": "bgm_victory_wolf",
        "duration": 15,
        "bpm": 80,
    },
}


@router.get("/presets")
async def list_presets():
    return {
        name: {"caption": p["caption"], "filename": p["filename"], "duration": p["duration"], "bpm": p["bpm"]}
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
    try:
        result = await asyncio.to_thread(
            _generate_sync, req.caption, req.lyrics, req.duration, req.bpm, req.infer_step, output_path,
        )
        return result
    except Exception as exc:
        _log.exception("Generate custom failed")
        return {"success": False, "error": str(exc)}


@router.post("/generate/{preset_name}")
async def generate_preset(preset_name: str):
    preset = PRESETS.get(preset_name)
    if not preset:
        return {"error": f"Unknown preset: {preset_name}", "available": list(PRESETS.keys())}
    BGM_DIR.mkdir(parents=True, exist_ok=True)
    output_path = BGM_DIR / f"{preset['filename']}.wav"
    try:
        result = await asyncio.to_thread(
            _generate_sync, preset["caption"], preset["lyrics"], preset["duration"], preset["bpm"], 8, output_path,
        )
        return result
    except Exception as exc:
        _log.exception("Generate preset failed")
        return {"success": False, "error": str(exc)}


def _generate_sync(
    caption: str, lyrics: str, duration: int, bpm: int, infer_step: int, output_path: Path,
) -> dict[str, Any]:
    _ensure_model()

    from acestep.inference import GenerationParams, GenerationConfig, generate_music

    _log.info("Generating BGM: caption=%s, duration=%ds, bpm=%d", caption[:60], duration, bpm)

    params = GenerationParams(
        caption=caption,
        lyrics=lyrics,
        instrumental=True,
        duration=duration,
        bpm=bpm,
        inference_steps=infer_step,
        guidance_scale=7.0,
    )
    config = GenerationConfig(
        batch_size=1,
        audio_format="wav",
    )

    import tempfile
    with tempfile.TemporaryDirectory() as tmp_dir:
        result = generate_music(
            dit_handler=_dit_handler,
            llm_handler=_llm_handler,
            params=params,
            config=config,
            save_dir=tmp_dir,
        )

        if not result.success or not result.audios:
            _log.error("Generation failed: %s", result.error or result.status_message)
            return {"success": False, "error": result.error or result.status_message}

        # Move generated file to target path
        src = Path(result.audios[0]["path"])
        if src.exists():
            import shutil
            shutil.move(str(src), str(output_path))

    size_kb = round(output_path.stat().st_size / 1024, 1) if output_path.exists() else 0
    _log.info("BGM saved: %s (%.1f KB)", output_path.name, size_kb)

    return {
        "success": True,
        "filename": output_path.name,
        "path": f"/assets/bgm/{output_path.name}",
        "size_kb": size_kb,
        "duration_seconds": duration,
        "caption": caption,
        "bpm": bpm,
    }
