import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from app.domain.events import GameEvent
from app.domain.roles import EventScope, EventType, Phase
from app.config import AppPaths
from app.infra.db import initialize_database, connect_database
from app.infra.repositories.events import insert_events
from app.infra.repositories.rooms import create_room
from server import api


class ServerFlowSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        api._human_seats.clear()
        api._seat_tokens.clear()
        self._orig_get_paths = api._get_paths
        self._orig_start_game = api.start_game
        self._tempdir: tempfile.TemporaryDirectory[str] | None = None

    def tearDown(self) -> None:
        api._get_paths = self._orig_get_paths
        api.start_game = self._orig_start_game
        if self._tempdir is not None:
            self._tempdir.cleanup()

    def _temp_paths(self) -> AppPaths:
        self._tempdir = tempfile.TemporaryDirectory()
        root = Path(self._tempdir.name)
        return AppPaths(
            root=root,
            app=root / "app",
            configs=root / "app" / "configs",
            prompts=root / "app" / "configs" / "prompts",
            data=root / "data",
            graphs=root / "data" / "graphs",
            replays=root / "data" / "replays",
            contexts=root / "data" / "contexts",
            database=root / "data" / "wolf.db",
            schema=Path(__file__).resolve().parents[1] / "app" / "infra" / "schema.sql",
        )

    def test_human_game_seat_access_requires_matching_token(self) -> None:
        api._human_seats["game-1"] = {1, 2}
        api._seat_tokens["game-1"] = {1: "token-a", 2: "token-b"}

        self.assertTrue(api._authorize_seat_access("game-1", 1, "token-a"))
        self.assertFalse(api._authorize_seat_access("game-1", 1, None))
        self.assertFalse(api._authorize_seat_access("game-1", 1, "token-b"))
        self.assertFalse(api._authorize_seat_access("game-1", None, None))

    def test_ai_game_allows_god_view_without_token(self) -> None:
        self.assertTrue(api._authorize_seat_access("ai-game", None, None))

    def test_persisted_human_game_still_requires_token_after_memory_loss(self) -> None:
        paths = self._temp_paths()
        initialize_database(paths.database, paths.schema)
        api._get_paths = lambda: paths
        conn = connect_database(paths.database)
        try:
            conn.execute(
                """
                INSERT INTO games (
                    id, status, started_at, round_count, config_id, config_json,
                    prompt_profile_json, seed, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "game-1",
                    "running",
                    "2026-05-22T00:00:00+08:00",
                    0,
                    "test-config",
                    "{}",
                    "{}",
                    1,
                    "2026-05-22T00:00:00+08:00",
                ),
            )
            conn.commit()
            api._persist_seat_tokens(conn, game_id="game-1", seat_tokens={3: "token-c"})
        finally:
            conn.close()

        api._human_seats.clear()
        api._seat_tokens.clear()

        self.assertFalse(api._authorize_seat_access("game-1", None, None))
        self.assertFalse(api._authorize_seat_access("game-1", 3, None))
        self.assertFalse(api._authorize_seat_access("game-1", 3, "wrong"))
        self.assertTrue(api._authorize_seat_access("game-1", 3, "token-c"))

    def test_finished_human_game_is_freely_observable(self) -> None:
        # A finished personal game must be replayable without a token —
        # otherwise the records→replay flow hangs at loading.
        paths = self._temp_paths()
        initialize_database(paths.database, paths.schema)
        api._get_paths = lambda: paths
        conn = connect_database(paths.database)
        try:
            conn.execute(
                """
                INSERT INTO games (
                    id, status, started_at, ended_at, round_count, config_id,
                    config_json, prompt_profile_json, seed, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "game-done",
                    "completed",
                    "2026-05-22T00:00:00+08:00",
                    "2026-05-22T00:10:00+08:00",
                    5,
                    "test-config",
                    "{}",
                    "{}",
                    1,
                    "2026-05-22T00:00:00+08:00",
                ),
            )
            conn.commit()
            api._persist_seat_tokens(conn, game_id="game-done", seat_tokens={3: "token-c"})
        finally:
            conn.close()

        api._human_seats.clear()
        api._seat_tokens.clear()

        # Observer (no seat / token) is allowed because the game is over.
        self.assertTrue(api._authorize_seat_access("game-done", None, None))
        # The original seat owner can still rejoin with their token.
        self.assertTrue(api._authorize_seat_access("game-done", 3, "token-c"))

    def test_sanitize_snapshot_keeps_only_own_pending_skills(self) -> None:
        detail = {
            "players": [
                {"seat_index": 1, "role": "villager", "faction": "village", "survived": 1},
                {"seat_index": 2, "role": "wolf", "faction": "wolf", "survived": 1},
            ],
            "events": [],
            "snapshot": {
                "state_json": {
                    "players": {
                        "1": {"role": "villager", "faction": "village", "alive": True},
                        "2": {"role": "wolf", "faction": "wolf", "alive": True},
                    },
                    "pending_skills": [
                        {"kind": "hunter_shot", "actor_id": 1},
                        {"kind": "sheriff_transfer", "actor_id": 2},
                    ],
                }
            },
        }

        sanitized = api._sanitize_detail_for_seat(detail, 1)

        self.assertEqual(
            sanitized["snapshot"]["state_json"]["pending_skills"],
            [{"kind": "hunter_shot", "actor_id": 1}],
        )

    def test_running_game_masks_other_alive_seats(self) -> None:
        detail = {
            "players": [
                {"seat_index": 1, "role": "seer", "faction": "good", "survived": 1},
                {"seat_index": 2, "role": "wolf", "faction": "wolf", "survived": 1},
            ],
            "snapshot": {"state_json": {"ended": False, "winner": None, "players": {}}},
            "game": {"status": "running"},
        }
        sanitized = api._sanitize_detail_for_seat(detail, 1)
        roles = {p["seat_index"]: p["role"] for p in sanitized["players"]}
        self.assertEqual(roles, {1: "seer", 2: "unknown"})

    def test_ended_game_reveals_all_identities(self) -> None:
        detail = {
            "players": [
                {"seat_index": 1, "role": "seer", "faction": "good", "survived": 1},
                {"seat_index": 2, "role": "wolf", "faction": "wolf", "survived": 1},
            ],
            "snapshot": {
                "state_json": {
                    "ended": True,
                    "winner": "good",
                    "players": {
                        "1": {"role": "seer", "faction": "good", "alive": True},
                        "2": {"role": "wolf", "faction": "wolf", "alive": True},
                    },
                }
            },
            "game": {"status": "completed"},
        }
        sanitized = api._sanitize_detail_for_seat(detail, 1)
        roles = {p["seat_index"]: p["role"] for p in sanitized["players"]}
        self.assertEqual(roles, {1: "seer", 2: "wolf"})
        snap_roles = {
            k: v["role"] for k, v in sanitized["snapshot"]["state_json"]["players"].items()
        }
        self.assertEqual(snap_roles, {"1": "seer", "2": "wolf"})

    def test_insert_events_stamps_seq_and_round_for_live_payloads(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.execute(
            """
            CREATE TABLE game_events (
                game_id TEXT,
                seq INTEGER,
                round INTEGER,
                phase TEXT,
                scope TEXT,
                actor_id INTEGER,
                target_ids_json TEXT,
                event_type TEXT,
                content TEXT,
                data_json TEXT,
                created_at TEXT
            )
            """
        )
        event = GameEvent(
            game_id="game-1",
            phase=Phase.DAY_SPEECH,
            scope=EventScope.PUBLIC,
            target_players=set(),
            event_type=EventType.PUBLIC_SPEECH_MADE,
            content="speech",
            data={"player_id": 1},
        )

        next_seq = insert_events(conn, game_id="game-1", round_no=3, start_seq=7, events=[event])

        self.assertEqual(next_seq, 8)
        self.assertEqual(event.seq, 7)
        self.assertEqual(event.round, 3)

    def test_room_started_payload_is_personalized_per_user(self) -> None:
        payload = {
            "type": "room_started",
            "game_id": "game-1",
            "seat_owners": {1: "user-a", 2: "user-b"},
            "seat_tokens_by_user": {"user-a": "token-a", "user-b": "token-b"},
        }

        personalized = api._personalize_room_payload(payload, "user-a")

        self.assertEqual(personalized["your_seat"], 1)
        self.assertEqual(personalized["seat_token"], "token-a")
        self.assertEqual(personalized["seat_owners"], {1: "user-a"})
        self.assertNotIn("seat_tokens_by_user", personalized)

    def test_start_room_returns_host_seat_token_as_ws_fallback(self) -> None:
        async def fake_start_game(_req: api.StartGameRequest) -> SimpleNamespace:
            return SimpleNamespace(game_id="game-1", seat_tokens={1: "host-token"})

        paths = self._temp_paths()
        initialize_database(paths.database, paths.schema)
        api._get_paths = lambda: paths
        api.start_game = fake_start_game
        conn = connect_database(paths.database)
        try:
            create_room(
                conn,
                room_id="room-1",
                config_id="12p_pre_witch_hunter_idiot",
                host_user_id="host-user",
                host_nickname="Host",
                use_llm=False,
            )
        finally:
            conn.close()

        import asyncio
        response = asyncio.run(api.start_room("room-1", api.StartRoomRequest(host_user_id="host-user")))

        self.assertEqual(response["game_id"], "game-1")
        self.assertEqual(response["your_seat"], 1)
        self.assertEqual(response["seat_token"], "host-token")


if __name__ == "__main__":
    unittest.main()
