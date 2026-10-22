import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone, timedelta
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "cache.db"


def to_iso(value):
    """Convert datetime to UTC text, but keeps null values."""
    if value is None:
        return None

    return value.astimezone(timezone.utc).isoformat()

DEFAULT_IMPORT_START = datetime(2025, 1, 1, tzinfo=timezone.utc)
SYNC_OVERLAP = timedelta(minutes=5)

def start_sync(repo_name):
    """Start a synchronization attempt and resolve its lower boundary."""
    started_at = datetime.now(timezone.utc)

    with closing(sqlite3.connect(DB_PATH, timeout=30)) as conn:
        with conn:
            conn.execute(
                """
                INSERT INTO sync_state (repository)
                VALUES (?)
                ON CONFLICT(repository) DO NOTHING
                """,
                (repo_name,),
            )

            initial_sync_completed, cursor = conn.execute(
                """
                SELECT initial_sync_completed, incremental_cursor
                FROM sync_state
                WHERE repository = ?
                """,
                (repo_name,),
            ).fetchone()

            since = DEFAULT_IMPORT_START

            if initial_sync_completed and cursor:
                cursor_at = datetime.fromisoformat(
                    cursor.replace("Z", "+00:00")
                )

                since = max(
                    DEFAULT_IMPORT_START,
                    cursor_at - SYNC_OVERLAP,
                    )

            conn.execute(
                """
                UPDATE sync_state
                SET status = 'running',
                    last_started_at = ?,
                    last_error = NULL
                WHERE repository = ?
                """,
                (to_iso(started_at), repo_name),
            )

    return started_at, since


def finish_sync(repo_name, started_at):
    with closing(sqlite3.connect(DB_PATH, timeout=30)) as conn:
        with conn:
            conn.execute(
                """
                UPDATE sync_state
                SET status = 'success',
                    initial_sync_completed = 1,
                    incremental_cursor = ?,
                    last_success_at = ?,
                    last_error = NULL
                WHERE repository = ?
                """,
                (
                    to_iso(started_at),
                    to_iso(datetime.now(timezone.utc)),
                    repo_name,
                ),
            )


def fail_sync(repo_name, error):
    with closing(sqlite3.connect(DB_PATH, timeout=30)) as conn:
        with conn:
            conn.execute(
                """
                UPDATE sync_state
                SET status = 'error',
                    last_error = ?
                WHERE repository = ?
                """,
                (
                    f"{type(error).__name__}: {error}"[:2000],
                    repo_name,
                ),
            )

def save_github_item(conn, repo_name, issue, base_info):
    """Insert item or refresh the database row."""
    params = {
        "repository": repo_name,
        "number": issue.number,
        "github_issue_id": issue.id,
        "item_type": (
            "pull_request" if issue.pull_request else "issue"
        ),
        "title": issue.title,
        "state": issue.state,
        "author": base_info["author"],
        "avatar_url": base_info["avatar_url"],
        "assignee": base_info["assignee"],
        "labels_json": json.dumps(
            base_info["labels"], ensure_ascii=False
        ),
        "created_at": to_iso(issue.created_at),
        "updated_at": to_iso(issue.updated_at),
        "closed_at": to_iso(issue.closed_at),
        "first_response_at": to_iso(
            base_info.get("first_response_at")
        ),
        "merged_at": to_iso(base_info.get("merged_at")),
        "is_merged": int(base_info.get("is_merged", False)),
        "synced_at": to_iso(datetime.now(timezone.utc)),
    }

    # A short transaction for each item.
    # The GitHub integration is before this line.
    with conn:
        conn.execute(
            """
            INSERT INTO github_items (
                repository, number, github_issue_id,
                item_type, title, state,
                author, avatar_url, assignee, labels_json,
                created_at, updated_at, closed_at,
                first_response_at, merged_at, is_merged,
                synced_at
            )
            VALUES (
                       :repository, :number, :github_issue_id,
                       :item_type, :title, :state,
                       :author, :avatar_url, :assignee, :labels_json,
                       :created_at, :updated_at, :closed_at,
                       :first_response_at, :merged_at, :is_merged,
                       :synced_at
                   )
            ON CONFLICT(repository, number) DO UPDATE SET
                                                          github_issue_id = excluded.github_issue_id,
                                                          item_type = excluded.item_type,
                                                          title = excluded.title,
                                                          state = excluded.state,
                                                          author = excluded.author,
                                                          avatar_url = excluded.avatar_url,
                                                          assignee = excluded.assignee,
                                                          labels_json = excluded.labels_json,
                                                          created_at = excluded.created_at,
                                                          updated_at = excluded.updated_at,
                                                          closed_at = excluded.closed_at,
                                                          first_response_at = excluded.first_response_at,
                                                          merged_at = excluded.merged_at,
                                                          is_merged = excluded.is_merged,
                                                          synced_at = excluded.synced_at
            """,
            params,
        )

def select_github_items(repo_name: str):
    """Read repository items from SQLite as dictionaries."""
    database_uri = DB_PATH.resolve().as_uri() + "?mode=ro"

    with closing(
            sqlite3.connect(database_uri, uri=True, timeout=30)
    ) as conn:
        print(f'sqlite3={sqlite3}')
        conn.row_factory = sqlite3.Row
        print(f'conn={conn}')
        rows = conn.execute(
            """
            SELECT
                github_issue_id AS id,
                number,
                item_type,
                title,
                created_at,
                closed_at,
                labels_json,
                assignee,
                author,
                avatar_url,
                first_response_at,
                merged_at,
                is_merged
            FROM github_items
            WHERE repository = ?
            ORDER BY created_at DESC, number DESC
            """,
            (repo_name,),
        ).fetchall()

        return [dict(row) for row in rows]
