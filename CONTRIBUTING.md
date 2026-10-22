# Contributing

Thanks for taking the time to contribute! 🙇‍♀️🙇‍♂️ Every little bit of help counts!

As one of the repositories under the `scanapi` GitHub organization, this repository follows the [ScanAPI Contributing Guideline](https://github.com/scanapi/contributors/blob/master/CONTRIBUTING.md).

## Local development

Follow [README.md](README.md) to install Python 3.11+, configure a local GitHub token, prepare SQLite, and populate the cache. Use `python src/run_app.py` to run the dashboard and optional scheduler.

Run commands from the repository root using the virtual environment's interpreter. Keep code comments and new documentation in English.

## Code quality

Before committing Python changes, format the source:

```bash
python -m black src/
```

Run the same checks used by CI:

```bash
python -m black --check src/
python -m flake8 src/
```

CI currently runs these checks on Python 3.11. Document any existing failures rather than reporting an unverified pass.

## Synchronization review

When changing persistence or scheduling, verify the relevant behavior with a disposable database:

- Schema initialization and repeated upserts do not duplicate items.
- A successful automatic run advances the cursor, including an empty result.
- A failed import preserves the previous cursor and committed items.
- A manual date-range import does not advance automatic state.
- Date boundaries and metric timestamps are interpreted in UTC.
- The launcher registers one job, reports its next execution, and starts the UI.
- Dashboard reads do not call GitHub, and updated data is visible after cache expiry.

Use a test token only when live API verification is needed. Never commit secrets, logs, virtual environments, or personal IDE settings. Review local SQLite files before inclusion; adding an ignore rule does not untrack an already tracked file.

## Pull requests

Explain the problem, resulting behavior, and validation actually performed. Mention operational changes such as Python requirements, database setup, schedule defaults, and history coverage. Link the relevant issue and distinguish incomplete work from resolved requirements.

Refer to [Synchronization and operations](docs/synchronization.md) for the current implementation's boundaries.
