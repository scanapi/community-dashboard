from io import BytesIO
import streamlit as st
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from github_client import calculate_community_health
import plotly.express as px
from datetime import datetime, timedelta

# --- Layout Configuration ---
st.set_page_config(
    page_title="ScanAPI Community Dashboard",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🚀 ScanAPI Community Dashboard")
st.markdown("Monitor ecosystem contributions and project metrics.")
st.divider()

# --- Fetch Data Once ---
print("Starting community metrics calculation...", flush=True)
metrics = calculate_community_health("scanapi/scanapi")
print("Community metrics calculation completed.", flush=True)
df_issues = metrics["issues_df"]
df_pulls = metrics["pulls_df"]

# ---------------------------------------------------------
# 🏷️ DYNAMIC TAG DISCOVERY
# ---------------------------------------------------------
if not df_issues.empty and "labels" in df_issues.columns:
    all_extracted_labels = [
        label for sublist in df_issues["labels"] for label in sublist
    ]
    unique_labels = sorted(list(set(all_extracted_labels)))
else:
    unique_labels = []

# ---------------------------------------------------------
# 🎛️ SIDEBAR CONTROLS & FILTERING
# ---------------------------------------------------------
st.sidebar.header("🎯 Onboarding Filters")
st.sidebar.markdown("Narrow down beginner-friendly opportunities.")

difficulty_options = ["All Issues"]
for target_tag in ["good first issue", "help wanted"]:
    if target_tag in unique_labels:
        difficulty_options.append(target_tag)

beginner_filter = st.sidebar.radio(
    "Select Target Label:",
    options=difficulty_options,
    index=1 if len(difficulty_options) > 1 else 0,
)

technical_scope = st.sidebar.multiselect(
    "Filter by Technical Scope:",
    options=unique_labels,
    default=[],
    help="Select labels to match your skillset.",
)

if not df_issues.empty:
    filtered_df = df_issues.copy()

    # Apply Difficulty Filter
    if beginner_filter != "All Issues":
        filtered_df = filtered_df[
            filtered_df["labels"].apply(
                lambda tg: any(
                    beginner_filter.lower() == t.lower() for t in tg
                )
            )
        ]

    # Apply Technical Scope Filter
    if technical_scope:
        selected_scopes = [s.lower() for s in technical_scope]
        filtered_df = filtered_df[
            filtered_df["labels"].apply(
                lambda tg: any(
                    s in [t.lower() for t in tg] for s in selected_scopes
                )
            )
        ]
else:
    filtered_df = pd.DataFrame()

# --- Tab Layout ---
tab_onb, tab_lead, tab_trend, tab_market = st.tabs(
    ["📥 Onboarding Portal", "🏆 Leaderboard", "📈 Trends", "📱 Marketing"]
)

# ---------------------------------------------------------
# 📥 TAB 1: CONTRIBUTOR ONBOARDING HUB
# ---------------------------------------------------------
with tab_onb:
    st.header("Contributor Onboarding Hub")
    st.subheader("Lowering the barrier to entry")

    st.markdown("### 📊 Project Health & Responsiveness")
    col1, col2 = st.columns(2)

    with col1:
        ttfr = metrics["avg_ttfr_hours"]
        st.metric(
            label="⏱️ Avg Time-to-First-Response (TTFR)",
            value=f"{ttfr:.2f} hrs" if pd.notna(ttfr) else "N/A",
            # delta="Target: < 24h",
        )
    with col2:
        ttm = metrics["avg_ttm_hours"]
        st.metric(
            label="🚀 Avg Time-to-Merge (TTM)",
            value=f"{ttm:.2f} hrs" if pd.notna(ttm) else "N/A",
            # delta="Target: < 48h",
        )

    st.divider()

    st.markdown(f"### 🎯 Open Opportunities: `{beginner_filter}`")
    st.write(
        "Find outstanding tasks tailored for your skillset. "
        "Use the left sidebar to fine-tune lists."
    )

    if not filtered_df.empty:
        display_df = filtered_df[
            ["number", "title", "labels", "assignee", "created_at"]
        ]
        st.dataframe(display_df, use_container_width=True)
    else:
        st.info(
            "✨ No active open issues match your filters. "
            "Try broadening your sidebar selections!"
        )

# ---------------------------------------------------------
# 🏆 TAB 2: LEADERBOARD (Wall of Fame)
# ---------------------------------------------------------
with tab_lead:
    st.header("Wall of Fame")
    st.markdown(
        "Publicly acknowledging the most active developers "
        "within the ScanAPI ecosystem."
    )

    if not df_pulls.empty:
        # --- Interactive Controls Structure ---
        col_f1, col_f2, col_f3 = st.columns(3)

        with col_f1:
            metric_choice = st.selectbox(
                "Engagement Metric:",
                options=["Merged Pull Requests", "Active Contributions"],
                key="lead_metric",
            )
        with col_f2:
            time_filter = st.selectbox(
                "Leaderboard Timeframe:",
                options=["All Time", "Last 30 Days"],
                key="lead_time",
            )
        with col_f3:
            st.markdown(
                "<div style='padding-top: 28px;'></div>",
                unsafe_allow_html=True,
            )
            hide_bots = st.checkbox(
                "Hide Bot Accounts", value=True, key="lead_hide_bots"
            )

        # Clone dataframe safely
        df_lead = df_pulls.copy()

        # --- Exact Field Fallback Assignments ---
        # Ensures fields exist even if something went wrong during parsing
        if "author" not in df_lead.columns:
            df_lead["author"] = df_lead.get("assignee", "Unknown Contributor")
        if "avatar_url" not in df_lead.columns:
            df_lead["avatar_url"] = "https://github.com"

        # Force conversion to clean string representations
        df_lead["author"] = (
            df_lead["author"].fillna("Unknown Contributor").astype(str)
        )

        # --- Interactive Bot Exclusions Filter Logic ---
        if hide_bots:
            df_lead = df_lead[
                ~df_lead["author"].str.contains(
                    r"\[bot\]", case=False, na=False
                )
            ]
            bot_list = [
                "dependabot",
                "github-actions",
                "greenkeeper",
                "snyk-bot",
            ]
            df_lead = df_lead[~df_lead["author"].str.lower().isin(bot_list)]

        # --- Timeframe Filter Logic (With Timezone Safety) ---
        if time_filter == "Last 30 Days" and "created_at" in df_lead.columns:
            df_lead["created_at"] = pd.to_datetime(
                df_lead["created_at"], errors="coerce"
            )
            df_lead = df_lead.dropna(subset=["created_at"])

            if df_lead["created_at"].dt.tz is not None:
                df_lead["created_at"] = df_lead["created_at"].dt.tz_localize(
                    None
                )

            cutoff = datetime.utcnow() - timedelta(days=30)
            df_lead = df_lead[df_lead["created_at"] >= cutoff]

        # Group and rank metrics by true PR Author
        if not df_lead.empty:
            leaderboard_df = (
                df_lead.groupby(["author", "avatar_url"])
                .size()
                .reset_index(name="Volume")
                .sort_values(by="Volume", ascending=False)
                .reset_index(drop=True)
            )
        else:
            leaderboard_df = pd.DataFrame()

        # --- Dynamic Dashboard Visual Matrix Layout ---
        if not leaderboard_df.empty:
            st.markdown("### 🥇 Top Tier Contributors")
            # --- Dynamic Caption Evaluation ---
            if time_filter == "Last 30 Days":
                caption_text = (
                    "💡 Metrics reflect ecosystem contributions "
                    "over the last 30 days."
                )
            else:
                caption_text = (
                    "💡 Metrics reflect ecosystem contributions over a "
                    "rolling 100-day window."
                )

            st.caption(caption_text)
            # --- Dynamic Dashboard Visual Matrix Layout ---

            grid_cols = st.columns(4)
            for index, row in leaderboard_df.iterrows():
                col_idx = index % 4

                # Render clean avatar fallback string configurations
                avatar = (
                    row["avatar_url"]
                    if pd.notnull(row["avatar_url"])
                    else "https://github.com"
                )

                with grid_cols[col_idx]:
                    with st.container(border=True):
                        st.markdown(
                            f"""
                            <div style="text-align: center;">
                                <img src="{avatar}" style="
                                    border-radius: 50%;
                                    width: 85px;
                                    height: 85px;
                                    object-fit: cover;
                                    border: 3px solid #38bdf8;
                                ">
                                <h4 style="
                                    margin-top: 10px;
                                    margin-bottom: 5px;
                                    white-space: nowrap;
                                    overflow: hidden;
                                    text-overflow: ellipsis;
                                ">
                                    #{index + 1} {row['author']}
                                </h4>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                        st.metric(
                            label=metric_choice, value=int(row["Volume"])
                        )
        else:
            st.info(
                "✨ No active contributions match your selected "
                "metrics timeframe filters."
            )
    else:
        st.warning(
            "⚠️ Baseline Pull Requests data telemetry is missing or empty."
        )


# ---------------------------------------------------------
# 📈 TAB 3: TREND ANALYSIS & OPERATIONAL BOTTLENECKS
# ---------------------------------------------------------
with tab_trend:
    st.header("Issue Trend Analysis")
    st.subheader("Macroscopic view of project progression")

    if not df_issues.empty:
        # Clone raw data to avoid mutations
        df_trends = df_issues.copy()

        # Ensure datetime parsing is active
        df_trends["created_at"] = pd.to_datetime(df_trends["created_at"])
        df_trends["closed_at"] = pd.to_datetime(df_trends["closed_at"])

        # 🎛️ TIME-RANGE SIDEBAR CONTROL Extension
        st.sidebar.markdown("---")
        st.sidebar.header("📈 Historical Scope")

        time_window = st.sidebar.selectbox(
            "Select Time Frame:",
            options=[
                "Last 30 Days",
                "Last 60 Days",
                "Last 90 Days",
                "All Retrieved (Recent 100)",
            ],
            index=3,
        )

        # Apply Time Range Filters using explicit delta offsets
        now = datetime.now(df_trends["created_at"].dt.tz)
        if time_window == "Last 30 Days":
            cutoff = now - timedelta(days=30)
            df_trends = df_trends[df_trends["created_at"] >= cutoff]
        elif time_window == "Last 60 Days":
            cutoff = now - timedelta(days=60)
            df_trends = df_trends[df_trends["created_at"] >= cutoff]
        elif time_window == "Last 90 Days":
            cutoff = now - timedelta(days=90)
            df_trends = df_trends[df_trends["created_at"] >= cutoff]
        elif time_window == "All Retrieved (Recent 100)":
            pass  # No filtering needed

        # --- SECTION 1: CUMULATIVE VOLUMES (TREND ANALYSIS) ---
        st.markdown("### 📊 Cumulative Issues Volumetrics")
        # Updated description helper note
        st.write(
            f"Historical projection matching data window: `{time_window}`"
        )
        # Sort dates to build timeline
        df_trends = df_trends.sort_values("created_at")
        df_trends["date_only"] = df_trends["created_at"].dt.date

        # Compute arrival totals
        created_daily = (
            df_trends.groupby("date_only").size().reset_index(name="Opened")
        )
        created_daily["Cumulative Opened"] = created_daily["Opened"].cumsum()
        fig_cum = px.area(
            created_daily,
            x="date_only",
            y="Cumulative Opened",
            title=f"Ecosystem Growth Tracking ({time_window})",
            labels={
                "date_only": "Timeline",
                "Cumulative Opened": "Total Issues Created",
            },
            template="plotly_dark",
        )
        st.plotly_chart(fig_cum, use_container_width=True)

        st.divider()

        # --- SECTION 2: BOTTLENECK IDENTIFICATION BY TAGS ---
        st.markdown("### 🏷️ Workload Bottleneck Analysis")
        st.write("Breakdown of task volume by community label types.")

        # Explode tags out to analyze categorical density
        df_exploded = df_trends.explode("labels")

        if not df_exploded.empty and df_exploded["labels"].notna().any():
            tag_counts = (
                df_exploded.groupby("labels")
                .size()
                .reset_index(name="Issue Count")
                .sort_values(by="Issue Count", ascending=False)
            )

            # Generate horizontal bar plot to analyze tag backlogs
            fig_tags = px.bar(
                tag_counts,
                x="Issue Count",
                y="labels",
                orientation="h",
                title="Density Distribution of Active Labels",
                labels={
                    "labels": "Repository Tag",
                    "Issue Count": "Volume",
                },
                color="Issue Count",
                color_continuous_scale="Blues",
                template="plotly_dark",
            )
            fig_tags.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig_tags, use_container_width=True)
        else:
            st.info("No categorical tags detected within this range.")

    else:
        st.info("No baseline issue data found to chart trend analysis logs.")

# ---------------------------------------------------------
# 📱 TAB 4: MARKETING & SOCIAL MEDIA ASSETS
# ---------------------------------------------------------
with tab_market:
    st.header("Social Media Assets & Advocacy Hub")
    st.subheader("Amplify community wins instantly")

    st.markdown("### 📝 Weekly Progress Snippet")
    st.write("Copy this data-driven summary to share your project momentum.")

    if not df_pulls.empty:
        total_prs = len(df_pulls)
        has_asg = "assignee" in df_pulls.columns
        unique_authors = df_pulls["assignee"].nunique() if has_asg else 1
        if unique_authors == 0:
            unique_authors = 1
    else:
        total_prs = 0
        unique_authors = 0

    marketing_text = (
        f"🔥 Huge shoutout to the ScanAPI ecosystem!\n\n"
        f"This week, our community successfully merged {total_prs} "
        f"Pull Requests driven by {unique_authors} unique authors! 🚀"
        f"\n\nCheck out our performance metrics and contribute: "
        f"https://github.com ✨"
    )

    st.text_area(
        label="Generated Social Post Summary:",
        value=marketing_text,
        height=180,
        help="Click the copy icon in the upper right corner to copy.",
    )

    st.divider()

    st.markdown("### 🎨 Dynamic Contributor Card Generator")
    st.write(
        "Generate custom-branded milestone graphics to celebrate "
        "outstanding contributors."
    )

    c_handle = st.text_input(
        "Enter Contributor GitHub Username:", "developer_name"
    )
    milestone_text = st.text_input(
        "Enter Achievement Milestone:", "Core optimization!"
    )

    if st.button("Generate Branded Milestone Card"):
        card_w, card_h = 800, 400
        scanapi_dark = (15, 23, 42)
        scanapi_electric = (56, 189, 248)
        white = (255, 255, 255)

        img = Image.new("RGB", (card_w, card_h), color=scanapi_dark)
        draw = ImageDraw.Draw(img)
        draw.rectangle([(0, 0), (card_w, 15)], fill=scanapi_electric)

        font_title = ImageFont.load_default()

        draw.text(
            (50, 60), "ScanAPI Community Milestone", fill=scanapi_electric
        )
        draw.text((50, 120), f"🎉 Congratulations, @{c_handle}!", fill=white)
        draw.text((50, 180), f"Contribution: {milestone_text}", fill=white)
        draw.text(
            (50, 330),
            "Powered by ScanAPI Dashboard 🚀",
            fill=(100, 116, 139),
        )

        buf = BytesIO()
        img.save(buf, format="PNG")
        byte_im = buf.getvalue()

        st.image(
            img, caption="Preview Generated Card", use_container_width=True
        )

        st.download_button(
            label="📥 Download Milestone Card (.png)",
            data=byte_im,
            file_name=f"scanapi_milestone_{c_handle}.png",
            mime="image/png",
        )

st.sidebar.markdown("---")
st.sidebar.markdown("💡 [ScanAPI Repo](https://github.com)")
