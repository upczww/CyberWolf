from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual import events
from textual.worker import Worker, WorkerState
from textual.reactive import reactive
from textual.widgets import RichLog, Static

from app.config import get_llm_settings, get_paths
from app.engine.bootstrap import bootstrap_and_run_game, list_config_ids
from app.infra.events import EventBus
from app.services.tts import tts_engine
from app.ui.db_view import GameViewCache, delete_game_view
from app.ui.i18n import I18n, Language, normalize_language


def _format_elapsed(started_at: str | None, ended_at: str | None) -> str:
    if not started_at:
        return ""
    try:
        start = datetime.fromisoformat(started_at)
        end = datetime.fromisoformat(ended_at) if ended_at else datetime.now(start.tzinfo)
        delta = int((end - start).total_seconds())
        if delta < 60:
            return f"{delta}s"
        if delta < 3600:
            return f"{delta // 60}m{delta % 60}s"
        return f"{delta // 3600}h{(delta % 3600) // 60}m"
    except (ValueError, TypeError):
        return ""


SCOPE_ORDER = ["all", "public", "wolf_team", "role_private", "god", "system"]
SCOPE_COLORS = {
    "public": "cyan",
    "wolf_team": "red",
    "role_private": "yellow",
    "god": "magenta",
    "system": "green",
}


ROLE_EMOJI = {
    "wolf": "🐺",
    "seer": "🔮",
    "witch": "🧪",
    "hunter": "🏹",
    "idiot": "🎭",
    "guard": "🛡",
    "villager": "👤",
}

ACTIVE_EMOJI = "🟢"
DEAD_EMOJI = "💀"
STRIKETHROUGH = "\u0336"  # combining strikethrough
PLAYER_COLUMN_SLOTS = 6


class WerewolfApp(App[None]):
    BINDINGS = [
        Binding("r", "refresh", "刷新/Refresh"),
        Binding("l", "latest_game", "最新/Latest"),
        Binding("n", "next_game", "下一局/Next"),
        Binding("p", "prev_game", "上一局/Prev"),
        Binding("f", "cycle_scope", "范围/Scope"),
        Binding("a", "toggle_auto_refresh", "自动/Auto"),
        Binding("g", "toggle_language", "语言/Lang"),
        Binding("s", "start_game", "新局/Start"),
        Binding("d", "delete_game", "删除/Delete"),
        Binding("pageup", "log_page_up", "上翻"),
        Binding("pagedown", "log_page_down", "下翻"),
        Binding("home", "log_home", "顶部"),
        Binding("end", "log_end", "底部"),
        Binding("space", "toggle_scroll_pause", "暂停滚动/Pause"),
        Binding("w", "scope_wolf", "狼视角/Wolf"),
        Binding("t", "toggle_tts", "语音/TTS"),
        Binding("e", "replay", "复盘/Replay"),
        Binding("q", "quit", "退出/Quit"),
    ]

    CSS = """
    Screen {
        layout: vertical;
        background: $background;
    }

    #titlebar {
        height: 3;
        padding: 0 2;
        content-align: left middle;
        background: $boost;
        text-style: bold;
    }

    #board {
        height: 1fr;
    }

    .players {
        width: 28;
        background: $surface;
    }

    .player_card {
        height: 1fr;
        padding: 0 1;
        content-align: left middle;
    }

    #public_area {
        width: 1fr;
        background: $background;
    }

    #public_title {
        height: 3;
        padding: 0 1;
        content-align: left middle;
        background: $panel;
        text-style: bold;
    }

    #events {
        height: 1fr;
        padding: 1 2;
        border: tall $primary;
        background: $surface;
    }

    #events.filtered {
        border: tall $error;
    }

    #toolbar {
        height: 3;
        padding: 0 2;
        content-align: left middle;
        background: $boost;
    }
    """

    game_id: reactive[str | None] = reactive(None)
    auto_refresh: reactive[bool] = reactive(True)
    event_scope: reactive[str] = reactive("all")
    selected_game_index: reactive[int] = reactive(0)

    def __init__(self, *, database: Path, game_id: str | None = None, language: str = "zh") -> None:
        super().__init__()
        self._database = database
        self.game_id = game_id
        self._language: Language = normalize_language(language)
        self._i18n = I18n(self._language)
        self._game_ids: list[str] = []
        self._total_game_count: int = 0
        self._view: dict[str, Any] | None = None
        self._paths = get_paths()
        self._config_ids = list_config_ids(self._paths.configs)
        self._event_seqs: list[int] = []
        self._last_scope = self.event_scope
        self._last_game_id: str | None = None
        self._launch_worker: Worker | None = None
        self._confirming_delete: bool = False
        self._running_game_id: str | None = None
        self._view_cache = GameViewCache(database)
        self._event_format_cache: dict[tuple[int, str], Text] = {}  # (seq, lang) -> formatted Text
        self._scroll_paused: bool = False  # True when user is browsing history

    def compose(self) -> ComposeResult:
        yield Static(id="titlebar")
        with Horizontal(id="board"):
            with Vertical(id="left_players", classes="players"):
                for index in range(PLAYER_COLUMN_SLOTS):
                    yield Static(id=f"left_player_{index}", classes="player_card")
            with Vertical(id="public_area"):
                yield Static(id="public_title")
                yield RichLog(id="events", wrap=False, markup=False, highlight=False)
            with Vertical(id="right_players", classes="players"):
                for index in range(PLAYER_COLUMN_SLOTS):
                    yield Static(id=f"right_player_{index}", classes="player_card")
        yield Static(id="toolbar")

    def on_mount(self) -> None:
        self._render_static_chrome()
        self.query_one("#events", RichLog).auto_scroll = True
        self.set_interval(0.5, self.refresh_view)
        self.refresh_view()

    def on_unmount(self) -> None:
        self._view_cache.close()

    def refresh_view(self) -> None:
        if not self.auto_refresh and self._view is not None:
            return
        self._reload_view()

    def action_refresh(self) -> None:
        self._reload_view(force=True)

    def action_latest_game(self) -> None:
        self.selected_game_index = 0
        if self._game_ids:
            self.game_id = self._game_ids[0]
        self._reload_view(force=True)

    def action_next_game(self) -> None:
        if not self._game_ids:
            return
        self.selected_game_index = min(self.selected_game_index + 1, len(self._game_ids) - 1)
        self.game_id = self._game_ids[self.selected_game_index]
        self._reload_view(force=True)

    def action_prev_game(self) -> None:
        if not self._game_ids:
            return
        self.selected_game_index = max(self.selected_game_index - 1, 0)
        self.game_id = self._game_ids[self.selected_game_index]
        self._reload_view(force=True)

    def action_cycle_scope(self) -> None:
        current = SCOPE_ORDER.index(self.event_scope)
        self.event_scope = SCOPE_ORDER[(current + 1) % len(SCOPE_ORDER)]
        log = self.query_one("#events", RichLog)
        if self.event_scope == "all":
            log.remove_class("filtered")
        else:
            log.add_class("filtered")
        self._reload_view(force=True)

    def action_toggle_auto_refresh(self) -> None:
        self.auto_refresh = not self.auto_refresh
        self._render_static_chrome()

    def action_toggle_language(self) -> None:
        self._language = "en" if self._language == "zh" else "zh"
        self._i18n = I18n(self._language)
        self._event_format_cache.clear()
        self._render_static_chrome()
        if self._view is not None:
            self._render_players(self._view)
            self._render_events(self._view, force=True)

    def action_log_page_up(self) -> None:
        self._scroll_paused = True
        self.query_one("#events", RichLog).action_page_up()

    def action_log_page_down(self) -> None:
        self.query_one("#events", RichLog).action_page_down()

    def action_log_home(self) -> None:
        self._scroll_paused = True
        self.query_one("#events", RichLog).action_scroll_home()

    def action_log_end(self) -> None:
        self._scroll_paused = False
        self.query_one("#events", RichLog).action_scroll_end()

    def action_toggle_scroll_pause(self) -> None:
        self._scroll_paused = not self._scroll_paused
        if not self._scroll_paused:
            self.query_one("#events", RichLog).scroll_end(animate=False)

    def action_scope_wolf(self) -> None:
        """Toggle between wolf_team scope and all."""
        if self.event_scope == "wolf_team":
            self.event_scope = "all"
            self.query_one("#events", RichLog).remove_class("filtered")
        else:
            self.event_scope = "wolf_team"
            self.query_one("#events", RichLog).add_class("filtered")
        self._reload_view(force=True)

    def action_toggle_tts(self) -> None:
        """Toggle TTS on/off."""
        new_state = tts_engine.toggle()
        label = "TTS ON" if new_state else "TTS OFF"
        self._render_static_chrome(extra=label)

    def action_replay(self) -> None:
        """Generate replay analysis for current game."""
        if self.game_id is None:
            return
        from app.config import get_llm_settings
        llm_settings = get_llm_settings()
        if llm_settings is None:
            self._render_static_chrome(extra="需要配置 LLM")
            return
        self._render_static_chrome(extra="复盘分析中...")
        self.run_worker(self._do_replay(self.game_id, llm_settings), exclusive=False)

    async def _do_replay(self, game_id: str, llm_settings) -> None:
        """Run replay generation in background worker."""
        from app.services.replay import generate_replay, format_replay_for_display
        result = await generate_replay(self._database, game_id, llm_settings)
        if result is None:
            self._render_static_chrome(extra="复盘失败（游戏未结束或LLM错误）")
            return
        text = format_replay_for_display(result)
        log = self.query_one("#events", RichLog)
        log.write("\n")
        log.write(text)
        log.scroll_end(animate=False)
        self._render_static_chrome(extra="复盘完成")

    def action_start_game(self) -> None:
        if self._launch_worker is not None and self._launch_worker.state == WorkerState.RUNNING:
            return
        # Stop old running game if any
        if self._running_game_id is not None:
            self._render_static_chrome(extra=self._i18n.t("status.stop_first"))
            self._stop_running_game()
        self._launch_worker = self.run_worker(self._launch_game(), exclusive=True)
        self._render_static_chrome(extra=self._i18n.t("status.launching"))

    def action_delete_game(self) -> None:
        if self._confirming_delete:
            return
        if self.game_id is None:
            return
        self._confirming_delete = True
        self._render_static_chrome(extra=self._i18n.t("status.confirm_delete"))

    def on_key(self, event: events.Key) -> None:
        if self._confirming_delete:
            if event.key == "y":
                self._confirming_delete = False
                self.run_worker(self._do_delete_game(), exclusive=True)
            else:
                self._confirming_delete = False
                self._render_static_chrome()
            event.prevent_default()
            return
        # Number keys 1-9: jump to recent game by index
        if event.key in "123456789" and self._game_ids:
            idx = int(event.key) - 1
            if idx < len(self._game_ids):
                self.selected_game_index = idx
                self.game_id = self._game_ids[idx]
                self._reload_view(force=True)
            event.prevent_default()
            return

    def _stop_running_game(self) -> None:
        """Mark running game as failed and stop the worker."""
        if self._launch_worker is not None and self._launch_worker.state == WorkerState.RUNNING:
            self._launch_worker.cancel()
        if self._running_game_id is not None:
            try:
                delete_game_view(self._database, game_id=self._running_game_id)
            except Exception:
                pass
            self._running_game_id = None

    async def _do_delete_game(self) -> None:
        """Delete current game and reset view."""
        gid = self.game_id
        self._render_static_chrome(extra=self._i18n.t("status.deleting"))
        # Stop if it's the running game
        if gid == self._running_game_id:
            self._stop_running_game()
        if gid is not None:
            try:
                delete_game_view(self._database, game_id=gid)
            except Exception:
                pass
        self._view = None
        self._event_seqs = []
        self.game_id = None
        self._render_static_chrome(extra=self._i18n.t("status.deleted"))
        # Jump to latest game
        self._reload_view(force=True)

    def _reload_view(self, *, force: bool = False) -> None:
        try:
            if force or self._view is None or self._last_game_id != self.game_id or self._last_scope != self.event_scope:
                # Full load on game switch, scope change, or force
                self._view_cache.reset()
                view = self._view_cache.load_full(
                    game_id=self.game_id, event_scope=self.event_scope, event_limit=300,
                )
            else:
                # Incremental load — only new events
                view = self._view_cache.load_incremental()
                if view is None:
                    return  # No changes
                # Merge cached slow fields from previous view
                if "recent_games" not in view and self._view is not None:
                    view["recent_games"] = self._view.get("recent_games", [])
                    view["total_game_count"] = self._view.get("total_game_count", 0)
                    view["metrics"] = self._view.get("metrics")
        except sqlite3.DatabaseError:
            view = None

        if view is None:
            self._view = None
            self.title = self._i18n.t("app.title")
            self.query_one("#events", RichLog).clear()
            self._render_player_column("left_player", [])
            self._render_player_column("right_player", [])
            self._render_static_chrome(message=self._i18n.t("empty.no_games"))
            return

        self._view = view
        game = view["game"]
        self.game_id = game["id"]
        self.title = f"{self._i18n.t('app.title')} - {game['id'][:8]}"
        self._game_ids = [row["id"] for row in view.get("recent_games", [])]
        self._total_game_count = view.get("total_game_count", len(self._game_ids))
        if game["id"] in self._game_ids:
            self.selected_game_index = self._game_ids.index(game["id"])

        self._render_static_chrome()
        self._render_players(view)
        self._render_events(view, force=force)

    def _render_static_chrome(self, *, message: str | None = None, extra: str | None = None) -> None:
        self.query_one("#titlebar", Static).update(self._title_text(message=message, extra=extra))
        self.query_one("#public_title", Static).update(self._public_title_text())
        if self._confirming_delete:
            self.query_one("#toolbar", Static).update(
                f"[bold yellow]{self._i18n.t('status.confirm_delete')}[/bold yellow]"
            )
        else:
            self.query_one("#toolbar", Static).update(self._i18n.t("toolbar.help"))

    def _title_text(self, *, message: str | None = None, extra: str | None = None) -> Text:
        text = Text()
        text.append(self._i18n.t("app.title"), style="bold")
        if message:
            text.append(f"  {message}", style="yellow")
            return text
        game_short = self.game_id[:8] if self.game_id else "-"
        game_pos = f"{self.selected_game_index + 1}/{self._total_game_count}" if self._game_ids else "-"
        text.append(f"  {self._i18n.t('status.game')} {game_short} ({game_pos})")
        text.append(f"  {self._i18n.t('status.scope')} {self._i18n.enum('scope', self.event_scope)}")
        text.append(
            f"  {self._i18n.t('status.auto')} "
            f"{self._i18n.t('status.on') if self.auto_refresh else self._i18n.t('status.off')}"
        )
        text.append(f"  Lang {self._language}")
        if tts_engine.enabled:
            text.append("  🔊", style="green bold")
        if self._scroll_paused:
            text.append("  ⏸ PAUSED", style="yellow bold")
        if self._launch_worker is not None and self._launch_worker.state == WorkerState.RUNNING:
            text.append("  worker=running", style="green")
        if extra:
            text.append(f"  {extra}", style="green")
        return text

    def _public_title_text(self) -> Text:
        text = Text()
        text.append(self._i18n.t("public.title"), style="bold")
        if self._view is None:
            return text
        snapshot = self._view["snapshot"]
        game = self._view["game"]
        text.append(f"  R{game['round_count']}")
        phase = game.get("current_phase") or (snapshot["phase"] if snapshot else None)
        if phase:
            text.append(f"  {self._translate_optional('phase', phase)}", style="cyan")
        elapsed = _format_elapsed(game.get("started_at"), game.get("ended_at"))
        if elapsed:
            text.append(f"  {elapsed}", style="dim")
        # Survival counter: gods / villagers / wolves (屠边局)
        players = self._view.get("players", [])
        if players:
            _GOD_ROLES = {"seer", "witch", "hunter", "idiot", "guard"}
            gods_alive = sum(1 for p in players if p.get("survived") and p.get("role") in _GOD_ROLES)
            villagers_alive = sum(1 for p in players if p.get("survived") and p.get("role") == "villager")
            wolf_alive = sum(1 for p in players if p.get("survived") and (p.get("faction") == "wolf" or p.get("role") == "wolf"))
            text.append(f"  神{gods_alive}", style="magenta bold")
            text.append(f" 民{villagers_alive}", style="bold")
            text.append(f" 狼{wolf_alive}", style="red bold")
        text.append(f"  {self._i18n.enum('status', game['status'])}")
        winner = self._translate_optional("winner", game["winner"])
        if winner != "-":
            reason = ""
            for ev in reversed(self._view.get("events", [])):
                if ev.get("event_type") == "game_ended":
                    ev_data = ev.get("data_json") if isinstance(ev.get("data_json"), dict) else {}
                    reason = ev_data.get("reason", "")
                    break
            reason_text = self._i18n.t(f"win_reason.{reason}", "") if reason else ""
            if reason_text:
                text.append(f"  {winner} {reason_text}", style="green")
            else:
                text.append(f"  {self._i18n.t('panel.winner')}: {winner}", style="green")
        return text

    def _render_players(self, view: dict[str, Any]) -> None:
        players = sorted(view["players"], key=lambda row: int(row["seat_index"]))
        active_player_id = self._active_player_id(view)
        acting_role = self._acting_role(view)
        split_at = (len(players) + 1) // 2
        self._render_player_column("left_player", players[:split_at], active_player_id, acting_role)
        self._render_player_column("right_player", players[split_at:], active_player_id, acting_role)

    def _render_player_column(
        self,
        widget_prefix: str,
        players: list[dict[str, Any]],
        active_player_id: int | None = None,
        acting_role: str | None = None,
    ) -> None:
        for index in range(PLAYER_COLUMN_SLOTS):
            widget = self.query_one(f"#{widget_prefix}_{index}", Static)
            if index < len(players):
                widget.update(self._player_text(players[index], active_player_id, acting_role))
            else:
                widget.update("")

    @staticmethod
    def _strike(text: str) -> str:
        return "".join(c + STRIKETHROUGH for c in text)

    def _player_text(self, row: dict[str, Any], active_player_id: int | None, acting_role: str | None = None) -> Text:
        player_id = int(row["player_id"])
        alive = bool(row["survived"])
        active = alive and active_player_id == player_id
        role = str(row["role"])
        faction = str(row.get("faction", "good"))
        is_wolf = faction == "wolf" or role == "wolf"
        # Highlight players whose role matches current acting phase
        is_acting = alive and acting_role is not None and (
            role == acting_role or (acting_role == "wolf" and is_wolf)
        )
        prefix = f"{ACTIVE_EMOJI} " if active else ("▸ " if is_acting else "  ")
        seat = int(row['seat_index'])
        name = f"{self._i18n.t('player.prefix')}{seat:>2}"
        name_display = self._strike(name) if not alive else name
        # Faction-based coloring: wolves are red, good players are default/green
        if active:
            style = "green bold"
        elif not alive:
            style = "dim"
        elif is_acting:
            style = "bright_magenta" if not is_wolf else "bright_red"
        elif is_wolf:
            style = "red"
        else:
            style = ""
        text = Text()
        text.append(f"{prefix}{ROLE_EMOJI.get(role, '❔')} {name_display}", style=style)
        if not alive:
            text.append(f" {DEAD_EMOJI}", style="red bold" if is_wolf else "dim red")
        action_badges = row.get("action_badges")
        if action_badges:
            text.append(f" {action_badges}", style="bold" if alive else "dim")
        if row["is_sheriff"]:
            text.append(" ♛", style="yellow")
        skill_label = row.get("skill_label")
        if skill_label:
            text.append(f"  {skill_label}", style="yellow" if alive else "dim")
        # Role name with faction color
        role_name = self._i18n.enum("role", row["role"])
        role_text = self._strike(role_name) if not alive else role_name
        role_style = "red dim" if is_wolf else "dim"
        text.append(f"\n   {role_text}", style=role_style)
        return text

    def _active_player_id(self, view: dict[str, Any]) -> int | None:
        for event in reversed(view["events"]):
            data = event.get("data_json")
            if not isinstance(data, dict):
                continue
            for key in ("actor_id", "speaker_id", "voter_id", "player_id"):
                value = data.get(key)
                if isinstance(value, int):
                    return value
        return None

    @staticmethod
    def _acting_role(view: dict[str, Any]) -> str | None:
        """Determine which role is currently acting based on game phase."""
        phase = view["game"].get("current_phase")
        if not phase:
            snapshot = view.get("snapshot")
            phase = snapshot.get("phase") if snapshot else None
        if not phase:
            return None
        _PHASE_ROLE_MAP = {
            "night_wolf": "wolf",
            "night_seer": "seer",
            "night_witch": "witch",
            "night_guard": "guard",
            "pending_skills": "hunter",
        }
        return _PHASE_ROLE_MAP.get(phase)

    def _render_events(self, view: dict[str, Any], *, force: bool = False) -> None:
        log = self.query_one("#events", RichLog)
        new_seqs = [int(event["seq"]) for event in view["events"]]
        same_stream = (
            not force
            and self._last_game_id == view["game"]["id"]
            and self._last_scope == self.event_scope
            and self._event_seqs
            and len(new_seqs) >= len(self._event_seqs)
            and new_seqs[: len(self._event_seqs)] == self._event_seqs
        )
        events = view["events"][len(self._event_seqs) :] if same_stream else view["events"]
        if not events:
            self._event_seqs = new_seqs
            return
        if not same_stream:
            log.clear()
            self._event_format_cache.clear()
        for event in events:
            formatted = self._get_formatted_event(event)
            if formatted.plain:  # Skip empty (hidden phase_ended)
                log.write(formatted)
        self._event_seqs = new_seqs
        self._last_scope = self.event_scope
        self._last_game_id = view["game"]["id"]
        if not self._scroll_paused:
            log.scroll_end(animate=False)

    def _get_formatted_event(self, event: dict[str, Any]) -> Text:
        """Get formatted event text, using cache for already-seen events."""
        cache_key = (int(event["seq"]), self._language)
        cached = self._event_format_cache.get(cache_key)
        if cached is not None:
            return cached
        formatted = self._format_event_rich(event)
        self._event_format_cache[cache_key] = formatted
        # Keep cache bounded
        if len(self._event_format_cache) > 400:
            # Remove oldest entries (lowest seq numbers)
            keys = sorted(self._event_format_cache.keys())
            for key in keys[:100]:
                del self._event_format_cache[key]
        return formatted

    def _translate_optional(self, prefix: str, value: object | None) -> str:
        if value is None or value == "":
            return "-"
        return self._i18n.enum(prefix, value)

    def _event_message(self, event: dict[str, Any]) -> str:
        data = event.get("data_json") if isinstance(event.get("data_json"), dict) else {}
        content_key = str(event.get("content") or "")
        event_type = str(event.get("event_type") or "")

        if content_key == "event.game_setup_completed":
            return self._format_i18n(content_key + ".detail", players=data.get("players", "-"))
        if event_type == "phase_started":
            if content_key == "event.day_announce":
                deaths = data.get("deaths") or []
                if deaths:
                    return self._format_i18n("event.day_announce.deaths", deaths=self._format_player_list(deaths))
                return self._i18n.t("event.day_announce.none")
            return self._format_i18n("event.phase_started.detail", phase=self._translate_optional("phase", data.get("phase")))
        if event_type == "phase_ended":
            return self._format_i18n("event.phase_ended.detail", phase=self._translate_optional("phase", data.get("phase")))
        if event_type == "wolf_target_selected":
            return self._format_i18n("event.wolf_target_selected.detail", target=self._format_player(data.get("target_id")))
        if event_type == "seer_checked":
            return self._format_i18n(
                "event.seer_checked.detail",
                target=self._format_player(data.get("target_id")),
                result=self._translate_optional("seer_result", data.get("result")),
            )
        if event_type == "witch_used_antidote":
            return self._format_i18n("event.witch_used_antidote.detail", target=self._format_player(data.get("target_id")))
        if event_type == "witch_used_poison":
            return self._format_i18n("event.witch_used_poison.detail", target=self._format_player(data.get("target_id")))
        if event_type == "sheriff_elected":
            player = self._format_player(data.get("player_id"))
            votes = data.get("votes", {})
            if votes:
                vote_lines = []
                for voter_id, target_id in votes.items():
                    vote_lines.append(f"{self._format_player(int(voter_id))}→{self._format_player(int(target_id))}")
                return f"{player} 当选警长  票型: {' '.join(vote_lines)}"
            return self._format_i18n("event.sheriff_elected.detail", player=player)
        if event_type == "player_died":
            return self._format_i18n(
                "event.player_died.detail",
                player=self._format_player(data.get("player_id")),
                cause=self._translate_optional("death", data.get("cause")),
            )
        if event_type == "public_speech_made":
            return self._format_i18n(
                "event.public_speech_made.detail",
                player=self._format_player(data.get("player_id")),
                speech=self._truncate(data.get("speech") or event.get("content") or "", 80),
            )
        if event_type == "speaking_started":
            return self._format_i18n(
                "event.speaking_started.detail",
                player=self._format_player(data.get("player_id")),
            )
        if event_type == "speech_order_announced":
            order_list = data.get("order") or []
            order_text = self._format_player_list(order_list)
            return self._format_i18n("event.speech_order_announced.detail", order=order_text)
        if event_type == "sheriff_campaign":
            return self._format_i18n(
                "event.sheriff_campaign.detail",
                player=self._format_player(data.get("player_id")),
                speech=self._truncate(data.get("speech") or "", 80),
            )
        if event_type == "sheriff_declare":
            return self._format_i18n(
                "event.sheriff_declare.detail",
                player=self._format_player(data.get("player_id")),
            )
        if event_type == "sheriff_direction":
            clockwise = data.get("clockwise", True)
            direction = "左手边（顺时针）" if clockwise else "右手边（逆时针）"
            return self._format_i18n(
                "event.sheriff_direction.detail",
                player=self._format_player(data.get("player_id")),
                direction=direction,
            )
        if event_type == "wolf_self_destruct":
            return self._format_i18n(
                "event.wolf_self_destruct.detail",
                player=self._format_player(data.get("player_id")),
            )
        if event_type == "death_speech":
            return self._format_i18n(
                "event.death_speech.detail",
                player=self._format_player(data.get("player_id")),
                speech=self._truncate(data.get("speech") or "", 80),
            )
        if event_type == "vote_cast":
            return self._format_i18n(
                "event.vote_cast.detail",
                voter=self._format_player(data.get("voter_id")),
                target=self._format_player(data.get("target_id")),
            )
        if event_type == "vote_resolved":
            votes_data = data.get("votes")
            chosen = data.get("chosen")
            votes_text = self._format_votes(votes_data)
            tally_text = self._format_vote_tally(votes_data)
            chosen_text = self._format_player(chosen)
            base = self._format_i18n("event.vote_resolved.detail", votes=votes_text, chosen=chosen_text)
            if tally_text:
                return f"{base}\n    📊 {tally_text}"
            return base
        if content_key == "event.idiot_revealed":
            return self._format_i18n("event.idiot_revealed.detail", player=self._format_player(data.get("actor_id") or data.get("player_id")))
        if content_key == "event.hunter_shot":
            return self._format_i18n(
                "event.hunter_shot.detail",
                actor=self._format_player(data.get("actor_id")),
                target=self._format_player(data.get("target_id")),
            )
        if event_type == "sheriff_transferred":
            actor = self._format_player(data.get("actor_id"))
            target_id = data.get("target_id")
            if target_id is None:
                return self._format_i18n("event.sheriff_destroyed.detail", actor=actor)
            return self._format_i18n("event.sheriff_transferred.detail", actor=actor, target=self._format_player(target_id))
        if event_type == "game_ended":
            reason = data.get("reason", "")
            reason_text = self._i18n.t(f"win_reason.{reason}", "") if reason else ""
            winner_text = self._translate_optional("winner", data.get("winner"))
            if reason_text:
                return f"{winner_text} {reason_text}"
            return self._format_i18n("event.game_ended.detail", winner=winner_text)
        if event_type == "error_raised":
            error = data.get("error") or f"max_steps={data.get('max_steps', '-')}"
            return self._format_i18n("event.error_raised.detail", error=error)

        if content_key.startswith("event."):
            detail_key = content_key + ".detail"
            detail = self._i18n.t(detail_key, "")
            if detail:
                return detail
        return str(event.get("content") or "")

    @staticmethod
    def _truncate(text: str, max_len: int = 80) -> str:
        """Truncate long text (e.g. LLM speeches) for compact display."""
        # Replace newlines with spaces for single-line display
        flat = text.replace("\n", " ").strip()
        if len(flat) <= max_len:
            return flat
        return flat[:max_len] + "…"

    def _format_i18n(self, key: str, **kwargs: object) -> str:
        return self._i18n.t(key).format(**kwargs)

    def _format_player(self, value: object) -> str:
        if value is None:
            return "-"
        return f"{self._i18n.t('player.prefix')}{value}"

    def _format_player_list(self, values: object) -> str:
        if not isinstance(values, list):
            return "-"
        separator = "、" if self._language == "zh" else ", "
        return separator.join(self._format_player(value) for value in values)

    def _format_votes(self, votes: object) -> str:
        if not isinstance(votes, dict) or not votes:
            return "-"
        sheriff_id = self._view["snapshot"]["state_json"].get("sheriff_id") if self._view and self._view.get("snapshot") and isinstance(self._view["snapshot"].get("state_json"), dict) else None
        parts = []
        for voter, target in sorted(votes.items(), key=lambda item: int(item[0])):
            target_text = self._i18n.t("vote.none") if target is None else self._format_player(target)
            voter_text = self._format_player(voter)
            # Annotate sheriff's vote with weight
            if sheriff_id is not None and int(voter) == sheriff_id:
                voter_text = f"{voter_text}♛"
            parts.append(f"{voter_text}→{target_text}")
        return ("，" if self._language == "zh" else ", ").join(parts)

    def _format_vote_tally(self, votes: object) -> str:
        """Format vote tally as ranked summary (e.g. 'P3: 4票 > P7: 2票')."""
        if not isinstance(votes, dict) or not votes:
            return ""
        sheriff_id = self._view["snapshot"]["state_json"].get("sheriff_id") if self._view and self._view.get("snapshot") and isinstance(self._view["snapshot"].get("state_json"), dict) else None
        tally: dict[int, float] = {}
        abstain = 0
        for voter, target in votes.items():
            if target is None:
                abstain += 1
                continue
            weight = 1.5 if sheriff_id is not None and int(voter) == sheriff_id else 1.0
            target_int = int(target)
            tally[target_int] = tally.get(target_int, 0) + weight
        if not tally:
            return ""
        ranked = sorted(tally.items(), key=lambda x: -x[1])
        parts = []
        for pid, score in ranked:
            score_str = str(int(score)) if score == int(score) else f"{score:.1f}"
            parts.append(f"{self._format_player(pid)}:{score_str}票")
        result = " > ".join(parts)
        if abstain:
            result += f" 弃权:{abstain}"
        return result

    def _format_event_plain(self, event: dict[str, Any]) -> str:
        scope_name = self._i18n.enum("scope", event["scope"])
        event_type = self._translate_optional("event", event["event_type"])
        message = self._event_message(event)
        ts = event.get("created_at", "")
        time_short = ts[11:19] if len(ts) >= 19 else ts  # extract HH:MM:SS
        phase = self._translate_optional("phase", event["phase"])
        event_key = str(event.get("event_type") or "")
        scope_tag = self._scope_tag(str(event["scope"]), scope_name)
        header = f"{time_short} #{int(event['seq']):03d} R{event['round']} {scope_tag:<6} {event_type}"

        # Compact phase_started: just a separator line (except day_announce which has content)
        if event_key == "phase_started":
            content_key = str(event.get("content") or "")
            if content_key == "event.day_announce":
                return f"\n── R{event['round']}  ☀ {message}  {time_short} ──"
            data = event.get("data_json") if isinstance(event.get("data_json"), dict) else {}
            phase_val = data.get("phase", "")
            prefix = "\n\n" if phase_val == "night_start" else "\n"
            return f"{prefix}── R{event['round']}  {phase}  {time_short} ──"
        # Hide phase_ended entirely
        if event_key == "phase_ended":
            return ""
        if event_key == "speaking_started":
            return ""  # Merged into the speech event that follows
        if event_key in {"sheriff_campaign", "public_speech_made", "death_speech"}:
            speaker = self._event_player_label(event)
            return f"\n| {header}  {speaker}\n|   {message}"
        if event_key == "vote_cast":
            # Compact vote display — no header
            data = event.get("data_json") if isinstance(event.get("data_json"), dict) else {}
            voter_id = data.get("voter_id")
            voter = self._format_player(voter_id)
            target = self._format_player(data.get("target_id"))
            # Show sheriff weight
            sheriff_id = None
            if self._view and self._view.get("snapshot") and isinstance(self._view["snapshot"].get("state_json"), dict):
                sheriff_id = self._view["snapshot"]["state_json"].get("sheriff_id")
            suffix = " ♛×1.5" if sheriff_id is not None and voter_id == sheriff_id else ""
            return f"    🗳 {voter} -> {target}{suffix}"
        if event_key == "game_ended":
            return f"\n{'=' * 40}\n    🏆 {message}\n{'=' * 40}"
        if event_key in {"vote_resolved", "sheriff_elected", "error_raised"}:
            return f"{header}\n    >> {message}"
        return f"{header}\n    {message}"

    def _format_event_rich(self, event: dict[str, Any]) -> Text:
        plain = self._format_event_plain(event)
        if not plain:
            return Text("")  # phase_ended hidden
        text = Text(plain)
        event_key = str(event.get("event_type") or "")
        scope = str(event.get("scope") or "")
        scope_name = self._i18n.enum("scope", scope)
        scope_tag = self._scope_tag(scope, scope_name)
        scope_start = plain.find(scope_tag)
        if scope_start >= 0:
            text.stylize(SCOPE_COLORS.get(scope, "white") + " bold", scope_start, scope_start + len(scope_tag))
        if event_key == "phase_started":
            # Entire line is a separator — style it all
            text.stylize("cyan bold", 0, len(plain))
        elif event_key in {"sheriff_campaign", "public_speech_made", "death_speech"}:
            line_start = 1 if plain.startswith("\n") else 0
            line_end = plain.find("\n", line_start)
            if line_end < 0:
                line_end = len(plain)
            player_id = self._event_player_id(event)
            text.stylize("bright_cyan bold", line_start, line_end)
            if player_id is not None:
                speaker = self._format_player(player_id)
                speaker_start = plain.find(speaker, line_start, line_end)
                if speaker_start >= 0:
                    text.stylize("black on bright_cyan bold", speaker_start, speaker_start + len(speaker))
            for marker in ("\n|",):
                marker_start = plain.find(marker)
                while marker_start >= 0:
                    text.stylize("dim cyan", marker_start + 1, marker_start + 2)
                    marker_start = plain.find(marker, marker_start + 1)
        elif event_key == "vote_cast":
            text.stylize("dim", 0, len(plain))
        elif event_key == "game_ended":
            text.stylize("bold green on black", 0, len(plain))
        elif event_key in {"vote_resolved", "sheriff_elected"}:
            text.stylize("green bold", plain.find(">>") if ">>" in plain else 0, len(plain))
        elif event_key == "error_raised":
            text.stylize("red bold", 0, len(plain))
        return text

    def _scope_tag(self, scope: str, scope_name: str) -> str:
        labels = {
            "public": "公开",
            "wolf_team": "狼队",
            "role_private": "私有",
            "god": "上帝",
            "system": "系统",
        }
        return f"[{labels.get(scope, scope_name)}]"

    def _event_player_label(self, event: dict[str, Any]) -> str:
        player_id = self._event_player_id(event)
        return self._format_player(player_id) if player_id is not None else ""

    def _event_player_id(self, event: dict[str, Any]) -> int | None:
        data = event.get("data_json") if isinstance(event.get("data_json"), dict) else {}
        player_id = data.get("player_id") or data.get("actor_id") or data.get("speaker_id")
        if player_id is None:
            return None
        try:
            return int(player_id)
        except (TypeError, ValueError):
            return None

    async def _launch_game(self) -> None:
        config_id = self._config_ids[0] if self._config_ids else "12p_pre_witch_hunter_idiot"
        event_bus = EventBus()
        event_bus.subscribe(self._on_live_game_event)
        event_bus.subscribe(tts_engine.on_event)
        tts_engine.start_worker(asyncio.get_event_loop())
        boot = await bootstrap_and_run_game(
            paths=self._paths,
            config_id=config_id,
            llm_settings=get_llm_settings(),
            event_bus=event_bus,
            on_game_started=self._show_started_game,
        )
        # Set player roles for TTS voice mapping
        tts_engine.set_player_roles(boot.state["players"])
        self._running_game_id = boot.state["game_id"]
        self.game_id = boot.state["game_id"]
        self.selected_game_index = 0
        self.auto_refresh = True
        self._event_seqs = []
        self._reload_view(force=True)

    def _show_started_game(self, game_id: str) -> None:
        self._running_game_id = game_id
        self.game_id = game_id
        self.selected_game_index = 0
        self.auto_refresh = True
        self._event_seqs = []
        self._last_game_id = None
        self._reload_view(force=True)

    def _on_live_game_event(self, event: object) -> None:
        if getattr(event, "game_id", None) != self.game_id:
            return
        try:
            self.call_from_thread(self._reload_view)
        except RuntimeError:
            # Already in the app thread (worker runs in same loop)
            self._reload_view()
