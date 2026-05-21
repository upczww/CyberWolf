"""Phase state machine — `transitions` library driver for the game loop.

The game's phase progression is modelled entirely as an `AsyncMachine`
from the `transitions` library:

  * Each unique phase id in `RuntimeConfig.phase_order` is a state.
  * Adjacent pairs in phase_order become default `advance` transitions.
  * `auto_transitions=True` exposes `to_<phase>()` triggers so a handler
    that returns `next_phase_override` can request an arbitrary jump
    (validated against the state set).
  * `queued=True` lets `on_enter` callbacks chain the next transition
    safely; there is no external `while` loop — the FSM drives itself
    from initial to terminal via the chained on_enter dispatch.

This module exposes:

  * `compute_phase_graph(runtime)` — pure (states, edges) extraction.
  * `build_phase_machine(runtime, model, on_enter_callback)` — wires an
    `AsyncMachine` onto an arbitrary model object whose
    `on_enter_callback` method handles every state.
  * `render_mermaid` / `render_dot` / `export_graph_bundle` — diagram
    exporters that work directly from a runtime config (no FSM needed).
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from transitions.extensions.asyncio import AsyncMachine

if TYPE_CHECKING:
    from app.domain.config import RuntimeConfig


PHASE_LABELS_ZH: dict[str, str] = {
    "setup_game": "游戏初始化",
    "night_start": "夜晚开始",
    "night_wolf": "狼人行动",
    "night_seer": "预言家查验",
    "night_witch": "女巫决策",
    "night_guard": "守卫守护",
    "night_hunter": "猎人确认",
    "night_idiot_reveal": "白痴亮牌",
    "night_resolve": "夜晚结算",
    "day_announce": "公布死讯",
    "sheriff_election": "警长竞选",
    "day_speech": "白天发言",
    "day_vote": "放逐投票",
    "day_resolve": "放逐结算",
    "pending_skills": "技能触发",
    "check_win": "胜负判定",
    "game_over": "游戏结束",
}


# ---------------------------------------------------------------------------
# Graph extraction
# ---------------------------------------------------------------------------


def compute_phase_graph(runtime: "RuntimeConfig") -> tuple[list[str], list[tuple[str, str]]]:
    """Return (unique_states, deduped_edges) for the runtime's phase_order."""
    phase_order = [p.value for p in runtime["phase_order"]]
    if not phase_order:
        raise ValueError("phase_order is empty")
    states = list(dict.fromkeys(phase_order))

    seen: set[tuple[str, str]] = set()
    edges: list[tuple[str, str]] = []
    for src, dst in zip(phase_order, phase_order[1:]):
        if (src, dst) in seen:
            continue
        seen.add((src, dst))
        edges.append((src, dst))
    return states, edges


# ---------------------------------------------------------------------------
# FSM construction
# ---------------------------------------------------------------------------


def build_phase_machine(
    runtime: "RuntimeConfig",
    *,
    model: object,
) -> AsyncMachine:
    """Construct an `AsyncMachine` from the registry's PhaseState objects.

    Each PhaseState already carries its on_enter callback name (set by
    the `@phase` decorator), so transitions library uses our State
    subclasses as-is — no parallel state-dict construction.

    Unknown phase ids in the runtime's phase_order (e.g. a YAML entry
    with no handler decorated) fall back to a bare `State` so the
    graph stays buildable; the engine treats them as no-ops.
    """
    from app.engine.registry import PHASE_REGISTRY  # avoid circular import

    states_list, edges = compute_phase_graph(runtime)
    state_objs = [
        PHASE_REGISTRY[name] if name in PHASE_REGISTRY else _bare_state(name)
        for name in states_list
    ]
    transitions = [
        {"trigger": "advance", "source": src, "dest": dst} for src, dst in edges
    ]
    return AsyncMachine(
        model=model,
        states=state_objs,
        initial=states_list[0],
        transitions=transitions,
        auto_transitions=True,    # to_<phase>() jumps
        queued=True,              # chained triggers from inside on_enter
        ignore_invalid_triggers=False,
    )


def _bare_state(name: str):
    """Fallback State for a phase id with no decorated handler."""
    from transitions.extensions.asyncio import AsyncState
    return AsyncState(name)


# ---------------------------------------------------------------------------
# Diagram export
# ---------------------------------------------------------------------------


def _phase_label(phase_value: str, lang: str = "zh") -> str:
    if lang == "zh":
        return PHASE_LABELS_ZH.get(phase_value, phase_value)
    return phase_value


def render_mermaid(runtime: "RuntimeConfig", *, lang: str = "zh") -> str:
    states, edges = compute_phase_graph(runtime)
    lines = ["graph TD"]
    for s in states:
        lines.append(f"    {s}[{_phase_label(s, lang)}]")
    for src, dst in edges:
        lines.append(f"    {src} --> {dst}")
    return "\n".join(lines) + "\n"


def render_dot(runtime: "RuntimeConfig", *, lang: str = "zh") -> str:
    states, edges = compute_phase_graph(runtime)
    lines = ["digraph werewolf {", '  rankdir="TB";']
    for s in states:
        lines.append(f'  "{s}" [shape=box,label="{_phase_label(s, lang)}"];')
    for src, dst in edges:
        lines.append(f'  "{src}" -> "{dst}";')
    lines.append("}")
    return "\n".join(lines) + "\n"


def export_graph_bundle(
    runtime: "RuntimeConfig",
    output_dir: Path,
    *,
    stem: str,
) -> dict[str, Path | None]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path | None] = {
        "mermaid": output_dir / f"{stem}.mermaid",
        "dot": output_dir / f"{stem}.dot",
        "png": None,
    }
    paths["mermaid"].write_text(render_mermaid(runtime, lang="zh"), encoding="utf-8")
    (output_dir / f"{stem}_en.mermaid").write_text(
        render_mermaid(runtime, lang="en"), encoding="utf-8"
    )
    paths["dot"].write_text(render_dot(runtime, lang="zh"), encoding="utf-8")
    (output_dir / f"{stem}_en.dot").write_text(
        render_dot(runtime, lang="en"), encoding="utf-8"
    )

    if shutil.which("dot"):
        png_path = output_dir / f"{stem}.png"
        subprocess.run(["dot", "-Tpng", str(paths["dot"]), "-o", str(png_path)], check=False)
        if png_path.exists():
            paths["png"] = png_path
    return paths
