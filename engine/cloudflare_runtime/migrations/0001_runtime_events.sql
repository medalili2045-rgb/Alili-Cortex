-- Additive migration for the isolated AC Python Worker adapter.
-- Review and apply explicitly; this file is NOT executed by CI or deployment.
CREATE TABLE IF NOT EXISTS ac_runtime_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL CHECK (length(event_type) BETWEEN 1 AND 80),
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ac_runtime_events_created_at
    ON ac_runtime_events(created_at);
