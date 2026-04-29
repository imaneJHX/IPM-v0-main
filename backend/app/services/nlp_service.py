"""NLP service for sourcing classification and prompt-ready constraints."""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, NamedTuple

from app.core import llm_client
from app.core.config import settings
from app.schemas.business_need import (
    ClassifiedConstraint,
    GapAnalysisConstraints,
    HorizonValue,
    Suggestion,
    SourcingAmbiguityFlag,
    SourcingClassification,
    SourcingDomainTag,
    SourcingGapAnalysisConstraints,
    SourcingObjectiveTag,
    SourcingSourceTag,
    Tags,
)

logger = logging.getLogger(__name__)

_OBJECTIF_VALUES = (
    "cost_reduction",
    "cx_improvement",
    "risk_mitigation",
    "market_opportunity",
)
_DOMAIN_VALUES = (
    "IA",
    "Cloud",
    "Cybersecurite",
    "Data",
    "RH",
    "Finance",
    "Operations",
    "Autre",
)
_IMPACT_VALUES = ("Revenue", "Cost", "Risk", "CustomerExperience")
_ORIGINE_VALUES = (
    "enjeu_marche",
    "probleme_operationnel",
    "demande_client",
)
_CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}


class _CacheEntry(NamedTuple):
    tags: Tags
    suggestions: list[Suggestion]
    timestamp: float


class _IntentSignals(NamedTuple):
    explicit_intent: str
    implicit_intent: str
    strategic_intent: str


class _LiveSuggestionContext(NamedTuple):
    objective: str | None
    domains: list[str]
    impacts: list[str]
    tags: list[str]
    phase: str
    status: str


_cache: dict[str, _CacheEntry] = {}
_CACHE_TTL = 300

_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "IA": [
        "predict",
        "prediction",
        "forecast",
        "forecasting",
        "classif",
        "recommend",
        "score",
        "detect",
        "anomaly",
        "fraud detection",
        "summar",
        "generate",
        "extract",
        "machine learning",
        "ml",
        "llm",
        "nlp",
        "computer vision",
        "vision",
        "ocr",
        "chatbot",
        "copilot",
        "genai",
        "generative ai",
        "predi",
        "previ",
        "classif",
        "recommand",
        "score de",
        "detect",
        "anomal",
        "fraude",
        "resum",
        "gener",
        "extra",
        "vision par ordinateur",
        "ia generative",
    ],
    "Cloud": [
        "cloud",
        "aws",
        "azure",
        "gcp",
        "saas",
        "paas",
        "iaas",
        "container",
        "kubernetes",
        "serverless",
        "migration cloud",
    ],
    "Cybersecurite": [
        "security",
        "cyber",
        "soc",
        "siem",
        "zero trust",
        "identity",
        "iam",
        "compliance",
        "rgpd",
        "phishing",
        "securit",
        "cybersecurit",
    ],
    "Data": [
        "data",
        "bi",
        "dashboard",
        "analytics",
        "etl",
        "elt",
        "warehouse",
        "lake",
        "governance",
        "reporting",
        "donnee",
    ],
    "RH": [
        "hr",
        "rh",
        "recruit",
        "talent",
        "employee",
        "workforce",
        "training",
        "onboarding",
        "recrut",
        "formation",
    ],
    "Finance": [
        "finance",
        "financial",
        "accounting",
        "payment",
        "invoice",
        "treasury",
        "budget",
        "fraud",
        "facture",
        "tresorerie",
    ],
    "Operations": [
        "operations",
        "supply chain",
        "logistics",
        "procurement",
        "manufacturing",
        "project",
        "devops",
        "rpa",
        "workflow",
        "process",
        "operation",
        "logistique",
        "approvisionnement",
        "production",
        "processus",
    ],
}

_OBJECTIF_KEYWORDS: dict[str, list[str]] = {
    "cost_reduction": [
        "reduce cost",
        "cost reduction",
        "save",
        "efficiency",
        "automate",
        "productivity",
        "manual",
        "optimize",
        "streamline",
        "reduce time",
        "reduction des couts",
        "gagner du temps",
        "automatis",
        "productivit",
        "optimis",
    ],
    "cx_improvement": [
        "customer experience",
        "client experience",
        "support",
        "self-service",
        "response time",
        "satisfaction",
        "retention",
        "service quality",
        "experience client",
        "self service",
        "temps de reponse",
        "satisfaction client",
    ],
    "risk_mitigation": [
        "risk",
        "security",
        "compliance",
        "fraud",
        "audit",
        "resilience",
        "incident",
        "phishing",
        "governance",
        "risque",
        "conformit",
        "resilience",
    ],
    "market_opportunity": [
        "revenue",
        "growth",
        "new market",
        "new service",
        "upsell",
        "competitive",
        "go-to-market",
        "launch",
        "innovation",
        "revenu",
        "croissance",
        "nouveau marche",
        "nouveau service",
        "mise sur le marche",
    ],
}

_IMPACT_KEYWORDS: dict[str, list[str]] = {
    "Revenue": [
        "revenue",
        "upsell",
        "cross-sell",
        "growth",
        "new market",
        "retention",
        "sales",
        "revenu",
        "croissance",
        "vente",
    ],
    "Cost": [
        "cost",
        "efficiency",
        "productivity",
        "manual",
        "automation",
        "optimization",
        "save",
        "cout",
        "econom",
        "automatis",
    ],
    "Risk": [
        "risk",
        "security",
        "fraud",
        "audit",
        "compliance",
        "resilience",
        "incident",
        "risque",
        "conformit",
    ],
    "CustomerExperience": [
        "customer",
        "client",
        "support",
        "satisfaction",
        "response",
        "journey",
        "self-service",
        "experience",
        "service client",
        "parcours",
    ],
}

_ORIGINE_KEYWORDS: dict[str, list[str]] = {
    "demande_client": [
        "client request",
        "customer request",
        "customer complaint",
        "feedback client",
        "feature request",
        "customer feedback",
        "contract requirement",
        "client",
        "customer",
        "feedback",
        "demande client",
        "retour client",
        "besoin client",
        "exigence contractuelle",
    ],
    "enjeu_marche": [
        "market",
        "competition",
        "competitive",
        "regulation",
        "regulatory",
        "trend",
        "industry",
        "compliance",
        "marche",
        "concurr",
        "reglement",
        "tendance",
        "secteur",
    ],
    "probleme_operationnel": [
        "manual",
        "delay",
        "incident",
        "inefficiency",
        "technical debt",
        "process",
        "operations",
        "rework",
        "retard",
        "incident",
        "ineffic",
        "processus",
        "operation",
        "dette technique",
    ],
}

_MEASURABLE_PATTERNS = (
    re.compile(r"\b\d+(?:[.,]\d+)?\s*%"),
    re.compile(r"\b(?:from|de)\s+\d+(?:[.,]\d+)?\s*(?:to|a|->)\s+\d+(?:[.,]\d+)?"),
    re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:days?|day|hours?|hour|minutes?|mins?|weeks?|week|months?|month|jours?|jour|heures?|heure|minutes?|semaine|semaines|mois)\b"),
    re.compile(r"\b(?:nps|sla|roi|kpi|csat)\b"),
    re.compile(r"\b(?:reduce|cut|lower|increase|improve|decrease|save|gain|reduc|baisse|augment|amelior|gagne)\w*\b.{0,24}\b\d+(?:[.,]\d+)?"),
    re.compile(r"\b(?:save|saving|cost|cout|budget|spend|econom|economiser|economie)\w*\b.{0,24}\b(?:€|\$)?\d+(?:[.,]\d+)?\s*(?:k|m|mn|million|millions)?\b"),
    re.compile(r"\b(?:process|handle|traiter|dossier|dossiers|tickets?|cases?|erreurs?|errors?|taux)\b.{0,24}\b\d+(?:[.,]\d+)?\b"),
)
_NAMED_CLIENT_PATTERNS = (
    re.compile(r"\b(?:client|customer|account|compte)\s+([A-Z][\w&.-]+(?:\s+[A-Z][\w&.-]+){0,2})"),
    re.compile(r"\b(?:for client|pour client|chez)\s+([A-Z][\w&.-]+(?:\s+[A-Z][\w&.-]+){0,2})"),
)
_AI_INFERENCE_PATTERNS = (
    re.compile(r"\bpredict\w*"),
    re.compile(r"\bforecast\w*"),
    re.compile(r"\bclassif\w*"),
    re.compile(r"\brecommend\w*"),
    re.compile(r"\bscore\w*"),
    re.compile(r"\bdetect\w*"),
    re.compile(r"\banomal\w*"),
    re.compile(r"\bsummar\w*"),
    re.compile(r"\bgenerat\w*"),
    re.compile(r"\bmachine learning\b"),
    re.compile(r"\bml model\b"),
    re.compile(r"\bneural network\b"),
    re.compile(r"\breseau(?:x)? de neurones?\b"),
    re.compile(r"\bllm\b"),
    re.compile(r"\bnlp\b.{0,24}\b(?:semantic|interpret|intent|sentiment|classification)\b"),
    re.compile(r"\b(?:semantic|semanticque|semantique)\b.{0,24}\bnlp\b"),
    re.compile(r"\bgenai\b"),
    re.compile(r"\bgenerative ai\b"),
    re.compile(r"\bcomputer vision\b"),
    re.compile(r"\bpredi\w*"),
    re.compile(r"\bprevi\w*"),
    re.compile(r"\bclassif\w*"),
    re.compile(r"\brecommand\w*"),
    re.compile(r"\bdetect\w*"),
    re.compile(r"\banomal\w*"),
    re.compile(r"\bresum\w*"),
    re.compile(r"\bgener\w*"),
    re.compile(r"\bia generative\b"),
    re.compile(r"\bvision par ordinateur\b"),
    re.compile(r"\bscoring intelligent\b"),
    re.compile(r"\bgenerer une reponse\b"),
    re.compile(r"\bclassifier automatiquement\b"),
    re.compile(r"\bdetecter une anomalie\b"),
)
_HORIZON_HINTS = {
    "court_terme": "Anchor the need on a first measurable result achievable within 3 months.",
    "moyen_terme": "Describe the main milestone and ownership for a 6 to 12 month rollout.",
    "long_terme": "Clarify the strategic capability, scale target, and phased roadmap beyond 12 months.",
}
_HORIZON_GAP_RULES = {
    "court_terme": "Prefer low-complexity gaps, fast integrations, and near-term operational value.",
    "moyen_terme": "Balance implementation realism with scalable design over the next 6 to 12 months.",
    "long_terme": "Favor scalable capabilities, strategic fit, and future-proof architecture over short-term shortcuts.",
}
_DXC_STRATEGIC_INTENTS = {
    "cost_reduction": "Position the need around delivery efficiency, scalable operations, and service industrialization for DXC.",
    "cx_improvement": "Position the need around experience-led transformation, service quality, and measurable adoption outcomes for DXC.",
    "risk_mitigation": "Position the need around trusted transformation, governance, cyber resilience, and compliance execution for DXC.",
    "market_opportunity": "Position the need around growth acceleration, reusable offerings, and strategic differentiation for DXC.",
}
_SUGGESTION_SLOTS = (
    ("reformulation", "Reformulation"),
    ("business_precision", "Business Precision"),
    ("value_angle", "Value Angle"),
)
_OBJECTIVE_PROMPT_LABELS = {
    "cost_reduction": "cost reduction",
    "cx_improvement": "customer experience improvement",
    "risk_mitigation": "risk mitigation",
    "market_opportunity": "market opportunity",
}
_HORIZON_PROMPT_LABELS = {
    "court_terme": "short term",
    "moyen_terme": "medium term",
    "long_terme": "long term",
}
_SMART_SUGGESTION_CATEGORIES = (
    "Business Framing",
    "Value Angle",
    "Data Readiness",
    "KPI Definition",
    "Risk Alert",
    "Delivery Readiness",
    "Cost Optimization",
    "Customer Experience",
    "Process Improvement",
)
_CUSTOMER_EXPERIENCE_HINTS = (
    "ux",
    "user experience",
    "mobile",
    "app",
    "journey",
    "customer",
    "client",
    "conversion",
    "abandonment",
    "onboarding",
    "checkout",
)
_DATA_READINESS_HINTS = (
    "data",
    "analytics",
    "tracking",
    "kpi",
    "dashboard",
    "reporting",
    "events",
    "telemetry",
)
_DELIVERY_HINTS = (
    "workflow",
    "process",
    "integration",
    "mobile",
    "platform",
    "service",
)
_STRUCTURED_SOURCE_KEYWORDS: dict[str, list[str]] = {
    "opportunite_marche": [
        "market",
        "growth",
        "new product",
        "new service",
        "trend",
        "competitive",
        "regulation",
        "revenue",
        "marche",
        "croissance",
        "opportunite",
        "nouveau produit",
        "nouveau service",
        "tendance",
        "concurr",
        "reglement",
    ],
    "innovation_interne": [
        "innovation interne",
        "innovation lab",
        "r&d",
        "experimentation",
        "proof of concept interne",
        "prototype interne",
        "internal innovation",
        "internal experiment",
        "internal prototype",
        "lab innovation",
    ],
}
_STRUCTURED_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "Data": [
        "dashboard",
        "reporting",
        "bi",
        "etl",
        "elt",
        "analytics",
        "visualization",
        "visualisation",
        "cleaning",
        "nettoyage",
        "data",
        "donnee",
        "kpi",
    ],
    "Process": [
        "process",
        "processus",
        "workflow",
        "operations",
        "operation",
        "production",
        "supply chain",
        "logistics",
        "rpa",
        "automation",
        "automatisation",
    ],
    "Business": [
        "customer",
        "client",
        "sales",
        "finance",
        "rh",
        "hr",
        "service",
        "revenue",
        "market",
        "commercial",
        "business",
        "metier",
    ],
    "IT": [
        "cloud",
        "aws",
        "azure",
        "sap",
        "servicenow",
        "api",
        "integration",
        "platform",
        "infrastructure",
        "security",
        "cyber",
        "it",
        "devops",
    ],
}
_STRUCTURED_OBJECTIVE_KEYWORDS: dict[str, list[str]] = {
    "optimisation_operationnelle": [
        "optimize",
        "optimise",
        "optimization",
        "optimisation",
        "quick win",
        "improve process",
        "reduce delay",
        "gagner du temps",
        "reduire le delai",
        "fluidifier",
    ],
    "automatisation": [
        "automate",
        "automation",
        "rpa",
        "workflow automation",
        "manual",
        "automatis",
        "sans intervention manuelle",
    ],
    "reduction_couts": [
        "cost",
        "saving",
        "reduce cost",
        "budget",
        "econom",
        "cout",
        "economiser",
        "reduire les couts",
    ],
    "amelioration_qualite": [
        "quality",
        "qualite",
        "error",
        "accuracy",
        "satisfaction",
        "sla",
        "nps",
        "conformite",
        "rework",
        "service quality",
    ],
    "transformation_strategique": [
        "transform",
        "transformation",
        "platform",
        "operating model",
        "industrialization",
        "industrialisation",
        "scale",
        "scalable",
        "global",
        "modernization",
        "modernisation",
        "strategic",
        "strategique",
    ],
    "innovation": [
        "innovation",
        "new offer",
        "new product",
        "new service",
        "pilot",
        "prototype",
        "poc",
        "differentiation",
        "differenciation",
        "experiment",
        "experimentation",
        "launch",
    ],
}
_STRUCTURED_OBJECTIVE_HORIZON_BIAS: dict[str, dict[str, int]] = {
    "court_terme": {
        "optimisation_operationnelle": 2,
        "automatisation": 1,
    },
    "moyen_terme": {
        "automatisation": 2,
        "amelioration_qualite": 1,
        "transformation_strategique": 1,
    },
    "long_terme": {
        "transformation_strategique": 2,
        "innovation": 1,
    },
}
_HORIZON_OBJECTIVE_CONFLICTS: dict[str, set[str]] = {
    "court_terme": {"transformation_strategique", "innovation"},
    "moyen_terme": {"innovation"},
    "long_terme": {"optimisation_operationnelle", "automatisation", "reduction_couts"},
}


def _context_cache_key(context: _LiveSuggestionContext | None) -> str:
    """Serialize additive SG-1 context so live suggestions stay context-aware."""
    if context is None:
        return "none"
    payload = {
        "objective": context.objective or "",
        "domains": context.domains,
        "impacts": context.impacts,
        "tags": context.tags,
        "phase": context.phase,
        "status": context.status,
    }
    return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def _cache_key(
    pitch: str,
    horizon: HorizonValue | None,
    context: _LiveSuggestionContext | None,
) -> str:
    """Build a cache key that preserves horizon and live SG-1 context."""
    return f"{pitch.strip().lower()}::{horizon or 'none'}::{_context_cache_key(context)}"


def _get_cached(
    pitch: str,
    horizon: HorizonValue | None,
    context: _LiveSuggestionContext | None,
) -> tuple[Tags, list[Suggestion]] | None:
    """Return cached analysis if still valid."""
    entry = _cache.get(_cache_key(pitch, horizon, context))
    if entry and (time.monotonic() - entry.timestamp) < _CACHE_TTL:
        return entry.tags, entry.suggestions
    return None


def _set_cache(
    pitch: str,
    horizon: HorizonValue | None,
    context: _LiveSuggestionContext | None,
    tags: Tags,
    suggestions: list[Suggestion],
) -> None:
    """Store analysis result in cache."""
    _cache[_cache_key(pitch, horizon, context)] = _CacheEntry(
        tags=tags,
        suggestions=suggestions,
        timestamp=time.monotonic(),
    )


def _normalize_live_suggestion_context(
    *,
    objective: str | None = None,
    domains: list[str] | None = None,
    impacts: list[str] | None = None,
    tags: list[str] | None = None,
    phase: str | None = None,
    status: str | None = None,
) -> _LiveSuggestionContext:
    """Normalize optional frontend context sent by the SG-1 live panel."""

    def _clean_list(values: list[str] | None) -> list[str]:
        if not values:
            return []
        normalized: list[str] = []
        seen: set[str] = set()
        for item in values:
            text = str(item or "").strip()
            if not text:
                continue
            lowered = text.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            normalized.append(text)
        return normalized

    return _LiveSuggestionContext(
        objective=str(objective).strip() if objective else None,
        domains=_clean_list(domains),
        impacts=_clean_list(impacts),
        tags=_clean_list(tags),
        phase=str(phase or "SG-1").strip() or "SG-1",
        status=str(status or "Draft").strip() or "Draft",
    )


def _llm_is_configured() -> bool:
    """Return True when the selected LLM provider is configured."""
    if settings.llm_provider == "groq":
        return bool(settings.groq_api_key.strip())
    if settings.llm_provider == "azure":
        return bool(
            settings.azure_openai_api_key.strip()
            and settings.azure_openai_endpoint.strip()
        )
    return False


def _score_keywords(text: str, mapping: dict[str, list[str]]) -> dict[str, int]:
    """Return keyword-match scores for each label."""
    scores: dict[str, int] = {}
    for label, keywords in mapping.items():
        score = 0
        for keyword in keywords:
            if keyword in text:
                score += 2 if " " in keyword else 1
        scores[label] = score
    return scores


def _normalize_pitch(text: str) -> str:
    """Collapse whitespace for cleaner fallback suggestions."""
    normalized = re.sub(r"\s+", " ", text).strip()
    if normalized and normalized[-1] not in ".!?":
        normalized += "."
    return normalized


def _infer_pitch_language(text: str) -> str:
    """Return 'fr' or 'en' using lightweight lexical cues."""
    lowered = text.lower()
    french_markers = (
        " le ",
        " la ",
        " les ",
        " des ",
        " pour ",
        " avec ",
        " dans ",
        " afin de ",
        " equipe",
        " processus",
        " donnees",
        " redu",
        " amelior",
    )
    english_markers = (
        " the ",
        " and ",
        " with ",
        " within ",
        " reduce ",
        " improve ",
        " customer ",
        " team ",
        " process ",
        " data ",
    )
    french_score = sum(marker in lowered for marker in french_markers)
    english_score = sum(marker in lowered for marker in english_markers)
    if re.search(r"[àâçéèêëîïôûùüÿœ]", lowered):
        french_score += 2
    return "fr" if french_score >= english_score else "en"


def _extract_metric_hint(pitch: str, objectif: str) -> str:
    """Reuse any measurable target in the pitch, otherwise inject KPI placeholders."""
    patterns = (
        r"\b\d+(?:[.,]\d+)?\s?(?:%|percent|pour ?cent|€|eur|euros?|heures?|hours?|hrs?|jours?|days?|mois|months?|nps(?: points?)?)\b",
        r"\bfrom\s+\d+(?:[.,]\d+)?(?:\s+\w+){0,4}\s+to\s+\d+(?:[.,]\d+)?(?:\s+\w+){0,4}\b",
        r"\bde\s+\d+(?:[.,]\d+)?(?:\s+\w+){0,4}\s+a\s+\d+(?:[.,]\d+)?(?:\s+\w+){0,4}\b",
    )
    for pattern in patterns:
        match = re.search(pattern, pitch, flags=re.IGNORECASE)
        if match:
            return match.group(0).strip()

    fallback_metrics = {
        "cost_reduction": "a measurable reduction in cost or cycle time",
        "cx_improvement": "a measurable uplift in conversion, satisfaction, or response time",
        "risk_mitigation": "a measurable reduction in incidents or risk exposure",
        "market_opportunity": "a measurable target for incremental revenue or conversion",
    }
    return fallback_metrics.get(objectif, fallback_metrics["cost_reduction"])


def _scope_hint(domains: list[str]) -> str:
    """Map the first detected domain to an impacted team or process."""
    primary_domain = domains[0] if domains else "Autre"
    scope_map = {
        "IA": "the AI-enabled decision process",
        "Cloud": "the cloud platform team",
        "Cybersecurite": "the cyber and compliance team",
        "Data": "the data and reporting process",
        "RH": "the HR team",
        "Finance": "the finance team",
        "Operations": "the business operations team",
        "Autre": "the impacted business team",
    }
    return scope_map.get(primary_domain, scope_map["Autre"])


def _objective_action(objectif: str) -> str:
    """Return an action phrase aligned with the classified objective."""
    action_map = {
        "cost_reduction": "reduce costs and operational friction",
        "cx_improvement": "improve experience and service responsiveness",
        "risk_mitigation": "reduce risk and strengthen control",
        "market_opportunity": "accelerate growth and value capture",
    }
    return action_map.get(objectif, action_map["cost_reduction"])


def _impact_phrase(impacts: list[str]) -> str:
    """Translate the first impact tag into a business-value framing."""
    primary_impact = impacts[0] if impacts else "Cost"
    impact_map = {
        "Revenue": "measurable revenue growth",
        "Cost": "measurable economic performance",
        "Risk": "measurable risk reduction",
        "CustomerExperience": "measurable customer experience improvement",
    }
    return impact_map.get(primary_impact, impact_map["Cost"])


def _benchmark_hint(objectif: str, impacts: list[str]) -> str:
    """Provide a safe benchmark framing without inventing reference numbers."""
    if "CustomerExperience" in impacts:
        return "time-to-completion, conversion, abandonment, and service-adoption KPIs"
    if objectif == "risk_mitigation":
        return "control coverage, incident reduction, and audit-readiness KPIs"
    if objectif == "market_opportunity":
        return "pipeline conversion, upsell, and launch-readiness KPIs"
    return "cost-to-serve, cycle-time, and productivity KPIs"


def _horizon_phrase(horizon: HorizonValue | None) -> str:
    """Human-readable timeframe phrasing for suggestions."""
    if horizon == "court_terme":
        return "within 3 months"
    if horizon == "moyen_terme":
        return "within 6 to 12 months"
    if horizon == "long_terme":
        return "over the next 12 months and beyond"
    return "within an agreed delivery window"


def _sentence_count(text: str) -> int:
    """Count non-empty sentence fragments."""
    return len([chunk for chunk in re.split(r"[.!?]+", text) if chunk.strip()])


def _extract_intent_rule(tags: Tags, prefix: str) -> str:
    """Return the first hard rule matching the given prefix."""
    constraints = tags.gap_analysis_constraints
    if not constraints:
        return ""
    for rule in constraints.hard_rules:
        if rule.startswith(prefix):
            return rule
    return ""


def _normalize_objective_hint(value: str | None, fallback: str) -> str:
    """Map loose objective labels coming from the UI back to the core taxonomy."""
    lowered = str(value or "").strip().lower()
    if "customer" in lowered or "cx" in lowered or "experience" in lowered:
        return "cx_improvement"
    if "risk" in lowered or "control" in lowered or "security" in lowered:
        return "risk_mitigation"
    if "market" in lowered or "growth" in lowered or "revenue" in lowered or "opportunity" in lowered:
        return "market_opportunity"
    if "cost" in lowered or "efficiency" in lowered or "productivity" in lowered:
        return "cost_reduction"
    return fallback


def _effective_context(
    pitch: str,
    tags: Tags,
    horizon: HorizonValue | None,
    context: _LiveSuggestionContext | None,
) -> tuple[str, list[str], list[str], list[str], str, str]:
    """Merge UI context with NLP tags without losing deterministic classification."""
    _ = pitch, horizon
    effective_objective = _normalize_objective_hint(context.objective if context else None, tags.objectif)
    effective_domains = _unique((context.domains if context and context.domains else []) + list(tags.domaine))
    effective_impacts = _unique((context.impacts if context and context.impacts else []) + list(tags.impact))
    flattened_tags = _unique((context.tags if context and context.tags else []) + [tags.objectif, *tags.domaine, *tags.impact, tags.origine])
    phase = context.phase if context else "SG-1"
    status = context.status if context else "Draft"
    return effective_objective, effective_domains, effective_impacts, flattened_tags, phase, status


def _pitch_has_customer_experience_signal(pitch: str) -> bool:
    """Detect whether the pitch hints at UX or customer-experience outcomes."""
    lowered = pitch.lower()
    return any(keyword in lowered for keyword in _CUSTOMER_EXPERIENCE_HINTS)


def _pitch_has_data_readiness_signal(pitch: str, domains: list[str]) -> bool:
    """Detect whether suggestions should emphasize data readiness."""
    lowered = pitch.lower()
    return "Data" in domains or any(keyword in lowered for keyword in _DATA_READINESS_HINTS)


def _pitch_has_process_signal(pitch: str, domains: list[str]) -> bool:
    """Detect operational workflow/process hints for recommendation categories."""
    lowered = pitch.lower()
    return "Operations" in domains or any(keyword in lowered for keyword in _DELIVERY_HINTS)


def _suggestion(
    *,
    identifier: str,
    title: str,
    category: str,
    explanation: str,
    improved_pitch: str | None,
    next_action: str,
    confidence: str,
    action_type: str,
    suggested_tags: list[str] | None = None,
) -> Suggestion:
    """Create a normalized suggestion object with legacy text compatibility."""
    return Suggestion(
        id=identifier,
        title=title,
        category=category,
        explanation=_normalize_pitch(explanation),
        improved_pitch=_normalize_pitch(improved_pitch) if improved_pitch else None,
        next_action=_normalize_pitch(next_action),
        confidence=confidence,
        action_type=action_type,
        suggested_tags=suggested_tags or [],
    )


def _build_suggestions(
    pitch: str,
    tags: Tags,
    horizon: HorizonValue | None,
    context: _LiveSuggestionContext | None,
) -> list[Suggestion]:
    """Build deterministic English smart suggestions from the current SG-1 context."""
    lowered = pitch.lower()
    objective, domains, impacts, _flattened_tags, phase, status = _effective_context(pitch, tags, horizon, context)
    metric_hint = _extract_metric_hint(pitch, objective)
    scope_hint = _scope_hint(domains)
    horizon_phrase = _horizon_phrase(horizon)
    objective_action = _objective_action(objective)
    impact_phrase = _impact_phrase(impacts)
    benchmark_hint = _benchmark_hint(objective, impacts)
    short_pitch = len(pitch.strip()) < 28 or len(pitch.split()) <= 4
    cx_signal = _pitch_has_customer_experience_signal(pitch)
    data_signal = _pitch_has_data_readiness_signal(pitch, domains)
    process_signal = _pitch_has_process_signal(pitch, domains)

    improved_outcome_pitch = (
        "Improve the mobile user experience to reduce task completion time, increase conversion rate, and lower support requests."
        if cx_signal and "mobile" in lowered
        else f"We want to {objective_action} with a measurable target of {metric_hint} for {scope_hint} {horizon_phrase}."
    )
    kpi_pitch = (
        "Improve the mobile experience with measurable KPIs across conversion, completion time, abandonment, and support demand."
        if cx_signal
        else f"Improve the initiative definition with named KPIs, ownership, and a measurable target of {metric_hint}."
    )

    suggestions: list[Suggestion] = [
        _suggestion(
            identifier="smart-business-framing",
            title="Clarify the measurable business outcome" if short_pitch else "Strengthen the business framing",
            category="Business Framing",
            explanation="The current pitch is directionally useful, but it does not yet describe the measurable business outcome, the impacted journey, or the operating scope clearly enough for SG-1 validation.",
            improved_pitch=improved_outcome_pitch,
            next_action="Add the target journey, the owning team, and the baseline-to-target KPI you want to improve before moving forward.",
            confidence="high" if short_pitch else "medium",
            action_type="apply_pitch",
        ),
        _suggestion(
            identifier="smart-kpi-definition",
            title="Define KPI names before target values",
            category="KPI Definition",
            explanation="The need should name the KPI family first, then let DXC confirm the baseline and target during qualification rather than inventing values too early.",
            improved_pitch=kpi_pitch,
            next_action="Add KPI names such as conversion rate, task completion time, abandonment rate, support-ticket volume, CSAT, or cost per transaction, then provide the current baseline and desired target.",
            confidence="high",
            action_type="copy",
        ),
    ]

    if cx_signal and "CustomerExperience" not in impacts:
        suggestions.append(
            _suggestion(
                identifier="smart-impact-review",
                title="Review the impact classification",
                category="Customer Experience",
                explanation="The wording points to user experience, journey friction, and time-to-completion, so the current impact profile may be too narrow if it only emphasizes cost.",
                improved_pitch="Improve mobile UX to increase customer satisfaction and reduce the time required to complete key user journeys.",
                next_action="Consider adding CustomerExperience alongside Cost if the initiative is meant to improve satisfaction, self-service adoption, journey efficiency, or digital conversion.",
                confidence="medium",
                action_type="apply_tag",
                suggested_tags=["CustomerExperience"],
            )
        )

    if data_signal:
        suggestions.append(
            _suggestion(
                identifier="smart-data-readiness",
                title="Specify the evidence source for the need",
                category="Data Readiness",
                explanation="The delivery team will need usage analytics, journey telemetry, or operational data to prove the before-and-after outcome and avoid a subjective redesign discussion.",
                improved_pitch="Improve the business need by referencing the analytics source, the tracked journey, and the reporting signal that will validate the expected outcome.",
                next_action="Name the main data source to use during qualification, such as mobile analytics, CRM, support tickets, event telemetry, or journey reporting.",
                confidence="medium",
                action_type="copy",
            )
        )
    else:
        suggestions.append(
            _suggestion(
                identifier="smart-delivery-readiness",
                title="Frame the next SG-1 delivery question",
                category="Delivery Readiness" if not process_signal else "Process Improvement",
                explanation=f"The current statement is not yet specific enough to decide what should enter discovery, who owns the scope, or how {phase} in {status} status should be validated.",
                improved_pitch=f"Refine the need so it names the business scope, the first discovery priority, and the decision criteria needed to move from {phase} to the next stage gate.",
                next_action="List the top in-scope journey, the process owner, the main constraint, and the first discovery question DXC should answer.",
                confidence="medium",
                action_type="copy",
            )
        )

    if "Cost" in impacts or objective == "cost_reduction":
        suggestions.append(
            _suggestion(
                identifier="smart-value-angle",
                title="Link the request to a business value narrative",
                category="Cost Optimization" if "Cost" in impacts else "Value Angle",
                explanation=f"The initiative will be easier to approve if the pitch connects the proposed change to {impact_phrase} and to the KPI set that matters in similar DXC engagements.",
                improved_pitch=f"Position the need as a lever to {objective_action}, with value demonstrated through {benchmark_hint} and governed through a DXC-ready delivery model.",
                next_action="State which business value story matters most now: lower cost-to-serve, better conversion, reduced support demand, higher productivity, or lower operational risk.",
                confidence="medium",
                action_type="copy",
            )
        )

    return suggestions[:4]


def _parse_suggestion_payload(payload: Any) -> list[Suggestion]:
    """Accept structured smart-suggestion payloads while tolerating older formats."""
    suggestions: list[Suggestion] = []
    if isinstance(payload, dict):
        raw_suggestions = payload.get("suggestions", payload.get("smart_suggestions", []))
        if isinstance(raw_suggestions, list):
            payload = raw_suggestions

    if isinstance(payload, list):
        for index, item in enumerate(payload, start=1):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", item.get("label", "")) or "").strip()
            category = str(item.get("category", "Business Framing") or "Business Framing").strip()
            explanation = str(item.get("explanation", item.get("text", "")) or "").strip()
            next_action = str(item.get("next_action", "") or "").strip()
            improved_pitch = str(item.get("improved_pitch", "") or "").strip() or None
            confidence = str(item.get("confidence", "medium") or "medium").strip().lower()
            action_type = str(item.get("action_type", "copy") or "copy").strip()

            if not title or not explanation or not next_action:
                continue
            if category not in _SMART_SUGGESTION_CATEGORIES:
                category = "Business Framing"
            if confidence not in _CONFIDENCE_ORDER:
                confidence = "medium"
            if action_type not in {"copy", "apply_pitch", "apply_tag", "none"}:
                action_type = "copy"

            suggestions.append(
                _suggestion(
                    identifier=str(item.get("id", f"smart-{index:03d}")),
                    title=title,
                    category=category,
                    explanation=explanation,
                    improved_pitch=improved_pitch,
                    next_action=next_action,
                    confidence=confidence,
                    action_type=action_type,
                    suggested_tags=[
                        str(tag).strip()
                        for tag in (item.get("suggested_tags", []) if isinstance(item.get("suggested_tags", []), list) else [])
                        if str(tag).strip()
                    ],
                )
            )
    return suggestions


def _quality_control_suggestions(
    pitch: str,
    tags: Tags,
    horizon: HorizonValue | None,
    context: _LiveSuggestionContext | None,
    suggestions: list[Suggestion],
) -> list[Suggestion]:
    """Replace missing, non-English, or generic suggestions with deterministic fallbacks."""
    fallbacks = _build_suggestions(pitch, tags, horizon, context)
    generic_markers = (
        "please provide more details",
        "be more specific",
        "improve clarity",
        "add more detail",
        "state the objective",
        "quantify the value",
        "keep typing",
        "clarify the context",
    )
    french_markers = (" le ", " la ", " les ", " des ", " pour ", " avec ", " dans ", " donnees", " couts")
    pitch_has_number = bool(re.search(r"\d", pitch))
    suggestions_by_id = {suggestion.id: suggestion for suggestion in suggestions}

    validated: list[Suggestion] = []
    for fallback in fallbacks:
        candidate = suggestions_by_id.get(fallback.id) or next(
            (item for item in suggestions if item.category == fallback.category),
            None,
        )
        if candidate is None:
            validated.append(fallback)
            continue

        combined_text = " ".join(
            part for part in [
                candidate.title,
                candidate.explanation,
                candidate.improved_pitch or "",
                candidate.next_action,
            ] if part
        ).strip()
        lowered = f" {combined_text.lower()} "
        contains_french = any(marker in lowered for marker in french_markers) or bool(re.search(r"[àâçéèêëîïôûùüÿœ]", lowered))
        contains_unverified_numbers = (not pitch_has_number) and bool(re.search(r"\b\d+(?:[.,]\d+)?\b", combined_text))
        mentions_dx_claim = "dxc" in lowered and any(token in lowered for token in ("saved", "reduced", "improved by", "%"))
        if (
            len(combined_text) < 120
            or _sentence_count(candidate.explanation) < 1
            or any(marker in lowered for marker in generic_markers)
            or contains_french
            or contains_unverified_numbers
            or mentions_dx_claim
        ):
            validated.append(fallback)
            continue

        validated.append(
            candidate.model_copy(
                update={
                    "title": candidate.title.strip(),
                    "explanation": _normalize_pitch(candidate.explanation),
                    "improved_pitch": _normalize_pitch(candidate.improved_pitch) if candidate.improved_pitch else None,
                    "next_action": _normalize_pitch(candidate.next_action),
                }
            )
        )
    return validated[:4]


def _prompt_ready_tags(values: list[str], fallback: str) -> str:
    """Format tag arrays for prompt injection."""
    return ", ".join(values) if values else fallback


async def _generate_suggestions_with_llm(
    pitch: str,
    horizon: HorizonValue | None,
    tags: Tags,
    context: _LiveSuggestionContext | None,
) -> list[Suggestion]:
    """Generate higher-quality business suggestions with a dedicated prompt."""
    objective, domains, impacts, flattened_tags, phase, status = _effective_context(pitch, tags, horizon, context)
    response = await llm_client.complete(
        prompt_name="pitch-suggestions",
        variables={
            "pitch": pitch,
            "domain_tags": _prompt_ready_tags(domains, "Autre"),
            "objective": _OBJECTIVE_PROMPT_LABELS.get(objective, objective),
            "impact_tags": _prompt_ready_tags(impacts, "Cost"),
            "horizon": _HORIZON_PROMPT_LABELS.get(horizon, "not specified"),
            "nlp_tags": _prompt_ready_tags(flattened_tags, "none"),
            "phase": phase,
            "status": status,
            "explicit_intent": _extract_intent_rule(tags, "Explicit intent:"),
            "implicit_intent": _extract_intent_rule(tags, "Implicit intent:"),
            "strategic_intent": _extract_intent_rule(tags, "DXC strategic intent:"),
        },
        response_format="json",
    )
    parsed = llm_client.parse_json_response(response)
    suggestions = _parse_suggestion_payload(parsed)
    return _quality_control_suggestions(pitch, tags, horizon, context, suggestions)


def _first_matching_keyword(text: str, keywords: list[str]) -> str | None:
    """Return the first keyword present in text for explainable intent traces."""
    for keyword in keywords:
        if keyword in text:
            return keyword
    return None


def _unique(values: list[str]) -> list[str]:
    """Preserve order while removing duplicates."""
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values


def _coerce_confidence(value: Any) -> str | None:
    """Return a valid confidence label when present."""
    if isinstance(value, str) and value in _CONFIDENCE_ORDER:
        return value
    return None


def _coerce_confidence_map(raw: Any) -> dict[str, str]:
    """Extract confidence maps from dicts or [{value, confidence}] arrays."""
    if isinstance(raw, dict) and isinstance(raw.get("value"), str):
        confidence = _coerce_confidence(raw.get("confidence"))
        return {raw["value"]: confidence} if confidence else {}

    if isinstance(raw, dict):
        return {
            str(key): confidence
            for key, value in raw.items()
            if (confidence := _coerce_confidence(value))
        }

    if isinstance(raw, list):
        extracted: dict[str, str] = {}
        for item in raw:
            if not isinstance(item, dict):
                continue
            value = item.get("value")
            confidence = _coerce_confidence(item.get("confidence"))
            if isinstance(value, str) and confidence:
                extracted[value] = confidence
        return extracted

    return {}


def _coerce_scalar(value: Any, allowed: tuple[str, ...]) -> str | None:
    """Validate a single enum-like value."""
    if isinstance(value, dict):
        value = value.get("value")
    if isinstance(value, str) and value in allowed:
        return value
    if isinstance(value, str) and value == "initiative_strategique" and "enjeu_marche" in allowed:
        return "enjeu_marche"
    return None


def _tag_value(raw: dict[str, Any], *keys: str) -> Any:
    """Return the first present tag field across legacy and nested contracts."""
    for key in keys:
        if key in raw:
            return raw.get(key)
    return None


def _tag_confidence(raw: dict[str, Any], value_key: str, confidence_key: str) -> str | None:
    """Read confidence from either a sibling field or a nested {value, confidence} object."""
    direct = _coerce_confidence(raw.get(confidence_key))
    if direct:
        return direct
    nested = raw.get(value_key)
    if isinstance(nested, dict):
        return _coerce_confidence(nested.get("confidence"))
    return None


def _normalize_raw_tag_payload(raw_tags: dict[str, Any] | Tags | None) -> dict[str, Any]:
    """Accept both legacy tags and the new nested prompt contract."""
    source = raw_tags.model_dump() if isinstance(raw_tags, Tags) else raw_tags or {}
    source_tags = source.get("tags") if isinstance(source.get("tags"), dict) else source
    source_tags = source_tags if isinstance(source_tags, dict) else {}

    objective = _tag_value(source_tags, "objectif", "objective")
    origin = _tag_value(source_tags, "origine", "origin")
    domain = _tag_value(source_tags, "domaine", "domain")
    impact = _tag_value(source_tags, "impact")
    gap_constraints = source_tags.get("gap_analysis_constraints") if isinstance(source_tags.get("gap_analysis_constraints"), dict) else source_tags.get("gapAnalysisConstraints")

    normalized: dict[str, Any] = {
        "objectif": objective,
        "objectif_confidence": _tag_confidence(source_tags, "objectif", "objectif_confidence")
        or _tag_confidence(source_tags, "objective", "objective_confidence"),
        "domaine": domain,
        "domaine_confidence": source_tags.get("domaine_confidence")
        if isinstance(source_tags.get("domaine_confidence"), (dict, list))
        else (
            source_tags.get("domain_confidence")
            if isinstance(source_tags.get("domain_confidence"), (dict, list))
            else domain
        ),
        "impact": impact,
        "impact_confidence": source_tags.get("impact_confidence")
        if isinstance(source_tags.get("impact_confidence"), (dict, list))
        else impact,
        "origine": origin,
        "origine_confidence": _tag_confidence(source_tags, "origine", "origine_confidence")
        or _tag_confidence(source_tags, "origin", "origin_confidence"),
        "gap_analysis_constraints": gap_constraints if isinstance(gap_constraints, dict) else {},
        "horizon_conflict": bool(source_tags.get("horizon_conflict", source_tags.get("horizonConflict", False))),
    }
    return normalized


def _coerce_list(value: Any, allowed: tuple[str, ...]) -> list[str]:
    """Validate enum-like lists while tolerating object items."""
    items = value if isinstance(value, list) else [value]
    normalized: list[str] = []
    for item in items:
        if isinstance(item, dict):
            item = item.get("value")
        if isinstance(item, str) and item in allowed and item not in normalized:
            normalized.append(item)
    return normalized


def _best_label(scores: dict[str, int], default: str) -> str:
    """Return the highest-scoring label or a safe default."""
    if not scores:
        return default
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else default


def _confidence_from_score(score: int) -> str:
    """Translate a simple score into a confidence bucket."""
    if score >= 3:
        return "high"
    if score >= 1:
        return "medium"
    return "low"


def _objective_confidence(selected: str, scores: dict[str, int]) -> str:
    """Estimate objective confidence from separation vs runner-up."""
    ranked_scores = sorted(scores.values(), reverse=True)
    selected_score = scores.get(selected, 0)
    runner_up = ranked_scores[1] if len(ranked_scores) > 1 else 0

    if selected_score >= 2 and (selected_score - runner_up) >= 1:
        return "high"
    if selected_score >= 1:
        return "medium"
    return "low"


def _confidence_from_rank(selected: str, scores: dict[str, int]) -> str:
    """Estimate confidence using the selected score and separation from alternatives."""
    selected_score = scores.get(selected, 0)
    ranked_values = sorted(scores.values(), reverse=True)
    runner_up = ranked_values[1] if len(ranked_values) > 1 else 0
    if selected_score >= 3 and (selected_score - runner_up) >= 1:
        return "high"
    if selected_score >= 1:
        return "medium"
    return "low"


def _matched_keywords(text: str, keywords: list[str]) -> list[str]:
    """Return the ordered keywords that appear in the pitch."""
    return [keyword for keyword in keywords if keyword in text]


def _legacy_domain_to_structured(domains: list[str]) -> str:
    """Provide a deterministic fallback domain mapping for the SG-1 typed view."""
    if "IA" in domains:
        return "IA"
    if "Data" in domains:
        return "Data"
    if "Operations" in domains:
        return "Process"
    if "Cloud" in domains or "Cybersecurite" in domains:
        return "IT"
    if any(domain in domains for domain in ("RH", "Finance")):
        return "Business"
    return "autre"


def _infer_structured_source(
    *,
    pitch: str,
    lowered_pitch: str,
    measurable_result_detected: bool,
    named_client_detected: bool,
) -> SourcingSourceTag:
    """Build the SG-1 source tag with deterministic business rules and reason."""
    resolved = resolve_origin(pitch)
    if resolved["value"] == "demande_client":
        reason = (
            "Un client est cite explicitement dans le pitch; la source est donc classee comme demande_client."
        )
        if measurable_result_detected:
            reason = (
                "Le pitch mentionne un resultat mesurable et cite explicitement un client; la regle d'exception classe donc la source comme demande_client."
            )
        return SourcingSourceTag(value="demande_client", confidence=resolved["confidence"], reason=reason)

    if resolved["value"] == "probleme_operationnel":
        return SourcingSourceTag(
            value="probleme_operationnel",
            confidence=resolved["confidence"],
            reason=(
                "Le pitch contient un resultat mesurable lie a une amelioration ou un ecart operationnel; la source est donc classee comme probleme_operationnel."
            ),
        )

    if any(keyword in lowered_pitch for keyword in _STRUCTURED_SOURCE_KEYWORDS["innovation_interne"]):
        return SourcingSourceTag(
            value="innovation_interne",
            confidence="high",
            reason=(
                "Le pitch met en avant une experimentation ou une innovation interne explicite plutot qu'une demande client ou un incident operationnel."
            ),
        )

    source_scores = {
        "probleme_operationnel": _score_keywords(lowered_pitch, {"probleme_operationnel": _ORIGINE_KEYWORDS["probleme_operationnel"]})["probleme_operationnel"],
        "demande_client": _score_keywords(lowered_pitch, {"demande_client": _ORIGINE_KEYWORDS["demande_client"]})["demande_client"],
        "opportunite_marche": _score_keywords(lowered_pitch, {"opportunite_marche": _STRUCTURED_SOURCE_KEYWORDS["opportunite_marche"]})["opportunite_marche"],
        "innovation_interne": _score_keywords(lowered_pitch, {"innovation_interne": _STRUCTURED_SOURCE_KEYWORDS["innovation_interne"]})["innovation_interne"],
        "autre": 0,
    }
    selected = _best_label(source_scores, "autre")
    confidence = _confidence_from_rank(selected, source_scores)
    matched = _matched_keywords(lowered_pitch, _STRUCTURED_SOURCE_KEYWORDS.get(selected, _ORIGINE_KEYWORDS.get(selected, [])))
    keyword_text = matched[0] if matched else "les signaux du pitch"
    reason_map = {
        "probleme_operationnel": f"La classification s'appuie sur des indices operationnels comme '{keyword_text}'.",
        "demande_client": f"La classification s'appuie sur des indices de demande client comme '{keyword_text}'.",
        "opportunite_marche": f"La classification s'appuie sur des indices de marche ou de croissance comme '{keyword_text}'.",
        "innovation_interne": f"La classification s'appuie sur des indices d'innovation interne comme '{keyword_text}'.",
        "autre": "Le pitch reste ambigu sur l'origine et ne contient pas assez de signaux directs pour une classe plus precise.",
    }
    return SourcingSourceTag(value=selected, confidence=confidence, reason=reason_map[selected])


def _infer_structured_domain(
    *,
    lowered_pitch: str,
    legacy_domains: list[str],
    inference_explicit: bool,
) -> SourcingDomainTag:
    """Build the SG-1 domain tag while enforcing the IA/Data disambiguation rule."""
    data_matches = _matched_keywords(lowered_pitch, _STRUCTURED_DOMAIN_KEYWORDS["Data"])
    if "predictive analytics" in lowered_pitch or "predictive-analytics" in lowered_pitch:
        data_matches = [match for match in data_matches if match != "analytics"]
    if inference_explicit:
        matched = _matched_keywords(lowered_pitch, _DOMAIN_KEYWORDS["IA"])
        keyword_text = matched[0] if matched else "une etape d'inference explicite"
        return SourcingDomainTag(
            value="IA",
            confidence="medium" if data_matches else "high",
            reason=(
                (
                    f"Le pitch decrit explicitement une etape d'inference ou de prediction via '{keyword_text}'. "
                    f"Des signaux Data comme '{data_matches[0]}' sont aussi presents, donc IA reste prioritaire avec une confiance medium."
                )
                if data_matches
                else f"Le pitch decrit explicitement une etape d'inference ou de prediction via '{keyword_text}', donc le domaine retenu est IA."
            ),
        )

    if data_matches:
        return SourcingDomainTag(
            value="Data",
            confidence="high",
            reason=(
                f"Le pitch parle de '{data_matches[0]}' sans etape d'inference explicite; la classification retenue est donc Data et non IA."
            ),
        )

    domain_scores = {
        "Data": _score_keywords(lowered_pitch, {"Data": _STRUCTURED_DOMAIN_KEYWORDS["Data"]})["Data"],
        "Process": _score_keywords(lowered_pitch, {"Process": _STRUCTURED_DOMAIN_KEYWORDS["Process"]})["Process"],
        "Business": _score_keywords(lowered_pitch, {"Business": _STRUCTURED_DOMAIN_KEYWORDS["Business"]})["Business"],
        "IT": _score_keywords(lowered_pitch, {"IT": _STRUCTURED_DOMAIN_KEYWORDS["IT"]})["IT"],
        "autre": 0,
    }
    if all(score == 0 for score in domain_scores.values()):
        fallback = _legacy_domain_to_structured(legacy_domains)
        confidence = "medium" if fallback != "autre" else "low"
        reason = (
            f"La classification reprend les signaux metier deja detectes ({', '.join(legacy_domains)}) pour alimenter le Gap Analysis."
            if fallback != "autre"
            else "Le pitch ne contient pas assez d'indices pour distinguer un domaine unique avec certitude."
        )
        return SourcingDomainTag(value=fallback, confidence=confidence, reason=reason)

    selected = _best_label(domain_scores, "autre")
    confidence = _confidence_from_rank(selected, domain_scores)
    matched = _matched_keywords(lowered_pitch, _STRUCTURED_DOMAIN_KEYWORDS.get(selected, []))
    keyword_text = matched[0] if matched else "les signaux dominants du pitch"
    reason_map = {
        "Data": f"Le pitch met surtout l'accent sur la donnee et le reporting via '{keyword_text}'.",
        "Process": f"Le pitch met surtout l'accent sur le processus ou le workflow via '{keyword_text}'.",
        "Business": f"Le pitch met surtout l'accent sur les enjeux metier via '{keyword_text}'.",
        "IT": f"Le pitch met surtout l'accent sur la plateforme ou l'infrastructure IT via '{keyword_text}'.",
        "autre": "Le pitch reste trop transversal pour isoler un domaine unique avec un bon niveau de certitude.",
    }
    return SourcingDomainTag(value=selected, confidence=confidence, reason=reason_map[selected])


def _structured_objective_base_scores(
    *,
    lowered_pitch: str,
    legacy_objectif: str,
) -> dict[str, int]:
    """Score the SG-1 typed objective before horizon bias is applied."""
    scores = {
        key: _score_keywords(lowered_pitch, {key: keywords})[key]
        for key, keywords in _STRUCTURED_OBJECTIVE_KEYWORDS.items()
    }
    legacy_bias = {
        "cost_reduction": {"optimisation_operationnelle": 1, "reduction_couts": 2},
        "cx_improvement": {"amelioration_qualite": 2},
        "risk_mitigation": {"amelioration_qualite": 2},
        "market_opportunity": {"innovation": 1, "transformation_strategique": 2},
    }.get(legacy_objectif, {})
    for key, delta in legacy_bias.items():
        scores[key] = scores.get(key, 0) + delta
    return scores


def _best_structured_objective(scores: dict[str, int]) -> str:
    return _best_label(scores, "autre")


def _infer_structured_objective(
    *,
    lowered_pitch: str,
    legacy_objectif: str,
    horizon: HorizonValue | None,
) -> SourcingObjectiveTag:
    """Build the SG-1 typed objective while tracking whether horizon changed the outcome."""
    base_scores = _structured_objective_base_scores(
        lowered_pitch=lowered_pitch,
        legacy_objectif=legacy_objectif,
    )
    biased_scores = dict(base_scores)
    horizon_bias = _STRUCTURED_OBJECTIVE_HORIZON_BIAS.get(horizon or "", {})
    for key, delta in horizon_bias.items():
        biased_scores[key] = biased_scores.get(key, 0) + delta

    base_choice = _best_structured_objective(base_scores)
    selected = _best_structured_objective(biased_scores)
    confidence = _confidence_from_rank(selected, biased_scores)
    influenced_by_horizon = bool(horizon and horizon_bias.get(selected, 0) > 0 and selected != "autre")

    matched = _matched_keywords(lowered_pitch, _STRUCTURED_OBJECTIVE_KEYWORDS.get(selected, []))
    keyword_text = matched[0] if matched else legacy_objectif
    reason = f"L'objectif est surtout aligne sur '{selected}' a partir de l'indice '{keyword_text}'."
    if influenced_by_horizon and selected != base_choice:
        reason = (
            f"L'horizon '{horizon}' a oriente la classification vers '{selected}' alors que le pitch seul pointait plutot vers '{base_choice}'."
        )
    elif influenced_by_horizon:
        reason = (
            f"L'horizon '{horizon}' renforce l'orientation '{selected}' deja visible dans le pitch, en plus de l'indice '{keyword_text}'."
        )

    return SourcingObjectiveTag(
        value=selected,
        confidence=confidence,
        reason=reason,
        influencedByHorizon=influenced_by_horizon,
    )


def _build_ambiguity_flags(
    source: SourcingSourceTag,
    domain: SourcingDomainTag,
    objective: SourcingObjectiveTag,
) -> list[SourcingAmbiguityFlag]:
    """Expose low/medium confidence decisions for SG-1 and Gap Analysis."""
    flags: list[SourcingAmbiguityFlag] = []
    for field, tag in (
        ("source", source),
        ("domain", domain),
        ("objective", objective),
    ):
        if tag.confidence in {"low", "medium"}:
            flags.append(
                SourcingAmbiguityFlag(
                    field=field,
                    confidence=tag.confidence,
                    reason=tag.reason,
                )
            )
    return flags


def _apply_horizon_bias(
    horizon: HorizonValue | None,
    objectif_scores: dict[str, int],
    impact_scores: dict[str, int],
    origin_scores: dict[str, int],
) -> None:
    """Use the selected horizon as an intent-strength signal without changing enums."""
    if horizon == "court_terme":
        objectif_scores["cost_reduction"] = objectif_scores.get("cost_reduction", 0) + 1
        impact_scores["Cost"] = impact_scores.get("Cost", 0) + 1
        origin_scores["probleme_operationnel"] = origin_scores.get("probleme_operationnel", 0) + 1
    elif horizon == "moyen_terme":
        objectif_scores["cx_improvement"] = objectif_scores.get("cx_improvement", 0) + 1
        impact_scores["CustomerExperience"] = impact_scores.get("CustomerExperience", 0) + 1
    elif horizon == "long_terme":
        objectif_scores["market_opportunity"] = objectif_scores.get("market_opportunity", 0) + 1
        impact_scores["Revenue"] = impact_scores.get("Revenue", 0) + 1
        origin_scores["enjeu_marche"] = origin_scores.get("enjeu_marche", 0) + 1


def _infer_intent_signals(
    lowered_pitch: str,
    objectif: str,
    domains: list[str],
    impacts: list[str],
    horizon: HorizonValue | None,
    measurable_result_detected: bool,
    inference_explicit: bool,
) -> _IntentSignals:
    """Build explicit, implicit, and DXC-strategic intent statements for prompt reuse."""
    explicit_keyword = _first_matching_keyword(
        lowered_pitch,
        _OBJECTIF_KEYWORDS.get(objectif, []),
    )
    domain_anchor = ", ".join(domains[:2]) if domains else "Autre"
    impact_anchor = ", ".join(impacts[:2]) if impacts else "Cost"

    if explicit_keyword:
        explicit_intent = (
            f"Explicit intent: the pitch directly emphasizes '{explicit_keyword}'"
            f" and points to '{objectif}' within the '{domain_anchor}' context."
        )
    else:
        explicit_intent = (
            f"Explicit intent: the pitch does not name the taxonomy directly,"
            f" so use the strongest visible business cues for '{objectif}'."
        )

    implicit_signals: list[str] = [
        f"Treat the likely business value as '{impact_anchor}'.",
        f"Use horizon '{horizon or 'not_specified'}' as a prioritization cue.",
    ]
    if measurable_result_detected:
        implicit_signals.append(
            "A measurable target is present, which reinforces an operational execution intent."
        )
    if inference_explicit:
        implicit_signals.append(
            "Inference or prediction is explicit, so AI can be retained as a genuine capability signal."
        )
    else:
        implicit_signals.append(
            "No explicit inference step is present, so AI must not be introduced as an assumed capability."
        )

    strategic_intent = _DXC_STRATEGIC_INTENTS.get(
        objectif,
        "Position the need around business value, delivery clarity, and reusable transformation outcomes for DXC.",
    )

    return _IntentSignals(
        explicit_intent=explicit_intent,
        implicit_intent="Implicit intent: " + " ".join(implicit_signals),
        strategic_intent="DXC strategic intent: " + strategic_intent,
    )


def _max_confidence(left: str, right: str) -> str:
    """Keep the strongest of two confidence values."""
    return left if _CONFIDENCE_ORDER[left] >= _CONFIDENCE_ORDER[right] else right


def _contains_measurable_result(text: str) -> bool:
    """Detect percentages, KPIs, durations, or explicit target deltas."""
    return any(pattern.search(text) for pattern in _MEASURABLE_PATTERNS)


def _mentions_named_client(text: str) -> bool:
    """Detect client names only when a relationship cue is present."""
    return any(pattern.search(text) for pattern in _NAMED_CLIENT_PATTERNS)


def _has_client_relationship(text: str) -> bool:
    """Capture explicit client-driven wording."""
    return any(
        cue in text
        for cue in (
            "client",
            "customer",
            "for client",
            "pour client",
            "account",
            "compte",
            "chez",
        )
    )


def _has_explicit_ai_inference(text: str) -> bool:
    """Allow the IA tag only for explicit inference or prediction steps."""
    return any(pattern.search(text) for pattern in _AI_INFERENCE_PATTERNS)


def _has_explicit_reduction_goal(text: str) -> bool:
    """Detect an explicit reduction target that should favor cost/efficiency objectives."""
    return bool(
        re.search(
            r"\b(reduce|reducing|reduction|lower|cut|decrease|save|saving|réduire|reduction|baisse|econom|économ)\w*\b",
            text,
            re.IGNORECASE,
        )
    )


def _has_customer_outcome_signal(text: str) -> bool:
    """Detect explicit customer-outcome language for impact enrichment."""
    lowered = text.lower()
    return any(token in lowered for token in ("customer", "client", "churn", "retention", "self-service", "satisfaction", "journey", "experience"))


def resolve_origin(pitch: str) -> dict[str, str]:
    """Resolve origin deterministically before any LLM call."""
    lowered_pitch = pitch.lower()
    has_measurable = _contains_measurable_result(lowered_pitch)
    has_named_client = _mentions_named_client(pitch)
    has_client_relationship = _has_client_relationship(lowered_pitch)

    if has_measurable and not has_named_client:
        return {"value": "probleme_operationnel", "confidence": "high"}
    if has_named_client and has_client_relationship:
        return {"value": "demande_client", "confidence": "high"}
    return {"value": "enjeu_marche", "confidence": "medium"}


def normalize_tags(
    pitch: str,
    horizon: HorizonValue | None,
    raw_tags: dict[str, Any] | Tags | None = None,
) -> Tags:
    """Normalize raw tags and attach prompt-ready gap analysis constraints."""
    lowered = pitch.strip().lower()
    source_tags = _normalize_raw_tag_payload(raw_tags)

    objectif_scores = _score_keywords(lowered, _OBJECTIF_KEYWORDS)
    domain_scores = _score_keywords(lowered, _DOMAIN_KEYWORDS)
    impact_scores = _score_keywords(lowered, _IMPACT_KEYWORDS)
    origin_scores = _score_keywords(lowered, _ORIGINE_KEYWORDS)
    _apply_horizon_bias(horizon, objectif_scores, impact_scores, origin_scores)

    measurable_result_detected = _contains_measurable_result(lowered)
    named_client_detected = _mentions_named_client(pitch)
    inference_explicit = _has_explicit_ai_inference(lowered)
    explicit_reduction_goal = _has_explicit_reduction_goal(pitch)
    customer_outcome_signal = _has_customer_outcome_signal(pitch)

    if measurable_result_detected and explicit_reduction_goal:
        objectif_scores["cost_reduction"] = objectif_scores.get("cost_reduction", 0) + 3
        impact_scores["Cost"] = impact_scores.get("Cost", 0) + 3
    if customer_outcome_signal:
        impact_scores["CustomerExperience"] = impact_scores.get("CustomerExperience", 0) + 1

    objectif = _coerce_scalar(source_tags.get("objectif"), _OBJECTIF_VALUES)
    if not objectif:
        objectif = _best_label(objectif_scores, "cost_reduction")
    objectif_confidence = _coerce_confidence(source_tags.get("objectif_confidence"))
    if not objectif_confidence:
        objectif_confidence = _objective_confidence(objectif, objectif_scores)
    if objectif == "cost_reduction" and measurable_result_detected and explicit_reduction_goal:
        objectif_confidence = "high"

    domains = _coerce_list(source_tags.get("domaine"), _DOMAIN_VALUES)
    if not domains:
        domains = [
            label
            for label, score in sorted(
                domain_scores.items(),
                key=lambda item: item[1],
                reverse=True,
            )
            if score > 0
        ][:3]

    # Rule 2: IA only exists when inference or prediction is explicit.
    if inference_explicit:
        domains = ["IA", *[label for label in domains if label not in {"IA", "Data"}]]
    else:
        domains = [label for label in domains if label != "IA"]

    domains = _unique(domains)
    if not domains:
        fallback_domains = [
            label
            for label, score in sorted(
                domain_scores.items(),
                key=lambda item: item[1],
                reverse=True,
            )
            if score > 0 and (label != "IA" or inference_explicit)
        ][:3]
        domains = fallback_domains or ["Autre"]

    provided_domain_confidence = _coerce_confidence_map(
        source_tags.get("domaine_confidence")
    )
    domaine_confidence: dict[str, str] = {}
    for label in domains:
        heuristic_confidence = _confidence_from_score(domain_scores.get(label, 0))
        domaine_confidence[label] = (
            provided_domain_confidence.get(label) or heuristic_confidence
        )
        if label == "IA":
            domaine_confidence[label] = (
                "medium"
                if any(keyword in lowered for keyword in _STRUCTURED_DOMAIN_KEYWORDS["Data"])
                and "predictive analytics" not in lowered
                else _max_confidence(
                    domaine_confidence[label],
                    "high" if domain_scores.get("IA", 0) > 0 else "medium",
                )
            )

    impacts = _coerce_list(source_tags.get("impact"), _IMPACT_VALUES)
    if not impacts:
        impacts = [
            label
            for label, score in impact_scores.items()
            if score > 0
        ]

    if not impacts:
        impact_defaults = {
            "cost_reduction": ["Cost"],
            "cx_improvement": ["CustomerExperience"],
            "risk_mitigation": ["Risk"],
            "market_opportunity": ["Revenue"],
        }
        impacts = impact_defaults.get(objectif, ["Cost"])

    if measurable_result_detected and explicit_reduction_goal and "Cost" not in impacts:
        impacts = ["Cost", *impacts]
    if customer_outcome_signal and "CustomerExperience" not in impacts:
        impacts.append("CustomerExperience")

    provided_impact_confidence = _coerce_confidence_map(
        source_tags.get("impact_confidence")
    )
    impact_confidence: dict[str, str] = {}
    for label in impacts:
        heuristic_confidence = _confidence_from_score(impact_scores.get(label, 0))
        impact_confidence[label] = (
            provided_impact_confidence.get(label) or heuristic_confidence
        )
        if label == "Cost" and measurable_result_detected and explicit_reduction_goal:
            impact_confidence[label] = "high"
        elif label == "CustomerExperience" and customer_outcome_signal:
            impact_confidence[label] = "medium"
        if label in {"Cost", "CustomerExperience", "Risk", "Revenue"} and impact_scores.get(label, 0) == 0:
            impact_confidence[label] = _max_confidence(impact_confidence[label], "medium")

    origine = _coerce_scalar(source_tags.get("origine"), _ORIGINE_VALUES)
    if not origine:
        origine = _best_label(origin_scores, "probleme_operationnel")
    origine_confidence = _coerce_confidence(source_tags.get("origine_confidence"))
    if not origine_confidence:
        origine_confidence = _confidence_from_score(origin_scores.get(origine, 0))

    resolved_origin = resolve_origin(pitch)
    origine = _coerce_scalar(resolved_origin["value"], _ORIGINE_VALUES) or origine
    origine_confidence = resolved_origin["confidence"]

    structured_source = _infer_structured_source(
        pitch=pitch,
        lowered_pitch=lowered,
        measurable_result_detected=measurable_result_detected,
        named_client_detected=named_client_detected,
    )
    structured_domain = _infer_structured_domain(
        lowered_pitch=lowered,
        legacy_domains=domains,
        inference_explicit=inference_explicit,
    )
    structured_objective = _infer_structured_objective(
        lowered_pitch=lowered,
        legacy_objectif=objectif,
        horizon=horizon,
    )
    horizon_conflict = (
        structured_objective.value in _HORIZON_OBJECTIVE_CONFLICTS.get(horizon or "", set())
        or bool(source_tags.get("horizon_conflict"))
    )
    if horizon_conflict:
        objectif_confidence = "low"
        structured_objective = structured_objective.model_copy(
            update={
                "confidence": "low",
                "reason": (
                    f"The declared horizon '{horizon}' conflicts with the inferred objective '{structured_objective.value}'."
                ),
            }
        )
    ambiguity_flags = _build_ambiguity_flags(
        structured_source,
        structured_domain,
        structured_objective,
    )
    typed_constraints = SourcingGapAnalysisConstraints(
        source=structured_source.value,
        domain=structured_domain.value,
        objective=structured_objective.value,
        horizon=horizon,
        ambiguityFlags=ambiguity_flags,
    )
    sourcing_classification = SourcingClassification(
        source=structured_source,
        domain=structured_domain,
        objective=structured_objective,
        constraintsForGapAnalysis=typed_constraints,
    )

    intent_signals = _infer_intent_signals(
        lowered_pitch=lowered,
        objectif=objectif,
        domains=domains,
        impacts=impacts,
        horizon=horizon,
        measurable_result_detected=measurable_result_detected,
        inference_explicit=inference_explicit,
    )

    hard_rules = [
        "Treat this sourcing classification as a hard constraint for gap analysis.",
        f"Keep the primary objective anchored on '{objectif}'.",
        f"Respect the selected horizon: '{horizon or 'not_specified'}'.",
        (
            "Typed SG-1 constraints for gap analysis: "
            f"source='{structured_source.value}', domain='{structured_domain.value}', objective='{structured_objective.value}'."
        ),
        intent_signals.explicit_intent,
        intent_signals.implicit_intent,
        intent_signals.strategic_intent,
    ]
    if measurable_result_detected and not named_client_detected:
        hard_rules.append(
            "Because the pitch includes a measurable result without a named client, keep the origin as 'probleme_operationnel'."
        )
    if not inference_explicit:
        hard_rules.append(
            "Do not introduce AI, predictive, or generative requirements unless the pitch explicitly includes an inference or prediction step."
        )
    else:
        hard_rules.append(
            "If AI-related gaps are raised, tie them directly to the explicit inference or prediction step stated in the pitch."
        )
    if horizon in _HORIZON_GAP_RULES:
        hard_rules.append(_HORIZON_GAP_RULES[horizon])
    if horizon_conflict:
        hard_rules.append(
            f"Horizon conflict detected: keep objective confidence low because horizon '{horizon}' does not align cleanly with objective '{structured_objective.value}'."
        )
    if ambiguity_flags:
        hard_rules.append(
            "Ambiguity flags remain active on: "
            + ", ".join(flag.field for flag in ambiguity_flags)
            + "."
        )

    constraints = GapAnalysisConstraints(
        phase="SG-1",
        horizon=horizon,
        horizon_conflict=horizon_conflict,
        objectif=ClassifiedConstraint(
            value=objectif,
            confidence=objectif_confidence,
            reason=structured_objective.reason,
        ),
        domaine=[
            ClassifiedConstraint(
                value=label,
                confidence=domaine_confidence[label],
                reason=(
                    structured_domain.reason
                    if label == "IA" or (label == "Data" and structured_domain.value == "Data")
                    else f"Legacy domain '{label}' retained from pitch keyword analysis."
                ),
            )
            for label in domains
        ],
        impact=[
            ClassifiedConstraint(
                value=label,
                confidence=impact_confidence[label],
                reason=f"Impact '{label}' retained from business-value keyword analysis.",
            )
            for label in impacts
        ],
        origine=ClassifiedConstraint(
            value=origine,
            confidence=origine_confidence,
            reason=structured_source.reason,
        ),
        constraintsForGapAnalysis=typed_constraints,
        inference_explicit=inference_explicit,
        measurable_result_detected=measurable_result_detected,
        named_client_detected=named_client_detected,
        hard_rules=hard_rules,
    )

    return Tags(
        objectif=objectif,
        domaine=domains,
        impact=impacts,
        origine=origine,
        objectif_confidence=objectif_confidence,
        domaine_confidence=domaine_confidence,
        impact_confidence=impact_confidence,
        origine_confidence=origine_confidence,
        horizon_conflict=horizon_conflict,
        gap_analysis_constraints=constraints,
        sourcing_classification=sourcing_classification,
    )


def _analyze_pitch_locally(
    pitch: str,
    horizon: HorizonValue | None,
    context: _LiveSuggestionContext | None,
) -> tuple[Tags, list[Suggestion]]:
    """Return a deterministic fallback analysis when LLM access is unavailable."""
    tags = normalize_tags(pitch, horizon)
    suggestions = _build_suggestions(pitch, tags, horizon, context)
    return tags, suggestions


async def analyze_pitch(
    pitch: str,
    horizon: HorizonValue | None = None,
    *,
    objective: str | None = None,
    domains: list[str] | None = None,
    impacts: list[str] | None = None,
    tags: list[str] | None = None,
    phase: str | None = None,
    status: str | None = None,
) -> tuple[Tags, list[Suggestion]]:
    """Analyze a business need pitch and return structured tags and suggestions."""
    context = _normalize_live_suggestion_context(
        objective=objective,
        domains=domains,
        impacts=impacts,
        tags=tags,
        phase=phase,
        status=status,
    )
    cached = _get_cached(pitch, horizon, context)
    if cached:
        logger.debug("Cache hit for pitch analysis")
        return cached

    if not _llm_is_configured():
        logger.warning(
            "LLM provider is not configured. Using local fallback pitch analysis."
        )
        tags, suggestions = _analyze_pitch_locally(pitch, horizon, context)
        _set_cache(pitch, horizon, context, tags, suggestions)
        return tags, suggestions

    try:
        heuristic_tags = normalize_tags(pitch, horizon)
        resolved_origin = resolve_origin(pitch)
        intent_hard_rules = (
            heuristic_tags.gap_analysis_constraints.hard_rules
            if heuristic_tags.gap_analysis_constraints
            else []
        )
        response = await llm_client.complete(
            prompt_name="nlp_tagging",
            variables={
                "pitch": pitch,
                "horizon": horizon or "not_specified",
                "explicit_intent": intent_hard_rules[3] if len(intent_hard_rules) > 3 else "",
                "implicit_intent": intent_hard_rules[4] if len(intent_hard_rules) > 4 else "",
                "strategic_intent": intent_hard_rules[5] if len(intent_hard_rules) > 5 else "",
                "resolved_origin": resolved_origin["value"],
                "resolved_origin_confidence": resolved_origin["confidence"],
            },
            response_format="json",
        )
        parsed = llm_client.parse_json_response(response)
        logger.info("LLM response keys: %s", list(parsed.keys()))

        tags = normalize_tags(pitch, horizon, parsed)
        try:
            suggestions = await _generate_suggestions_with_llm(pitch, horizon, tags, context)
        except Exception as exc:
            logger.warning(
                "LLM suggestion generation failed (%s). Using deterministic suggestions.",
                exc,
            )
            suggestions = _build_suggestions(pitch, tags, horizon, context)

        logger.info("Generated %d suggestions for pitch (len=%d)", len(suggestions), len(pitch))
    except Exception as exc:
        logger.warning(
            "LLM pitch analysis failed (%s). Using local fallback analysis.",
            exc,
        )
        tags, suggestions = _analyze_pitch_locally(pitch, horizon, context)

    _set_cache(pitch, horizon, context, tags, suggestions)
    return tags, suggestions
