![](https://github.com/scanapi/design/raw/main/images/github-hero-dark.png)

# Community Dashboard

A Streamlit dashboard for exploring ScanAPI community activity, issues, pull requests, response times, and merge times.

GitHub data is synchronized into SQLite by a separate worker. Dashboard metric queries read the local database instead of calling the GitHub API on each page execution.

## Requirements

- Python **3.11 or newer** for the integrated launcher, which uses `tomllib`.
- Git and a Python virtual environment.
- A GitHub personal access token for authenticated synchronization.
- A writable local database at `src/job/cache.db`.

The stack includes Streamlit, Pandas, Plotly, PyGithub, SQLite, and APScheduler 3.x.

## Installation

Clone this repository or your fork, then open a terminal in the repository root:

```bash
git clone <repository-url>
cd community-dashboard
```

Windows PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The Windows example selects Python 3.13; another installed Python version of 3.11 or newer can be used.

Linux/macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

In the remaining cross-platform examples, `python` means the interpreter in this environment. Use its explicit path or activate the environment first.

## GitHub authentication

Create `.streamlit/secrets.toml` **in the repository root**, alongside `src`:

```toml
GITHUB_TOKEN = "<YOUR_GITHUB_PERSONAL_ACCESS_TOKEN>"
```

Use a token authorized to read the target repository. Do not commit real tokens. An empty token selects unauthenticated access with lower API limits, but the current client still requires a readable secrets file: a missing file can raise `StreamlitSecretNotFoundError`.

## Prepare the SQLite schema

The application does not automatically create tables. Run this command from the repository root to apply the two existing SQL scripts to the expected database:

```bash
python -c "import sqlite3; from pathlib import Path; conn = sqlite3.connect('src/job/cache.db'); scripts = sorted(Path('sql').glob('*.sql')); [conn.executescript(p.read_text(encoding='utf-8')) for p in scripts]; conn.close()"
```

These scripts use `IF NOT EXISTS`; they preserve existing rows and do not perform schema migrations. The branch currently includes a database file, but setup should not depend on its existing contents. Back up populated databases before operational changes.

## Populate the cache

For an immediate automatic synchronization, run this from the repository root **before starting the scheduler**:

```bash
python -c "from src.job.github_async import synchronize_repository; print(synchronize_repository('scanapi/scanapi'))"
```

On the first successful automatic run, the worker imports issues and pull requests whose current GitHub `updated_at` is on or after **2025-01-01 UTC**, up to the run's start time. It traverses paginated results without the old 100-item slice.

Later runs resume from the persisted cursor with a five-minute overlap. Existing items are updated using an upsert. This is not a complete event history: items last updated before 2025 are outside the default initial range.

## Start the dashboard and scheduler

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe src/run_app.py
```

Linux/macOS:

```bash
.venv/bin/python src/run_app.py
```

Open the local URL printed in the terminal, normally http://localhost:8501.

The launcher starts APScheduler and a Streamlit subprocess using the same interpreter, sets the project working directory and import path, and logs the next execution time.

**Startup registers the schedule; it does not immediately run the import.** Keep the process running for scheduled executions.

## Configure the schedule

Edit `src/scheduler.toml` and restart the launcher. The currently committed configuration is:

```toml
[scheduler]
enabled = true
repository = "scanapi/scanapi"
cron = "25 * * * *"
timezone = "America/Sao_Paulo"
misfire_grace_time = 3600
```

This runs at minute **25 of every hour** in the configured time zone. To run daily at midnight, change only:

```toml
cron = "0 0 * * *"
```

Cron has five fields: minute, hour, day of month, month, day of week. Set `enabled = false` to use the same launcher for the dashboard without a scheduler.

The UI currently queries `scanapi/scanapi` in `src/app.py`. Changing `scheduler.repository` does not change the dashboard's repository automatically.

Run only one synchronization process per repository. The scheduler's `max_instances=1` prevents overlap within that scheduler, not across separate launchers or manual commands.

## Manual date-range import

For a targeted import, use the existing CLI:

```bash
python -m src.job.help_scheduler --repository scanapi/scanapi --start-date 2026-10-01 --end-date 2026-10-03
```

The end date is inclusive in UTC. If omitted, the range ends at the current instant. This command processes the range one day at a time and **does not update the automatic cursor in `sync_state`**.

Without date arguments, this CLI repeats daily intervals starting on 2025-01-01; it is not the incremental scheduler entry point. Prefer automatic synchronization for routine refreshes.

## Operations and contribution

See [Synchronization and operations](docs/synchronization.md) for database state, logs, recovery, and limitations.

See [Contributing](CONTRIBUTING.md) for development checks and review guidance.
