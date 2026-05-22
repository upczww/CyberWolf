CREATE TABLE IF NOT EXISTS games (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    winner TEXT,
    round_count INTEGER NOT NULL DEFAULT 0,
    config_id TEXT NOT NULL,
    config_json TEXT NOT NULL,
    prompt_profile_json TEXT NOT NULL,
    graph_mermaid_path TEXT,
    graph_dot_path TEXT,
    graph_png_path TEXT,
    seed INTEGER,
    end_reason TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS game_players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL,
    player_id INTEGER NOT NULL,
    seat_index INTEGER NOT NULL,
    role TEXT NOT NULL,
    faction TEXT NOT NULL,
    is_sheriff INTEGER NOT NULL DEFAULT 0,
    survived INTEGER NOT NULL DEFAULT 1,
    death_round INTEGER,
    death_cause TEXT,
    summary_json TEXT,
    FOREIGN KEY (game_id) REFERENCES games(id)
);

CREATE TABLE IF NOT EXISTS game_seat_tokens (
    game_id TEXT NOT NULL,
    seat_index INTEGER NOT NULL,
    seat_token TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (game_id, seat_index),
    FOREIGN KEY (game_id) REFERENCES games(id)
);

CREATE TABLE IF NOT EXISTS game_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    round INTEGER NOT NULL,
    phase TEXT NOT NULL,
    scope TEXT NOT NULL,
    actor_id INTEGER,
    target_ids_json TEXT NOT NULL,
    event_type TEXT NOT NULL,
    content TEXT NOT NULL,
    data_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (game_id) REFERENCES games(id)
);

CREATE TABLE IF NOT EXISTS state_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    round INTEGER NOT NULL,
    phase TEXT NOT NULL,
    snapshot_type TEXT NOT NULL,
    state_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (game_id) REFERENCES games(id)
);

CREATE TABLE IF NOT EXISTS llm_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL,
    player_id INTEGER,
    round INTEGER NOT NULL,
    phase TEXT NOT NULL,
    model TEXT NOT NULL,
    tool_name TEXT,
    prompt_key TEXT,
    request_json TEXT NOT NULL,
    response_json TEXT,
    latency_ms INTEGER NOT NULL DEFAULT 0,
    retry_count INTEGER NOT NULL DEFAULT 0,
    fallback_level INTEGER NOT NULL DEFAULT 0,
    success INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (game_id) REFERENCES games(id)
);

CREATE TABLE IF NOT EXISTS game_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL,
    total_events INTEGER NOT NULL DEFAULT 0,
    total_llm_calls INTEGER NOT NULL DEFAULT 0,
    total_fallbacks INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    notes_json TEXT,
    FOREIGN KEY (game_id) REFERENCES games(id)
);

CREATE TABLE IF NOT EXISTS configs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    player_count INTEGER NOT NULL,
    config_json TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

-- Multi-human lobby rooms. A room owns up to 12 seats; each seat is either
-- AI (user_id IS NULL) or a human (user_id + nickname). The host is the
-- user_id who created the room. When status = 'started', game_id points
-- to the game spawned from this room.
CREATE TABLE IF NOT EXISTS rooms (
    id TEXT PRIMARY KEY,
    config_id TEXT NOT NULL,
    host_user_id TEXT NOT NULL,
    invite_token TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'lobby',
    game_id TEXT,
    use_llm INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    started_at TEXT,
    closed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_rooms_status ON rooms(status);
CREATE INDEX IF NOT EXISTS idx_rooms_token ON rooms(invite_token);

CREATE TABLE IF NOT EXISTS room_seats (
    room_id TEXT NOT NULL,
    seat_index INTEGER NOT NULL,
    user_id TEXT,
    nickname TEXT,
    joined_at TEXT,
    PRIMARY KEY (room_id, seat_index),
    FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_room_seats_user ON room_seats(user_id);
