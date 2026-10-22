import json
import pandas as pd
import streamlit as st

from src.job.help_db import select_github_items


@st.cache_data(
    ttl=900,
    show_spinner="Loading community metrics from SQLite...",
)
def fetch_raw_repo_data(repo_name: str):
    """
    Load repository items from SQLite and organize them
    into the structure expected by the dashboard.
    """
    rows = select_github_items(repo_name)

    issues_data = []
    pulls_data = []

    for row in rows:
        base_info = {
            "id": row["id"],
            "number": row["number"],
            "title": row["title"],
            "created_at": row["created_at"],
            "closed_at": row["closed_at"],
            "labels": json.loads(row["labels_json"] or "[]"),
            "assignee": row["assignee"],
            "author": row["author"] or "Unknown",
            "avatar_url": row["avatar_url"] or "https://github.com",
        }

        if row["item_type"] == "pull_request":
            base_info["merged_at"] = row["merged_at"]
            base_info["is_merged"] = bool(row["is_merged"])
            pulls_data.append(base_info)

        elif row["item_type"] == "issue":
            base_info["first_response_at"] = row["first_response_at"]
            issues_data.append(base_info)

    return {
        "issues": issues_data,
        "pulls": pulls_data,
    }


def calculate_community_health(repo_name: str):
    """
    Transforms raw dictionary arrays into structured DataFrames.
    Calculates key performance metrics: TTFR and TTM.
    """
    raw_data = fetch_raw_repo_data(repo_name)

    df_issues = pd.DataFrame(raw_data["issues"])
    df_pulls = pd.DataFrame(raw_data["pulls"])

    # --- Time-to-First-Response (TTFR) Calculation ---
    if not df_issues.empty:
        df_issues["created_at"] = pd.to_datetime(df_issues["created_at"], utc=True)
        df_issues["first_response_at"] = pd.to_datetime(
            df_issues["first_response_at"], utc=True
        )
        time_diff = df_issues["first_response_at"] - df_issues["created_at"]
        df_issues["ttfr_hours"] = time_diff.dt.total_seconds() / 3600
        avg_ttfr = df_issues["ttfr_hours"].mean()
    else:
        avg_ttfr = None

    # --- Time-to-Merge (TTM) Calculation ---
    if not df_pulls.empty:
        df_pulls["created_at"] = pd.to_datetime(df_pulls["created_at"], utc=True)
        df_pulls["merged_at"] = pd.to_datetime(df_pulls["merged_at"], utc=True)
        # E712 fix: checking boolean directly without '== True'
        merged_prs = df_pulls[df_pulls["is_merged"]].copy()
        time_diff_pr = merged_prs["merged_at"] - merged_prs["created_at"]
        merged_prs["ttm_hours"] = time_diff_pr.dt.total_seconds() / 3600
        avg_ttm = merged_prs["ttm_hours"].mean()
    else:
        avg_ttm = None

    return {
        "issues_df": df_issues,
        "pulls_df": df_pulls,
        "avg_ttfr_hours": avg_ttfr,
        "avg_ttm_hours": avg_ttm,
    }
