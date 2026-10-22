import logging
import os
import subprocess
import sys
import tomllib
from logging.handlers import RotatingFileHandler
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger


SOURCE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SOURCE_DIR.parent

# Keep the configuration file in its current location.
CONFIG_PATH = SOURCE_DIR / "scheduler.toml"

# Support direct execution with: python src/run_app.py.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)


def configure_logging():
    """Configure console output and rotating log files."""
    logs_dir = PROJECT_ROOT / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.StreamHandler(),
            RotatingFileHandler(
                logs_dir / "scheduler.log",
                maxBytes=5_000_000,
                backupCount=5,
                encoding="utf-8",
                ),
        ],
    )


def execute_sync(repository):
    """Synchronize repository updates using the persisted cursor."""
    from src.job.github_async import synchronize_repository

    logger.info("Scheduled synchronization started: %s", repository)

    try:
        total = synchronize_repository(repo_name=repository)
    except Exception:
        logger.exception(
            "Scheduled synchronization failed: %s",
            repository,
        )
        raise

    logger.info(
        "Scheduled synchronization completed: repository=%s, items=%s",
        repository,
        total,
    )

def main():
    # Resolve relative configuration paths from the project root.
    os.chdir(PROJECT_ROOT)
    configure_logging()

    with CONFIG_PATH.open("rb") as config_file:
        settings = tomllib.load(config_file)["scheduler"]

    scheduler = None

    try:
        if settings.get("enabled", True):
            scheduler = BackgroundScheduler(
                timezone=settings["timezone"],
            )

            scheduler.add_job(
                execute_sync,
                trigger=CronTrigger.from_crontab(
                    settings["cron"],
                    timezone=settings["timezone"],
                ),
                kwargs={
                    "repository": settings["repository"],
                },
                id="github_repository_sync",
                replace_existing=True,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=settings.get(
                    "misfire_grace_time", 3600
                ),
            )

            scheduler.start()

            job = scheduler.get_job("github_repository_sync")

            logger.info(
                "Scheduler started. Next execution: %s",
                job.next_run_time,
            )

        # Make the project package available to the Streamlit subprocess.
        child_env = os.environ.copy()
        existing_pythonpath = child_env.get("PYTHONPATH")

        child_env["PYTHONPATH"] = str(PROJECT_ROOT)

        if existing_pythonpath:
            child_env["PYTHONPATH"] += (
                    os.pathsep + existing_pythonpath
            )

        # Start Streamlit from the project root.
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                str(SOURCE_DIR / "app.py"),
            ],
            cwd=PROJECT_ROOT,
            env=child_env,
            check=False,
        )

        return result.returncode

    except KeyboardInterrupt:
        logger.info("Application shutdown requested.")
        return 0

    finally:
        if scheduler is not None and scheduler.running:
            # Allow an active synchronization to finish before exiting.
            scheduler.shutdown(wait=True)


if __name__ == "__main__":
    raise SystemExit(main())