"""Deterministic delivery-recommendation helpers with optional LLM enrichment."""

from __future__ import annotations

import json
import re
from typing import Any

from app.core import llm_client
from app.schemas.business_need import (
    CoverageValidation,
    DxcAlignment,
    OrganizationalRecommendation,
    PrerequisiteAction,
    RecommendationKPI,
    SolutionRecommendations,
    TechnicalRecommendation,
)

DXC_ECOSYSTEM = ["Microsoft", "SAP", "ServiceNow", "AWS", "ITIL"]
DEFAULT_RESPONSIBLE_ROLES = [
    "Project Manager",
    "Product Owner",
    "Solution Architect",
    "Data Engineer",
    "Business Analyst",
    "Security Officer",
    "Change Manager",
    "Other",
]
DEFAULT_KPI_UNITS = ["€", "%", "minutes", "hours", "days", "count", "ratio"]
DEFAULT_PRIORITIES = ["low", "medium", "high", "critical"]
DEFAULT_TARGET_PHASES = ["prerequisite", "design", "build", "test", "deployment", "run"]

_TOKEN_RE = re.compile(r"[a-z0-9]{3,}")
_COST_KEYWORDS = {"cost", "saving", "efficiency", "budget", "productivity", "manual"}
_CX_KEYWORDS = {"customer", "client", "response", "service", "support", "journey", "experience"}
_SECURITY_KEYWORDS = {"security", "privacy", "compliance", "audit", "iam", "governance"}
_DATA_KEYWORDS = {"data", "quality", "mapping", "pipeline", "warehouse", "etl", "analytics"}
_INTEGRATION_KEYWORDS = {"api", "integration", "platform", "workflow", "architecture", "system"}
_AI_KEYWORDS = {"ai", "model", "prediction", "predictive", "nlp", "anomaly", "scoring"}


def _tokenize(text: str) -> set[str]:
    return {token for token in _TOKEN_RE.findall((text or "").lower())}


def _normalize_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text)
    return normalized


def _extract_gap_items(items: object, *, primary_keys: tuple[str, ...]) -> list[str]:
    if not isinstance(items, list):
        return []
    extracted: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = ""
        if isinstance(item, dict):
            for key in primary_keys:
                value = item.get(key)
                if str(value or "").strip():
                    text = str(value).strip()
                    break
        else:
            text = str(item or "").strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        extracted.append(text)
    return extracted


def _safe_int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _priority_for_text(text: str, prerequisite_mode: bool) -> str:
    lowered = text.lower()
    critical_signals = _SECURITY_KEYWORDS | {"blocking", "major", "critical"}
    high_signals = _DATA_KEYWORDS | _INTEGRATION_KEYWORDS | _AI_KEYWORDS
    if any(token in lowered for token in critical_signals):
        return "critical"
    if prerequisite_mode or any(token in lowered for token in high_signals):
        return "high"
    if any(token in lowered for token in ("workflow", "quality", "reporting", "dashboard")):
        return "medium"
    return "medium"


def _effort_for_text(text: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in ("architecture", "migration", "erp", "platform", "security")):
        return "XL"
    if any(token in lowered for token in ("integration", "api", "data", "pipeline", "model")):
        return "L"
    if any(token in lowered for token in ("workflow", "dashboard", "reporting", "governance")):
        return "M"
    return "S"


def _technology_stack_for_text(text: str, domains_list: list[str], solution: dict[str, Any]) -> list[str]:
    lowered = text.lower()
    stack: list[str] = []
    if any(token in lowered for token in _AI_KEYWORDS) or "IA" in domains_list:
        stack.extend(["Microsoft Azure AI", "AWS SageMaker"])
    if any(token in lowered for token in _DATA_KEYWORDS) or "Data" in domains_list:
        stack.extend(["Microsoft Power BI", "AWS Glue", "SAP Datasphere"])
    if any(token in lowered for token in _INTEGRATION_KEYWORDS) or any(domain in domains_list for domain in ("Process", "IT")):
        stack.extend(["ServiceNow", "Microsoft Power Platform", "AWS Integration Services"])
    if any(token in lowered for token in _SECURITY_KEYWORDS):
        stack.extend(["Microsoft Defender", "AWS Security Hub", "ITIL controls"])
    if str(solution.get("source", "")).lower().find("sap") >= 0 or str(solution.get("description", "")).lower().find("sap") >= 0:
        stack.append("SAP")

    unique: list[str] = []
    seen: set[str] = set()
    for item in stack:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique[:4] or ["Microsoft", "ServiceNow", "ITIL"]


def _expected_impact_text(feature: str, impact_list: list[str], fit_score: int) -> str:
    if "Cost" in impact_list or _tokenize(feature) & _COST_KEYWORDS:
        return "Reduces operational cost and manual effort exposure before delivery scaling."
    if "CustomerExperience" in impact_list or _tokenize(feature) & _CX_KEYWORDS:
        return "Improves service responsiveness and user experience during rollout."
    if "Risk" in impact_list or _tokenize(feature) & _SECURITY_KEYWORDS:
        return "Reduces compliance, security, and delivery-governance exposure."
    if fit_score <= 4:
        return "Removes a blocking prerequisite before full delivery commitment."
    return "Improves delivery readiness and closes a material solution gap."


def _dependencies_for_feature(feature: str, resources_needed: list[str], risks: list[str]) -> list[str]:
    dependencies: list[str] = []
    for resource in resources_needed[:2]:
        dependencies.append(resource)
    for risk in risks[:1]:
        if any(token in risk.lower() for token in _tokenize(feature.lower())):
            dependencies.append(risk)
    return dependencies


def _responsible_role_for_resource(resource: str) -> str:
    lowered = resource.lower()
    if any(token in lowered for token in ("security", "privacy", "compliance", "audit")):
        return "Security Officer"
    if any(token in lowered for token in ("data", "mapping", "pipeline", "quality", "etl")):
        return "Data Engineer"
    if any(token in lowered for token in ("architecture", "integration", "platform", "api")):
        return "Solution Architect"
    if any(token in lowered for token in ("product owner", "sponsor", "business")):
        return "Product Owner"
    if any(token in lowered for token in ("adoption", "training", "change")):
        return "Change Manager"
    if any(token in lowered for token in ("analysis", "requirements", "workflow")):
        return "Business Analyst"
    if any(token in lowered for token in ("governance", "steering", "cadence", "lead")):
        return "Project Manager"
    return "Other"


def _target_phase_for_resource(resource: str, delivery_mode: str) -> str:
    lowered = resource.lower()
    if delivery_mode == "PREREQUISITE":
        return "prerequisite"
    if any(token in lowered for token in ("architecture", "requirements", "data flow", "integration")):
        return "design"
    if any(token in lowered for token in ("build", "implementation", "platform")):
        return "build"
    if any(token in lowered for token in ("test", "validation", "quality")):
        return "test"
    if any(token in lowered for token in ("rollout", "deployment", "release")):
        return "deployment"
    if any(token in lowered for token in ("run", "support", "operations", "itil")):
        return "run"
    return "design"


def _priority_for_resource(resource: str, delivery_mode: str) -> str:
    lowered = resource.lower()
    if delivery_mode == "PREREQUISITE":
        return "high"
    if any(token in lowered for token in ("security", "compliance", "integration", "data")):
        return "high"
    return "medium"


def _kpi(
    *,
    identifier: str,
    name: str,
    linked_impact: str,
    metric_type: str,
    unit: str,
    baseline: str,
    target: str,
    measurement: str,
    linked_recommendation_id: str | None,
) -> RecommendationKPI:
    return RecommendationKPI(
        id=identifier,
        name=name,
        linked_impact=linked_impact,
        metric_type=metric_type,
        unit=unit,
        baseline=baseline,
        target=target,
        measurement_criteria=measurement,
        measurement_method=measurement,
        linked_recommendation_id=linked_recommendation_id,
    )


def _default_kpis(impact_list: list[str], technical_recommendations: list[TechnicalRecommendation]) -> list[RecommendationKPI]:
    linked_id = technical_recommendations[0].id if technical_recommendations else None
    kpis: list[RecommendationKPI] = []

    if "Cost" in impact_list:
        kpis.extend([
            _kpi(
                identifier="KPI-001",
                name="Operational cost reduction",
                linked_impact="Cost",
                metric_type="percentage",
                unit="%",
                baseline="Baseline run cost measured during qualification",
                target="Reduce operating cost by 15% within 90 days after go-live",
                measurement="Compare baseline versus post-deployment operating cost by month.",
                linked_recommendation_id=linked_id,
            ),
            _kpi(
                identifier="KPI-002",
                name="Estimated annual savings",
                linked_impact="Cost",
                metric_type="currency",
                unit="€",
                baseline="Current annualized delivery and run cost",
                target="Deliver at least €100k annualized savings",
                measurement="Track run-rate savings validated by Finance after deployment.",
                linked_recommendation_id=linked_id,
            ),
        ])

    if "CustomerExperience" in impact_list:
        kpis.append(
            _kpi(
                identifier=f"KPI-{len(kpis) + 1:03d}",
                name="Average response time",
                linked_impact="CustomerExperience",
                metric_type="duration",
                unit="hours",
                baseline="Current average response time",
                target="Reduce average response time by 30% within 60 days",
                measurement="Measure average response time weekly on the target service journey.",
                linked_recommendation_id=linked_id,
            )
        )

    if "Risk" in impact_list:
        kpis.append(
            _kpi(
                identifier=f"KPI-{len(kpis) + 1:03d}",
                name="Control compliance rate",
                linked_impact="Risk",
                metric_type="percentage",
                unit="%",
                baseline="Current control adherence level",
                target="Reach 95% control compliance before production cutover",
                measurement="Track completion of required controls across design, test, and deployment checkpoints.",
                linked_recommendation_id=linked_id,
            )
        )

    if not kpis:
        kpis.append(
            _kpi(
                identifier="KPI-001",
                name="Delivery readiness",
                linked_impact="Efficiency",
                metric_type="ratio",
                unit="ratio",
                baseline="Current readiness baseline from SG-2",
                target="Close all high-priority gaps before build start",
                measurement="Review prerequisite completion ratio at each steering checkpoint.",
                linked_recommendation_id=linked_id,
            )
        )

    return kpis[:6]


def _dxc_alignment_notes(domains_list: list[str], delivery_mode: str, technical_recommendations: list[TechnicalRecommendation]) -> str:
    dominant_stack = ", ".join(technical_recommendations[0].technology_stack[:3]) if technical_recommendations else "Microsoft, ServiceNow, AWS"
    domain_text = ", ".join(domains_list) if domains_list else "the identified domains"
    mode_text = "Prerequisite actions are prioritized before full delivery." if delivery_mode == "PREREQUISITE" else "The recommendation set is ready for delivery planning."
    return (
        f"DXC ecosystem considered for {domain_text}: {', '.join(DXC_ECOSYSTEM)}. "
        f"The proposed delivery stack stays realistic and uses compatible enterprise components when relevant, with emphasis on {dominant_stack}. "
        f"{mode_text}"
    )


def _parse_llm_json_list(payload: object) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _match_feature_reference(candidate: dict[str, Any], feature: str) -> bool:
    related = candidate.get("related_feature_missing")
    if isinstance(related, str) and feature.lower() == related.strip().lower():
        return True
    if isinstance(related, list) and any(feature.lower() == str(item).strip().lower() for item in related):
        return True
    searchable = " ".join(str(candidate.get(key, "") or "") for key in ("title", "description", "proposed_solution"))
    return feature.lower() in searchable.lower()


def _match_resource_reference(candidate: dict[str, Any], resource: str) -> bool:
    related = str(candidate.get("related_resource_needed", "") or "").strip()
    if related.lower() == resource.lower():
        return True
    searchable = " ".join(str(candidate.get(key, "") or "") for key in ("title", "action"))
    return resource.lower() in searchable.lower()


def _apply_llm_enrichment_to_technical(
    recommendations: list[TechnicalRecommendation],
    llm_items: list[dict[str, Any]],
) -> list[TechnicalRecommendation]:
    enriched: list[TechnicalRecommendation] = []
    for recommendation in recommendations:
        match = next(
            (item for item in llm_items if any(_match_feature_reference(item, feature) for feature in recommendation.related_feature_missing)),
            None,
        )
        if not match:
            enriched.append(recommendation)
            continue
        enriched.append(
            recommendation.model_copy(
                update={
                    "title": str(match.get("title", recommendation.title) or recommendation.title),
                    "description": str(match.get("description", recommendation.description) or recommendation.description),
                    "proposed_solution": str(match.get("proposed_solution", recommendation.proposed_solution) or recommendation.proposed_solution),
                    "technology_stack": _normalize_list(match.get("technology_stack")) or recommendation.technology_stack,
                    "expected_impact": str(match.get("expected_impact", recommendation.expected_impact) or recommendation.expected_impact),
                    "dependencies": _normalize_list(match.get("dependencies")) or recommendation.dependencies,
                }
            )
        )
    return enriched


def _apply_llm_enrichment_to_organizational(
    recommendations: list[OrganizationalRecommendation],
    llm_items: list[dict[str, Any]],
) -> list[OrganizationalRecommendation]:
    enriched: list[OrganizationalRecommendation] = []
    for recommendation in recommendations:
        match = next((item for item in llm_items if _match_resource_reference(item, recommendation.related_resource_needed)), None)
        if not match:
            enriched.append(recommendation)
            continue
        enriched.append(
            recommendation.model_copy(
                update={
                    "title": str(match.get("title", recommendation.title) or recommendation.title),
                    "action": str(match.get("action", recommendation.action) or recommendation.action),
                    "responsible_role": str(match.get("responsible_role", recommendation.responsible_role) or recommendation.responsible_role),
                    "target_phase": str(match.get("target_phase", recommendation.target_phase) or recommendation.target_phase),
                    "priority": str(match.get("priority", recommendation.priority) or recommendation.priority),
                }
            )
        )
    return enriched


def _normalize_kpis_from_llm(payload: object) -> list[RecommendationKPI]:
    items = _parse_llm_json_list(payload)
    normalized: list[RecommendationKPI] = []
    for index, item in enumerate(items, start=1):
        name = str(item.get("name", "") or "").strip()
        target = str(item.get("target", "") or "").strip()
        measurement = str(item.get("measurement_method", item.get("measurement_criteria", "")) or "").strip()
        if not (name and target and measurement):
            continue
        normalized.append(
            RecommendationKPI(
                id=str(item.get("id", f"KPI-{index:03d}")),
                name=name,
                linked_impact=str(item.get("linked_impact", "Other") or "Other"),
                metric_type=str(item.get("metric_type", "count") or "count"),
                unit=str(item.get("unit", "count") or "count"),
                baseline=str(item.get("baseline", "") or ""),
                target=target,
                measurement_criteria=measurement,
                measurement_method=measurement,
                linked_recommendation_id=str(item.get("linked_recommendation_id", "") or "") or None,
            )
        )
    return normalized


def _ensure_feature_coverage(
    features_missing: list[str],
    recommendations: list[TechnicalRecommendation],
    domains_list: list[str],
    solution: dict[str, Any],
    resources_needed: list[str],
    risks: list[str],
    impact_list: list[str],
    fit_score: int,
    delivery_mode: str,
) -> tuple[list[TechnicalRecommendation], list[dict[str, str]], list[str]]:
    covered = {feature.lower() for rec in recommendations for feature in rec.related_feature_missing}
    mapping_audit: list[dict[str, str]] = []
    missing_coverage: list[str] = []
    next_id = len(recommendations) + 1

    for feature in features_missing:
        if feature.lower() in covered:
            mapping_audit.append({"type": "feature_missing", "source": feature, "status": "covered"})
            continue

        priority = _priority_for_text(feature, delivery_mode == "PREREQUISITE")
        recommendation = TechnicalRecommendation(
            id=f"TECH-{next_id:03d}",
            related_feature_missing=[feature],
            title=f"Close gap: {feature}",
            description=f"Treat the missing capability '{feature}' as an explicit delivery workstream before scaling implementation.",
            proposed_solution=(
                f"Design and implement a controlled remediation for '{feature}' using DXC-compatible enterprise components and integration standards."
            ),
            technology_stack=_technology_stack_for_text(feature, domains_list, solution),
            priority=priority,
            estimated_effort=_effort_for_text(feature),
            expected_impact=_expected_impact_text(feature, impact_list, fit_score),
            dependencies=_dependencies_for_feature(feature, resources_needed, risks),
            prerequisite=delivery_mode == "PREREQUISITE" or priority in {"high", "critical"},
        )
        recommendations.append(recommendation)
        covered.add(feature.lower())
        next_id += 1
        mapping_audit.append({"type": "feature_missing", "source": feature, "status": "auto-generated"})
        missing_coverage.append(feature)

    return recommendations, mapping_audit, missing_coverage


def _ensure_resource_coverage(
    resources_needed: list[str],
    recommendations: list[OrganizationalRecommendation],
    delivery_mode: str,
) -> tuple[list[OrganizationalRecommendation], list[dict[str, str]], list[str]]:
    covered = {rec.related_resource_needed.lower() for rec in recommendations}
    mapping_audit: list[dict[str, str]] = []
    missing_coverage: list[str] = []
    next_id = len(recommendations) + 1

    for resource in resources_needed:
        if resource.lower() in covered:
            mapping_audit.append({"type": "resource_needed", "source": resource, "status": "covered"})
            continue

        recommendations.append(
            OrganizationalRecommendation(
                id=f"ORG-{next_id:03d}",
                related_resource_needed=resource,
                title=f"Mobilize organizational dependency: {resource}",
                action=f"Assign ownership and execute the required action for '{resource}' before the target delivery phase.",
                responsible_role=_responsible_role_for_resource(resource),
                target_phase=_target_phase_for_resource(resource, delivery_mode),
                priority=_priority_for_resource(resource, delivery_mode),
            )
        )
        next_id += 1
        covered.add(resource.lower())
        mapping_audit.append({"type": "resource_needed", "source": resource, "status": "auto-generated"})
        missing_coverage.append(resource)

    return recommendations, mapping_audit, missing_coverage


def _ensure_kpi_rules(
    impact_list: list[str],
    kpis: list[RecommendationKPI],
    technical_recommendations: list[TechnicalRecommendation],
) -> tuple[list[RecommendationKPI], bool, list[str]]:
    normalized = list(kpis)
    linked_id = technical_recommendations[0].id if technical_recommendations else None
    missing_coverage: list[str] = []

    if "Cost" in impact_list and not any(item.unit in {"€", "%"} for item in normalized):
        normalized.append(
            _kpi(
                identifier=f"KPI-{len(normalized) + 1:03d}",
                name="Cost treatment reduction",
                linked_impact="Cost",
                metric_type="percentage",
                unit="%",
                baseline="Current operational cost baseline",
                target="Reduce treatment cost by 12% within the first operating quarter",
                measurement="Compare per-case treatment cost before and after implementation.",
                linked_recommendation_id=linked_id,
            )
        )
        missing_coverage.append("Cost KPI rule auto-satisfied")

    if "CustomerExperience" in impact_list and not any(item.unit in {"minutes", "hours", "days"} for item in normalized):
        normalized.append(
            _kpi(
                identifier=f"KPI-{len(normalized) + 1:03d}",
                name="Customer resolution delay",
                linked_impact="CustomerExperience",
                metric_type="duration",
                unit="hours",
                baseline="Current resolution delay baseline",
                target="Reduce average resolution delay by 25% within 60 days",
                measurement="Track resolution duration per interaction on the target process.",
                linked_recommendation_id=linked_id,
            )
        )
        missing_coverage.append("CustomerExperience KPI rule auto-satisfied")

    rules_satisfied = True
    if "Cost" in impact_list and not any(item.unit in {"€", "%"} for item in normalized):
        rules_satisfied = False
    if "CustomerExperience" in impact_list and not any(item.unit in {"minutes", "hours", "days"} for item in normalized):
        rules_satisfied = False

    return normalized[:6], rules_satisfied, missing_coverage


def _build_prerequisite_actions(
    features_missing: list[str],
    technical_recommendations: list[TechnicalRecommendation],
) -> list[PrerequisiteAction]:
    actions: list[PrerequisiteAction] = []
    for index, feature in enumerate(features_missing, start=1):
        related = next((item for item in technical_recommendations if feature in item.related_feature_missing), None)
        actions.append(
            PrerequisiteAction(
                id=f"PRE-{index:03d}",
                title=f"Resolve prerequisite gap: {feature}",
                description=(
                    f"Close the blocking gap '{feature}' before committing to full delivery. "
                    f"Use recommendation {related.id if related else 'TECH'} as the implementation baseline."
                ),
                blocking_gap=feature,
                responsible_role=_responsible_role_for_resource(feature),
                priority="critical" if related and related.priority == "critical" else "high",
            )
        )
    return actions


def _summarize_technical(rec: TechnicalRecommendation) -> str:
    related = ", ".join(rec.related_feature_missing)
    return f"{rec.id} - {rec.title} [{rec.priority}] - covers: {related}"


def _summarize_organizational(rec: OrganizationalRecommendation) -> str:
    return f"{rec.id} - {rec.title} [{rec.priority}] - owner: {rec.responsible_role}"


async def _optional_llm_enrichment(variables: dict[str, str]) -> dict[str, Any]:
    try:
        response = await llm_client.complete(
            prompt_name="solution-recommendations-v2",
            variables=variables,
            response_format="json",
        )
        parsed = llm_client.parse_json_response(response)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


async def generate_solution_recommendations(
    *,
    need_pitch: str,
    horizon: str,
    objectif: str,
    impact_list: list[str],
    domains_list: list[str],
    selected_solution: dict[str, Any],
) -> SolutionRecommendations:
    """Build delivery recommendations with explicit coverage validation."""

    solution_id = str(selected_solution.get("id", "unknown"))
    solution_name = str(selected_solution.get("name", "Unknown solution"))
    description = str(selected_solution.get("description", "") or "")
    features = _normalize_list(selected_solution.get("features"))
    business_impact = str(selected_solution.get("business_impact", "") or "")
    maturity_level = str(selected_solution.get("maturity_level", "") or "")

    gap = selected_solution.get("gap_analysis") if isinstance(selected_solution.get("gap_analysis"), dict) else {}
    features_missing = _extract_gap_items(gap.get("features_missing_detail"), primary_keys=("name", "reason"))
    if not features_missing:
        features_missing = _normalize_list(gap.get("features_missing"))
    resources_needed = _extract_gap_items(gap.get("resources_needed_detail"), primary_keys=("name", "reason"))
    if not resources_needed:
        resources_needed = _normalize_list(gap.get("resources_needed"))
    risks = _extract_gap_items(gap.get("risk_register"), primary_keys=("title", "mitigation"))
    if not risks:
        risks = _normalize_list(gap.get("risks"))
    fit_score = _safe_int(gap.get("fit_score"), 5)
    prerequisite_mode = bool(gap.get("prerequisite_mode")) or fit_score <= 4
    delivery_mode = "PREREQUISITE" if prerequisite_mode else "DELIVERY"

    constraints = {}
    audit = gap.get("audit") if isinstance(gap.get("audit"), dict) else {}
    if isinstance(audit.get("nlp_constraints"), dict):
        constraints = audit["nlp_constraints"]

    technical_recommendations: list[TechnicalRecommendation] = []
    for index, feature in enumerate(features_missing, start=1):
        priority = _priority_for_text(feature, prerequisite_mode)
        technical_recommendations.append(
            TechnicalRecommendation(
                id=f"TECH-{index:03d}",
                related_feature_missing=[feature],
                title=f"Close gap: {feature}",
                description=f"Treat the missing capability '{feature}' as an explicit technical delivery workstream.",
                proposed_solution=(
                    f"Implement a remediation path for '{feature}' with enterprise integration, security, observability, and run-support design from day one."
                ),
                technology_stack=_technology_stack_for_text(feature, domains_list, selected_solution),
                priority=priority,
                estimated_effort=_effort_for_text(feature),
                expected_impact=_expected_impact_text(feature, impact_list, fit_score),
                dependencies=_dependencies_for_feature(feature, resources_needed, risks),
                prerequisite=prerequisite_mode or priority in {"high", "critical"},
            )
        )

    organizational_recommendations: list[OrganizationalRecommendation] = []
    for index, resource in enumerate(resources_needed, start=1):
        organizational_recommendations.append(
            OrganizationalRecommendation(
                id=f"ORG-{index:03d}",
                related_resource_needed=resource,
                title=f"Mobilize: {resource}",
                action=f"Assign a named owner and complete the required action for '{resource}' before the target phase.",
                responsible_role=_responsible_role_for_resource(resource),
                target_phase=_target_phase_for_resource(resource, delivery_mode),
                priority=_priority_for_resource(resource, delivery_mode),
            )
        )

    variables = {
        "pitch": need_pitch,
        "horizon": horizon,
        "objectif": objectif,
        "impact": ", ".join(impact_list) if impact_list else "Not specified",
        "domains": ", ".join(domains_list) if domains_list else "Not specified",
        "solution_name": solution_name,
        "solution_description": description or "Not specified",
        "solution_features": ", ".join(features) if features else "Not listed",
        "solution_business_impact": business_impact or "Not specified",
        "solution_maturity": maturity_level or "Not specified",
        "features_missing_json": json.dumps(features_missing, ensure_ascii=False),
        "resources_needed_json": json.dumps(resources_needed, ensure_ascii=False),
        "risks_json": json.dumps(risks, ensure_ascii=False),
        "constraints_for_gap_analysis_json": json.dumps(constraints, ensure_ascii=False),
        "fit_score": str(fit_score),
        "delivery_mode": delivery_mode,
        "dxc_ecosystem": ", ".join(DXC_ECOSYSTEM),
    }
    llm_payload = await _optional_llm_enrichment(variables)

    technical_recommendations = _apply_llm_enrichment_to_technical(
        technical_recommendations,
        _parse_llm_json_list(llm_payload.get("technical_recommendations")),
    )
    organizational_recommendations = _apply_llm_enrichment_to_organizational(
        organizational_recommendations,
        _parse_llm_json_list(llm_payload.get("organizational_recommendations")),
    )

    technical_recommendations, tech_audit, auto_feature_coverage = _ensure_feature_coverage(
        features_missing,
        technical_recommendations,
        domains_list,
        selected_solution,
        resources_needed,
        risks,
        impact_list,
        fit_score,
        delivery_mode,
    )
    organizational_recommendations, org_audit, auto_resource_coverage = _ensure_resource_coverage(
        resources_needed,
        organizational_recommendations,
        delivery_mode,
    )

    kpis = _normalize_kpis_from_llm(llm_payload.get("kpis")) or _default_kpis(impact_list, technical_recommendations)
    kpis, kpi_rules_satisfied, auto_kpi_coverage = _ensure_kpi_rules(
        impact_list,
        kpis,
        technical_recommendations,
    )

    prerequisite_reason = ""
    prerequisite_actions: list[PrerequisiteAction] = []
    if delivery_mode == "PREREQUISITE":
        prerequisite_reason = (
            f"Fit score is {fit_score}/10, so prerequisite gaps must be closed before full delivery can be committed."
        )
        prerequisite_actions = _build_prerequisite_actions(features_missing, technical_recommendations)

    features_missing_covered = all(
        any(feature in recommendation.related_feature_missing for recommendation in technical_recommendations)
        for feature in features_missing
    )
    resources_needed_covered = all(
        any(resource == recommendation.related_resource_needed for recommendation in organizational_recommendations)
        for resource in resources_needed
    )

    missing_coverage: list[str] = []
    if not features_missing_covered:
        missing_coverage.extend(features_missing)
    if not resources_needed_covered:
        missing_coverage.extend(resources_needed)
    if not kpi_rules_satisfied:
        missing_coverage.append("KPI rules are not fully satisfied")

    dxc_alignment = DxcAlignment(
        ecosystem_considered=DXC_ECOSYSTEM,
        alignment_notes=str(
            ((llm_payload.get("dxc_alignment") or {}).get("alignment_notes"))
            or _dxc_alignment_notes(domains_list, delivery_mode, technical_recommendations)
        ),
    )

    coverage_validation = CoverageValidation(
        features_missing_covered=features_missing_covered,
        resources_needed_covered=resources_needed_covered,
        kpi_rules_satisfied=kpi_rules_satisfied,
        missing_coverage=missing_coverage,
    )

    mapping_audit = tech_audit + org_audit
    mapping_audit.extend({"type": "coverage_auto_fix", "source": item, "status": "applied"} for item in auto_feature_coverage)
    mapping_audit.extend({"type": "coverage_auto_fix", "source": item, "status": "applied"} for item in auto_resource_coverage)
    mapping_audit.extend({"type": "coverage_auto_fix", "source": item, "status": "applied"} for item in auto_kpi_coverage)
    return SolutionRecommendations(
        phase="SG-3",
        solution_id=solution_id,
        solution_name=solution_name,
        delivery_mode=delivery_mode,
        technical_recommendations=technical_recommendations[:8],
        organizational_recommendations=organizational_recommendations[:8],
        kpis=kpis[:6],
        prerequisite_reason=prerequisite_reason,
        prerequisite_actions=prerequisite_actions[:8],
        dxc_alignment=dxc_alignment,
        coverage_validation=coverage_validation,
        technical_recommendation_summaries=[_summarize_technical(item) for item in technical_recommendations[:8]],
        organizational_recommendation_summaries=[_summarize_organizational(item) for item in organizational_recommendations[:8]],
        mapping_audit=mapping_audit,
    )
