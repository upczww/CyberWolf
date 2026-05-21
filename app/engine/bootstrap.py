from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import time_ns
from typing import Callable
from uuid import uuid4

from app.config import AppPaths, LLMSettings
from app.domain.state import GameState, init_game_state
from app.engine.config_loader import compile_runtime_config, load_game_config
from app.engine.graph import CompiledGraph, build_game_graph
from app.engine.graph_viz import export_graph_bundle
from app.engine.human import HumanAwaiter
from app.engine.session import run_game_session
from app.infra.db import connect_database, initialize_database
from app.infra.events import EventBus
from app.infra.repositories.games import insert_game_bootstrap


@dataclass(slots=True)
class BootstrappedGame:
    state: GameState
    graph: CompiledGraph
    graph_artifacts: dict[str, str | None]
    llm_enabled: bool


async def bootstrap_and_run_game(
    *,
    paths: AppPaths,
    config_id: str,
    llm_settings: LLMSettings | None,
    seed: int | None = None,
    event_bus: EventBus | None = None,
    llm_callback: object = None,
    on_game_started: Callable[[str], None] | None = None,
    human_seat: int | None = None,
    human_seats: set[int] | None = None,
    human_awaiter: HumanAwaiter | None = None,
    phase_delay_seconds: float = 0.0,
) -> BootstrappedGame:
    seed = time_ns() if seed is None else seed
    initialize_database(paths.database, paths.schema)
    config = load_game_config(paths.configs / f"{config_id}.yaml")
    runtime = compile_runtime_config(config)
    graph = build_game_graph(runtime)
    game_id = str(uuid4())
    artifacts = export_graph_bundle(graph, runtime, paths.graphs, stem=game_id)
    artifact_strings = {key: str(value) if value else None for key, value in artifacts.items()}

    conn = connect_database(paths.database)
    try:
        insert_game_bootstrap(conn, game_id=game_id, runtime=runtime, seed=seed, graph_artifacts=artifact_strings)
        state = init_game_state(
            runtime, game_id=game_id, seed=seed,
            graph_artifacts=artifact_strings,
            human_seat=human_seat, human_seats=human_seats,
        )
        if on_game_started is not None:
            on_game_started(game_id)
        final_state = await run_game_session(
            state, conn=conn, event_bus=event_bus or EventBus(),
            llm_settings=llm_settings, llm_callback=llm_callback,
            human_awaiter=human_awaiter,
            phase_delay_seconds=phase_delay_seconds,
        )
    finally:
        conn.close()

    return BootstrappedGame(
        state=final_state,
        graph=graph,
        graph_artifacts=artifact_strings,
        llm_enabled=llm_settings is not None,
    )


def list_config_ids(config_dir: Path) -> list[str]:
    return sorted(path.stem for path in config_dir.glob("*.yaml"))
