"""Streamlit dashboard for business needs progress tracking.

This Streamlit app connects to the IPM FastAPI backend when IPM_API_URL is set.
Sample data remains available as a fallback for demos and disconnected deploys.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from html import escape
import json
import os
from pathlib import Path
from random import Random
import tomllib
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from streamlit_autorefresh import st_autorefresh


PROJECT_ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class AppConfig:
    """Runtime configuration for local and Streamlit Cloud deployments."""

    api_url: str
    source: str

    @property
    def has_backend(self) -> bool:
        return bool(self.api_url)


def load_local_env() -> None:
    """Load simple KEY=VALUE pairs from .env for local Streamlit runs.

    Streamlit Community Cloud should use app secrets instead. The real .env file
    is ignored by Git, so this is safe for local developer machines.
    """

    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def read_toml_secret(name: str) -> str:
    """Read a root-level Streamlit secret without touching st.secrets.

    Accessing st.secrets when no secrets are configured can render "No secrets
    found" in the app. Reading the optional TOML files directly keeps missing
    secrets quiet while still supporting local .streamlit/secrets.toml and the
    standard user-level Streamlit secrets location.
    """

    secret_paths = [
        PROJECT_ROOT / ".streamlit" / "secrets.toml",
        Path.home() / ".streamlit" / "secrets.toml",
    ]
    for secret_path in secret_paths:
        if not secret_path.exists():
            continue
        try:
            payload = tomllib.loads(secret_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        value = payload.get(name, "")
        if value:
            return str(value).strip()
    return ""


def get_config_value(name: str) -> tuple[str, str]:
    """Read config from environment first, then optional secrets.toml files."""

    env_value = os.getenv(name, "").strip()
    if env_value:
        return env_value, "environment"

    secret_value = read_toml_secret(name)
    if secret_value:
        return secret_value, "secrets.toml"

    return "", "demo"


def load_app_config() -> AppConfig:
    """Build app config for local development and Streamlit Community Cloud."""

    api_url, source = get_config_value("IPM_API_URL")
    return AppConfig(api_url=api_url.rstrip("/"), source=source)


load_local_env()
APP_CONFIG = load_app_config()


# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Streamlit Dashboard — Business Needs Progress Tracking",
    page_icon="IPM",
    layout="wide",
)


# Refresh the dashboard every few seconds to simulate a real-time monitor.
REFRESH_INTERVAL_MS = 6_000
refresh_count = st_autorefresh(
    interval=REFRESH_INTERVAL_MS,
    key="ipm_flow_dashboard_refresh",
)


# ---------------------------------------------------------------------------
# Enterprise visual styling
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
        :root {
            --ipm-bg: #F7F7FA;
            --ipm-panel: #ffffff;
            --ipm-text: #1F2937;
            --ipm-muted: #6b7280;
            --ipm-border: #e6e8ef;
            --ipm-blue: #6C8CFF;
            --ipm-violet: #7B7FF6;
            --ipm-purple: #8B5CF6;
            --ipm-green: #10B981;
            --ipm-orange: #FF7A45;
            --ipm-red: #EF4444;
            --ipm-sidebar: #172033;
        }

        .stApp {
            background:
                linear-gradient(135deg, rgba(255, 122, 69, 0.08), rgba(108, 140, 255, 0.07) 34%, transparent 58%),
                linear-gradient(180deg, #ffffff 0%, var(--ipm-bg) 52%, #f0f2f8 100%);
            color: var(--ipm-text);
            font-family: "Inter", "Segoe UI", Arial, sans-serif;
        }

        .main .block-container {
            padding-top: 1.75rem;
            padding-bottom: 2rem;
            max-width: 1480px;
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #172033 0%, #1f2937 62%, #20243a 100%);
            border-right: 1px solid rgba(255, 255, 255, 0.10);
        }

        [data-testid="stSidebar"] * {
            color: #f9fafb;
        }

        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] .stMarkdown p {
            color: #d7dbea !important;
        }

        [data-testid="stSidebar"] [data-baseweb="select"] > div {
            background-color: rgba(255, 255, 255, 0.10);
            border-color: rgba(255, 255, 255, 0.20);
            border-radius: 0.75rem;
        }

        [data-testid="stSidebar"] [data-baseweb="tag"] {
            background: linear-gradient(135deg, #FF7A45, #6C8CFF);
            border-radius: 999px;
        }

        [data-testid="stMetric"] {
            background: transparent;
        }

        .ipm-sidebar-brand {
            padding: 1.25rem 0 1rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.12);
            margin-bottom: 1.25rem;
            position: relative;
        }

        .ipm-sidebar-brand:after {
            content: "";
            position: absolute;
            bottom: -1px;
            left: 0;
            width: 4.75rem;
            height: 2px;
            background: linear-gradient(90deg, #FF7A45, #6C8CFF);
        }

        .ipm-sidebar-title {
            font-size: 1.45rem;
            font-weight: 800;
            letter-spacing: 0;
            line-height: 1.1;
        }

        .ipm-sidebar-subtitle {
            margin-top: 0.35rem;
            color: #FFB08C;
            font-size: 0.82rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }

        .ipm-sidebar-caption {
            margin-top: 0.55rem;
            color: #cdd7ff;
            font-size: 0.9rem;
            line-height: 1.45;
        }

        .ipm-hero {
            background:
                linear-gradient(135deg, #ffffff 0%, #ffffff 60%, rgba(108, 140, 255, 0.10) 100%);
            border: 1px solid rgba(230, 232, 239, 0.95);
            border-radius: 1.35rem;
            box-shadow: 0 18px 45px rgba(31, 41, 55, 0.10);
            color: var(--ipm-text);
            padding: 1.6rem 1.8rem;
            margin-bottom: 1.1rem;
            position: relative;
            overflow: hidden;
        }

        .ipm-hero:after {
            content: "";
            position: absolute;
            right: 0;
            bottom: 0;
            left: 0;
            height: 4px;
            background: linear-gradient(90deg, #FF7A45, #FF8A4C 28%, #7B7FF6 66%, #6C8CFF);
        }

        .ipm-badge {
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            background: linear-gradient(135deg, rgba(255, 122, 69, 0.12), rgba(108, 140, 255, 0.12));
            border: 1px solid rgba(108, 140, 255, 0.22);
            border-radius: 999px;
            color: #1F2937;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0;
            padding: 0.35rem 0.7rem;
            margin-bottom: 0.75rem;
        }

        .ipm-hero h1 {
            font-size: 2.15rem;
            font-weight: 800;
            letter-spacing: 0;
            margin: 0;
            line-height: 1.15;
        }

        .ipm-hero p {
            color: #5b6473;
            font-size: 1.02rem;
            margin: 0.65rem 0 0;
            max-width: 720px;
        }

        .ipm-live-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: rgba(255, 255, 255, 0.96);
            border: 1px solid var(--ipm-border);
            border-radius: 1rem;
            box-shadow: 0 12px 30px rgba(31, 41, 55, 0.06);
            padding: 0.85rem 1rem;
            margin-bottom: 1.35rem;
        }

        .ipm-live-label {
            color: var(--ipm-muted);
            font-size: 0.9rem;
        }

        .ipm-live-time {
            color: var(--ipm-orange);
            font-weight: 800;
            font-size: 1rem;
        }

        .ipm-section-title {
            margin: 1.25rem 0 0.75rem;
        }

        .ipm-section-title h2 {
            color: #1F2937;
            font-size: 1.18rem;
            font-weight: 800;
            letter-spacing: 0;
            margin: 0;
        }

        .ipm-section-title p {
            color: var(--ipm-muted);
            font-size: 0.92rem;
            margin: 0.2rem 0 0;
        }

        .ipm-kpi-card {
            background: #ffffff;
            border: 1px solid rgba(230, 232, 239, 0.98);
            border-top: 4px solid var(--accent);
            border-radius: 1.05rem;
            box-shadow: 0 14px 32px rgba(31, 41, 55, 0.07);
            min-height: 122px;
            padding: 1rem;
            position: relative;
            overflow: hidden;
        }

        .ipm-kpi-card:before {
            content: "";
            position: absolute;
            inset: 0 0 auto 0;
            height: 4px;
            background: linear-gradient(90deg, var(--accent), rgba(108, 140, 255, 0.55));
        }

        .ipm-kpi-label {
            color: var(--ipm-muted);
            font-size: 0.82rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }

        .ipm-kpi-value {
            color: #1F2937;
            font-size: 2rem;
            font-weight: 850;
            letter-spacing: 0;
            margin-top: 0.45rem;
            line-height: 1;
        }

        .ipm-kpi-note {
            color: var(--ipm-muted);
            font-size: 0.82rem;
            margin-top: 0.45rem;
        }

        .stPlotlyChart {
            background: #ffffff;
            border: 1px solid rgba(230, 232, 239, 0.98);
            border-radius: 1.1rem;
            box-shadow: 0 14px 32px rgba(31, 41, 55, 0.06);
            padding: 0.5rem;
        }

        [data-testid="stDataFrame"] {
            background: #ffffff;
            border: 1px solid var(--ipm-border);
            border-radius: 1rem;
            box-shadow: 0 14px 32px rgba(31, 41, 55, 0.06);
            padding: 0.35rem;
        }

        .ipm-activity-card {
            background: #ffffff;
            border: 1px solid rgba(230, 232, 239, 0.98);
            border-left: 4px solid var(--accent);
            border-radius: 1rem;
            box-shadow: 0 12px 28px rgba(31, 41, 55, 0.06);
            padding: 0.95rem 1rem;
            min-height: 128px;
        }

        .ipm-activity-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 0.7rem;
            margin-bottom: 0.5rem;
        }

        .ipm-activity-id {
            color: var(--ipm-violet);
            font-size: 0.8rem;
            font-weight: 800;
        }

        .ipm-pill {
            background: linear-gradient(135deg, rgba(255, 122, 69, 0.12), rgba(108, 140, 255, 0.12));
            color: var(--accent);
            border-radius: 999px;
            font-size: 0.72rem;
            font-weight: 800;
            padding: 0.2rem 0.55rem;
            white-space: nowrap;
        }

        .ipm-activity-title {
            color: #1F2937;
            font-size: 0.98rem;
            font-weight: 800;
            line-height: 1.25;
            margin-bottom: 0.55rem;
        }

        .ipm-activity-meta {
            color: var(--ipm-muted);
            font-size: 0.82rem;
            line-height: 1.45;
        }

        .ipm-footer {
            color: var(--ipm-muted);
            font-size: 0.85rem;
            margin-top: 1.4rem;
            padding: 0.8rem 0;
        }

        hr {
            border-color: rgba(229, 231, 235, 0.75);
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Backend integration and sample data generation
# ---------------------------------------------------------------------------
STATUS_TO_PHASE = {
    "draft": "Sourcing",
    "submitted": "Sourcing",
    "in_qualification": "Qualification",
    "in_selection": "Qualification",
    "delivery": "Delivery",
    "export_ready": "Delivery",
    "abandoned": "Sourcing",
}

STATUS_TO_GATE = {
    "draft": "REWORK",
    "submitted": "GO",
    "in_qualification": "GO",
    "in_selection": "GO",
    "delivery": "GO",
    "export_ready": "GO",
    "abandoned": "ABANDON",
}

STATUS_TO_RECOMMENDATION = {
    "draft": "Needs sourcing validation",
    "submitted": "Ready for qualification",
    "in_qualification": "Assessment in progress",
    "in_selection": "Ready for selection",
    "delivery": "Prepare delivery recommendations",
    "export_ready": "Ready for export",
    "abandoned": "Not active",
}

HORIZON_RISK = {
    "court_terme": "Medium",
    "moyen_terme": "Low",
    "long_terme": "Medium",
}

HORIZON_OPTIONS = {
    "Short term": "court_terme",
    "Medium term": "moyen_terme",
    "Long term": "long_terme",
}

DASHBOARD_COLUMNS = [
    "Initiative ID",
    "Title",
    "Phase",
    "Stage Gate",
    "IVI Score",
    "Risk Level",
    "Recommendation Status",
    "Last Update",
]


def get_default_api_url() -> str:
    """Return the configured backend URL, or blank when demo mode is active."""

    return APP_CONFIG.api_url


def make_api_url(base_url: str, path: str) -> str:
    """Build an API URL while accepting either root or /api/v1 base URLs."""

    normalized_base = base_url.rstrip("/")
    if normalized_base.endswith("/api/v1"):
        return f"{normalized_base}{path}"
    return f"{normalized_base}/api/v1{path}"


def api_json_request(url: str, method: str = "GET", payload: dict | None = None) -> object:
    """Call the backend with only standard-library HTTP support."""

    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        url,
        data=body,
        method=method,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=12) as response:
            response_body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{exc.code} {exc.reason}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(str(exc.reason)) from exc

    return json.loads(response_body) if response_body else {}


def score_need(row: dict) -> float:
    """Create a compact dashboard score from status, tags, and duplicate risk."""

    status_scores = {
        "draft": 2.5,
        "submitted": 3.2,
        "in_qualification": 3.7,
        "in_selection": 4.0,
        "delivery": 4.4,
        "export_ready": 4.7,
        "abandoned": 1.4,
    }
    score = status_scores.get(row.get("status"), 3.0)
    tags = row.get("tags") or {}
    if tags.get("horizon_conflict"):
        score -= 0.35
    if row.get("duplicate_matches"):
        score -= 0.2
    return round(max(1.0, min(5.0, score)), 2)


def risk_for_need(row: dict) -> str:
    """Estimate risk from current status, horizon, duplicate matches, and tag signals."""

    status = row.get("status")
    tags = row.get("tags") or {}
    if status == "abandoned":
        return "High"
    if tags.get("horizon_conflict") or row.get("duplicate_matches"):
        return "High"
    return HORIZON_RISK.get(row.get("horizon"), "Medium")


def need_title(pitch: str) -> str:
    """Use the first sentence as a readable dashboard title."""

    title = " ".join((pitch or "").strip().split())
    if not title:
        return "Untitled business need"
    first_sentence = title.split(".")[0]
    return first_sentence[:82] + ("..." if len(first_sentence) > 82 else "")


def needs_to_dashboard_rows(needs: list[dict]) -> pd.DataFrame:
    """Map backend BusinessNeedResponse objects into dashboard table rows."""

    rows = []
    for need in needs:
        status = need.get("status", "draft")
        updated_at = need.get("updated_at") or need.get("created_at") or ""
        rows.append(
            {
                "Initiative ID": need.get("id", "IPM-UNKNOWN"),
                "Title": need_title(need.get("pitch", "")),
                "Phase": STATUS_TO_PHASE.get(status, "Sourcing"),
                "Stage Gate": STATUS_TO_GATE.get(status, "REWORK"),
                "IVI Score": score_need(need),
                "Risk Level": risk_for_need(need),
                "Recommendation Status": STATUS_TO_RECOMMENDATION.get(status, "Needs review"),
                "Last Update": pd.to_datetime(updated_at, errors="coerce").strftime("%Y-%m-%d %H:%M")
                if updated_at
                else datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
        )

    return pd.DataFrame(rows, columns=DASHBOARD_COLUMNS)


def build_trend_data_from_needs(df: pd.DataFrame) -> pd.DataFrame:
    """Build a lightweight recent trend view from backend initiative timestamps."""

    if df.empty:
        return load_sample_trend_data()

    dated = df.copy()
    dated["Last Update Date"] = pd.to_datetime(dated["Last Update"], errors="coerce")
    dated = dated.dropna(subset=["Last Update Date"])
    if dated.empty:
        return load_sample_trend_data()

    start_date = datetime.now().date() - timedelta(weeks=11)
    rows = []
    for week_index in range(12):
        week_start = start_date + timedelta(weeks=week_index)
        week_end = week_start + timedelta(days=7)
        through_week = dated[dated["Last Update Date"].dt.date < week_end]
        in_week = dated[
            (dated["Last Update Date"].dt.date >= week_start)
            & (dated["Last Update Date"].dt.date < week_end)
        ]
        if through_week.empty:
            average_ivi = 0.0
        else:
            average_ivi = round(float(through_week["IVI Score"].mean()), 2)
        rows.append(
            {
                "Week": week_start.strftime("%Y-%m-%d"),
                "Submitted initiatives": int(len(through_week)),
                "Qualified initiatives": int(through_week["Phase"].isin(["Qualification", "Delivery"]).sum()),
                "Delivery-ready initiatives": int((through_week["Phase"] == "Delivery").sum()),
                "High-risk initiatives": int((through_week["Risk Level"] == "High").sum()),
                "Average IVI score": average_ivi,
                "GO": int((in_week["Stage Gate"] == "GO").sum()),
                "REWORK": int((in_week["Stage Gate"] == "REWORK").sum()),
                "ABANDON": int((in_week["Stage Gate"] == "ABANDON").sum()),
            }
        )

    return pd.DataFrame(rows)


@st.cache_data(ttl=10, show_spinner=False)
def load_backend_needs(api_url: str) -> tuple[pd.DataFrame, str | None]:
    """Fetch business needs from the FastAPI backend."""

    try:
        payload = api_json_request(make_api_url(api_url, "/needs"))
    except Exception as exc:
        return pd.DataFrame(), str(exc)

    return needs_to_dashboard_rows(payload if isinstance(payload, list) else []), None


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


@st.cache_data(ttl=30)
def load_sample_trend_data() -> pd.DataFrame:
    """Create weekly sample trends for the time-based analytics section."""

    start_date = datetime.now().date() - timedelta(weeks=11)
    rows = []
    submitted = 7
    qualified = 3
    delivery_ready = 1

    for week_index in range(12):
        week_start = start_date + timedelta(weeks=week_index)
        submitted += [2, 1, 3, 2, 4, 1, 3, 2, 3, 4, 2, 3][week_index]
        qualified += [1, 1, 2, 1, 2, 2, 1, 2, 2, 3, 2, 2][week_index]
        delivery_ready += [0, 1, 0, 1, 1, 1, 0, 2, 1, 1, 2, 1][week_index]
        high_risk = [1, 2, 2, 3, 2, 4, 3, 3, 4, 5, 4, 3][week_index]
        go_decisions = [2, 3, 3, 4, 5, 5, 6, 7, 7, 8, 9, 10][week_index]
        rework_decisions = [1, 1, 2, 2, 2, 3, 3, 2, 3, 3, 2, 2][week_index]
        abandon_decisions = [0, 0, 1, 0, 1, 1, 1, 1, 1, 2, 1, 1][week_index]
        average_ivi = [3.20, 3.28, 3.35, 3.42, 3.48, 3.56, 3.64, 3.72, 3.81, 3.90, 4.02, 4.10][
            week_index
        ]

        rows.append(
            {
                "Week": week_start.strftime("%Y-%m-%d"),
                "Submitted initiatives": submitted,
                "Qualified initiatives": qualified,
                "Delivery-ready initiatives": delivery_ready,
                "High-risk initiatives": high_risk,
                "Average IVI score": average_ivi,
                "GO": go_decisions,
                "REWORK": rework_decisions,
                "ABANDON": abandon_decisions,
            }
        )

    return pd.DataFrame(rows)


api_url = get_default_api_url()


# ---------------------------------------------------------------------------
# Visual theme helpers
# ---------------------------------------------------------------------------
PHASE_ORDER = ["Sourcing", "Qualification", "Delivery"]
STAGE_GATE_ORDER = ["GO", "REWORK", "ABANDON"]
RISK_ORDER = ["Low", "Medium", "High"]

PHASE_COLORS = {
    "Sourcing": "#A8B8FF",
    "Qualification": "#B8B5FF",
    "Delivery": "#8DD7BF",
}
STAGE_GATE_COLORS = {
    "GO": "#8DD7BF",
    "REWORK": "#F7C77A",
    "ABANDON": "#F3A6A6",
}
RISK_COLORS = {
    "Low": "#8DD7BF",
    "Medium": "#F7C77A",
    "High": "#F3A6A6",
}


def style_plotly_figure(fig):
    """Apply a consistent clean layout to Plotly charts."""

    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        margin=dict(l=20, r=20, t=48, b=28),
        legend_title_text="",
        font=dict(family="Inter, Segoe UI, Arial, sans-serif", size=13, color="#1F2937"),
        title=dict(font=dict(size=17, color="#1F2937")),
        hoverlabel=dict(bgcolor="#1F2937", font_size=12, font_color="#ffffff"),
        legend=dict(
            bgcolor="rgba(255,255,255,0.92)",
            bordercolor="#EEF0F4",
            borderwidth=1,
            font=dict(color="#1F2937", size=12),
        ),
    )
    fig.update_xaxes(showgrid=False, linecolor="#EEF0F4", tickfont=dict(color="#1F2937"))
    fig.update_yaxes(gridcolor="#EEF0F4", linecolor="#EEF0F4", tickfont=dict(color="#1F2937"))
    return fig


def render_section_title(title: str, subtitle: str) -> None:
    """Render a consistent section heading."""

    st.markdown(
        f"""
        <div class="ipm-section-title">
            <h2>{escape(title)}</h2>
            <p>{escape(subtitle)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_card(label: str, value: str | int, note: str, accent: str) -> None:
    """Render a custom KPI card with a colored accent rail."""

    st.markdown(
        f"""
        <div class="ipm-kpi-card" style="--accent: {accent};">
            <div class="ipm-kpi-label">{escape(label)}</div>
            <div class="ipm-kpi-value">{escape(str(value))}</div>
            <div class="ipm-kpi-note">{escape(note)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
st.sidebar.markdown(
    """
    <div class="ipm-sidebar-brand">
        <div class="ipm-sidebar-title">IPM Flow</div>
        <div class="ipm-sidebar-subtitle">Business Needs Progress Tracking</div>
        <div class="ipm-sidebar-caption">
            Monitor initiatives across Sourcing, Qualification, and Delivery.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.sidebar.markdown("### Backend")
api_url = st.sidebar.text_input(
    "FastAPI URL",
    value=api_url,
    placeholder="https://your-backend-url.com",
    help="Use your deployed backend URL, for example https://your-api.vercel.app.",
)
use_sample_data = st.sidebar.toggle(
    "Use sample data",
    value=not bool(api_url),
    help="Turn on demo data when the backend is not available.",
)
if st.sidebar.button("Refresh backend data", use_container_width=True):
    load_backend_needs.clear()

api_url = api_url.rstrip("/")

if not api_url:
    st.sidebar.info(
        "Demo mode is active. Add IPM_API_URL in Streamlit secrets or .env to connect live backend data."
    )
elif APP_CONFIG.source != "demo":
    st.sidebar.info(
        f"Backend URL loaded from {APP_CONFIG.source}."
    )

if api_url and not use_sample_data:
    backend_df, backend_error = load_backend_needs(api_url)
else:
    backend_df, backend_error = pd.DataFrame(), None

using_backend = bool(api_url) and not use_sample_data and backend_error is None
if using_backend:
    df = backend_df
    trend_df = build_trend_data_from_needs(df)
else:
    df = load_sample_initiatives(refresh_count)
    trend_df = load_sample_trend_data()

if backend_error and not use_sample_data:
    st.sidebar.warning("Backend unavailable. Showing demo data for now.")

with st.sidebar.expander("Create need", expanded=False):
    with st.form("create_need_form", clear_on_submit=True):
        pitch = st.text_area(
            "Pitch",
            height=120,
            placeholder="Describe the business need, expected value, and context.",
        )
        horizon_label = st.selectbox("Horizon", options=list(HORIZON_OPTIONS.keys()), index=1)
        submitted = st.form_submit_button("Submit to backend", use_container_width=True)

    if submitted:
        if not api_url:
            st.info("Add IPM_API_URL to submit business needs to the backend.")
        elif len(pitch.strip()) < 20:
            st.warning("Pitch must be at least 20 characters.")
        else:
            try:
                api_json_request(
                    make_api_url(api_url, "/needs"),
                    method="POST",
                    payload={"pitch": pitch, "horizon": HORIZON_OPTIONS[horizon_label]},
                )
                load_backend_needs.clear()
                st.success("Need created in the backend.")
                st.rerun()
            except Exception as exc:
                st.warning(f"Could not create need. Please check the backend URL. Details: {exc}")

st.sidebar.markdown("### Portfolio Filters")

selected_phases = st.sidebar.multiselect(
    "Phase",
    options=PHASE_ORDER,
    default=PHASE_ORDER,
)
selected_stage_gates = st.sidebar.multiselect(
    "Stage Gate",
    options=STAGE_GATE_ORDER,
    default=STAGE_GATE_ORDER,
)
selected_risks = st.sidebar.multiselect(
    "Risk Level",
    options=RISK_ORDER,
    default=RISK_ORDER,
)

filtered_df = df[
    df["Phase"].isin(selected_phases)
    & df["Stage Gate"].isin(selected_stage_gates)
    & df["Risk Level"].isin(selected_risks)
].copy()


# ---------------------------------------------------------------------------
# Branded header and live status
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="ipm-hero">
        <div class="ipm-badge">Innovation Process Model</div>
        <h1>Streamlit Dashboard — Business Needs Progress Tracking</h1>
        <p>AI-powered innovation assessment and PoC readiness monitoring</p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div class="ipm-live-row">
        <div>
            <strong>Live portfolio monitor</strong><br>
            <span class="ipm-live-label">
                {"Connected to " + escape(api_url) if using_backend else "Sample data refreshes every " + str(REFRESH_INTERVAL_MS // 1000) + " seconds for demo behavior."}
            </span>
        </div>
        <div>
            <span class="ipm-live-label">Last refresh</span><br>
            <span class="ipm-live-time">{datetime.now().strftime("%H:%M:%S")}</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# KPI cards
# ---------------------------------------------------------------------------
render_section_title(
    "Portfolio KPIs",
    "Executive view of initiative volume, phase progress, IVI performance, and risk exposure.",
)

total_initiatives = len(filtered_df)
sourcing_count = int((filtered_df["Phase"] == "Sourcing").sum())
qualification_count = int((filtered_df["Phase"] == "Qualification").sum())
delivery_count = int((filtered_df["Phase"] == "Delivery").sum())
average_ivi = filtered_df["IVI Score"].mean() if total_initiatives else 0
high_risk_count = int((filtered_df["Risk Level"] == "High").sum())

kpi_cols = st.columns(6)
with kpi_cols[0]:
    render_kpi_card("Total initiatives", total_initiatives, "Active portfolio scope", "#FF7A45")
with kpi_cols[1]:
    render_kpi_card("Sourcing", sourcing_count, "Needs being captured", PHASE_COLORS["Sourcing"])
with kpi_cols[2]:
    render_kpi_card(
        "Qualification",
        qualification_count,
        "Assessment in progress",
        PHASE_COLORS["Qualification"],
    )
with kpi_cols[3]:
    render_kpi_card("Delivery", delivery_count, "PoC readiness path", PHASE_COLORS["Delivery"])
with kpi_cols[4]:
    render_kpi_card("Average IVI score", f"{average_ivi:.2f}/5", "Innovation Value Index", "#FF7A45")
with kpi_cols[5]:
    render_kpi_card("High-risk initiatives", high_risk_count, "Requires attention", RISK_COLORS["High"])


# ---------------------------------------------------------------------------
# Trend analysis over time
# ---------------------------------------------------------------------------
render_section_title(
    "Trend Analysis Over Time",
    "Evolution of initiatives, qualification progress, IVI score, and risk exposure.",
)

show_average_ivi = st.toggle(
    "Overlay Average IVI score",
    value=True,
    help="Display the Average IVI score on a secondary y-axis.",
)

trend_fig = make_subplots(specs=[[{"secondary_y": True}]])
trend_series = [
    ("Submitted initiatives", "#A8B8FF"),
    ("Qualified initiatives", "#B8B5FF"),
    ("Delivery-ready initiatives", "#8DD7BF"),
    ("High-risk initiatives", "#F3A6A6"),
]

for series_name, series_color in trend_series:
    trend_fig.add_trace(
        go.Scatter(
            x=trend_df["Week"],
            y=trend_df[series_name],
            mode="lines+markers",
            name=series_name,
            line=dict(color=series_color, width=3.2),
            marker=dict(size=8, color=series_color, line=dict(color="#ffffff", width=1.5)),
            hovertemplate="<b>%{fullData.name}</b><br>Week: %{x}<br>Count: %{y}<extra></extra>",
        ),
        secondary_y=False,
    )

if show_average_ivi:
    trend_fig.add_trace(
        go.Scatter(
            x=trend_df["Week"],
            y=trend_df["Average IVI score"],
            mode="lines+markers",
            name="Average IVI score",
            line=dict(color="#FFB18A", width=3.4, dash="dot"),
            marker=dict(size=8, color="#FFB18A", line=dict(color="#ffffff", width=1.5)),
            hovertemplate="<b>Average IVI score</b><br>Week: %{x}<br>Score: %{y:.2f}/5<extra></extra>",
        ),
        secondary_y=True,
    )

trend_fig.update_layout(
    title="Innovation Portfolio Momentum",
    height=520,
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1,
        bgcolor="rgba(255,255,255,0)",
    ),
)
trend_fig.update_yaxes(title_text="Initiative count", secondary_y=False, rangemode="tozero")
trend_fig.update_yaxes(
    title_text="Average IVI score",
    secondary_y=True,
    range=[1, 5],
    showgrid=False,
    tickfont=dict(color="#FFB18A"),
    title_font=dict(color="#FFB18A"),
)
st.plotly_chart(style_plotly_figure(trend_fig), use_container_width=True)

gate_trend = trend_df.melt(
    id_vars="Week",
    value_vars=STAGE_GATE_ORDER,
    var_name="Stage Gate",
    value_name="Decisions",
)
gate_trend_fig = px.bar(
    gate_trend,
    x="Week",
    y="Decisions",
    color="Stage Gate",
    color_discrete_map=STAGE_GATE_COLORS,
    title="Stage Gate Decisions Over Time",
    barmode="stack",
)
gate_trend_fig.update_traces(
    hovertemplate="<b>%{fullData.name}</b><br>Week: %{x}<br>Decisions: %{y}<extra></extra>",
    marker_line_width=0,
)
gate_trend_fig.update_layout(height=310, legend=dict(orientation="h", y=1.08, x=1, xanchor="right"))
st.plotly_chart(style_plotly_figure(gate_trend_fig), use_container_width=True)


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
render_section_title(
    "Initiative Monitoring Charts",
    "Phase distribution, Stage Gate decisions, IVI scoring, and risk concentration.",
)

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
        phase_fig.update_traces(textposition="outside", marker_line_width=0, opacity=0.95)
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
        stage_gate_fig.update_traces(textinfo="percent+label", marker=dict(line=dict(color="#ffffff", width=3)))
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
        ivi_fig.update_traces(marker_line_width=0, opacity=0.95)
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
        risk_fig.update_traces(textposition="outside", marker_line_width=0, opacity=0.95)
        st.plotly_chart(style_plotly_figure(risk_fig), use_container_width=True)


# ---------------------------------------------------------------------------
# Recent activity
# ---------------------------------------------------------------------------
render_section_title(
    "Recent Activity",
    "Latest initiative updates from the filtered innovation portfolio.",
)

if filtered_df.empty:
    st.info("Recent activity will appear here when initiatives match the active filters.")
else:
    recent_df = filtered_df.sort_values("Last Update", ascending=False).head(3)
    recent_cols = st.columns(3)
    for col, (_, initiative) in zip(recent_cols, recent_df.iterrows()):
        accent = RISK_COLORS.get(initiative["Risk Level"], "#B8B5FF")
        with col:
            st.markdown(
                f"""
                <div class="ipm-activity-card" style="--accent: {accent};">
                    <div class="ipm-activity-top">
                        <span class="ipm-activity-id">{escape(initiative["Initiative ID"])}</span>
                        <span class="ipm-pill">{escape(initiative["Phase"])}</span>
                    </div>
                    <div class="ipm-activity-title">{escape(initiative["Title"])}</div>
                    <div class="ipm-activity-meta">
                        Stage Gate: <strong>{escape(initiative["Stage Gate"])}</strong><br>
                        IVI: <strong>{initiative["IVI Score"]:.2f}/5</strong> |
                        Risk: <strong>{escape(initiative["Risk Level"])}</strong><br>
                        Updated: {escape(initiative["Last Update"])}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Main monitoring table
# ---------------------------------------------------------------------------
render_section_title(
    "Main Innovation Initiative Monitoring Table",
    "Detailed operational view for Stage Gate tracking, recommendations, and PoC preparation.",
)

st.dataframe(
    filtered_df[DASHBOARD_COLUMNS],
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
st.markdown(
    f"""
    <div class="ipm-footer">
        {"Connected to the IPM Flow backend at " + escape(api_url) + "." if using_backend else "Running with sample data. Set IPM_API_URL or enter a FastAPI URL in the sidebar to connect live data."}
    </div>
    """,
    unsafe_allow_html=True,
)
