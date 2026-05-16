from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    root: Path
    app: Path
    configs: Path
    prompts: Path
    data: Path
    graphs: Path
    replays: Path
    contexts: Path
    database: Path
    schema: Path


@dataclass(frozen=True)
class LLMSettings:
    provider_name: str
    api_key: str
    api_url: str
    model_id: str
    api_key_header: str = "Authorization"
    api_key_prefix: str = "Bearer "
    extra_headers: dict[str, str] | None = None
    verify_ssl: bool = True
    timeout_seconds: float = 50.0
    max_retries: int = 5
    retry_backoff_seconds: float = 1.0
    max_concurrency: int = 1
    max_calls_per_game: int = 200
    enabled_phase_names: tuple[str, ...] = (
        "night_wolf",
        "night_seer",
        "night_witch",
        "sheriff_election",
        "day_speech",
        "day_vote",
        "pending_skills",
    )


def get_paths(root: Path | None = None) -> AppPaths:
    repo_root = (root or Path(__file__).resolve().parents[1]).resolve()
    app_dir = repo_root / "app"
    return AppPaths(
        root=repo_root,
        app=app_dir,
        configs=app_dir / "configs",
        prompts=app_dir / "configs" / "prompts",
        data=repo_root / "data",
        graphs=repo_root / "data" / "graphs",
        replays=repo_root / "data" / "replays",
        contexts=repo_root / "data" / "contexts",
        database=repo_root / "data" / "wolf.db",
        schema=app_dir / "infra" / "schema.sql",
    )


def load_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def get_llm_settings(root: Path | None = None) -> LLMSettings | None:
    paths = get_paths(root)
    env_values = load_dotenv(paths.root / ".env")
    merged = {**env_values, **os.environ}
    api_key = merged.get("API_KEY", "").strip()
    api_url = merged.get("API_URL", "").strip()
    model_id = merged.get("MODEL_ID", "").strip()
    if not api_key or not api_url or not model_id:
        return None
    phase_names_raw = merged.get(
        "LLM_ENABLED_PHASES",
        "night_wolf,night_seer,night_witch,sheriff_election,day_speech,day_vote,pending_skills",
    )
    enabled_phase_names = tuple(
        item.strip() for item in phase_names_raw.split(",") if item.strip()
    ) or (
        "night_wolf",
        "night_seer",
        "night_witch",
        "sheriff_election",
        "day_speech",
        "day_vote",
        "pending_skills",
    )
    extra_headers_raw = merged.get("LLM_EXTRA_HEADERS_JSON", "").strip()
    extra_headers = json.loads(extra_headers_raw) if extra_headers_raw else None
    return LLMSettings(
        provider_name=merged.get("LLM_PROVIDER", "openai_compatible").strip() or "openai_compatible",
        api_key=api_key,
        api_url=api_url,
        model_id=model_id,
        api_key_header=merged.get("LLM_API_KEY_HEADER", "Authorization").strip() or "Authorization",
        api_key_prefix=merged.get("LLM_API_KEY_PREFIX", "Bearer "),
        extra_headers=extra_headers,
        verify_ssl=merged.get("LLM_VERIFY_SSL", "true").strip().lower() not in {"0", "false", "no"},
        timeout_seconds=float(merged.get("LLM_TIMEOUT_SECONDS", 50.0)),
        max_retries=max(5, int(merged.get("LLM_MAX_RETRIES", 5))),
        retry_backoff_seconds=float(merged.get("LLM_RETRY_BACKOFF_SECONDS", 1.0)),
        max_concurrency=int(merged.get("LLM_MAX_CONCURRENCY", 1)),
        max_calls_per_game=int(merged.get("LLM_MAX_CALLS_PER_GAME", 200)),
        enabled_phase_names=enabled_phase_names,
    )
