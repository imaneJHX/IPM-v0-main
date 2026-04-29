"""Aspect-based feedback handling and conversational stage-gate sessions."""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from app.schemas.business_need import (
    ABSAExtraction,
    StageGateDiffEntry,
    StageGateInteractionResponse,
    StageGateMessage,
    StageGateSummaryItem,
)

_ASPECT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "expertise": ("expert", "skill", "team", "profile", "staff", "capacity"),
    "maturité": ("maturity", "matur", "reference", "production", "pilot", "poc"),
    "durée": ("duration", "timeline", "delay", "roadmap", "month", "week", "time"),
    "données": ("data", "quality", "availability", "access", "source", "mapping"),
    "impact_business": ("impact", "roi", "value", "benefit", "business", "customer", "cost"),
}
_NEGATIVE = ("risk", "weak", "poor", "unclear", "missing", "late", "low", "insufficient", "problem")
_POSITIVE = ("strong", "good", "clear", "solid", "excellent", "credible", "valuable")
_STRONG = ("critical", "blocking", "major", "severe", "urgent", "must", "strongly")
_MEDIUM = ("should", "concern", "needs", "moderate", "important")
_OBJECTIVE_HINTS: dict[str, tuple[str, ...]] = {
    "cost_reduction": ("cost", "saving", "efficiency", "productivity", "automation"),
    "cx_improvement": ("customer", "experience", "satisfaction", "service", "journey"),
    "risk_mitigation": ("risk", "security", "compliance", "fraud", "privacy"),
    "market_opportunity": ("revenue", "market", "growth", "opportunity", "launch"),
}
_DOMAIN_HINTS: dict[str, tuple[str, ...]] = {
    "IA": ("ai", "llm", "prediction", "classification", "copilot", "genai"),
    "Cloud": ("cloud", "aws", "azure", "integration", "platform", "kubernetes"),
    "Cybersecurite": ("security", "privacy", "cyber", "compliance", "iam"),
    "Data": ("data", "quality", "etl", "analytics", "governance"),
    "RH": ("hr", "rh", "employee", "talent", "workforce"),
    "Finance": ("finance", "accounting", "invoice", "budget", "payment"),
    "Operations": ("operations", "workflow", "logistics", "supply", "process"),
}
_ADJUSTMENT_TABLE = {
    ("négatif", "fort"): -2,
    ("négatif", "moyen"): -1,
    ("positif", "moyen"): 1,
    ("positif", "fort"): 2,
}
_SESSIONS: dict[tuple[str, str], dict[str, Any]] = {}


def _clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _extract_sentences(comment: str) -> list[str]:
    parts = re.split(r"(?<=[.!?;])\s+", _clean_text(comment))
    return [part for part in parts if part]


def extract_absa(comment: str) -> list[ABSAExtraction]:
    """Deterministically extract aspect-based feedback from a free-text comment."""
    sentences = _extract_sentences(comment)
    if not sentences and _clean_text(comment):
        sentences = [_clean_text(comment)]

    results: list[ABSAExtraction] = []
    seen: set[tuple[str, str]] = set()
    for sentence in sentences:
        lowered = sentence.lower()
        for aspect, keywords in _ASPECT_KEYWORDS.items():
            if not any(keyword in lowered for keyword in keywords):
                continue
            sentiment = "neutre"
            if any(keyword in lowered for keyword in _NEGATIVE):
                sentiment = "négatif"
            elif any(keyword in lowered for keyword in _POSITIVE):
                sentiment = "positif"

            intensity = "faible"
            if any(keyword in lowered for keyword in _STRONG):
                intensity = "fort"
            elif any(keyword in lowered for keyword in _MEDIUM):
                intensity = "moyen"

            key = (aspect, sentence)
            if key in seen:
                continue
            seen.add(key)
            results.append(
                ABSAExtraction(
                    aspect=aspect, sentiment=sentiment, intensité=intensity, extrait=sentence
                )
            )

    if not results and _clean_text(comment):
        results.append(
            ABSAExtraction(
                aspect="impact_business",
                sentiment="neutre",
                intensité="faible",
                extrait=_clean_text(comment),
            )
        )
    return results


def _clamp_score(value: int) -> int:
    return max(1, min(5, value))


def _score_key(aspect: str) -> str | None:
    return {
        "expertise": "expertise",
        "maturité": "maturite",
        "durée": "duree",
        "données": "donnees",
        "impact_business": "impact_business",
    }.get(aspect)


def apply_ivi_feedback(snapshot: dict[str, Any], feedback: list[ABSAExtraction]) -> tuple[dict[str, Any], list[StageGateDiffEntry]]:
    """Apply ABSA-based score adjustments and build a before/after diff."""
    corrected = deepcopy(snapshot)
    gap = corrected.get("gap_analysis") if isinstance(corrected.get("gap_analysis"), dict) else corrected
    scoring = gap.get("ivi_scoring") if isinstance(gap.get("ivi_scoring"), dict) else {}
    diffs: list[StageGateDiffEntry] = []

    for item in feedback:
        score_key = _score_key(item.aspect)
        if not score_key:
            continue
        dimension = scoring.get(score_key)
        if not isinstance(dimension, dict):
            continue
        before = int(dimension.get("score", 3) or 3)
        delta = _ADJUSTMENT_TABLE.get((item.sentiment, item.intensité), 0)
        after = _clamp_score(before + delta)
        if after == before:
            continue
        dimension["score"] = after
        justification = _clean_text(dimension.get("justification"))
        diff_reason = (
            f"Client feedback on {item.aspect} was classified as {item.sentiment}/{item.intensité} from '{item.extrait}'."
        )
        dimension["justification"] = f"{justification} Adjustment applied: {diff_reason}".strip()
        diffs.append(
            StageGateDiffEntry(
                field=f"ivi_scoring.{score_key}.score",
                before=str(before),
                after=str(after),
                justification=diff_reason,
            )
        )

    if isinstance(gap.get("ivi_score"), (int, float)) and scoring:
        before_ivi = float(gap.get("ivi_score", 0) or 0)
        values = [
            float((scoring.get(key) or {}).get("score", 0) or 0)
            for key in ("maturite", "expertise", "duree", "donnees", "impact_business")
        ]
        after_ivi = round(sum(values) / 5 * 20, 1) if values else before_ivi
        if after_ivi != before_ivi:
            gap["ivi_score"] = after_ivi
            diffs.append(
                StageGateDiffEntry(
                    field="ivi_score",
                    before=str(before_ivi),
                    after=str(after_ivi),
                    justification="Recomputed from adjusted IVI dimension scores.",
                )
            )

    return corrected, diffs


def apply_sg1_feedback(snapshot: dict[str, Any], comment: str) -> tuple[dict[str, Any], list[StageGateDiffEntry]]:
    """Apply lightweight sourcing corrections from reviewer feedback."""
    corrected = deepcopy(snapshot)
    tags = corrected.get("tags") if isinstance(corrected.get("tags"), dict) else corrected
    diffs: list[StageGateDiffEntry] = []
    lowered = _clean_text(comment).lower()

    for objectif, keywords in _OBJECTIVE_HINTS.items():
        if any(keyword in lowered for keyword in keywords):
            before = str(tags.get("objectif", ""))
            if before and before != objectif:
                tags["objectif"] = objectif
                diffs.append(
                    StageGateDiffEntry(
                        field="tags.objectif",
                        before=before,
                        after=objectif,
                        justification="Reviewer feedback included stronger objective cues than the original classification.",
                    )
                )
            break

    detected_domains = [domain for domain, keywords in _DOMAIN_HINTS.items() if any(keyword in lowered for keyword in keywords)]
    if detected_domains:
        before_domains = list(tags.get("domaine") or [])
        after_domains = list(dict.fromkeys([*before_domains, *detected_domains]))
        if after_domains != before_domains:
            tags["domaine"] = after_domains
            diffs.append(
                StageGateDiffEntry(
                    field="tags.domaine",
                    before=", ".join(before_domains) or "None",
                    after=", ".join(after_domains),
                    justification="Reviewer feedback named additional domain signals that should remain hard constraints.",
                )
            )

    if any(token in lowered for token in ("uncertain", "confidence", "doubt", "ambiguous")):
        for key in ("objectif_confidence", "origine_confidence"):
            before = str(tags.get(key, "medium"))
            if before != "low":
                tags[key] = "low"
                diffs.append(
                    StageGateDiffEntry(
                        field=f"tags.{key}",
                        before=before,
                        after="low",
                        justification="Reviewer explicitly questioned confidence in the current sourcing classification.",
                    )
                )

    pitch = _clean_text(corrected.get("pitch"))
    horizon = corrected.get("horizon")
    if pitch:
        from app.services import nlp_service

        normalized = nlp_service.normalize_tags(pitch, horizon, tags)
        normalized_dump = normalized.model_dump()
        sourcing = normalized_dump.get("sourcing_classification")
        if any(token in lowered for token in ("uncertain", "confidence", "doubt", "ambiguous")) and isinstance(sourcing, dict):
            for field in ("source", "domain", "objective"):
                tag = sourcing.get(field)
                if isinstance(tag, dict):
                    tag["confidence"] = "low"
            constraints = sourcing.get("constraintsForGapAnalysis")
            if isinstance(constraints, dict):
                constraints["ambiguityFlags"] = [
                    {
                        "field": field,
                        "confidence": "low",
                        "reason": "Reviewer explicitly questioned confidence in the SG-1 classification.",
                    }
                    for field in ("source", "domain", "objective")
                ]
        corrected["tags"] = normalized_dump

    return corrected, diffs


def summarize_gate(gate: str, snapshot: dict[str, Any]) -> list[StageGateSummaryItem]:
    """Build a compact structured summary for a stage gate."""
    if gate == "SG-1":
        tags = snapshot.get("tags") if isinstance(snapshot.get("tags"), dict) else snapshot
        sourcing = tags.get("sourcing_classification") if isinstance(tags.get("sourcing_classification"), dict) else {}
        source_value = sourcing.get("source", {}).get("value") if isinstance(sourcing.get("source"), dict) else None
        domain_value = sourcing.get("domain", {}).get("value") if isinstance(sourcing.get("domain"), dict) else None
        objective_value = sourcing.get("objective", {}).get("value") if isinstance(sourcing.get("objective"), dict) else None
        return [
            StageGateSummaryItem(label="Objective", value=str(objective_value or tags.get("objectif", "Not specified"))),
            StageGateSummaryItem(label="Domains", value=", ".join(tags.get("domaine") or []) or "Not specified"),
            StageGateSummaryItem(label="Impact", value=", ".join(tags.get("impact") or []) or "Not specified"),
            StageGateSummaryItem(label="Source", value=str(source_value or tags.get("origine", "Not specified"))),
            StageGateSummaryItem(label="Domain", value=str(domain_value or "Not specified")),
        ]
    if gate == "SG-3":
        gap = snapshot.get("gap_analysis") if isinstance(snapshot.get("gap_analysis"), dict) else snapshot
        return [
            StageGateSummaryItem(label="Solution", value=str(gap.get("solution_name", "Not specified"))),
            StageGateSummaryItem(label="Fit score", value=f"{gap.get('fit_score', '-')}/10"),
            StageGateSummaryItem(label="IVI score", value=f"{gap.get('ivi_score', '-')}/100"),
            StageGateSummaryItem(label="Prerequisite mode", value="Yes" if gap.get("prerequisite_mode") else "No"),
        ]
    recommendations = snapshot.get("recommendations")
    recommendation_count = len(recommendations) if isinstance(recommendations, list) else 0
    return [
        StageGateSummaryItem(label="Recommendations", value=str(recommendation_count)),
        StageGateSummaryItem(label="Export ready", value="Yes" if snapshot.get("export_ready") else "No"),
        StageGateSummaryItem(label="Roadmap", value="Present" if snapshot.get("roadmap") else "Not specified"),
        StageGateSummaryItem(label="KPI count", value=str(snapshot.get("kpi_count", 0))),
    ]


def _phase_for_gate(gate: str) -> str:
    return {"SG-1": "Sourcing", "SG-3": "Qualification", "SG-4": "Delivery"}[gate]


def interact_stage_gate(need_id: str, gate: str, action: str, comment: str | None, snapshot: dict[str, Any]) -> StageGateInteractionResponse:
    """Stateful conversational gate handler with rework counting and escalation."""
    key = (need_id, gate)
    session = _SESSIONS.setdefault(
        key,
        {"messages": [], "nb_reworks": 0, "snapshot": deepcopy(snapshot)},
    )
    if snapshot:
        session["snapshot"] = deepcopy(snapshot)

    messages = [StageGateMessage(**msg) if not isinstance(msg, StageGateMessage) else msg for msg in session["messages"]]
    feedback = extract_absa(comment or "") if action == "REWORK" and comment else []
    diffs: list[StageGateDiffEntry] = []
    corrected_snapshot = deepcopy(session["snapshot"])
    decision = "PENDING"

    if action == "GO":
        decision = "GO"
        messages.append(StageGateMessage(role="agent", content="Gate approved. The phase can move forward."))
    elif action == "ABANDON":
        decision = "ABANDON"
        messages.append(StageGateMessage(role="agent", content="Gate stopped. The initiative should be abandoned or escalated outside the workflow."))
    elif action == "REWORK":
        session["nb_reworks"] += 1
        messages.append(StageGateMessage(role="reviewer", content=_clean_text(comment)))
        if gate == "SG-1":
            corrected_snapshot, diffs = apply_sg1_feedback(corrected_snapshot, comment or "")
        else:
            corrected_snapshot, diffs = apply_ivi_feedback(corrected_snapshot, feedback)
        decision = "ESCALATE" if session["nb_reworks"] >= 3 else "REWORK"
        agent_message = (
            "Three rework cycles have been reached without GO. Escalate to a human supervisor."
            if decision == "ESCALATE"
            else "Corrections have been applied from the reviewer comment. Review the diff and decide GO, REWORK, or ABANDON."
        )
        messages.append(StageGateMessage(role="agent", content=agent_message))
        session["snapshot"] = corrected_snapshot
    else:
        messages.append(StageGateMessage(role="agent", content="Phase summary ready for review."))

    session["messages"] = [message.model_dump() for message in messages[-8:]]
    recommendation = {
        "SG-1": "Recommendation: GO if the sourcing tags and confidence levels are acceptable; otherwise request a constrained rework.",
        "SG-3": "Recommendation: GO if IVI, fit, and prerequisite mode are acceptable for downstream selection.",
        "SG-4": "Recommendation: GO if recommendations, KPIs, and roadmap are export-ready.",
    }[gate]

    return StageGateInteractionResponse(
        gate=gate, phase=_phase_for_gate(gate), decision=decision, recommendation=recommendation,
        summary=summarize_gate(gate, corrected_snapshot), actions=["GO", "REWORK", "ABANDON"],
        messages=messages[-8:], aspect_feedback=feedback, diffs=diffs,
        corrected_snapshot=corrected_snapshot, nb_reworks=session["nb_reworks"],
        escalated=decision == "ESCALATE",
    )
