# Synchronization and operations

## Code responsibilities

| File | Responsibility |
| --- | --- |
| `src/run_app.py` | Starts the background scheduler and Streamlit subprocess. |
| `src/scheduler.toml` | Enables scheduling and configures repository, cron, time zone, and allowed lateness. |
| `src/job/github_async.py` | Fetches paginated GitHub items and coordinates automatic or manual synchronization. |
| `src/job/help_db.py` | Reads and writes SQLite and maintains the automatic cursor. |
| `src/job/help_scheduler.py` | Runs manual date ranges day by day. |
| `src/github_client.py` | Reads cached rows, restores labels and booleans, and calculates metrics. |
| `src/job/cache.db` | Local persistent database shared by worker and dashboard. |
| `sql/` | Initial table and index definitions. |

## Automatic synchronization

The scheduler calls `synchronize_repository(repo_name=repository)` without explicit dates.

1. `start_sync()` inserts the repository's control row if absent and marks it running.
2. The lower bound is 2025-01-01 UTC for an incomplete initial load, or the stored cursor minus five minutes, clamped to that initial date.
3. The upper bound is the execution's start time, exclusive.
4. GitHub issues and pull requests are fetched with `state="all"`, ordered by update time. The API receives a `since` filter; the upper bound is checked locally.
5. Each item is committed separately with an upsert on `(repository, number)`.
6. After successful processing, `finish_sync()` advances the cursor to the run's start time, records completion, and marks the initial load complete.

Failures inside the synchronization try block call `fail_sync()` and propagate to the scheduler. Previously committed items remain available and the cursor stays unchanged. Failures before control initialization, such as a missing table in `start_sync()`, may not be recorded in the table.

A successful run with no matching items still advances the cursor.

## Tables

`github_items` stores the latest fetched item state, author, assignee, labels as JSON, UTC timestamp strings, first issue comment time, and PR merge information. It does not store every historical change. The first-response metric currently uses the first issue comment, including comments from the author or bots.

`sync_state` contains one mutable row per repository, not an execution history:

| Field | Meaning |
| --- | --- |
| `initial_sync_completed` | The configured initial range has completed successfully. |
| `incremental_cursor` | Start timestamp of the last successful automatic run. |
| `last_started_at` | Start of the latest automatic attempt. |
| `last_success_at` | Completion time of the latest successful automatic run. |
| `status` | pending, running, success, or error. |
| `last_error` | Latest recorded automatic-sync error, truncated to 2,000 characters. |

Inspect the database with a SQLite client:

```sql
SELECT repository, status, initial_sync_completed,
       incremental_cursor, last_started_at, last_success_at, last_error
FROM sync_state;

SELECT repository, item_type, COUNT(*) AS total
FROM github_items
GROUP BY repository, item_type;
```

## Manual imports and time semantics

`python -m src.job.help_scheduler` calls `import_issues_daily()`. Explicit periods are processed as UTC half-open intervals, with an inclusive CLI end date converted to the following midnight. The current day is capped at the instant the command started.

Manual runs update item rows but do not modify automatic synchronization state. They stop on the first failed day; earlier commits remain.

Both modes filter the item's **current last-update timestamp**, not creation time or all past events. An item updated in September and again in October will not match a September-only query. Deletions are not reconciled automatically. The default initial import also excludes items last updated before 2025, so it should not be described as full repository history.

Large day-by-day imports can repeatedly scan later API results because the upper bound is applied locally. Use small manual ranges when needed and the persisted cursor for normal refreshes. Synchronization remains subject to GitHub API limits.

## Scheduler lifecycle

The launcher registers a cron job; it does not perform an immediate initial import. Follow the README's one-off automatic synchronization command to populate an empty cache.

Scheduling is in memory. Shutdown or downtime does not retain a queue of missed cron executions. At the next actual automatic run, the persisted data cursor determines the outstanding update interval.

`coalesce=True` combines eligible delayed executions; `misfire_grace_time` is an allowed lateness in seconds, not a retry interval or a guarantee of recovery across restarts. `max_instances=1` applies only to that scheduler instance.

Use one launcher and avoid overlapping manual imports. The database status column is not a lock. A killed process can leave status as running; a later automatic attempt overwrites it and resumes from the unchanged cursor. Graceful shutdown waits for an active synchronization to finish.

## Logs and dashboard freshness

- Launcher and scheduled jobs: `logs/scheduler.log`, rotated at 5,000,000 bytes with five backups.
- Manual CLI: `logs/sync_YYYY-MM-DD.log`, appended for each execution.
- CLI exit code: 0 for success, 1 for a caught import failure.

The dashboard caches its SQLite query results for 900 seconds. A worker in another process does not invalidate that memory cache. New rows become visible on a subsequent page execution after expiration, or after restarting the dashboard.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `No module named 'src'` | Run `python src/run_app.py` from the repository root; it prepares the subprocess import path. |
| `No module named 'tomllib'` | Use Python 3.11 or newer with dependencies installed in that interpreter. |
| `StreamlitSecretNotFoundError` | Create root-level `.streamlit/secrets.toml` as shown in the README. |
| `unable to open database file` / `no such table` | Confirm `src/job/cache.db`, permissions, and apply the schema scripts. |
| No imported data immediately after launch | The launcher waits for the cron time; perform the one-off automatic import first. |
| API authorization or rate-limit failure | Check token access and logs; retry after resolving the cause. The automatic cursor does not advance on failure. |
| Unexpected repository on screen | Scheduler configuration and the hard-coded repository in `src/app.py` must agree. |

To run only the dashboard, set `enabled = false` in `src/scheduler.toml` and use the launcher. Direct `streamlit run src/app.py` does not start the scheduler and may require explicit project-root import-path setup.

## Current limitations

There is no automatic schema migration, distributed execution lock, automatic deletion reconciliation, or event/snapshot history. Paginated API traversal is not a transactional GitHub snapshot; the overlap reduces boundary risks but is not a proof against every concurrent update scenario. The branch includes local database and IDE artifacts that should be reviewed before upstream submission.
