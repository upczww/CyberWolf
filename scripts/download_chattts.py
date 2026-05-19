"""Pre-warm ChatTTS weights via huggingface_hub.hf_hub_download.

Uses per-file downloads (which go through `requests` and therefore honor
HTTP(S)_PROXY) instead of `snapshot_download` (which goes through `httpx` and
breaks on some local Clash-style proxies with SSL UNEXPECTED_EOF).

Run once. After it finishes, the FastAPI server can `chat.load(source="huggingface")`
fully offline because the cache at ~/.cache/huggingface/hub/models--2Noise--ChatTTS
is populated.

Usage:
    python scripts/download_chattts.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


REPO_ID = "2Noise/ChatTTS"
# Files needed by ChatTTS.load(source="huggingface") — the allow_patterns from
# its own snapshot_download call: *.yaml, *.json, *.safetensors.
FILES = [
    "config/path.yaml",
    "config/decoder.yaml",
    "config/dvae.yaml",
    "config/gpt.yaml",
    "config/decoder.safetensors",
    "config/dvae.safetensors",
    "config/gpt.safetensors",
    "asset/tokenizer.pt",
    "asset/tokenizer/special_tokens_map.json",
    "asset/tokenizer/tokenizer.json",
    "asset/tokenizer/tokenizer_config.json",
    "asset/Embed.safetensors",
    "asset/Decoder.safetensors",
    "asset/DVAE.safetensors",
    "asset/DVAE_full.safetensors",
    "asset/GPT.safetensors",
    "asset/Vocos.safetensors",
    "asset/spk_stat.pt",
]


def main() -> int:
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    try:
        from huggingface_hub import hf_hub_download, list_repo_files
    except Exception as exc:
        print(f"[chattts-warm] huggingface_hub import failed: {exc}", file=sys.stderr)
        return 1

    # Best effort: discover the real file list. If listing fails, fall back to the
    # hard-coded set above.
    try:
        listed = list_repo_files(REPO_ID)
        # keep just the patterns ChatTTS itself filters for
        wanted = [f for f in listed if f.endswith((".yaml", ".json", ".safetensors", ".pt"))]
        if wanted:
            target_files = wanted
        else:
            target_files = FILES
    except Exception as exc:
        print(f"[chattts-warm] list_repo_files failed ({exc}), using built-in list")
        target_files = FILES

    print(f"[chattts-warm] downloading {len(target_files)} files from {REPO_ID}")
    cache_root = Path.home() / ".cache" / "huggingface"
    print(f"[chattts-warm] cache root: {cache_root}")

    failed: list[tuple[str, str]] = []
    for i, fname in enumerate(target_files, 1):
        try:
            p = hf_hub_download(repo_id=REPO_ID, filename=fname)
            print(f"  [{i:2d}/{len(target_files)}] OK   {fname}  → {p}")
        except Exception as exc:
            print(f"  [{i:2d}/{len(target_files)}] FAIL {fname}: {exc}")
            failed.append((fname, str(exc)))

    if failed:
        print(f"\n[chattts-warm] {len(failed)} files failed; some may be optional.")
        for fname, err in failed:
            print(f"  - {fname}: {err}")

    # Verify ChatTTS can actually load now
    print("\n[chattts-warm] verifying via ChatTTS.load(source='huggingface')…")
    try:
        import ChatTTS  # type: ignore[import-untyped]
        chat = ChatTTS.Chat()
        ok = chat.load(compile=False, source="huggingface")
    except Exception as exc:
        print(f"[chattts-warm] load() raised: {exc}", file=sys.stderr)
        return 3
    if not ok:
        print("[chattts-warm] load() returned falsy — some required file missing", file=sys.stderr)
        return 4
    print("[chattts-warm] ChatTTS loaded OK. Restart the FastAPI server.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
