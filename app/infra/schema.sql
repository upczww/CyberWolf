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
