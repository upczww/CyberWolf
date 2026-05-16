from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.config import RuntimeConfig
from app.domain.roles import Phase


@dataclass(slots=True)
class GraphNode:
    node_id: str
    phase: Phase
    ordinal: int


@dataclass(slots=True)
class ConditionalEdge:
    source: str
    router: str
    targets: list[str]


@dataclass(slots=True)
class CompiledGraph:
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[tuple[str, str]] = field(default_factory=list)
    conditional_edges: list[ConditionalEdge] = field(default_factory=list)


def build_game_graph(runtime: RuntimeConfig) -> CompiledGraph:
    graph = CompiledGraph()
    for idx, phase in enumerate(runtime["phase_order"]):
        graph.nodes.append(GraphNode(node_id=_node_id(idx, phase), phase=phase, ordinal=idx))

    for idx, node in enumerate(graph.nodes[:-1]):
        graph.edges.append((node.node_id, graph.nodes[idx + 1].node_id))

    for idx, node in enumerate(graph.nodes):
        if node.phase == Phase.CHECK_WIN:
            graph.conditional_edges.append(
                ConditionalEdge(
                    source=node.node_id,
                    router="route_check_win",
                    targets=[
                        _node_id_for_phase(graph.nodes, Phase.GAME_OVER) or node.node_id,
                        graph.nodes[idx + 1].node_id if idx + 1 < len(graph.nodes) else node.node_id,
                    ],
                )
            )
        if node.phase == Phase.DAY_VOTE:
            targets = [_node_id_for_phase(graph.nodes, Phase.DAY_RESOLVE)]
            speech_node = _node_id_for_phase(graph.nodes, Phase.DAY_SPEECH)
            night_start_node = _node_id_for_phase(graph.nodes, Phase.NIGHT_START)
            graph.conditional_edges.append(
                ConditionalEdge(
                    source=node.node_id,
                    router="route_vote_result",
                    targets=[target for target in [targets[0], speech_node, night_start_node] if target is not None],
                )
            )

    graph.conditional_edges.append(
        ConditionalEdge(
            source=_node_id_for_phase(graph.nodes, Phase.PENDING_SKILLS) or _node_id_for_phase(graph.nodes, Phase.DAY_RESOLVE) or graph.nodes[0].node_id,
            router="route_pending_skills",
            targets=[
                target
                for target in [
                    _node_id_for_phase(graph.nodes, Phase.PENDING_SKILLS),
                    _node_id_for_phase(graph.nodes, Phase.CHECK_WIN),
                    _node_id_for_phase(graph.nodes, Phase.NIGHT_START),
                    _node_id_for_phase(graph.nodes, Phase.DAY_RESOLVE),
                ]
                if target is not None
            ],
        )
    )
    return graph


def _node_id(idx: int, phase: Phase) -> str:
    return f"{idx:02d}_{phase.value}"


def _node_id_for_phase(nodes: list[GraphNode], phase: Phase) -> str | None:
    for node in nodes:
        if node.phase == phase:
            return node.node_id
    return None
