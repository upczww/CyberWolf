from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from app.domain.config import RuntimeConfig
from app.engine.graph import CompiledGraph


PHASE_LABELS_ZH: dict[str, str] = {
    "setup_game": "游戏初始化",
    "night_start": "夜晚开始",
    "night_wolf": "狼人行动",
    "night_seer": "预言家查验",
    "night_witch": "女巫决策",
    "night_guard": "守卫守护",
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

ROUTER_LABELS_ZH: dict[str, str] = {
    "route_check_win": "胜负判定",
    "route_vote_result": "投票结果",
    "route_pending_skills": "待处理技能",
}


def _phase_label(phase_value: str, lang: str = "zh") -> str:
    if lang == "zh":
        return PHASE_LABELS_ZH.get(phase_value, phase_value)
    return phase_value


def _router_label(router: str, lang: str = "zh") -> str:
    if lang == "zh":
        return ROUTER_LABELS_ZH.get(router, router)
    return router


def render_mermaid(graph: CompiledGraph, *, lang: str = "zh") -> str:
    lines = ["graph TD"]
    for node in graph.nodes:
        label = _phase_label(node.phase.value, lang)
        lines.append(f"    {node.node_id}[{label}]")
    for source, target in graph.edges:
        lines.append(f"    {source} --> {target}")
    for edge in graph.conditional_edges:
        router = _router_label(edge.router, lang)
        for target in edge.targets:
            lines.append(f"    {edge.source} -. {router} .-> {target}")
    return "\n".join(lines) + "\n"


def render_dot(graph: CompiledGraph, *, lang: str = "zh") -> str:
    lines = ["digraph werewolf {"]
    lines.append('  rankdir="TB";')
    for node in graph.nodes:
        label = _phase_label(node.phase.value, lang)
        lines.append(f'  "{node.node_id}" [shape=box,label="{label}"];')
    for source, target in graph.edges:
        lines.append(f'  "{source}" -> "{target}";')
    for edge in graph.conditional_edges:
        router = _router_label(edge.router, lang)
        for target in edge.targets:
            lines.append(f'  "{edge.source}" -> "{target}" [style=dashed,label="{router}"];')
    lines.append("}")
    return "\n".join(lines) + "\n"


def export_graph_bundle(
    graph: CompiledGraph,
    runtime: RuntimeConfig,
    output_dir: Path,
    *,
    stem: str,
) -> dict[str, Path | None]:
    output_dir.mkdir(parents=True, exist_ok=True)
    mermaid_path = output_dir / f"{stem}.mermaid"
    mermaid_en_path = output_dir / f"{stem}_en.mermaid"
    dot_path = output_dir / f"{stem}.dot"
    dot_en_path = output_dir / f"{stem}_en.dot"
    png_path = output_dir / f"{stem}.png"

    # Chinese versions (default)
    mermaid_path.write_text(render_mermaid(graph, lang="zh"), encoding="utf-8")
    dot_path.write_text(render_dot(graph, lang="zh"), encoding="utf-8")

    # English versions
    mermaid_en_path.write_text(render_mermaid(graph, lang="en"), encoding="utf-8")
    dot_en_path.write_text(render_dot(graph, lang="en"), encoding="utf-8")

    if shutil.which("dot"):
        subprocess.run(["dot", "-Tpng", str(dot_path), "-o", str(png_path)], check=False)
        if not png_path.exists():
            png_path = None  # type: ignore[assignment]
    else:
        png_path = None  # type: ignore[assignment]

    return {"mermaid": mermaid_path, "dot": dot_path, "png": png_path}
