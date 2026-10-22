from contextlib import closing
import sqlite3
from github import Github
import streamlit as st
from datetime import timedelta
from src.job.help_db import DB_PATH, save_github_item, start_sync, finish_sync, fail_sync
import logging


def get_github_client():
    """
    Fetches the token from secrets.toml and initializes
    the GitHub client. Streamlit automatically searches
    within .streamlit/secrets.toml.
    """
    token = st.secrets.get("GITHUB_TOKEN", None)
    if token:
        return Github(token)
    # Fallback to unauthenticated client (lower rate limits)
    return Github()

logger = logging.getLogger(__name__)

def synchronize_repository(
        repo_name,
        start_at=None,
        end_before=None,
):
    """Synchronize a manual interval or resume from the stored cursor."""
    if start_at is not None:
        if end_before is None or start_at >= end_before:
            raise ValueError(
                "A valid exclusive end timestamp is required."
            )

        # Manual imports must not advance the automatic cursor.
        return sync_repo_data(
            repo_name=repo_name,
            since=start_at,
            end_before=end_before,
        )

    if end_before is not None:
        raise ValueError(
            "An end timestamp requires a start timestamp."
        )

    started_at, since = start_sync(repo_name)

    logger.info(
        "Automatic synchronization started: "
        "repository=%s, since=%s, end_exclusive=%s",
        repo_name,
        since.isoformat(),
        started_at.isoformat(),
    )

    try:
        total = sync_repo_data(
            repo_name=repo_name,
            since=since,
            end_before=started_at,
        )

        # Advance the cursor only after all items have been committed.
        finish_sync(repo_name, started_at)

    except Exception as error:
        fail_sync(repo_name, error)
        raise

    logger.info(
        "Automatic synchronization completed: repository=%s, items=%s",
        repo_name,
        total,
    )

    return total

def sync_repo_data(
        repo_name: str,
        since=None,
        end_before=None,
):
    """
    Search date on GitHub and store at SQLite
    Busca dados no GitHub e grava no SQLite.

    since=None: full data payload
    since=datetime UTC: payload items updated only at this day.

    Returns qtd updated items.
    """
    g = get_github_client()

    try:
        repo = g.get_repo(repo_name)

        filters = {
            "state": "all",
            "sort": "updated",
            "direction": "asc",
        }

        if since is not None:
            # Request a small overlap to include the exact lower boundary.
            filters["since"] = since - timedelta(seconds=1)

        processed = 0

        with closing(
                sqlite3.connect(DB_PATH, timeout=30)
        ) as conn:
            for issue in repo.get_issues(**filters):
                updated_at = issue.updated_at

                # Include the lower boundary.
                if since is not None and updated_at < since:
                    continue

                # Exclude the upper boundary.
                if end_before is not None and updated_at >= end_before:
                    continue

                base_info = {
                    "id": issue.id,
                    "number": issue.number,
                    "title": issue.title,
                    "created_at": issue.created_at,
                    "closed_at": issue.closed_at,
                    "labels": [
                        label.name for label in issue.labels
                    ],
                    "assignee": (
                        issue.assignee.login
                        if issue.assignee
                        else None
                    ),
                    "author": (
                        issue.user.login
                        if issue.user
                        else "Unknown"
                    ),
                    "avatar_url": (
                        issue.user.avatar_url
                        if issue.user
                        else "https://github.com"
                    ),
                }

                if issue.pull_request:
                    pr = repo.get_pull(issue.number)

                    base_info["merged_at"] = pr.merged_at
                    base_info["is_merged"] = pr.merged

                else:
                    first_comment = next(
                        iter(issue.get_comments()), None
                    )

                    base_info["first_response_at"] = (
                        first_comment.created_at
                        if first_comment
                        else None
                    )

                save_github_item(
                    conn, repo_name, issue, base_info
                )

                processed += 1

        return processed

    finally:
        g.close()