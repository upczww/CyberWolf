"""ChatTTS-based text-to-speech for game narration.

Each player gets a unique voice (via seed). Emotion is controlled by
speed/temperature parameters based on role and game context.
"""
from __future__ import annotations

import asyncio
import io
import logging
import threading
import wave
from typing import Any

import numpy as np

from app.domain.events import GameEvent
from app.domain.roles import EventType

_log = logging.getLogger(__name__)

# Emotion presets: (speed, temperature, top_p, top_k)
# Higher temperature = more expressive/emotional
EMOTION_PRESETS: dict[str, dict[str, Any]] = {
    "neutral": {"speed": 3, "temperature": 0.3, "top_P": 0.7, "top_K": 20},
    "angry": {"speed": 5, "temperature": 0.5, "top_P": 0.8, "top_K": 30},
    "sad": {"speed": 1, "temperature": 0.2, "top_P": 0.6, "top_K": 15},
    "cheerful": {"speed": 4, "temperature": 0.5, "top_P": 0.8, "top_K": 25},
    "serious": {"speed": 2, "temperature": 0.3, "top_P": 0.7, "top_K": 20},
    "fearful": {"speed": 6, "temperature": 0.6, "top_P": 0.9, "top_K": 30},
}

# Role + context -> emotion
ROLE_EMOTION_MAP: dict[tuple[str, str], str] = {
    ("wolf", "public_speech_made"): "serious",
    ("wolf", "death_speech"): "angry",
    ("wolf", "sheriff_campaign"): "cheerful",
    ("seer", "public_speech_made"): "serious",
    ("seer", "death_speech"): "sad",
    ("seer", "sheriff_campaign"): "serious",
    ("witch", "public_speech_made"): "neutral",
    ("witch", "death_speech"): "sad",
    ("hunter", "public_speech_made"): "cheerful",
    ("hunter", "death_speech"): "angry",
    ("villager", "public_speech_made"): "neutral",
    ("villager", "death_speech"): "sad",
    ("idiot", "public_speech_made"): "cheerful",
    ("idiot", "death_speech"): "cheerful",
}

# 12 fixed seeds for distinct voices
PLAYER_VOICE_SEEDS = [42, 137, 256, 389, 512, 678, 777, 888, 999, 1024, 1111, 1234]

# Events that should trigger TTS
_TTS_EVENT_TYPES = {
    EventType.PUBLIC_SPEECH_MADE,
    EventType.DEATH_SPEECH,
    EventType.SHERIFF_CAMPAIGN,
}


class TTSEngine:
    """ChatTTS wrapper with lazy initialization and async playback queue."""

    def __init__(self) -> None:
        self._chat: Any = None
        self._lock = threading.Lock()
        self._queue: asyncio.Queue[tuple[str, int, str]] = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None
        self._enabled = False
        self._player_roles: dict[int, str] = {}  # player_id -> role (set per game)

    @property
    def enabled(self) -> bool:
        return self._enabled

    def toggle(self) -> bool:
        """Toggle TTS on/off. Returns new state."""
        self._enabled = not self._enabled
        if self._enabled:
            self._ensure_loaded()
        return self._enabled

    def set_player_roles(self, players: dict[int, dict]) -> None:
        """Set player roles for voice/emotion mapping."""
        self._player_roles = {pid: p.get("role", "villager") for pid, p in players.items()}

    def start_worker(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        """Start the async playback worker."""
        if self._worker_task is None or self._worker_task.done():
            if loop:
                self._worker_task = loop.create_task(self._playback_worker())
            else:
                self._worker_task = asyncio.ensure_future(self._playback_worker())

    def on_event(self, event: GameEvent) -> None:
        """EventBus callback — queue speech events for TTS."""
        if not self._enabled:
            return
        if event.event_type not in _TTS_EVENT_TYPES:
            return
        data = event.data or {}
        text = data.get("speech", "")
        if not text:
            return
        player_id = data.get("player_id", 0)
        event_type = event.event_type.value
        try:
            self._queue.put_nowait((text, player_id, event_type))
        except (asyncio.QueueFull, RuntimeError):
            pass  # Drop if queue is full or loop closed

    def _ensure_loaded(self) -> None:
        """Lazy-load ChatTTS model (first call only, ~10s)."""
        if self._chat is not None:
            return
        with self._lock:
            if self._chat is not None:
                return
            _log.info("Loading ChatTTS model (first time, may take ~10s)...")
            try:
                import ChatTTS
                chat = ChatTTS.Chat()
                chat.load(compile=False)  # compile=False for CPU compatibility
                self._chat = chat
                _log.info("ChatTTS model loaded successfully")
            except Exception as exc:
                _log.error("Failed to load ChatTTS: %s", exc)
                self._enabled = False

    async def _playback_worker(self) -> None:
        """Consume queue and play audio sequentially."""
        while True:
            text, player_id, event_type = await self._queue.get()
            if not self._enabled:
                continue
            try:
                await asyncio.to_thread(self._synthesize_and_play, text, player_id, event_type)
            except Exception as exc:
                _log.warning("TTS playback failed: %s", exc)

    def _synthesize_and_play(self, text: str, player_id: int, event_type: str) -> None:
        """Synthesize speech and play it (blocking, runs in thread)."""
        if self._chat is None:
            self._ensure_loaded()
        if self._chat is None:
            return

        # Select voice seed for this player
        seed_idx = (player_id - 1) % len(PLAYER_VOICE_SEEDS)
        voice_seed = PLAYER_VOICE_SEEDS[seed_idx]

        # Select emotion based on role + event type
        role = self._player_roles.get(player_id, "villager")
        if isinstance(role, object) and hasattr(role, "value"):
            role = role.value
        emotion_key = ROLE_EMOTION_MAP.get((role, event_type), "neutral")
        emotion = EMOTION_PRESETS[emotion_key]

        # Generate speech with ChatTTS
        import torch
        params_infer = self._chat.InferCodeParams(
            spk_emb=self._get_speaker_embedding(voice_seed),
            temperature=emotion["temperature"],
            top_P=emotion["top_P"],
            top_K=emotion["top_K"],
        )
        params_refine = self._chat.RefineTextParams(
            temperature=emotion["temperature"],
            top_P=emotion["top_P"],
            top_K=emotion["top_K"],
        )

        # Truncate long text for TTS (max ~200 chars)
        tts_text = text[:200] + "..." if len(text) > 200 else text

        wavs = self._chat.infer(
            [tts_text],
            params_infer_code=params_infer,
            params_refine_text=params_refine,
        )

        if wavs and len(wavs) > 0 and wavs[0] is not None:
            audio_data = wavs[0]
            if isinstance(audio_data, torch.Tensor):
                audio_data = audio_data.numpy()
            audio_data = (audio_data * 32767).astype(np.int16)
            self._play_audio(audio_data, sample_rate=24000)

    def _get_speaker_embedding(self, seed: int) -> Any:
        """Generate a deterministic speaker embedding from seed."""
        import torch
        torch.manual_seed(seed)
        return self._chat.sample_random_speaker()

    @staticmethod
    def _play_audio(audio_data: np.ndarray, sample_rate: int = 24000) -> None:
        """Play audio via sounddevice or fallback to writing wav + system player."""
        try:
            import sounddevice as sd
            sd.play(audio_data.flatten(), samplerate=sample_rate, blocking=True)
            return
        except (ImportError, Exception):
            pass

        # Fallback: write to temp wav and play via system command
        import subprocess
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name
            with wave.open(f, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_data.flatten().tobytes())

        # Try common audio players
        for cmd in ["aplay", "paplay", "ffplay -nodisp -autoexit", "afplay"]:
            parts = cmd.split()
            try:
                subprocess.run([*parts, tmp_path], check=True, capture_output=True, timeout=30)
                return
            except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
                continue


# Singleton instance
tts_engine = TTSEngine()
