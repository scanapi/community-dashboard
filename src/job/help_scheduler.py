import argparse
import logging
import os
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_START_DATE = date(2025, 1, 1)
DEFAULT_REPOSITORY = "scanapi/scanapi"

logger = logging.getLogger(__name__)


def parse_date(value):
    """Parse a calendar date in YYYY-MM-DD format."""
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "Use a valid date in YYYY-MM-DD format."
        ) from error


def configure_logging():
    """Configure logging for standalone command-line execution."""
    logs_dir = PROJECT_ROOT / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    log_file = logs_dir / f"sync_{datetime.now():%Y-%m-%d}.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def import_issues_daily(
        repository=DEFAULT_REPOSITORY,
        start_date=DEFAULT_START_DATE,
        end_date=None,
):
    """
    Import repository items one UTC calendar day at a time.

    Default range: January 1, 2025 through the current instant.
    The optional end date is inclusive.

    Stop on the first failed day and propagate the exception.
    Return the total number of processed items.
    """
    from src.job.github_async import synchronize_repository

    execution_time = datetime.now(timezone.utc)
    today = execution_time.date()

    if end_date is not None and end_date < start_date:
        raise ValueError("The end date must not precede the start date.")

    if start_date > today:
        raise ValueError("The start date must not be in the future.")

    # Keep the execution range fixed while processing all days.
    last_date = min(end_date, today) if end_date else today

    total_days = (last_date - start_date).days + 1
    completed_days = 0
    total_items = 0
    current_date = start_date

    logger.info(
        "Daily import started: repository=%s, start=%s, end=%s, days=%s",
        repository,
        start_date,
        last_date,
        total_days,
    )

    while current_date <= last_date:
        start_at = datetime.combine(
            current_date,
            time.min,
            tzinfo=timezone.utc,
        )

        # Use a half-open interval: [start_at, end_before).
        end_before = min(
            start_at + timedelta(days=1),
            execution_time,
            )

        # At exactly midnight, the current day has no elapsed interval.
        if start_at >= end_before:
            break

        logger.info(
            "Importing day %s/%s: repository=%s, start=%s, end_exclusive=%s",
            completed_days + 1,
            total_days,
            repository,
            start_at.isoformat(),
            end_before.isoformat(),
            )

        try:
            processed_items = synchronize_repository(
                repo_name=repository,
                start_at=start_at,
                end_before=end_before,
            )
        except Exception:
            logger.exception(
                "Daily import failed: repository=%s, failed_date=%s, "
                "completed_days=%s, processed_items=%s",
                repository,
                current_date,
                completed_days,
                total_items,
            )
            raise

        completed_days += 1
        total_items += processed_items

        logger.info(
            "Day completed: date=%s, items=%s, total_items=%s",
            current_date,
            processed_items,
            total_items,
        )

        current_date += timedelta(days=1)

    logger.info(
        "Daily import completed: repository=%s, days=%s, items=%s",
        repository,
        completed_days,
        total_items,
    )

    return total_items


def main():
    parser = argparse.ArgumentParser(
        description="Import GitHub repository items day by day into SQLite."
    )

    parser.add_argument(
        "--repository",
        default=DEFAULT_REPOSITORY,
        help="GitHub repository in owner/name format.",
    )

    parser.add_argument(
        "--start-date",
        type=parse_date,
        default=DEFAULT_START_DATE,
        help="First update date in UTC. Defaults to 2025-01-01.",
    )

    parser.add_argument(
        "--end-date",
        type=parse_date,
        default=None,
        help=(
            "Last update date to include, in UTC (YYYY-MM-DD). "
            "Defaults to the current instant."
        ),
    )

    args = parser.parse_args()

    # Resolve Streamlit secrets relative to the project root.
    os.chdir(PROJECT_ROOT)
    configure_logging()

    try:
        import_issues_daily(
            repository=args.repository,
            start_date=args.start_date,
            end_date=args.end_date,
        )
        return 0

    except Exception:
        logger.exception(
            "Synchronization job failed: %s",
            args.repository,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())