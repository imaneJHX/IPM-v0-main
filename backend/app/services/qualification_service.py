"""Deterministic helpers for qualification and gap-analysis scoring."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from app.data.dxc_profiles import DXC_PROFILES
from app.schemas.business_need import (
    GapAnalysisAudit,
    GapAnalysisResponse,
    GapCalibrationApplied,
    GapFeatureMatch,
    GapFeatureMissing,
    GapRecommendation,
    GapResourceNeed,
    GapRisk,
    GapAnalysisRuleAudit,
    GapContextCompressionAudit,
    IVIScoring,
    QualificationScoreDimension,
    QualificationScores,
    RequiredProfile,
    ScoredDimension,
    SourcingAmbiguityFlag,
    SourcingGapAnalysisConstraints,
    SolutionContextFiltered,
)

_TOKEN_RE = re.compile(r"[a-z0-9]{3,}")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?;])\s+")

_DOMAIN_KEYWORDS: dict[str, set[str]] = {
    "IA": {
        "agent", "agents", "ai", "automation", "chatbot", "copilot", "forecast",
        "genai", "generative", "llm", "ml", "model", "models", "nlp", "prediction",
    },
    "Cloud": {
        "api", "azure", "cloud", "container", "devops", "gcp", "hybrid", "iaas",
        "integration", "kubernetes", "migration", "platform", "saas", "serverless",
    },
    "Cybersecurite": {
        "audit", "compliance", "cyber", "fraud", "governance", "iam", "identity",
        "privacy", "risk", "secure", "security", "siem", "soc", "trust", "zero",
    },
    "Data": {
        "analytics", "bi", "dashboard", "data", "database", "dataset", "elt", "etl",
        "governance", "insight", "lake", "monitoring", "pipeline", "quality",
        "reporting", "warehouse",
    },
    "RH": {
        "candidate", "employee", "hiring", "hr", "human", "onboarding", "payroll",
        "recruitment", "talent", "workforce",
    },
    "Finance": {
        "accounting", "budget", "cost", "finance", "financial", "invoice", "payment",
        "profit", "roi", "treasury",
    },
    "Operations": {
        "capacity", "delivery", "logistics", "operations", "process", "production",
        "project", "procurement", "rpa", "supply", "workflow",
    },
    "Autre": set(),
}

_IMPACT_KEYWORDS: dict[str, set[str]] = {
    "Revenue": {
        "acquisition", "conversion", "cross", "growth", "market", "monetization",
        "revenue", "retention", "sales", "upsell", "win",
    },
    "Cost": {
        "automation", "cost", "efficiency", "manual", "optimization", "productivity",
        "reduce", "saving", "streamline", "time",
    },
    "Risk": {
        "audit", "compliance", "control", "fraud", "governance", "privacy", "risk",
        "secure", "security", "trust",
    },
    "CustomerExperience": {
        "client", "customer", "experience", "journey", "portal", "response",
        "satisfaction", "self", "service", "support",
    },
}

_OBJECTIVE_KEYWORDS: dict[str, set[str]] = {
    "cost_reduction": _IMPACT_KEYWORDS["Cost"] | {"effort", "operations"},
    "cx_improvement": _IMPACT_KEYWORDS["CustomerExperience"] | {"employee"},
    "risk_mitigation": _IMPACT_KEYWORDS["Risk"] | {"incident", "resilience"},
    "market_opportunity": _IMPACT_KEYWORDS["Revenue"] | {"innovation", "launch"},
}

_DATA_RISK_KEYWORDS = {
    "api", "data", "database", "governance", "integration", "mapping", "privacy",
    "quality", "security", "source",
}

_MATURITY_ALIASES: dict[str, str] = {
    "ga": "production",
    "general availability": "production",
    "live": "production",
    "production": "production",
    "prod": "production",
    "mvp": "mvp",
    "pilot": "pilot",
    "beta": "pilot",
    "prototype": "poc",
    "poc": "poc",
    "proof of concept": "poc",
}

_MATURITY_LABELS: dict[str, str] = {
    "production": "Production",
    "mvp": "MVP",
    "pilot": "Pilot",
    "poc": "POC",
    "unknown": "Unknown",
}

_MATURITY_SCORES: dict[str, int] = {
    "production": 5,
    "mvp": 4,
    "pilot": 3,
    "poc": 2,
    "unknown": 2,
}

_CONSTRAINT_DOMAIN_KEYWORDS: dict[str, set[str]] = {
    "IA": {
        "agent", "ai", "anomaly", "classification", "classifier", "copilot", "forecast",
        "genai", "inference", "llm", "machine", "ml", "model", "neural", "nlp",
        "prediction", "recommendation", "scoring", "semantic",
    },
    "Data": {
        "analytics", "bi", "dashboard", "data", "database", "dataset", "etl", "insight",
        "kpi", "pipeline", "quality", "reporting", "storage", "visualization", "warehouse",
    },
    "Process": {
        "approval", "automation", "business rule", "process", "step", "task", "validation",
        "workflow",
    },
    "Business": {
        "business", "client", "cost", "customer", "experience", "growth", "kpi", "margin",
        "operating", "revenue", "value",
    },
    "IT": {
        "api", "architecture", "aws", "azure", "cloud", "integration", "itil", "platform",
        "sap", "servicenow", "system", "technical",
    },
    "autre": set(),
}

_CONSTRAINT_OBJECTIVE_KEYWORDS: dict[str, set[str]] = {
    "optimisation_operationnelle": {
        "bottleneck", "delay", "efficiency", "lead time", "operations", "optimize", "process",
        "productivity", "reduce", "streamline", "throughput",
    },
    "automatisation": {
        "automate", "automation", "manual", "orchestration", "repetitive", "robotic", "workflow",
    },
    "reduction_couts": {
        "budget", "cost", "efficiency", "expense", "manual", "optimize", "productivity", "saving",
    },
    "amelioration_qualite": {
        "accuracy", "compliance", "conformity", "error", "precision", "quality", "rework",
    },
    "transformation_strategique": {
        "business model", "differentiation", "scale", "strategic", "transform", "transformation",
    },
    "innovation": {
        "differentiation", "innovation", "new offer", "new service", "prototype", "vision",
    },
    "autre": set(),
}

_IMPACT_STATEMENTS: dict[str, tuple[str, str]] = {
    "Cost": (
        "Supports the declared cost-reduction and productivity objective.",
        "Limits the ability to capture the expected cost reduction.",
    ),
    "CustomerExperience": (
        "Supports the expected customer-experience improvement.",
        "Weakens the expected customer-experience outcome.",
    ),
    "Risk": (
        "Supports the expected risk-control outcome.",
        "Leaves material risk-control uncertainty in the current scope.",
    ),
    "Revenue": (
        "Supports the expected growth or revenue outcome.",
        "Makes the expected growth outcome harder to evidence.",
    ),
}


@dataclass(frozen=True)
class CompressedSolutionContext:
    """Relevant solution evidence retained for LLM injection."""

    description: str
    business_impact: str
    features: list[str]
    audit: GapContextCompressionAudit


@dataclass(frozen=True)
class CatalogEvidence:
    """Availability of DXC catalog evidence per IVI dimension."""

    maturite: bool
    expertise: bool
    duree: bool
    donnees: bool
    impact_business: bool


@dataclass(frozen=True)
class ExpertiseProfileContext:
    """DXC staffing context used by expertise scoring and client messaging."""

    required_profiles: list[RequiredProfile]
    estimated_team_size: int
    specialist_profiles: int
    shortage_profiles: int
    staffing_message: str


def _tokenize(text: str) -> set[str]:
    return {token for token in _TOKEN_RE.findall((text or "").lower())}


def _split_sentences(text: str) -> list[str]:
    stripped = str(text or "").strip()
    if not stripped:
        return []
    parts = [part.strip() for part in _SENTENCE_SPLIT_RE.split(stripped) if part.strip()]
    return parts or [stripped]


def _normalize_list(value: object, limit: int | None = None) -> list[str]:
    if not isinstance(value, list):
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item or "").strip()
        if not text:
            continue
        key = re.sub(r"\s+", " ", text.lower())
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text)
        if limit is not None and len(normalized) >= limit:
            break
    return normalized


def _normalize_text_key(text: str) -> str:
    """Build a stable comparison key for deduping semantically identical strings."""
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _has_text_value(value: object) -> bool:
    return bool(str(value or "").strip())


def _has_list_value(value: object) -> bool:
    return isinstance(value, list) and any(str(item or "").strip() for item in value)


def _build_catalog_evidence(solution: dict[str, Any]) -> CatalogEvidence:
    """Track whether each IVI dimension has enough DXC catalog evidence to avoid invention."""
    has_description = _has_text_value(solution.get("description"))
    has_business_impact = _has_text_value(solution.get("business_impact"))
    has_features = _has_list_value(solution.get("features"))
    has_ai_type = _has_text_value(solution.get("ai_type"))
    has_maturity = _has_text_value(solution.get("maturity_level"))

    return CatalogEvidence(
        maturite=has_maturity,
        expertise=has_features or has_ai_type or has_description,
        duree=has_maturity or has_features or has_description,
        donnees=has_features or has_description or has_business_impact,
        impact_business=has_business_impact or has_description,
    )


def _unavailable_dimension(
    score: int,
    dimension_label: str,
    dx_catalog_fields: str,
) -> ScoredDimension:
    """Return a conservative score with an explicit no-invention explanation."""
    return ScoredDimension(
        score=score,
        justification=(
            f"Donnée indisponible dans le catalogue DXC pour la dimension '{dimension_label}'. "
            f"Champs attendus: {dx_catalog_fields}. Score conservateur appliqué sans invention de données."
        ),
    )


def _dimension_client_label(score: int) -> str:
    if score >= 4:
        return "fort"
    if score >= 3:
        return "intermédiaire"
    return "faible"


def _estimate_profile_people(
    profile_name: str,
    matched_skills: list[str],
    features_missing: list[str],
    complexity_signals: int,
) -> int:
    """Estimate a small DXC team size for a matched profile."""
    people = 1
    if profile_name in {"Data Scientist", "AI Engineer", "Cloud Architect"} and (
        len(matched_skills) >= 3 or len(features_missing) >= 3
    ):
        people += 1
    if profile_name == "Cloud Architect" and complexity_signals >= 4:
        people += 1
    return people


def _profile_priority_boost(profile_name: str, combined_text: str, features_missing: list[str]) -> int:
    """Apply small deterministic boosts for clear staffing signals."""
    missing_text = " ".join(features_missing).lower()
    lowered = combined_text.lower()

    if profile_name == "AI Engineer" and any(token in lowered for token in ("llm", "genai", "ai", "model", "prediction", "copilot")):
        return 2
    if profile_name == "Data Scientist" and any(token in lowered for token in ("prediction", "forecast", "scoring", "classification", "analytics")):
        return 2
    if profile_name == "Cloud Architect" and any(token in lowered for token in ("cloud", "azure", "aws", "platform", "integration")):
        return 2
    if profile_name == "Cloud Architect" and any(token in lowered or token in missing_text for token in ("data", "etl", "pipeline", "mapping", "quality", "api")):
        return 1
    if profile_name == "DevOps Engineer" and any(token in lowered for token in ("deployment", "ci/cd", "kubernetes", "monitoring", "automation")):
        return 2
    if profile_name == "Cybersecurity Expert" and any(token in lowered or token in missing_text for token in ("security", "privacy", "compliance", "audit", "iam")):
        return 2
    if profile_name == "UX/UI Designer" and any(token in lowered or token in missing_text for token in ("experience", "journey", "portal", "self-service", "usability")):
        return 2
    if profile_name == "Business Analyst" and any(token in missing_text for token in ("workflow", "requirements", "journey", "business", "kpi")):
        return 1
    if profile_name == "Cloud Architect" and (
        len(features_missing) >= 2 or any(token in lowered for token in ("architecture", "integration", "platform", "scalable"))
    ):
        return 2
    return 0


def _build_staffing_message(required_profiles: list[RequiredProfile]) -> str:
    """Summarize the DXC team composition in a client-ready sentence."""
    if not required_profiles:
        return "DXC staffing data is unavailable for this qualification."

    total_people = sum(profile.estimated_people for profile in required_profiles)
    parts = [
        f"{profile.estimated_people} {profile.name}{'s' if profile.estimated_people > 1 else ''}"
        for profile in required_profiles
    ]
    if len(parts) == 1:
        composition = parts[0]
    elif len(parts) == 2:
        composition = " et ".join(parts)
    else:
        composition = ", ".join(parts[:-1]) + f" et {parts[-1]}"

    return f"DXC mobilisera une equipe de {total_people} personnes : {composition}."


def match_required_profiles(
    solution: dict[str, Any],
    features_missing: list[str],
) -> list[RequiredProfile]:
    """Match only DXC-approved staffing profiles from the solution evidence and gaps."""
    combined_text = " ".join(
        str(part or "").strip()
        for part in [
            solution.get("name"),
            solution.get("description"),
            solution.get("business_impact"),
            solution.get("ai_type"),
            solution.get("maturity_level"),
            *(_normalize_list(solution.get("features"))),
            *features_missing,
        ]
        if str(part or "").strip()
    )
    lowered = combined_text.lower()
    complexity_signals = len(features_missing) + sum(
        1
        for token in ("ai", "cloud", "security", "integration", "data", "platform")
        if token in lowered
    )

    matches: list[tuple[int, RequiredProfile]] = []
    for profile in DXC_PROFILES:
        skills = [str(skill) for skill in profile.get("skills", [])]
        tasks = [str(task) for task in profile.get("typical_tasks", [])]
        matched_skills = [skill for skill in skills if skill.lower() in lowered]
        task_hits = sum(1 for task in tasks if any(token in lowered for token in _tokenize(task.lower())))
        score = len(matched_skills) + task_hits + _profile_priority_boost(str(profile["name"]), combined_text, features_missing)
        if score <= 0:
            continue

        matches.append((
            score,
            RequiredProfile(
                profile_id=str(profile["id"]),
                name=str(profile["name"]),
                seniority_level=str(profile["seniority_level"]),
                daily_capacity=int(profile["daily_capacity"]),
                estimated_people=_estimate_profile_people(
                    str(profile["name"]),
                    matched_skills,
                    features_missing,
                    complexity_signals,
                ),
                matched_skills=matched_skills[:4],
                typical_tasks=tasks[:3],
                rationale=(
                    f"Matched on {len(matched_skills)} skill signal(s), {task_hits} task signal(s), "
                    f"and {len(features_missing)} identified gap(s)."
                ),
            ),
        ))

    ranked = [profile for _score, profile in sorted(matches, key=lambda item: (-item[0], item[1].name))]

    if not ranked and features_missing:
        for fallback_name in ("Business Analyst", "Cloud Architect"):
            for profile in DXC_PROFILES:
                if profile["name"] != fallback_name:
                    continue
                ranked.append(
                    RequiredProfile(
                        profile_id=str(profile["id"]),
                        name=str(profile["name"]),
                        seniority_level=str(profile["seniority_level"]),
                        daily_capacity=int(profile["daily_capacity"]),
                        estimated_people=1,
                        matched_skills=[],
                        typical_tasks=[str(task) for task in profile.get("typical_tasks", [])][:3],
                        rationale="Fallback DXC staffing profile retained to structure qualification and delivery scoping.",
                    )
                )

    unique_ranked: list[RequiredProfile] = []
    seen_ids: set[str] = set()
    for profile in ranked:
        if profile.profile_id in seen_ids:
            continue
        seen_ids.add(profile.profile_id)
        unique_ranked.append(profile)

    return unique_ranked[:5]


def _build_expertise_profile_context(required_profiles: list[RequiredProfile]) -> ExpertiseProfileContext:
    """Compute staffing summary signals reused by expertise scoring and client messaging."""
    estimated_team_size = sum(profile.estimated_people for profile in required_profiles)
    specialist_profiles = sum(
        1
        for profile in required_profiles
        if profile.name in {
            "Data Scientist",
            "AI Engineer",
            "Cloud Architect",
            "Cybersecurity Expert",
        }
    )
    shortage_profiles = sum(
        1
        for profile in required_profiles
        if profile.estimated_people > profile.daily_capacity
    )
    return ExpertiseProfileContext(
        required_profiles=required_profiles,
        estimated_team_size=estimated_team_size,
        specialist_profiles=specialist_profiles,
        shortage_profiles=shortage_profiles,
        staffing_message=_build_staffing_message(required_profiles),
    )


def _build_client_message(
    solution_name: str,
    ivi_score: float,
    scoring: IVIScoring,
    evidence: CatalogEvidence,
    profile_context: ExpertiseProfileContext | None = None,
) -> str:
    """Build a concise DXC-facing message that the frontend can display directly."""
    unavailable_dimensions = [
        label
        for label, available in {
            "maturite": evidence.maturite,
            "expertise": evidence.expertise,
            "duree": evidence.duree,
            "donnees": evidence.donnees,
            "impact_business": evidence.impact_business,
        }.items()
        if not available
    ]

    strongest_dimension = max(
        {
            "maturite": scoring.maturite.score,
            "expertise": scoring.expertise.score,
            "duree": scoring.duree.score,
            "donnees": scoring.donnees.score,
            "impact_business": scoring.impact_business.score,
        },
        key=lambda key: {
            "maturite": scoring.maturite.score,
            "expertise": scoring.expertise.score,
            "duree": scoring.duree.score,
            "donnees": scoring.donnees.score,
            "impact_business": scoring.impact_business.score,
        }[key],
    )

    base = (
        f"Message client DXC: la solution '{solution_name}' obtient un score IVI global de {ivi_score:.1f}/100. "
        f"Le signal le plus favorable concerne '{strongest_dimension}' avec un niveau {_dimension_client_label(getattr(scoring, strongest_dimension).score)}."
    )
    if unavailable_dimensions:
        return (
            base
            + " Certaines dimensions reposent sur des données indisponibles dans le catalogue DXC: "
            + ", ".join(unavailable_dimensions)
            + "."
            + (f" {profile_context.staffing_message}" if profile_context and profile_context.required_profiles else "")
        )
    return base + " Toutes les dimensions IVI ont été évaluées à partir des signaux disponibles du catalogue DXC."


def _clamp_score_5(value: float) -> int:
    return max(1, min(5, int(round(value))))


def _catalog_fact(solution: dict[str, Any], fallback: str) -> str:
    """Build a short factual anchor using only fields already present in the catalog payload."""
    facts: list[str] = []
    if _has_text_value(solution.get("name")):
        facts.append(f"solution '{solution.get('name')}'")
    if _has_text_value(solution.get("maturity_level")):
        facts.append(f"maturity '{solution.get('maturity_level')}'")
    if _has_list_value(solution.get("features")):
        facts.append(f"{len(_normalize_list(solution.get('features')))} catalog feature(s)")
    if _has_text_value(solution.get("business_impact")):
        facts.append("documented business-impact text")
    return ", ".join(facts[:3]) or fallback


def estimate_duration_months(
    *,
    features_missing: list[str],
    required_profiles: list[RequiredProfile],
    maturity_normalized: str,
) -> tuple[float, str]:
    """Apply the requested duration formula with deterministic local inputs."""
    maturity_multiplier = {
        "production": 0.8,
        "mvp": 1.0,
        "pilot": 1.15,
        "poc": 1.35,
        "unknown": 1.2,
    }.get(maturity_normalized, 1.2)
    task_complexity = max(1.0, len(features_missing) * maturity_multiplier)
    profile_workload = sum(
        max(1, profile.estimated_people) * (1.4 if profile.seniority_level == "senior" else 1.0)
        for profile in required_profiles
    ) or 1.0
    nb_profiles = max(1, len(required_profiles))
    estimated = round((task_complexity * profile_workload) / nb_profiles, 1)
    formula = (
        "estimated_duration = Σ(task_complexity × profile_workload) ÷ nb_profiles"
        f" = ({task_complexity:.1f} × {profile_workload:.1f}) ÷ {nb_profiles} = {estimated:.1f}"
    )
    return estimated, formula


def _clamp_score_10(value: float) -> int:
    return max(1, min(10, int(round(value))))


def _normalize_maturity_level(raw: object) -> tuple[str, str]:
    text = str(raw or "").strip()
    lowered = text.lower()

    for alias, normalized in _MATURITY_ALIASES.items():
        if alias in lowered:
            return normalized, _MATURITY_LABELS[normalized]

    return "unknown", text or _MATURITY_LABELS["unknown"]


def _legacy_domain_keywords(domains_list: list[str]) -> set[str]:
    return set().union(*(_DOMAIN_KEYWORDS.get(domain, set()) for domain in domains_list))


def _constraint_domain_keywords(constraints: SourcingGapAnalysisConstraints | None) -> set[str]:
    if not constraints:
        return set()
    return _CONSTRAINT_DOMAIN_KEYWORDS.get(constraints.domain, set())


def _constraint_objective_keywords(constraints: SourcingGapAnalysisConstraints | None) -> set[str]:
    if not constraints:
        return set()
    return _CONSTRAINT_OBJECTIVE_KEYWORDS.get(constraints.objective, set())


def _solution_keywords(
    domains_list: list[str],
    impact_list: list[str],
    objectif: str,
    nlp_constraints: SourcingGapAnalysisConstraints | None = None,
) -> tuple[set[str], set[str], set[str]]:
    domain_keywords = _legacy_domain_keywords(domains_list) | _constraint_domain_keywords(nlp_constraints)
    impact_keywords = set().union(*(_IMPACT_KEYWORDS.get(impact, set()) for impact in impact_list))
    objective_keywords = _OBJECTIVE_KEYWORDS.get(objectif, set()) | _constraint_objective_keywords(nlp_constraints)
    return domain_keywords, impact_keywords, objective_keywords


def _score_relevance(
    text: str,
    need_tokens: set[str],
    domain_keywords: set[str],
    impact_keywords: set[str],
    objective_keywords: set[str],
) -> float:
    lowered = text.lower()
    tokens = _tokenize(lowered)
    overlap = len(tokens & need_tokens)
    score = float(overlap)

    if tokens & domain_keywords:
        score += 3
    if tokens & impact_keywords:
        score += 2
    if tokens & objective_keywords:
        score += 2
    if any(keyword in lowered for keyword in ("api", "integration", "workflow", "dashboard", "governance")):
        score += 0.5

    return score


def _build_filter_reason(
    *,
    domains_list: list[str],
    impact_list: list[str],
    objectif: str,
    nlp_constraints: SourcingGapAnalysisConstraints | None,
    fallback_applied: bool,
) -> str:
    if nlp_constraints:
        parts = [
            f"domain={nlp_constraints.domain}",
            f"objective={nlp_constraints.objective}",
        ]
        if nlp_constraints.horizon:
            parts.append(f"horizon={nlp_constraints.horizon}")
        if impact_list:
            parts.append(f"impact={','.join(impact_list)}")
        base = "Filtered by " + " and ".join(parts)
    else:
        base = (
            f"Filtered by domain={','.join(domains_list) or 'none'} and "
            f"objective={objectif or 'none'}"
        )
        if impact_list:
            base += f" with impact={','.join(impact_list)}"
    if fallback_applied:
        return base + "; no highly relevant subset was found, so the legacy fallback context was retained."
    return base


def compress_solution_context(
    *,
    need_pitch: str,
    objectif: str,
    domains_list: list[str],
    impact_list: list[str],
    solution: dict[str, Any],
    nlp_constraints: SourcingGapAnalysisConstraints | None = None,
) -> CompressedSolutionContext:
    """Retain only the solution signals that match the need's domain and impact."""

    feature_texts = _normalize_list(solution.get("features"))
    description_sentences = _split_sentences(str(solution.get("description", "") or ""))
    business_impact_sentences = _split_sentences(str(solution.get("business_impact", "") or ""))

    need_tokens = _tokenize(
        " ".join(
            part
            for part in [
                need_pitch,
                objectif,
                *(domains_list or []),
                *(impact_list or []),
                nlp_constraints.domain if nlp_constraints else "",
                nlp_constraints.objective if nlp_constraints else "",
                nlp_constraints.horizon if nlp_constraints and nlp_constraints.horizon else "",
            ]
            if part
        )
    )
    domain_keywords, impact_keywords, objective_keywords = _solution_keywords(
        domains_list,
        impact_list,
        objectif,
        nlp_constraints,
    )

    feature_scores = {
        text: _score_relevance(text, need_tokens, domain_keywords, impact_keywords, objective_keywords)
        for text in feature_texts
    }

    ranked_features = sorted(
        feature_texts,
        key=lambda text: feature_scores[text],
        reverse=True,
    )
    retained_features = [
        text
        for text in ranked_features
        if feature_scores[text] > 0
    ][:4]

    description_scores = {
        text: _score_relevance(text, need_tokens, domain_keywords, impact_keywords, objective_keywords)
        for text in description_sentences
    }

    ranked_description = sorted(
        description_sentences,
        key=lambda text: description_scores[text],
        reverse=True,
    )
    retained_description = [
        text
        for text in ranked_description
        if description_scores[text] > 0
    ][:2]

    business_impact_scores = {
        text: _score_relevance(text, need_tokens, domain_keywords, impact_keywords, objective_keywords)
        for text in business_impact_sentences
    }

    ranked_business_impact = sorted(
        business_impact_sentences,
        key=lambda text: business_impact_scores[text],
        reverse=True,
    )
    retained_business_impact = [
        text
        for text in ranked_business_impact
        if business_impact_scores[text] > 0
    ][:2]

    fallback_applied = not (retained_features or retained_description or retained_business_impact)
    if fallback_applied:
        retained_features = feature_texts[: min(3, len(feature_texts))]
        retained_description = description_sentences[:1] if description_sentences else []
        retained_business_impact = business_impact_sentences[:1] if business_impact_sentences else []

    included_items = [*retained_features, *retained_description, *retained_business_impact]
    excluded_items_count = max(
        0,
        (len(feature_texts) - len(retained_features))
        + (len(description_sentences) - len(retained_description))
        + (len(business_impact_sentences) - len(retained_business_impact)),
    )
    filter_reason = _build_filter_reason(
        domains_list=domains_list,
        impact_list=impact_list,
        objectif=objectif,
        nlp_constraints=nlp_constraints,
        fallback_applied=fallback_applied,
    )

    return CompressedSolutionContext(
        description=" ".join(retained_description),
        business_impact=" ".join(retained_business_impact),
        features=retained_features,
        audit=GapContextCompressionAudit(
            domain_tags=domains_list,
            impact_tags=impact_list,
            objective_tags=[objectif] if objectif else [],
            constraints_used=[
                item
                for item in [
                    f"domain={nlp_constraints.domain}" if nlp_constraints else "",
                    f"objective={nlp_constraints.objective}" if nlp_constraints else "",
                    f"horizon={nlp_constraints.horizon}" if nlp_constraints and nlp_constraints.horizon else "",
                ]
                if item
            ],
            retained_features=retained_features,
            retained_description_sentences=retained_description,
            retained_business_impact_sentences=retained_business_impact,
            omitted_features_count=max(0, len(feature_texts) - len(retained_features)),
            excluded_items_count=excluded_items_count,
            filter_reason=filter_reason,
            fallback_to_full_context=fallback_applied,
            included_items=[item for item in included_items if item],
        ),
    )


def _infer_matching_features(feature_texts: list[str], need_terms: set[str]) -> list[str]:
    matches = [feature for feature in feature_texts if _tokenize(feature) & need_terms]
    if matches:
        return matches[:5]
    return feature_texts[: min(2, len(feature_texts))]


def _infer_missing_features(
    *,
    objectif: str,
    domains_list: list[str],
    impact_list: list[str],
    combined_solution_text: str,
) -> list[str]:
    missing: list[str] = []
    lowered_solution = combined_solution_text.lower()

    if "api" not in lowered_solution and "integration" not in lowered_solution:
        missing.append("The integration scope and API mappings are not clearly defined.")
    if "Data" in domains_list and not any(token in lowered_solution for token in ("data", "quality", "governance", "dashboard", "analytics")):
        missing.append("The data foundation needed for the use case is not explicitly covered.")
    if "IA" in domains_list and not any(token in lowered_solution for token in ("ai", "ml", "model", "prediction", "copilot", "agent", "genai")):
        missing.append("The AI-specific capability expected by the use case is not clearly described.")
    if objectif == "risk_mitigation" and not any(token in lowered_solution for token in ("security", "compliance", "audit", "governance")):
        missing.append("Security, compliance, and audit controls still need to be specified.")
    if objectif == "cost_reduction" and not any(token in lowered_solution for token in ("automation", "efficiency", "productivity", "workflow", "rpa")):
        missing.append("The automation levers that create measurable savings remain unclear.")
    if objectif == "cx_improvement" and not any(token in lowered_solution for token in ("customer", "client", "support", "journey", "self-service")):
        missing.append("The customer or employee experience journey is not sufficiently covered.")
    if objectif == "market_opportunity" and not any(token in lowered_solution for token in ("growth", "market", "revenue", "scal")):
        missing.append("The commercial scaling capability for the opportunity is not explicit yet.")
    if "Risk" in impact_list and not any(token in lowered_solution for token in ("security", "risk", "compliance", "privacy")):
        missing.append("Risk-reduction mechanisms are not clearly represented in the current scope.")

    if not missing:
        missing.append("Need-specific workflow coverage should be validated during qualification.")

    return missing[:5]


def _infer_risks(
    *,
    objectif: str,
    domains_list: list[str],
    impact_list: list[str],
    combined_solution_text: str,
    maturity_normalized: str,
    features_missing: list[str],
) -> list[str]:
    risks: list[str] = []
    lowered_solution = combined_solution_text.lower()

    if maturity_normalized == "poc":
        risks.append("The solution is still at POC maturity, which increases delivery and support risk.")
    elif maturity_normalized == "pilot":
        risks.append("Pilot maturity means operational hardening and rollout governance may still be incomplete.")

    if any(token in " ".join(features_missing).lower() for token in _DATA_RISK_KEYWORDS):
        risks.append("Data mapping, quality, or integration assumptions still need validation.")

    if "IA" in domains_list and not any(token in lowered_solution for token in ("monitor", "governance", "explain", "quality")):
        risks.append("AI operations, monitoring, or governance controls are not explicit yet.")

    if "Risk" in impact_list or objectif == "risk_mitigation":
        if not any(token in lowered_solution for token in ("security", "privacy", "compliance", "audit")):
            risks.append("Compliance and security checkpoints may emerge late without an upfront control plan.")

    if len(features_missing) >= 3:
        risks.append("The current gap volume suggests scope expansion or phased delivery may be required.")

    if not risks:
        risks.append("Key delivery assumptions should be validated early to avoid scope drift.")

    return _normalize_list(risks, limit=4)


def _looks_like_risk(text: str) -> bool:
    """Detect whether a sentence describes delivery uncertainty rather than a missing feature."""
    lowered = text.lower()
    return any(
        keyword in lowered
        for keyword in (
            "risk",
            "uncert",
            "assumption",
            "validation",
            "governance",
            "security",
            "privacy",
            "compliance",
            "audit",
            "adoption",
            "rollout",
            "operational",
            "support risk",
            "scope expansion",
            "scope drift",
        )
    )


def _looks_like_feature_gap(text: str) -> bool:
    """Detect whether a sentence describes a missing capability rather than a risk."""
    lowered = text.lower()
    return any(
        keyword in lowered
        for keyword in (
            "not clearly defined",
            "not explicitly covered",
            "not clearly described",
            "need to be specified",
            "remain unclear",
            "not sufficiently covered",
            "not explicit yet",
            "not clearly represented",
            "capability",
            "integration scope",
            "foundation needed",
            "workflow coverage",
        )
    )


def _separate_gap_buckets(
    features_matching: list[str],
    features_missing: list[str],
    risks: list[str],
) -> tuple[list[str], list[str], list[str]]:
    """Keep overlap, missing capabilities, and delivery risks in clearly separate buckets."""
    matching_clean = _normalize_list(features_matching, limit=5)

    matching_keys = {_normalize_text_key(text) for text in matching_clean}
    missing_clean: list[str] = []
    risk_clean: list[str] = []
    missing_keys: set[str] = set()
    risk_keys: set[str] = set()

    for item in _normalize_list(features_missing, limit=8):
        key = _normalize_text_key(item)
        if key in matching_keys:
            continue
        if _looks_like_risk(item) and not _looks_like_feature_gap(item):
            if key not in risk_keys:
                risk_clean.append(item)
                risk_keys.add(key)
            continue
        if key not in missing_keys:
            missing_clean.append(item)
            missing_keys.add(key)

    for item in _normalize_list(risks, limit=8):
        key = _normalize_text_key(item)
        if key in matching_keys:
            continue
        if _looks_like_feature_gap(item) and not _looks_like_risk(item):
            if key not in missing_keys:
                missing_clean.append(item)
                missing_keys.add(key)
            continue
        if key not in risk_keys:
            risk_clean.append(item)
            risk_keys.add(key)

    return matching_clean[:5], missing_clean[:5], risk_clean[:4]


def _infer_resources(
    *,
    objectif: str,
    domains_list: list[str],
) -> list[str]:
    resources = [
        "Assign a product owner, business analyst, and implementation lead.",
        "Define the target integrations, data flows, and delivery milestones.",
        "Validate governance, security, and rollout checkpoints before implementation.",
    ]

    if "Data" in domains_list or "IA" in domains_list:
        resources.append("Secure cloud/data platform support for onboarding and quality controls.")
    elif objectif in {"cx_improvement", "market_opportunity"}:
        resources.append("Prepare adoption, training, and stakeholder change-management activities.")

    return resources[:4]


def _contains_alignment(text: str, keywords: set[str]) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def _build_fit_justification(
    *,
    fit_score: int,
    matching_count: int,
    missing_count: int,
    impact_alignment: bool,
    maturity_label: str,
) -> str:
    alignment_text = "business-impact wording is aligned" if impact_alignment else "business-impact alignment is only partial"
    return (
        f"Fit score {fit_score}/10 based on {matching_count} matching capability(ies) versus "
        f"{missing_count} gap(s); {alignment_text}, and solution maturity is {maturity_label}."
    )


def _primary_impact_key(objectif: str, impact_list: list[str]) -> str | None:
    if impact_list:
        return impact_list[0]
    return {
        "cost_reduction": "Cost",
        "cx_improvement": "CustomerExperience",
        "risk_mitigation": "Risk",
        "market_opportunity": "Revenue",
    }.get(objectif)


def _impact_statement(objectif: str, impact_list: list[str], positive: bool) -> str:
    impact_key = _primary_impact_key(objectif, impact_list)
    if impact_key and impact_key in _IMPACT_STATEMENTS:
        return _IMPACT_STATEMENTS[impact_key][0 if positive else 1]
    if positive:
        return "Supports the declared business objective."
    return "Leaves the declared business objective partially uncovered."


def _best_evidence(name: str, evidence_pool: list[str]) -> str:
    name_tokens = _tokenize(name)
    for text in evidence_pool:
        if _tokenize(text) & name_tokens:
            return text
    return evidence_pool[0] if evidence_pool else f"Retained catalog context references '{name}'."


def _build_feature_match_details(
    *,
    features_matching: list[str],
    evidence_pool: list[str],
    objectif: str,
    impact_list: list[str],
) -> list[GapFeatureMatch]:
    return [
        GapFeatureMatch(
            name=name,
            evidence=_best_evidence(name, evidence_pool),
            impact=_impact_statement(objectif, impact_list, True),
        )
        for name in features_matching[:5]
    ]


def _build_feature_missing_details(
    *,
    features_missing: list[str],
    objectif: str,
    impact_list: list[str],
) -> list[GapFeatureMissing]:
    return [
        GapFeatureMissing(
            name=name,
            reason=name,
            impact=_impact_statement(objectif, impact_list, False),
        )
        for name in features_missing[:5]
    ]


def _risk_category(title: str) -> str:
    lowered = title.lower()
    if any(token in lowered for token in ("security", "privacy", "compliance", "audit", "iam")):
        return "security"
    if any(token in lowered for token in ("data", "quality", "mapping", "source", "etl", "pipeline", "governance")):
        return "data"
    if any(token in lowered for token in ("api", "integration", "dependency", "architecture", "platform")):
        return "integration"
    if any(token in lowered for token in ("adoption", "training", "change-management", "rollout", "stakeholder")):
        return "adoption"
    if any(token in lowered for token in ("scope", "budget", "business", "sponsor", "value")):
        return "business"
    if any(token in lowered for token in ("technical", "support", "monitor", "poc", "maturity", "delivery")):
        return "technical"
    return "other"


def _risk_severity(title: str, category: str) -> str:
    lowered = title.lower()
    if any(token in lowered for token in ("poc", "security", "privacy", "compliance", "scope expansion", "support risk")):
        return "high"
    if category in {"security", "integration", "data"}:
        return "medium"
    return "low"


def _risk_mitigation(category: str) -> str:
    return {
        "technical": "Run architecture hardening and delivery-readiness checkpoints before implementation.",
        "business": "Confirm scope ownership, KPI sponsorship, and phased business decisions before GO.",
        "data": "Perform a data assessment and validate mappings, quality controls, and access assumptions.",
        "security": "Add explicit security, privacy, and compliance checkpoints into qualification and design.",
        "integration": "Validate API contracts, system dependencies, and end-to-end integration sequencing.",
        "adoption": "Plan change management, training, and rollout support before deployment.",
        "other": "Document the risk owner, mitigation checkpoint, and validation date before execution.",
    }[category]


def _build_risk_register(risks: list[str]) -> list[GapRisk]:
    register: list[GapRisk] = []
    for title in risks[:4]:
        category = _risk_category(title)
        register.append(
            GapRisk(
                title=title,
                category=category,
                severity=_risk_severity(title, category),
                mitigation=_risk_mitigation(category),
            )
        )
    return register


def _build_resource_details(resources_needed: list[str]) -> list[GapResourceNeed]:
    return [
        GapResourceNeed(
            name=item,
            reason="Delivery dependency identified during qualification scoping.",
        )
        for item in resources_needed[:4]
    ]


def _to_qualification_dimension(dimension: ScoredDimension) -> QualificationScoreDimension:
    return QualificationScoreDimension(
        score=max(0, min(10, int(dimension.score * 2))),
        justification=dimension.justification,
    )


def _build_structured_scores(ivi_scoring: IVIScoring) -> QualificationScores:
    return QualificationScores(
        maturite=_to_qualification_dimension(ivi_scoring.maturite),
        expertise=_to_qualification_dimension(ivi_scoring.expertise),
        duree=_to_qualification_dimension(ivi_scoring.duree),
        donnees=_to_qualification_dimension(ivi_scoring.donnees),
        impact_business=_to_qualification_dimension(ivi_scoring.impact_business),
    )


def _build_recommendation(
    *,
    fit_score: int,
    feasibility_score: int,
    prerequisite_mode: bool,
    features_matching: list[str],
    features_missing: list[str],
    risk_register: list[GapRisk],
    calibration_applied: list[GapCalibrationApplied],
    ambiguity_flags: list[SourcingAmbiguityFlag],
    solution_context_filtered: SolutionContextFiltered,
) -> GapRecommendation:
    high_risk_count = sum(1 for risk in risk_register if risk.severity == "high")
    ambiguity_count = len([flag for flag in ambiguity_flags if flag.confidence in {"low", "medium"}])

    if fit_score <= 3 or feasibility_score <= 2 or high_risk_count >= 2:
        decision = "no_go"
    elif not solution_context_filtered.included_items:
        decision = "needs_more_information"
    elif ambiguity_count > 0 or calibration_applied or prerequisite_mode or features_missing:
        decision = "go_with_conditions"
    else:
        decision = "go"

    justification = (
        f"Decision={decision} from fit={fit_score}/10, feasibility={feasibility_score}/5, "
        f"matching={len(features_matching)}, missing={len(features_missing)}, high_risks={high_risk_count}, "
        f"ambiguity_flags={ambiguity_count}, prerequisite_mode={prerequisite_mode}."
    )
    if solution_context_filtered.fallback_to_full_context:
        justification += " Context filtering fell back to the broader solution payload because no highly relevant subset was found."

    return GapRecommendation(decision=decision, justification=justification)


def _extract_text_list(
    raw_items: object,
    *,
    candidate_fields: tuple[str, ...],
    limit: int,
) -> list[str]:
    if not isinstance(raw_items, list):
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        text = ""
        if isinstance(item, dict):
            for field in candidate_fields:
                value = item.get(field)
                if str(value or "").strip():
                    text = str(value).strip()
                    break
        else:
            text = str(item or "").strip()
        if not text:
            continue
        key = _normalize_text_key(text)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text)
        if len(normalized) >= limit:
            break
    return normalized


def _build_maturity_dimension(
    maturity_label: str,
    maturity_normalized: str,
    solution: dict[str, Any],
) -> ScoredDimension:
    if maturity_normalized == "unknown":
        return _unavailable_dimension(
            2,
            "maturite",
            "maturity_level",
        )

    score = _MATURITY_SCORES.get(maturity_normalized, _MATURITY_SCORES["unknown"])
    if maturity_normalized == "production":
        justification = f"Maturity is {maturity_label}, which indicates production readiness and lower rollout uncertainty."
    elif maturity_normalized == "mvp":
        justification = f"Maturity is {maturity_label}, which suggests the offer is reusable but still requires project-specific hardening."
    elif maturity_normalized == "pilot":
        justification = f"Maturity is {maturity_label}, which means the solution is validated but not yet broadly industrialized."
    elif maturity_normalized == "poc":
        justification = f"Maturity is {maturity_label}, so industrialization and operating-model readiness remain limited."
    else:
        justification = "Solution maturity is not clearly documented, which reduces confidence in delivery readiness."

    return ScoredDimension(
        score=score,
        justification=f"{justification} Score rationale: normalized maturity='{maturity_normalized}'.",
        client_reassurance=(
            f"DXC catalog evidence anchors maturity on {_catalog_fact(solution, 'the current solution record')}."
        ),
    )


def _build_expertise_dimension(
    *,
    domains_list: list[str],
    ai_type: str,
    maturity_normalized: str,
    features_missing: list[str],
    resources_needed: list[str],
    profile_context: ExpertiseProfileContext,
    evidence_available: bool,
) -> ScoredDimension:
    if not evidence_available:
        return _unavailable_dimension(
            2,
            "expertise",
            "features, ai_type, description",
        )

    complexity = 0
    complexity += min(2, len([domain for domain in domains_list if domain in {"IA", "Cloud", "Cybersecurite", "Data"}]))
    if any(token in ai_type.lower() for token in ("agentic", "generative", "genai")):
        complexity += 1
    if len(features_missing) >= 3:
        complexity += 1
    if len(resources_needed) >= 4:
        complexity += 1
    if profile_context.specialist_profiles >= 3:
        complexity += 1
    if profile_context.estimated_team_size >= 5:
        complexity += 1
    if profile_context.shortage_profiles > 0:
        complexity += 1

    bonus = 1 if maturity_normalized in {"mvp", "production"} and profile_context.shortage_profiles == 0 else 0
    score = _clamp_score_5(5 - complexity + bonus)

    if score >= 4:
        justification = (
            "Required skills look manageable for delivery teams, with limited specialist dependency. "
            f"Complexity signals={complexity}, resources={len(resources_needed)}, missing_capabilities={len(features_missing)}, "
            f"matched_profiles={len(profile_context.required_profiles)}, estimated_team={profile_context.estimated_team_size}."
        )
    elif score == 3:
        justification = (
            "Delivery needs a focused mix of architecture, integration, and domain expertise. "
            f"Complexity signals={complexity}, resources={len(resources_needed)}, missing_capabilities={len(features_missing)}, "
            f"matched_profiles={len(profile_context.required_profiles)}, estimated_team={profile_context.estimated_team_size}."
        )
    else:
        justification = (
            "Specialized skills and cross-functional coordination are significant prerequisites for delivery. "
            f"Complexity signals={complexity}, resources={len(resources_needed)}, missing_capabilities={len(features_missing)}, "
            f"matched_profiles={len(profile_context.required_profiles)}, estimated_team={profile_context.estimated_team_size}."
        )

    return ScoredDimension(
        score=score,
        justification=justification,
        client_reassurance=(
            f"DXC mobilization is limited to approved profiles and currently maps {len(profile_context.required_profiles)} catalog-aligned role(s)."
        ),
    )


def _build_duration_dimension(
    *,
    horizon: str,
    maturity_normalized: str,
    features_missing: list[str],
    risks: list[str],
    resources_needed: list[str],
    required_profiles: list[RequiredProfile],
    evidence_available: bool,
) -> tuple[ScoredDimension, float, str]:
    if not evidence_available:
        return (
            _unavailable_dimension(
                2,
                "duree",
                "maturity_level, features, description",
            ),
            0.0,
            "",
        )

    estimated_months, formula = estimate_duration_months(
        features_missing=features_missing,
        required_profiles=required_profiles,
        maturity_normalized=maturity_normalized,
    )

    penalty = 0
    if len(features_missing) >= 2:
        penalty += 1
    if len(features_missing) >= 4:
        penalty += 1
    if len(resources_needed) >= 4:
        penalty += 1
    if len(risks) >= 3:
        penalty += 1
    if maturity_normalized == "poc":
        penalty += 1

    if estimated_months < 1:
        formula_score = 5
    elif estimated_months <= 3:
        formula_score = 4
    elif estimated_months <= 6:
        formula_score = 3
    elif estimated_months <= 12:
        formula_score = 2
    else:
        formula_score = 1

    if horizon == "court_terme" and penalty > 0:
        penalty += 1
    if horizon == "long_terme" and penalty > 0:
        penalty -= 1

    score = _clamp_score_5(min(formula_score, 5 - penalty))
    horizon_label = {
        "court_terme": "short-term",
        "moyen_terme": "mid-term",
        "long_terme": "long-term",
    }.get(horizon, "planned")

    justification = (
        f"Timeline fit is {score}/5 for a {horizon_label} horizon, considering "
        f"{len(features_missing)} missing capability(ies), {len(risks)} risk(s), "
        f"{len(resources_needed)} delivery dependency(ies), and maturity '{maturity_normalized}'."
    )
    return (
        ScoredDimension(
            score=score,
            justification=f"{justification} {formula}",
            client_reassurance=(
                f"Duration is estimated from identified gaps, approved DXC staffing, and catalog maturity evidence ({maturity_normalized})."
            ),
        ),
        estimated_months,
        formula,
    )


def _build_data_dimension(
    *,
    domains_list: list[str],
    combined_solution_text: str,
    features_missing: list[str],
    risks: list[str],
    data_context: dict[str, Any] | None,
    evidence_available: bool,
) -> ScoredDimension:
    if not evidence_available:
        return _unavailable_dimension(
            2,
            "donnees",
            "features, description, business_impact",
        )

    lowered_solution = combined_solution_text.lower()
    has_data_foundation = any(token in lowered_solution for token in _DATA_RISK_KEYWORDS)
    has_data_controls = any(token in lowered_solution for token in ("quality", "governance", "monitor", "privacy"))
    data_risk_signals = sum(
        1
        for text in [*features_missing, *risks]
        if any(keyword in text.lower() for keyword in _DATA_RISK_KEYWORDS)
    )

    base = 4 if has_data_foundation else 3
    if data_context:
        availability = str(data_context.get("availability", "partial"))
        quality = str(data_context.get("quality", "unknown"))
        accessibility = str(data_context.get("accessibility", "unknown"))
        if availability == "available":
            base += 1
        elif availability == "unavailable":
            base -= 1
        if quality == "high":
            base += 1
        elif quality == "low":
            base -= 1
        if accessibility == "restricted":
            base -= 1
    if any(domain in {"IA", "Data"} for domain in domains_list) and not has_data_foundation:
        base -= 1
    if has_data_controls:
        base += 1
    if data_risk_signals >= 2:
        base -= 1
    if data_risk_signals >= 4:
        base -= 1

    score = _clamp_score_5(base)
    if score >= 4:
        justification = (
            "Data and integration prerequisites are reasonably explicit, which reduces onboarding uncertainty. "
            f"Foundation={has_data_foundation}, controls={has_data_controls}, risk_signals={data_risk_signals}."
        )
    elif score == 3:
        justification = (
            "Core data dependencies are visible, but mapping and quality assumptions still need confirmation. "
            f"Foundation={has_data_foundation}, controls={has_data_controls}, risk_signals={data_risk_signals}."
        )
    else:
        justification = (
            "Data readiness is a material dependency because key sources, mappings, or controls are not yet secure. "
            f"Foundation={has_data_foundation}, controls={has_data_controls}, risk_signals={data_risk_signals}."
        )

    return ScoredDimension(
        score=score,
        justification=justification,
        client_reassurance=(
            "The data score combines catalog evidence with sourcing answers on availability, quality, and accessibility."
            if data_context
            else "The data score is based only on catalog evidence because sourcing data-readiness answers were not provided."
        ),
    )


def _build_impact_dimension(
    *,
    objective: str,
    impact_list: list[str],
    combined_solution_text: str,
    fit_score: int,
    features_missing: list[str],
    solution: dict[str, Any],
    evidence_available: bool,
) -> ScoredDimension:
    if not evidence_available:
        return _unavailable_dimension(
            2,
            "impact_business",
            "business_impact, description",
        )

    lowered_solution = combined_solution_text.lower()
    objective_alignment = _contains_alignment(lowered_solution, _OBJECTIVE_KEYWORDS.get(objective, set()))
    impact_hits = sum(1 for impact in impact_list if _contains_alignment(lowered_solution, _IMPACT_KEYWORDS.get(impact, set())))

    base = 2
    if objective_alignment:
        base += 1
    base += min(2, impact_hits)
    if fit_score >= 7:
        base += 1
    if len(features_missing) >= 4:
        base -= 1

    score = _clamp_score_5(base)
    if score >= 4:
        justification = (
            "The solution's expected value aligns well with the business objective and impact tags. "
            f"Objective_alignment={objective_alignment}, impact_hits={impact_hits}, fit_score={fit_score}."
        )
    elif score == 3:
        justification = (
            "Business impact alignment is credible, but some value assumptions still depend on closing the identified gaps. "
            f"Objective_alignment={objective_alignment}, impact_hits={impact_hits}, fit_score={fit_score}."
        )
    else:
        justification = (
            "Business impact remains uncertain because the solution evidence only partially matches the expected outcome. "
            f"Objective_alignment={objective_alignment}, impact_hits={impact_hits}, fit_score={fit_score}."
        )

    return ScoredDimension(
        score=score,
        justification=justification,
        client_reassurance=(
            f"Impact scoring stays anchored on objective/impact alignment and {_catalog_fact(solution, 'catalog evidence')} without invented figures."
        ),
    )


def _build_feasibility_dimension(
    *,
    ivi_scoring: IVIScoring,
    maturity_normalized: str,
    risks: list[str],
) -> tuple[ScoredDimension, GapAnalysisRuleAudit, int]:
    raw_score = _clamp_score_5(
        (
            ivi_scoring.maturite.score
            + ivi_scoring.expertise.score
            + ivi_scoring.duree.score
            + ivi_scoring.donnees.score
        ) / 4
    )

    if len(risks) >= 3:
        raw_score = max(1, raw_score - 1)

    applied = maturity_normalized == "poc" and raw_score > 3
    final_score = min(raw_score, 3) if applied else raw_score
    detail = (
        "Applied because solution maturity is POC, so feasibility is capped at 3."
        if applied
        else "Not applied because solution maturity is above POC or feasibility was already <= 3."
    )

    justification = (
        f"Feasibility is {final_score}/5 from maturity={ivi_scoring.maturite.score}, "
        f"expertise={ivi_scoring.expertise.score}, duration={ivi_scoring.duree.score}, "
        f"data={ivi_scoring.donnees.score}, adjusted for {len(risks)} risk(s)."
    )
    if applied:
        justification += " Calibration applied: feasibility was capped at 3 because the solution maturity is POC."

    return (
        ScoredDimension(score=final_score, justification=justification),
        GapAnalysisRuleAudit(
            code="feasibility_cap_for_poc_maturity",
            applied=applied,
            detail=detail,
        ),
        raw_score,
    )


def build_gap_analysis_response(
    *,
    need_pitch: str,
    horizon: str,
    objectif: str,
    domains_list: list[str],
    impact_list: list[str],
    solution: dict[str, Any],
    parsed: dict[str, Any] | None,
    compressed_context: CompressedSolutionContext,
    nlp_constraints: SourcingGapAnalysisConstraints | None = None,
    ambiguity_flags: list[SourcingAmbiguityFlag] | None = None,
) -> GapAnalysisResponse:
    """Build a stable, deterministic gap-analysis response."""

    name = str(solution.get("name", "Unknown solution"))
    description = str(solution.get("description", "") or "")
    business_impact = str(solution.get("business_impact", "") or "")
    ai_type = str(solution.get("ai_type", "") or "")
    raw_feature_texts = _normalize_list(solution.get("features"))
    feature_texts = compressed_context.features or raw_feature_texts
    maturity_normalized, maturity_label = _normalize_maturity_level(solution.get("maturity_level"))
    catalog_evidence = _build_catalog_evidence(solution)
    data_context = solution.get("data_context") if isinstance(solution.get("data_context"), dict) else None

    parsed = parsed or {}
    ambiguity_flags = ambiguity_flags or []
    features_matching = _extract_text_list(
        parsed.get("features_matching"),
        candidate_fields=("name", "feature", "title", "evidence", "impact"),
        limit=5,
    )
    features_missing = _extract_text_list(
        parsed.get("features_missing"),
        candidate_fields=("name", "feature", "title", "reason", "impact"),
        limit=5,
    )
    risks = _extract_text_list(
        parsed.get("risks"),
        candidate_fields=("title", "name", "risk", "reason", "mitigation"),
        limit=4,
    )
    resources_needed = _extract_text_list(
        parsed.get("resources_needed"),
        candidate_fields=("name", "title", "reason"),
        limit=4,
    )

    combined_solution_text = " ".join(
        part
        for part in [
            name,
            description,
            business_impact,
            str(solution.get("maturity_level", "") or ""),
            *raw_feature_texts,
        ]
        if part
    )
    need_terms = _tokenize(" ".join([need_pitch, objectif, *impact_list, *domains_list]))

    if not features_matching:
        features_matching = _infer_matching_features(feature_texts or raw_feature_texts, need_terms)

    if not features_missing:
        features_missing = _infer_missing_features(
            objectif=objectif,
            domains_list=domains_list,
            impact_list=impact_list,
            combined_solution_text=combined_solution_text,
        )

    if not risks:
        risks = _infer_risks(
            objectif=objectif,
            domains_list=domains_list,
            impact_list=impact_list,
            combined_solution_text=combined_solution_text,
            maturity_normalized=maturity_normalized,
            features_missing=features_missing,
        )

    if not resources_needed:
        resources_needed = _infer_resources(objectif=objectif, domains_list=domains_list)

    features_matching, features_missing, risks = _separate_gap_buckets(
        features_matching,
        features_missing,
        risks,
    )
    required_profiles = match_required_profiles(solution, features_missing)
    profile_context = _build_expertise_profile_context(required_profiles)

    lowered_solution = combined_solution_text.lower()
    impact_alignment = any(
        _contains_alignment(lowered_solution, _IMPACT_KEYWORDS.get(impact, set()))
        for impact in impact_list
    ) or _contains_alignment(lowered_solution, _OBJECTIVE_KEYWORDS.get(objectif, set()))

    raw_fit_score = _clamp_score_10(
        5
        + min(3, len(features_matching))
        - min(3, len(features_missing))
        + (1 if impact_alignment else 0)
        + (1 if maturity_normalized in {"mvp", "production"} else 0)
        - (1 if maturity_normalized == "poc" else 0)
    )

    fit_score = raw_fit_score
    fit_rule_applied = len(features_missing) > len(features_matching) and fit_score > 5
    if fit_rule_applied:
        fit_score = 5

    fit_rule = GapAnalysisRuleAudit(
        code="fit_cap_when_missing_exceeds_matching",
        applied=fit_rule_applied,
        detail=(
            f"Applied because {len(features_missing)} missing feature(s) exceed {len(features_matching)} matching feature(s); "
            "fit score is capped at 5."
            if fit_rule_applied
            else (
                f"Not applied because {len(features_missing)} missing feature(s) do not exceed "
                f"{len(features_matching)} matching feature(s), or fit score was already <= 5."
            )
        ),
    )

    fit_justification = _build_fit_justification(
        fit_score=fit_score,
        matching_count=len(features_matching),
        missing_count=len(features_missing),
        impact_alignment=impact_alignment,
        maturity_label=maturity_label,
    )
    if fit_rule_applied:
        fit_justification += " Calibration applied: fit score was capped at 5 because missing features exceed matching features."

    duration_dimension, estimated_duration_months, duration_formula = _build_duration_dimension(
        horizon=horizon,
        maturity_normalized=maturity_normalized,
        features_missing=features_missing,
        risks=risks,
        resources_needed=resources_needed,
        required_profiles=required_profiles,
        evidence_available=catalog_evidence.duree,
    )

    ivi_scoring = IVIScoring(
        maturite=_build_maturity_dimension(maturity_label, maturity_normalized, solution),
        expertise=_build_expertise_dimension(
            domains_list=domains_list,
            ai_type=ai_type,
            maturity_normalized=maturity_normalized,
            features_missing=features_missing,
            resources_needed=resources_needed,
            profile_context=profile_context,
            evidence_available=catalog_evidence.expertise,
        ),
        duree=duration_dimension,
        donnees=_build_data_dimension(
            domains_list=domains_list,
            combined_solution_text=combined_solution_text,
            features_missing=features_missing,
            risks=risks,
            data_context=data_context,
            evidence_available=catalog_evidence.donnees,
        ),
        impact_business=_build_impact_dimension(
            objective=objectif,
            impact_list=impact_list,
            combined_solution_text=combined_solution_text,
            fit_score=fit_score,
            features_missing=features_missing,
            solution=solution,
            evidence_available=catalog_evidence.impact_business,
        ),
    )

    feasibility, feasibility_rule, raw_feasibility_score = _build_feasibility_dimension(
        ivi_scoring=ivi_scoring,
        maturity_normalized=maturity_normalized,
        risks=risks,
    )

    structured_scores = _build_structured_scores(ivi_scoring)
    evidence_pool = [
        *raw_feature_texts,
        *compressed_context.audit.retained_description_sentences,
        *compressed_context.audit.retained_business_impact_sentences,
    ]
    features_matching_detail = _build_feature_match_details(
        features_matching=features_matching,
        evidence_pool=evidence_pool,
        objectif=objectif,
        impact_list=impact_list,
    )
    features_missing_detail = _build_feature_missing_details(
        features_missing=features_missing,
        objectif=objectif,
        impact_list=impact_list,
    )
    risk_register = _build_risk_register(risks)
    resources_needed_detail = _build_resource_details(resources_needed)
    solution_context_filtered = SolutionContextFiltered(
        included_items=compressed_context.audit.included_items,
        excluded_count=compressed_context.audit.excluded_items_count,
        filter_reason=compressed_context.audit.filter_reason,
        fallback_to_full_context=compressed_context.audit.fallback_to_full_context,
    )
    calibration_applied: list[GapCalibrationApplied] = []
    if fit_rule_applied:
        calibration_applied.append(
            GapCalibrationApplied(
                rule="features_missing > features_matching",
                field="fit_score",
                previous_score=raw_fit_score,
                new_score=fit_score,
                reason="Le nombre de fonctionnalites manquantes depasse le nombre de fonctionnalites couvertes.",
            )
        )
    if feasibility_rule.applied:
        calibration_applied.append(
            GapCalibrationApplied(
                rule="maturity == POC",
                field="feasibility",
                previous_score=raw_feasibility_score,
                new_score=feasibility.score,
                reason="La maturite normalisee de la solution est POC; la faisabilite est plafonnee a 3.",
            )
        )

    ivi_score = round(
        (
            ivi_scoring.maturite.score
            + ivi_scoring.expertise.score
            + ivi_scoring.duree.score
            + ivi_scoring.donnees.score
            + ivi_scoring.impact_business.score
        )
        / 5
        * 20,
        1,
    )

    client_message = _build_client_message(
        solution_name=name,
        ivi_score=ivi_score,
        scoring=ivi_scoring,
        evidence=catalog_evidence,
        profile_context=profile_context,
    )
    prerequisite_mode = fit_score <= 4
    if profile_context.required_profiles and profile_context.staffing_message not in client_message:
        client_message = f"{client_message} {profile_context.staffing_message}"
    if prerequisite_mode:
        client_message = f"{client_message} PREREQUIS mode activated because fit_score <= 4."
    recommendation = _build_recommendation(
        fit_score=fit_score,
        feasibility_score=feasibility.score,
        prerequisite_mode=prerequisite_mode,
        features_matching=features_matching,
        features_missing=features_missing,
        risk_register=risk_register,
        calibration_applied=calibration_applied,
        ambiguity_flags=ambiguity_flags,
        solution_context_filtered=solution_context_filtered,
    )

    return GapAnalysisResponse(
        phase="SG-2",
        solution_name=name,
        fit_score=fit_score,
        fit_justification=fit_justification,
        client_message=client_message,
        feasibility=feasibility,
        ivi_scoring=ivi_scoring,
        scores=structured_scores,
        ivi_score=ivi_score,
        prerequisite_mode=prerequisite_mode,
        estimated_duration_months=estimated_duration_months,
        duration_formula=duration_formula,
        required_profiles=required_profiles,
        features_matching=features_matching[:5],
        features_missing=features_missing[:5],
        risks=risks[:4],
        resources_needed=resources_needed[:4],
        features_matching_detail=features_matching_detail,
        features_missing_detail=features_missing_detail,
        risk_register=risk_register,
        resources_needed_detail=resources_needed_detail,
        solution_context_filtered=solution_context_filtered,
        calibration_applied=calibration_applied,
        recommendation=recommendation,
        audit=GapAnalysisAudit(
            applied_rules=[
                GapAnalysisRuleAudit(
                    code="nlp_constraints_received",
                    applied=bool(nlp_constraints),
                    detail=(
                        "SG-1 typed constraints were injected into gap analysis: "
                        f"source={nlp_constraints.source}, domain={nlp_constraints.domain}, objective={nlp_constraints.objective}, horizon={nlp_constraints.horizon}."
                        if nlp_constraints
                        else "No SG-1 typed constraints were available; the legacy gap-analysis flow remained active."
                    ),
                ),
                fit_rule,
                feasibility_rule,
                GapAnalysisRuleAudit(
                    code="solution_context_compression_applied",
                    applied=True,
                    detail=(
                        f"Retained {len(compressed_context.audit.retained_features)} feature(s), "
                        f"{len(compressed_context.audit.retained_description_sentences)} description sentence(s), "
                        f"and {len(compressed_context.audit.retained_business_impact_sentences)} impact sentence(s); "
                        f"omitted_features={compressed_context.audit.omitted_features_count}; "
                        f"filter_reason={compressed_context.audit.filter_reason}."
                    ),
                ),
            ],
            context_compression=compressed_context.audit,
            nlp_constraints=nlp_constraints,
            ambiguity_flags=ambiguity_flags,
        ),
    )
