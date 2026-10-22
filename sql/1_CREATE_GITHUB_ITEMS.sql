CREATE TABLE IF NOT EXISTS github_items (
    repository          TEXT NOT NULL,
    number              INTEGER NOT NULL,
    github_issue_id     INTEGER NOT NULL,
    item_type           TEXT NOT NULL CHECK (item_type IN ('issue', 'pull_request')),
    title               TEXT NOT NULL,
    state               TEXT NOT NULL CHECK (state IN ('open', 'closed')),
    author              TEXT,
    avatar_url          TEXT,
    assignee            TEXT,
    labels_json         TEXT NOT NULL DEFAULT '[]',
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    closed_at           TEXT,
    first_response_at   TEXT,
    merged_at           TEXT,
    is_merged           INTEGER NOT NULL DEFAULT 0 CHECK (is_merged IN (0, 1)),
    synced_at           TEXT NOT NULL,
    PRIMARY KEY (repository, number)
);

CREATE INDEX IF NOT EXISTS idx_github_items_type_created
    ON github_items (repository, item_type, created_at);

CREATE INDEX IF NOT EXISTS idx_github_items_updated
    ON github_items (repository, updated_at);