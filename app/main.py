from __future__ import annotations

import argparse
import asyncio
import json

from app.config import get_llm_settings, get_paths
from app.domain.events import GameEvent
from app.engine.bootstrap import bootstrap_and_run_game
from app.infra.events import EventBus


_SCOPE_COLORS = {
    "public": "\033[36m",        # cyan
    "wolf_team": "\033[31m",     # red
    "role_private": "\033[33m",  # yellow
    "god": "\033[35m",           # magenta
    "system": "\033[32m",        # green
}
_BOLD = "\033[1m"
_DIM = "\033[2m"
_RESET = "\033[0m"


def _print_event(event: GameEvent) -> None:
    scope = event.scope.value
    color = _SCOPE_COLORS.get(scope, "")
    phase = event.phase.value
    etype = event.event_type.value
    data_str = json.dumps(event.data, ensure_ascii=False) if event.data else ""
    print(f"{_DIM}{event.game_id[:8]}{_RESET} {color}[{scope}]{_RESET} {phase}/{_BOLD}{etype}{_RESET} {data_str}")


def _print_llm_output(phase: str, player_id: int, tool_name: str, args: dict | None, content: str | None) -> None:
    if args:
        args_str = json.dumps(args, ensure_ascii=False)
    else:
        args_str = ""
    # For speech, print full content; for others, truncate
    if tool_name == "public_speech" and args and args.get("public_speech"):
        print(f"  {_DIM}LLM P{player_id} {phase}/{tool_name}:{_RESET}")
        print(f"    {args['public_speech']}")
    else:
        snippet = args_str[:500]
        print(f"  {_DIM}LLM P{player_id} {phase}/{tool_name}:{_RESET} {snippet}")
    if content:
        print(f"    {_DIM}{content[:500]}{_RESET}")


async def async_main(config_id: str, *, use_llm: bool) -> None:
    paths = get_paths()
    llm_settings = get_llm_settings() if use_llm else None

    bus = EventBus()
    bus.subscribe(_print_event)

    boot = await bootstrap_and_run_game(
        paths=paths, config_id=config_id, llm_settings=llm_settings, event_bus=bus,
        llm_callback=_print_llm_output,
    )
    final_state = boot.state

    payload = {
        "game_id": final_state["game_id"],
        "config_id": final_state["config_id"],
        "phase": final_state["phase"].value,
        "status": final_state["status"].value,
        "winner": final_state["winner"],
        "round": final_state["round"],
        "llm_enabled": boot.llm_enabled,
        "graph_files": boot.graph_artifacts,
        "node_count": len(set(p.value for p in boot.runtime["phase_order"])),
    }
    print(json.dumps(payload, ensure_ascii=True, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap a werewolf game session.")
    parser.add_argument("--config", default="12p_pre_witch_hunter_idiot")
    parser.add_argument("--no-llm", action="store_true", help="disable real LLM calls and use local fallback decisions")
    args = parser.parse_args()
    asyncio.run(async_main(args.config, use_llm=not args.no_llm))


if __name__ == "__main__":
    main()
