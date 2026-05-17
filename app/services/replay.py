"""Game replay / post-game analysis.

Compresses a finished game into a concise timeline and sends it to LLM
for evaluation. Optimized for prefix caching (stable system prompt).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.config import AppPaths, LLMSettings
from app.infra.db import connect_database
from app.infra.repositories.events import fetch_events
from app.infra.repositories.games import fetch_game, fetch_game_players
from app.infra.repositories.snapshots import fetch_latest_snapshot
from app.services.llm_provider import get_provider

_log = logging.getLogger(__name__)

_SYSTEM_PROMPT = """你是一位专业的狼人杀复盘分析师。你将收到一局已结束的12人标准局（预女猎白+警长）的完整记录。

请从上帝视角分析这局游戏，输出结构化复盘报告。

评分标准：
- S：完美操作，对胜负有决定性贡献
- A：操作得当，发挥了角色应有价值
- B：中规中矩，无明显失误
- C：有失误但不致命
- D：严重失误，直接导致己方劣势

分析维度：
- 狼人：刀法选择、悍跳/潜水策略、自爆时机
- 预言家：验人方向、信息传递、警徽流
- 女巫：解药/毒药使用时机
- 猎人：开枪目标选择
- 村民/白痴：站边准确性、投票方向

输出格式（JSON）：
{
  "summary": "一句话总结本局",
  "turning_point": "关键转折点",
  "rounds": [{"round": N, "night": "夜晚摘要", "day": "白天摘要", "评价": "本轮评价"}],
  "player_ratings": [{"player_id": N, "role": "角色", "score": "S/A/B/C/D", "comment": "评价"}],
  "winner_reason": "获胜原因分析"
}

只输出 JSON，不要其他文字。"""


def build_replay_context(
    database: Path,
    game_id: str,
) -> dict[str, Any] | None:
    """Extract and compress game data into a concise replay context."""
    conn = connect_database(database)
    try:
        game = fetch_game(conn, game_id=game_id)
        if game is None:
            return None
        game = dict(game)
        if game.get("status") != "completed":
            return None

        players = fetch_game_players(conn, game_id=game_id)
        snapshot = fetch_latest_snapshot(conn, game_id=game_id)
        events = fetch_events(conn, game_id=game_id, limit=2000, scope="all")

        # Build seat table
        seat_table = []
        for row in sorted(players, key=lambda r: r["seat_index"]):
            p = dict(row)
            seat_table.append({
                "seat": int(p["seat_index"]),
                "role": p["role"],
                "faction": p["faction"],
                "survived": bool(p["survived"]),
                "death_cause": p.get("death_cause"),
                "death_round": p.get("death_round"),
            })

        # Compress events into per-round timeline
        decoded_events = []
        for row in reversed(events):
            ev = dict(row)
            data_json = ev.get("data_json")
            if isinstance(data_json, str):
                ev["data_json"] = json.loads(data_json)
            decoded_events.append(ev)

        timeline = _compress_timeline(decoded_events)

        # Winner info from snapshot
        state = json.loads(snapshot["state_json"]) if snapshot and isinstance(snapshot["state_json"], str) else (snapshot.get("state_json") if snapshot else {})
        winner = state.get("winner") or game.get("winner")

        return {
            "game_id": game_id,
            "config": game.get("config_id", "12p_pre_witch_hunter_idiot"),
            "winner": winner,
            "total_rounds": state.get("round", 0),
            "seat_table": seat_table,
            "timeline": timeline,
        }
    finally:
        conn.close()


def _compress_timeline(events: list[dict]) -> list[dict]:
    """Compress raw events into per-round summaries."""
    rounds: dict[int, dict[str, list[str]]] = {}

    for ev in events:
        round_no = ev.get("round", 1)
        if round_no not in rounds:
            rounds[round_no] = {"night": [], "day": []}

        phase = ev.get("phase", "")
        data = ev.get("data_json") if isinstance(ev.get("data_json"), dict) else {}
        etype = ev.get("event_type", "")
        is_night = "night" in phase

        entry = _event_to_text(etype, data, ev.get("content", ""))
        if not entry:
            continue

        bucket = "night" if is_night else "day"
        rounds[round_no][bucket].append(entry)

    # Format as list
    result = []
    for round_no in sorted(rounds.keys()):
        r = rounds[round_no]
        result.append({
            "round": round_no,
            "night": "; ".join(r["night"]) if r["night"] else "无事件",
            "day": "; ".join(r["day"]) if r["day"] else "无事件",
        })
    return result


def _event_to_text(etype: str, data: dict, content: str) -> str:
    """Convert an event to a short text description for the timeline."""
    if etype == "wolf_target_selected":
        return f"狼刀{data.get('target_id')}号"
    if etype == "seer_checked":
        result = "查杀" if data.get("result") == "wolf" else "查金"
        return f"预言家验{data.get('target_id')}号({result})"
    if etype == "witch_used_antidote":
        return f"女巫救{data.get('target_id')}号"
    if etype == "witch_used_poison":
        return f"女巫毒{data.get('target_id')}号"
    if etype == "player_died":
        cause = {"wolf": "刀杀", "poison": "毒杀", "hunter_shot": "枪杀", "exile": "放逐", "self_destruct": "自爆"}.get(data.get("cause", ""), "死亡")
        return f"{data.get('player_id')}号{cause}"
    if etype == "sheriff_elected":
        pid = data.get("player_id")
        if pid is None:
            return "无人当选警长"
        return f"{pid}号当选警长"
    if etype == "sheriff_transferred":
        target = data.get("target_id")
        if target is None:
            return f"{data.get('actor_id')}号撕警徽"
        return f"警徽转{target}号"
    if etype == "vote_resolved":
        chosen = data.get("chosen")
        if chosen is None:
            return "投票平票无人出局"
        votes = data.get("votes", {})
        vote_count = sum(1 for v in votes.values() if v == chosen)
        return f"投票{chosen}号出局({vote_count}票)"
    if etype == "public_speech_made":
        speech = str(data.get("speech", ""))[:100]
        return f"{data.get('player_id')}号发言:{speech}"
    if etype == "sheriff_campaign":
        speech = str(data.get("speech", ""))[:80]
        return f"{data.get('player_id')}号竞选:{speech}"
    if etype == "death_speech":
        speech = str(data.get("speech", ""))[:80]
        return f"{data.get('player_id')}号遗言:{speech}"
    if etype == "wolf_self_destruct":
        return f"{data.get('player_id')}号狼人自爆"
    if content == "event.hunter_shot":
        return f"{data.get('actor_id')}号猎人开枪带走{data.get('target_id')}号"
    if content == "event.idiot_revealed":
        return f"{data.get('actor_id', data.get('player_id'))}号白痴翻牌"
    if etype == "game_ended":
        winner = "好人" if data.get("winner") == "good" else "狼人"
        reason = data.get("reason", "")
        return f"游戏结束:{winner}胜({reason})"
    return ""


async def generate_replay(
    database: Path,
    game_id: str,
    llm_settings: LLMSettings,
) -> dict[str, Any] | None:
    """Generate a replay analysis for a finished game."""
    context = build_replay_context(database, game_id)
    if context is None:
        return None

    # Build user message (compact game data)
    user_content = json.dumps(context, ensure_ascii=False, indent=None)

    # Call LLM
    import asyncio
    provider = get_provider(llm_settings.provider_name)
    payload = provider.build_payload(
        settings=llm_settings,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        tools=[],
        force_tool=False,
    )

    try:
        response = await asyncio.to_thread(provider.post_json, llm_settings, payload)
    except Exception as exc:
        _log.error("Replay LLM call failed: %s", exc)
        return None

    # Parse response
    content_text = ""
    if isinstance(response, dict):
        choices = response.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            content_text = message.get("content", "")

    if not content_text:
        return None

    # Try to parse JSON from response
    try:
        # Strip markdown code fences if present
        text = content_text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        result = json.loads(text)
        result["_raw"] = content_text
        result["_tokens"] = {
            "system": len(_SYSTEM_PROMPT) // 4,  # rough estimate
            "user": len(user_content) // 4,
        }
        return result
    except json.JSONDecodeError:
        # Return raw text if not valid JSON
        return {"_raw": content_text, "summary": content_text[:500]}


def format_replay_for_display(replay: dict[str, Any]) -> str:
    """Format replay result as readable text for TUI display."""
    lines = []
    lines.append("=" * 50)
    lines.append("  复盘分析报告")
    lines.append("=" * 50)

    if replay.get("summary"):
        lines.append(f"\n总结: {replay['summary']}")

    if replay.get("turning_point"):
        lines.append(f"转折点: {replay['turning_point']}")

    if replay.get("winner_reason"):
        lines.append(f"获胜原因: {replay['winner_reason']}")

    rounds = replay.get("rounds", [])
    if rounds:
        lines.append("\n--- 逐轮分析 ---")
        for r in rounds:
            lines.append(f"\n第{r.get('round', '?')}轮:")
            if r.get("night"):
                lines.append(f"  夜晚: {r['night']}")
            if r.get("day"):
                lines.append(f"  白天: {r['day']}")
            if r.get("评价"):
                lines.append(f"  评价: {r['评价']}")

    ratings = replay.get("player_ratings", [])
    if ratings:
        lines.append("\n--- 玩家评分 ---")
        for p in sorted(ratings, key=lambda x: x.get("player_id", 0)):
            pid = p.get("player_id", "?")
            role = p.get("role", "?")
            score = p.get("score", "?")
            comment = p.get("comment", "")
            lines.append(f"  P{pid} ({role}) [{score}] {comment}")

    tokens = replay.get("_tokens", {})
    if tokens:
        total = tokens.get("system", 0) + tokens.get("user", 0)
        lines.append(f"\n[预估 token: ~{total} input]")

    lines.append("\n" + "=" * 50)
    return "\n".join(lines)
