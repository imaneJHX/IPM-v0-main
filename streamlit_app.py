"""IPM Flow real-time dashboard.

This Streamlit app uses sample data so it can run locally or on Streamlit
Community Cloud before the backend integration is connected.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from random import Random

import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_autorefresh import st_autorefresh


# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="IPM Flow Real-Time Dashboard",
    page_icon="📊",
    layout="wide",
)


# Refresh the dashboard every few seconds to simulate a real-time monitor.
REFRESH_INTERVAL_MS = 6_000
refresh_count = st_autorefresh(
    interval=REFRESH_INTERVAL_MS,
    key="ipm_flow_dashboard_refresh",
)


# ---------------------------------------------------------------------------
# Sample data generation
# ---------------------------------------------------------------------------
@st.cache_data(ttl=5)
def load_sample_initiatives(refresh_tick: int) -> pd.DataFrame:
    """Create realistic fake innovation initiatives for the dashboard.

    The refresh tick slightly changes scores and timestamps to make the
    dashboard feel live while remaining stable enough for report screenshots.
    """

    rng = Random(42 + refresh_tick)
    now = datetime.now()

    initiatives = [
        {
            "Initiative ID": "IPM-001",
            "Title": "AI Opportunity Radar for New Product Ideas",
            "Phase": "Sourcing",
            "Stage Gate": "GO",
            "Base IVI": 4.4,
            "Risk Level": "Low",
            "Recommendation Status": "Recommended for qualification",
        },
        {
            "Initiative ID": "IPM-002",
            "Title": "Semantic Search for Internal Knowledge Reuse",
            "Phase": "Qualification",
            "Stage Gate": "GO",
            "Base IVI": 4.7,
            "Risk Level": "Medium",
            "Recommendation Status": "Prioritize PoC scoping",
        },
        {
            "Initiative ID": "IPM-003",
            "Title": "RAG Assistant for Technical Feasibility Analysis",
            "Phase": "Delivery",
            "Stage Gate": "GO",
            "Base IVI": 4.5,
            "Risk Level": "Medium",
            "Recommendation Status": "Prepare PoC dossier",
        },
        {
            "Initiative ID": "IPM-004",
            "Title": "Automated IVI Scoring from Need Descriptions",
            "Phase": "Qualification",
            "Stage Gate": "REWORK",
            "Base IVI": 3.6,
            "Risk Level": "High",
            "Recommendation Status": "Clarify expected business value",
        },
        {
            "Initiative ID": "IPM-005",
            "Title": "Risk Signal Detection for Innovation Portfolios",
            "Phase": "Sourcing",
            "Stage Gate": "REWORK",
            "Base IVI": 3.2,
            "Risk Level": "Medium",
            "Recommendation Status": "Request additional context",
        },
        {
            "Initiative ID": "IPM-006",
            "Title": "Stage Gate Decision Support Workflow",
            "Phase": "Delivery",
            "Stage Gate": "GO",
            "Base IVI": 4.1,
            "Risk Level": "Low",
            "Recommendation Status": "Validate with pilot users",
        },
        {
            "Initiative ID": "IPM-007",
            "Title": "NLP Tagging for Strategic Need Classification",
            "Phase": "Qualification",
            "Stage Gate": "GO",
            "Base IVI": 4.0,
            "Risk Level": "Low",
            "Recommendation Status": "Continue assessment",
        },
        {
            "Initiative ID": "IPM-008",
            "Title": "Legacy Process Automation Candidate",
            "Phase": "Sourcing",
            "Stage Gate": "ABANDON",
            "Base IVI": 2.1,
            "Risk Level": "High",
            "Recommendation Status": "Not aligned with innovation scope",
        },
        {
            "Initiative ID": "IPM-009",
            "Title": "PoC Dossier Generator for Business Sponsors",
            "Phase": "Delivery",
            "Stage Gate": "GO",
            "Base IVI": 4.8,
            "Risk Level": "Medium",
            "Recommendation Status": "Finalize delivery evidence",
        },
        {
            "Initiative ID": "IPM-010",
            "Title": "Market Trend Matching with Semantic Embeddings",
            "Phase": "Sourcing",
            "Stage Gate": "GO",
            "Base IVI": 3.9,
            "Risk Level": "Low",
            "Recommendation Status": "Recommended for qualification",
        },
        {
            "Initiative ID": "IPM-011",
            "Title": "Cross-Domain Similar Initiative Finder",
            "Phase": "Qualification",
            "Stage Gate": "REWORK",
            "Base IVI": 3.4,
            "Risk Level": "High",
            "Recommendation Status": "Improve data source coverage",
        },
        {
            "Initiative ID": "IPM-012",
            "Title": "Executive Innovation Portfolio Summary",
            "Phase": "Delivery",
            "Stage Gate": "GO",
            "Base IVI": 4.2,
            "Risk Level": "Low",
            "Recommendation Status": "Ready for steering committee",
        },
    ]

    rows = []
    for index, initiative in enumerate(initiatives):
        # Keep IVI scores in the required 1-5 range while simulating updates.
        score_delta = rng.uniform(-0.12, 0.12)
        ivi_score = max(1.0, min(5.0, initiative.pop("Base IVI") + score_delta))

        rows.append(
            {
                **initiative,
                "IVI Score": round(ivi_score, 2),
                "Last Update": (now - timedelta(minutes=5 * index + rng.randint(0, 4))).strftime(
                    "%Y-%m-%d %H:%M"
                ),
            }
        )

    return pd.DataFrame(rows)


df = load_sample_initiatives(refresh_count)


# ---------------------------------------------------------------------------
# Visual theme helpers
# ---------------------------------------------------------------------------
PHASE_ORDER = ["Sourcing", "Qualification", "Delivery"]
STAGE_GATE_ORDER = ["GO", "REWORK", "ABANDON"]
RISK_ORDER = ["Low", "Medium", "High"]

PHASE_COLORS = {
    "Sourcing": "#2563EB",
    "Qualification": "#7C3AED",
    "Delivery": "#059669",
}
STAGE_GATE_COLORS = {
    "GO": "#059669",
    "REWORK": "#D97706",
    "ABANDON": "#DC2626",
}
RISK_COLORS = {
    "Low": "#16A34A",
    "Medium": "#F59E0B",
    "High": "#DC2626",
}


def style_plotly_figure(fig):
    """Apply a consistent clean layout to Plotly charts."""

    fig.update_layout(
        template="plotly_white",
        margin=dict(l=20, r=20, t=45, b=20),
        legend_title_text="",
        font=dict(size=13),
    )
    return fig


# ---------------------------------------------------------------------------
# Header and live status
# ---------------------------------------------------------------------------
st.title("📊 IPM Flow Real-Time Dashboard")
st.caption(
    "Monitoring innovation initiatives across Sourcing, Qualification, and Delivery, "
    "with Stage Gate decisions, IVI scoring, risk visibility, recommendations, "
    "and PoC preparation status."
)

status_col, refresh_col = st.columns([3, 1])
with status_col:
    st.info("Live sample data is refreshed automatically every few seconds.")
with refresh_col:
    st.metric("Last refresh", datetime.now().strftime("%H:%M:%S"))


# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
st.sidebar.header("🔎 Dashboard Filters")
selected_phases = st.sidebar.multiselect(
    "Phase",
    options=PHASE_ORDER,
    default=PHASE_ORDER,
)
selected_stage_gates = st.sidebar.multiselect(
    "Stage Gate status",
    options=STAGE_GATE_ORDER,
    default=STAGE_GATE_ORDER,
)
selected_risks = st.sidebar.multiselect(
    "Risk level",
    options=RISK_ORDER,
    default=RISK_ORDER,
)

filtered_df = df[
    df["Phase"].isin(selected_phases)
    & df["Stage Gate"].isin(selected_stage_gates)
    & df["Risk Level"].isin(selected_risks)
].copy()


# ---------------------------------------------------------------------------
# KPI cards
# ---------------------------------------------------------------------------
st.subheader("🎯 Portfolio KPIs")

total_initiatives = len(filtered_df)
sourcing_count = int((filtered_df["Phase"] == "Sourcing").sum())
qualification_count = int((filtered_df["Phase"] == "Qualification").sum())
delivery_count = int((filtered_df["Phase"] == "Delivery").sum())
average_ivi = filtered_df["IVI Score"].mean() if total_initiatives else 0
high_risk_count = int((filtered_df["Risk Level"] == "High").sum())

kpi_cols = st.columns(6)
kpi_cols[0].metric("Total initiatives", total_initiatives)
kpi_cols[1].metric("Sourcing", sourcing_count)
kpi_cols[2].metric("Qualification", qualification_count)
kpi_cols[3].metric("Delivery", delivery_count)
kpi_cols[4].metric("Average IVI", f"{average_ivi:.2f}/5")
kpi_cols[5].metric("High risk", high_risk_count)


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
st.subheader("📈 Initiative Monitoring Charts")

if filtered_df.empty:
    st.warning("No initiatives match the selected filters.")
else:
    chart_col_1, chart_col_2 = st.columns(2)

    with chart_col_1:
        phase_counts = (
            filtered_df["Phase"]
            .value_counts()
            .reindex(PHASE_ORDER, fill_value=0)
            .reset_index()
        )
        phase_counts.columns = ["Phase", "Initiatives"]
        phase_fig = px.bar(
            phase_counts,
            x="Phase",
            y="Initiatives",
            color="Phase",
            color_discrete_map=PHASE_COLORS,
            title="Initiatives by Phase",
            text="Initiatives",
        )
        phase_fig.update_traces(textposition="outside")
        st.plotly_chart(style_plotly_figure(phase_fig), use_container_width=True)

    with chart_col_2:
        stage_gate_counts = (
            filtered_df["Stage Gate"]
            .value_counts()
            .reindex(STAGE_GATE_ORDER, fill_value=0)
            .reset_index()
        )
        stage_gate_counts.columns = ["Stage Gate", "Initiatives"]
        stage_gate_fig = px.pie(
            stage_gate_counts,
            names="Stage Gate",
            values="Initiatives",
            title="Stage Gate Decision Distribution",
            color="Stage Gate",
            color_discrete_map=STAGE_GATE_COLORS,
            hole=0.45,
        )
        st.plotly_chart(style_plotly_figure(stage_gate_fig), use_container_width=True)

    chart_col_3, chart_col_4 = st.columns(2)

    with chart_col_3:
        ivi_fig = px.bar(
            filtered_df.sort_values("IVI Score", ascending=False),
            x="Initiative ID",
            y="IVI Score",
            color="Phase",
            color_discrete_map=PHASE_COLORS,
            title="IVI Score by Initiative",
            hover_data=["Title", "Risk Level", "Stage Gate"],
            range_y=[0, 5],
        )
        ivi_fig.update_layout(yaxis_title="IVI Score (1-5)")
        st.plotly_chart(style_plotly_figure(ivi_fig), use_container_width=True)

    with chart_col_4:
        risk_counts = (
            filtered_df["Risk Level"]
            .value_counts()
            .reindex(RISK_ORDER, fill_value=0)
            .reset_index()
        )
        risk_counts.columns = ["Risk Level", "Initiatives"]
        risk_fig = px.bar(
            risk_counts,
            x="Risk Level",
            y="Initiatives",
            color="Risk Level",
            color_discrete_map=RISK_COLORS,
            title="Risk Level Distribution",
            text="Initiatives",
        )
        risk_fig.update_traces(textposition="outside")
        st.plotly_chart(style_plotly_figure(risk_fig), use_container_width=True)


# ---------------------------------------------------------------------------
# Main monitoring table
# ---------------------------------------------------------------------------
st.subheader("🗂️ Main Innovation Initiative Monitoring Table")

display_columns = [
    "Initiative ID",
    "Title",
    "Phase",
    "Stage Gate",
    "IVI Score",
    "Risk Level",
    "Recommendation Status",
    "Last Update",
]

st.dataframe(
    filtered_df[display_columns],
    use_container_width=True,
    hide_index=True,
    column_config={
        "IVI Score": st.column_config.ProgressColumn(
            "IVI Score",
            help="Innovation Value Index score from 1 to 5.",
            min_value=1,
            max_value=5,
            format="%.2f",
        ),
        "Last Update": st.column_config.TextColumn(
            "Last Update",
            help="Most recent sample update timestamp.",
        ),
    },
)


# ---------------------------------------------------------------------------
# Footer note for deployment and backend integration
# ---------------------------------------------------------------------------
st.caption(
    "Prototype dashboard using sample data. For production, replace the sample "
    "data loader with API calls to the IPM Flow backend."
)
