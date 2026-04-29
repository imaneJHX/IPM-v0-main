"""Synthetic evaluation scaffolding for ABSA and NLP-tagging experiments."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SyntheticCommentExample:
    text: str
    expected_aspect: str
    expected_sentiment: str
    expected_intensity: str


@dataclass(frozen=True)
class SyntheticPitchExample:
    pitch: str
    horizon: str
    expected_objectif: str
    expected_domaine: tuple[str, ...]
    expected_impact: tuple[str, ...]
    expected_origine: str


def build_synthetic_comment_dataset() -> list[SyntheticCommentExample]:
    """Return a small curated seed set for ABSA evaluation expansion."""
    return [
        SyntheticCommentExample(
            text="The expertise looks strong, but the delivery team still needs one more cloud specialist.",
            expected_aspect="expertise",
            expected_sentiment="positif",
            expected_intensity="moyen",
        ),
        SyntheticCommentExample(
            text="Data availability is a major blocker because the sources are still restricted.",
            expected_aspect="données",
            expected_sentiment="négatif",
            expected_intensity="fort",
        ),
        SyntheticCommentExample(
            text="The projected timeline is acceptable and should stay within one quarter.",
            expected_aspect="durée",
            expected_sentiment="positif",
            expected_intensity="moyen",
        ),
        SyntheticCommentExample(
            text="Business impact is unclear and the ROI story remains weak.",
            expected_aspect="impact_business",
            expected_sentiment="négatif",
            expected_intensity="moyen",
        ),
        SyntheticCommentExample(
            text="Maturity feels low because the offer is still at POC stage.",
            expected_aspect="maturité",
            expected_sentiment="négatif",
            expected_intensity="moyen",
        ),
    ]


def build_synthetic_pitch_dataset() -> list[SyntheticPitchExample]:
    """Return a lightweight seed set for fixed-taxonomy NLP-tagging experiments."""
    return [
        SyntheticPitchExample(
            pitch="Automate invoice reconciliation to reduce closing time from 5 days to 1 day.",
            horizon="court_terme",
            expected_objectif="cost_reduction",
            expected_domaine=("Finance", "Operations"),
            expected_impact=("Cost", "Risk"),
            expected_origine="probleme_operationnel",
        ),
        SyntheticPitchExample(
            pitch="Launch a self-service customer portal to reduce average response time by 40%.",
            horizon="moyen_terme",
            expected_objectif="cx_improvement",
            expected_domaine=("Operations",),
            expected_impact=("CustomerExperience", "Cost"),
            expected_origine="probleme_operationnel",
        ),
        SyntheticPitchExample(
            pitch="Deploy AI fraud scoring for payment flows to reduce false negatives by 20%.",
            horizon="moyen_terme",
            expected_objectif="risk_mitigation",
            expected_domaine=("IA", "Finance"),
            expected_impact=("Risk", "Cost"),
            expected_origine="probleme_operationnel",
        ),
        SyntheticPitchExample(
            pitch="Create a new data product to open a subscription revenue stream in a new market.",
            horizon="long_terme",
            expected_objectif="market_opportunity",
            expected_domaine=("Data",),
            expected_impact=("Revenue",),
            expected_origine="enjeu_marche",
        ),
    ]
