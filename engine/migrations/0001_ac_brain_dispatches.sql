-- AC Python engine dispatch history.
-- Additive migration: does not modify existing worker_runs/ac_chat_messages tables.
CREATE TABLE IF NOT EXISTS ac_brain_dispatches (
    dispatch_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN (
            'queued', 'running', 'blocked', 'partial_failure',
            'completed_pending_review', 'completed', 'failed'
        )
    ),
    objective TEXT NOT NULL,
    plan_json TEXT NOT NULL,
    result_json TEXT,
    error_code TEXT
);

CREATE INDEX IF NOT EXISTS idx_ac_brain_dispatches_created_at
    ON ac_brain_dispatches(created_at);

CREATE INDEX IF NOT EXISTS idx_ac_brain_dispatches_status_created_at
    ON ac_brain_dispatches(status, created_at);
