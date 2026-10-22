CREATE TABLE IF NOT EXISTS sync_state (
    repository              TEXT PRIMARY KEY,
    initial_sync_completed  INTEGER NOT NULL DEFAULT 0 CHECK (initial_sync_completed IN (0, 1)),
    incremental_cursor      TEXT,
    last_started_at         TEXT,
    last_success_at         TEXT,
    status                  TEXT NOT NULL DEFAULT 'pending'
                                              CHECK (
                                                  status IN (
                                                             'pending',
                                                             'running',
                                                             'success',
                                                             'error'
                                                      )
                                                  ),
    last_error              TEXT
);