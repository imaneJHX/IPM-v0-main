"""Pydantic v2 request / response schemas for the business needs API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional, TypeAlias

from pydantic import BaseModel, Field, field_validator, model_validator

HorizonValue: TypeAlias = Literal["court_terme", "moyen_terme", "long_terme"]
ConfidenceLevel: TypeAlias = Literal["low", "medium", "high"]
ObjectifValue: TypeAlias = Literal[
    "cost_reduction", "cx_improvement", "risk_mitigation", "market_opportunity"
]
DomainValue: TypeAlias = Literal[
    "IA", "Cloud", "Cybersecurite", "Data", "RH", "Finance", "Operations", "Autre"
]
ImpactValue: TypeAlias = Literal["Revenue", "Cost", "Risk", "CustomerExperience"]
OrigineValue: TypeAlias = Literal[
    "enjeu_marche", "probleme_operationnel", "demande_client"
]
SourcingSourceValue: TypeAlias = Literal[
    "probleme_operationnel", "demande_client", "opportunite_marche", "innovation_interne", "autre"
]
SourcingDomainValue: TypeAlias = Literal["IA", "Data", "Process", "Business", "IT", "autre"]
SourcingObjectiveValue: TypeAlias = Literal[
    "optimisation_operationnelle",
    "automatisation",
    "reduction_couts",
    "amelioration_qualite",
    "transformation_strategique",
    "innovation",
    "autre",
]
DataAvailabilityValue: TypeAlias = Literal["available", "partial", "unavailable"]
DataQualityValue: TypeAlias = Literal["high", "medium", "low", "unknown"]
DataAccessibilityValue: TypeAlias = Literal["direct", "mediated", "restricted", "unknown"]
RiskCategoryValue: TypeAlias = Literal["technical", "business", "data", "security", "integration", "adoption", "other"]
RiskSeverityValue: TypeAlias = Literal["low", "medium", "high"]
DeliveryModeValue: TypeAlias = Literal["PREREQUISITE", "DELIVERY"]
RecommendationPriorityValue: TypeAlias = Literal["low", "medium", "high", "critical"]
ResponsibleRoleValue: TypeAlias = Literal[
    "Project Manager",
    "Product Owner",
    "Solution Architect",
    "Data Engineer",
    "Business Analyst",
    "Security Officer",
    "Change Manager",
    "Other",
]
TargetPhaseValue: TypeAlias = Literal["prerequisite", "design", "build", "test", "deployment", "run"]
KpiImpactValue: TypeAlias = Literal["Cost", "CustomerExperience", "Quality", "Efficiency", "Risk", "Compliance", "Other"]
KpiMetricTypeValue: TypeAlias = Literal["currency", "percentage", "duration", "count", "ratio"]
SmartSuggestionCategoryValue: TypeAlias = Literal[
    "Business Framing",
    "Value Angle",
    "Data Readiness",
    "KPI Definition",
    "Risk Alert",
    "Delivery Readiness",
    "Cost Optimization",
    "Customer Experience",
    "Process Improvement",
]
SmartSuggestionActionTypeValue: TypeAlias = Literal["copy", "apply_pitch", "apply_tag", "none"]
KpiUnitValue: TypeAlias = Literal["€", "%", "minutes", "hours", "days", "count", "ratio"]


# ---------------------------------------------------------------------------
# Nested schemas
# ---------------------------------------------------------------------------


class DataContext(BaseModel):
    """Client-declared data readiness captured during sourcing."""

    availability: DataAvailabilityValue = "partial"
    quality: DataQualityValue = "unknown"
    accessibility: DataAccessibilityValue = "unknown"
    notes: str | None = None


class SourcingAmbiguityFlag(BaseModel):
    """Confidence warning propagated from SG-1 into downstream analysis."""

    field: Literal["source", "domain", "objective"]
    confidence: Literal["low", "medium"]
    reason: str


class SourcingSourceTag(BaseModel):
    """Typed SG-1 source classification with explainability."""

    value: SourcingSourceValue
    confidence: ConfidenceLevel = "medium"
    reason: str = ""


class SourcingDomainTag(BaseModel):
    """Typed SG-1 domain classification with explainability."""

    value: SourcingDomainValue
    confidence: ConfidenceLevel = "medium"
    reason: str = ""


class SourcingObjectiveTag(BaseModel):
    """Typed SG-1 objective classification with explainability."""

    value: SourcingObjectiveValue
    confidence: ConfidenceLevel = "medium"
    reason: str = ""
    influencedByHorizon: bool = False


class SourcingGapAnalysisConstraints(BaseModel):
    """Stable SG-1 constraints injected into Gap Analysis."""

    source: SourcingSourceValue
    domain: SourcingDomainValue
    objective: SourcingObjectiveValue
    horizon: HorizonValue | None = None
    ambiguityFlags: list[SourcingAmbiguityFlag] = Field(default_factory=list)


class SourcingClassification(BaseModel):
    """Structured SG-1 classification shown to reviewers and downstream services."""

    phase: Literal["SG-1"] = "SG-1"
    source: SourcingSourceTag
    domain: SourcingDomainTag
    objective: SourcingObjectiveTag
    constraintsForGapAnalysis: SourcingGapAnalysisConstraints

class Tags(BaseModel):
    """AI-generated metadata tags for a business need."""

    objectif: ObjectifValue = Field(description="Primary objective classification")
    domaine: list[DomainValue] = Field(
        default_factory=list,
        description="Business domains (IA, Cloud, etc.)",
    )
    impact: list[ImpactValue] = Field(
        default_factory=list,
        description="Impact areas (Revenue, Cost, etc.)",
    )
    origine: OrigineValue = Field(description="Origin classification")
    objectif_confidence: ConfidenceLevel = Field(
        default="medium",
        description="Confidence score for the selected objective",
    )
    domaine_confidence: dict[str, ConfidenceLevel] = Field(
        default_factory=dict,
        description="Confidence score per selected domain",
    )
    impact_confidence: dict[str, ConfidenceLevel] = Field(
        default_factory=dict,
        description="Confidence score per selected impact",
    )
    origine_confidence: ConfidenceLevel = Field(
        default="medium",
        description="Confidence score for the selected origin",
    )
    horizon_conflict: bool = Field(
        default=False,
        description="True when the declared horizon conflicts with the inferred objective orientation",
    )
    data_context: DataContext | None = Field(
        default=None,
        description="Client-declared data readiness reused by qualification scoring",
    )
    gap_analysis_constraints: GapAnalysisConstraints | None = Field(
        default=None,
        description="Structured sourcing constraints reused by Gap Analysis",
    )
    sourcing_classification: SourcingClassification | None = Field(
        default=None,
        description="Typed SG-1 classification with confidence, reasons, and gap-analysis constraints",
    )


class ClassifiedConstraint(BaseModel):
    """A single classification value with its confidence level."""

    value: str
    confidence: ConfidenceLevel = "medium"
    reason: str | None = None


class GapAnalysisConstraints(BaseModel):
    """Structured sourcing output that can be injected into gap analysis."""

    phase: Literal["SG-1"] = "SG-1"
    horizon: HorizonValue | None = None
    horizon_conflict: bool = False
    objectif: ClassifiedConstraint
    domaine: list[ClassifiedConstraint] = Field(default_factory=list)
    impact: list[ClassifiedConstraint] = Field(default_factory=list)
    origine: ClassifiedConstraint
    constraintsForGapAnalysis: SourcingGapAnalysisConstraints | None = None
    inference_explicit: bool = False
    measurable_result_detected: bool = False
    named_client_detected: bool = False
    hard_rules: list[str] = Field(default_factory=list)


class DuplicateMatch(BaseModel):
    """A potential duplicate business need found via vector similarity."""

    id: str
    pitch: str
    status: str
    similarity_score: float = Field(ge=0.0, le=1.0)


class Suggestion(BaseModel):
    """AI-generated smart suggestion for SG-1 live guidance."""

    id: str
    title: str
    category: SmartSuggestionCategoryValue
    explanation: str
    improved_pitch: str | None = None
    next_action: str
    confidence: ConfidenceLevel = "medium"
    action_type: SmartSuggestionActionTypeValue = "copy"
    suggested_tags: list[str] = Field(default_factory=list)
    label: str | None = None
    text: str | None = None

    @field_validator("suggested_tags", mode="before")
    @classmethod
    def normalize_suggested_tags(cls, value: object) -> list[str]:
        """Keep suggested tags compact, ordered, and de-duplicated."""
        if not isinstance(value, list):
            return []
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            text = str(item or "").strip()
            if not text:
                continue
            lowered = text.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            normalized.append(text)
        return normalized

    @model_validator(mode="after")
    def sync_legacy_fields(self) -> "Suggestion":
        """Preserve legacy label/text fields for older consumers."""
        if not self.label:
            self.label = self.title
        if not self.text:
            self.text = self.improved_pitch or self.next_action or self.explanation
        return self


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    """Request body for the /needs/analyze endpoint."""

    pitch: str = Field(min_length=1, description="Free-text pitch to analyze")
    horizon: HorizonValue | None = Field(
        default=None,
        description="Optional delivery horizon used as classification context",
    )
    objective: str | None = Field(default=None, description="Current objective selection or inferred objective")
    domains: list[str] = Field(default_factory=list, description="Current domain tags or user-confirmed domains")
    impacts: list[str] = Field(default_factory=list, description="Current impact tags or user-confirmed impacts")
    tags: list[str] = Field(default_factory=list, description="Flattened NLP or UI tags already visible in SG-1")
    phase: str = Field(default="SG-1", description="Current stage-gate phase")
    status: str = Field(default="Draft", description="Current validation status shown in the UI")

    @field_validator("pitch")
    @classmethod
    def normalize_analyze_pitch(cls, value: str) -> str:
        """Normalize the live-analysis pitch without changing its intent."""
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Pitch must not be empty or whitespace only")
        return cleaned

    @field_validator("domains", "impacts", "tags", mode="before")
    @classmethod
    def normalize_live_context_lists(cls, value: object) -> list[str]:
        """Normalize additive live-analysis context lists."""
        if not isinstance(value, list):
            return []
        normalized: list[str] = []
        seen: set[str] = set()
        for item in value:
            text = str(item or "").strip()
            if not text:
                continue
            lowered = text.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            normalized.append(text)
        return normalized


class CreateNeedRequest(BaseModel):
    """Request body for POST /needs — only 2 fields from the user."""

    pitch: str = Field(min_length=20, description="Free-text pitch (≥20 chars)")
    horizon: HorizonValue
    tags: Tags | None = Field(default=None, description="Optional precomputed tags from /needs/analyze")
    data_context: DataContext | None = Field(
        default=None,
        description="Optional sourcing data-readiness answers",
    )

    @field_validator("pitch")
    @classmethod
    def pitch_not_blank(cls, v: str) -> str:
        """Ensure pitch is not just whitespace."""
        if not v.strip():
            raise ValueError("Pitch must not be empty or whitespace only")
        return v.strip()


class UpdateStatusRequest(BaseModel):
    """Request body for PATCH /needs/{id}/status."""

    status: Literal["draft", "submitted", "in_qualification", "in_selection", "delivery", "export_ready", "abandoned"]
    note: str | None = Field(
        default=None,
        description="Optional note. Required when abandoning, and reused for same-step rework requests.",
    )

    @field_validator("note")
    @classmethod
    def note_required_for_rework_or_abandon(cls, v: str | None, info) -> str | None:
        """Validate that a note is provided when transitioning to abandonment."""
        status = info.data.get("status")
        if status == "abandoned" and not v:
            raise ValueError(f"A note/reason is required when setting status to '{status}'")
        return v


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class AnalyzeResponse(BaseModel):
    """Response for the /needs/analyze endpoint."""

    tags: Tags
    suggestions: list[Suggestion] = Field(default_factory=list)


class BusinessNeedResponse(BaseModel):
    """Full business need object returned by the API."""

    id: str
    pitch: str
    horizon: HorizonValue
    tags: Tags
    status: Literal["draft", "submitted", "in_qualification", "in_selection", "delivery", "export_ready", "abandoned"]
    rework_note: str | None = None
    duplicate_matches: list[DuplicateMatch] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Catalog search schemas
# ---------------------------------------------------------------------------

class CatalogProduct(BaseModel):
    """A DXC product returned by the catalog similarity search."""

    id: str
    name: str
    description: str
    ipm_stage: Optional[str] = None
    internal_external: Optional[str] = None
    industry_focus: Optional[str] = None
    ai_type: Optional[str] = None
    ai_criticality: Optional[str] = None
    maturity_level: Optional[str] = None
    value_layer: Optional[str] = None
    monetization_potential: Optional[str] = None
    business_impact: Optional[str] = None
    lead: Optional[str] = None
    features: list[str] = Field(default_factory=list)
    relevance_score: float


class CatalogSearchResponse(BaseModel):
    """Response for the catalog-search endpoint."""

    results: list[CatalogProduct]
    total: int


# ---------------------------------------------------------------------------
# Gap analysis schemas
# ---------------------------------------------------------------------------

class GapAnalysisRequest(BaseModel):
    """Request body for the gap-analysis endpoint."""

    selected_solution: dict


class ScoredDimension(BaseModel):
    """A scored qualification dimension with an explicit justification."""

    score: int = Field(ge=1, le=5)
    justification: str
    client_reassurance: str | None = None
    reassurance_message: str | None = None

    @model_validator(mode="after")
    def sync_reassurance_fields(self) -> "ScoredDimension":
        """Keep legacy and new reassurance field names aligned."""
        if self.client_reassurance and not self.reassurance_message:
            self.reassurance_message = self.client_reassurance
        elif self.reassurance_message and not self.client_reassurance:
            self.client_reassurance = self.reassurance_message
        return self


class IVIScoring(BaseModel):
    """Qualification scores aligned with the IVI framework."""

    maturite: ScoredDimension
    expertise: ScoredDimension
    duree: ScoredDimension
    donnees: ScoredDimension
    impact_business: ScoredDimension


class QualificationScoreDimension(BaseModel):
    """Primary SG-2 score block normalized on a 0-10 scale."""

    score: int = Field(ge=0, le=10)
    justification: str


class QualificationScores(BaseModel):
    """Structured SG-2 scorecard aligned with the five IVI dimensions."""

    maturite: QualificationScoreDimension
    expertise: QualificationScoreDimension
    duree: QualificationScoreDimension
    donnees: QualificationScoreDimension
    impact_business: QualificationScoreDimension


class RequiredProfile(BaseModel):
    """DXC profile matched for delivery staffing."""

    profile_id: str
    name: str
    seniority_level: Literal["junior", "mid", "senior"]
    daily_capacity: int = Field(ge=1)
    estimated_people: int = Field(ge=1)
    matched_skills: list[str] = Field(default_factory=list)
    typical_tasks: list[str] = Field(default_factory=list)
    rationale: str


class GapAnalysisRuleAudit(BaseModel):
    """Deterministic rule application details for auditability."""

    code: str
    applied: bool
    detail: str


class GapContextCompressionAudit(BaseModel):
    """Signals retained after solution-context compression."""

    domain_tags: list[str] = Field(default_factory=list)
    impact_tags: list[str] = Field(default_factory=list)
    objective_tags: list[str] = Field(default_factory=list)
    constraints_used: list[str] = Field(default_factory=list)
    retained_features: list[str] = Field(default_factory=list)
    retained_description_sentences: list[str] = Field(default_factory=list)
    retained_business_impact_sentences: list[str] = Field(default_factory=list)
    omitted_features_count: int = Field(default=0, ge=0)
    excluded_items_count: int = Field(default=0, ge=0)
    filter_reason: str = ""
    fallback_to_full_context: bool = False
    included_items: list[str] = Field(default_factory=list)


class GapFeatureMatch(BaseModel):
    """Structured coverage evidence for a matching capability."""

    name: str
    evidence: str
    impact: str


class GapFeatureMissing(BaseModel):
    """Structured missing capability entry for auditability."""

    name: str
    reason: str
    impact: str


class GapRisk(BaseModel):
    """Structured risk register entry kept separate from missing features."""

    title: str
    category: RiskCategoryValue
    severity: RiskSeverityValue
    mitigation: str


class GapResourceNeed(BaseModel):
    """Structured delivery resource or dependency entry."""

    name: str
    reason: str


class SolutionContextFiltered(BaseModel):
    """Trace of the context-compression subset used for scoring and prompting."""

    included_items: list[str] = Field(default_factory=list)
    excluded_count: int = Field(default=0, ge=0)
    filter_reason: str = ""
    fallback_to_full_context: bool = False


class GapCalibrationApplied(BaseModel):
    """Trace of a business-rule calibration applied after initial scoring."""

    rule: str
    field: str
    previous_score: int = Field(ge=0, le=10)
    new_score: int = Field(ge=0, le=10)
    reason: str


class GapRecommendation(BaseModel):
    """Final SG-2 recommendation after calibrated scoring."""

    decision: Literal["go", "go_with_conditions", "no_go", "needs_more_information"]
    justification: str


class GapAnalysisAudit(BaseModel):
    """Audit trail attached to a gap-analysis response."""

    applied_rules: list[GapAnalysisRuleAudit] = Field(default_factory=list)
    context_compression: GapContextCompressionAudit
    nlp_constraints: SourcingGapAnalysisConstraints | None = None
    ambiguity_flags: list[SourcingAmbiguityFlag] = Field(default_factory=list)


class GapAnalysisResponse(BaseModel):
    """Response for the gap-analysis endpoint."""

    phase: Literal["SG-2"] = "SG-2"
    solution_name: str
    fit_score: int = Field(ge=1, le=10)
    fit_justification: str
    client_message: str
    feasibility: ScoredDimension
    ivi_scoring: IVIScoring
    scores: QualificationScores | None = None
    ivi_score: float = Field(ge=0, le=100)
    prerequisite_mode: bool = False
    estimated_duration_months: float = Field(default=0, ge=0)
    duration_formula: str = ""
    required_profiles: list[RequiredProfile] = Field(default_factory=list)
    features_matching: list[str] = Field(default_factory=list)
    features_missing: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    resources_needed: list[str] = Field(default_factory=list)
    features_matching_detail: list[GapFeatureMatch] = Field(default_factory=list)
    features_missing_detail: list[GapFeatureMissing] = Field(default_factory=list)
    risk_register: list[GapRisk] = Field(default_factory=list)
    resources_needed_detail: list[GapResourceNeed] = Field(default_factory=list)
    solution_context_filtered: SolutionContextFiltered | None = None
    calibration_applied: list[GapCalibrationApplied] = Field(default_factory=list)
    recommendation: GapRecommendation | None = None
    audit: GapAnalysisAudit


class GapAnalysisFeedbackRequest(BaseModel):
    """Request body for gap-analysis feedback adjustments."""

    comment: str = Field(min_length=1)


class GapAnalysisFeedbackResponse(BaseModel):
    """Response for gap-analysis feedback adjustments."""

    comment: str
    aspect_feedback: list["ABSAExtraction"] = Field(default_factory=list)
    diffs: list["StageGateDiffEntry"] = Field(default_factory=list)
    gap_analysis: GapAnalysisResponse


# ---------------------------------------------------------------------------
# Delivery recommendations schemas
# ---------------------------------------------------------------------------

class RecommendationsRequest(BaseModel):
    """Request body for the recommendations endpoint."""

    selected_solutions: list[dict] = Field(default_factory=list)


class RecommendationKPI(BaseModel):
    """A measurable KPI recommendation for a selected solution."""

    id: str = ""
    name: str
    linked_impact: KpiImpactValue = "Other"
    metric_type: KpiMetricTypeValue = "count"
    unit: KpiUnitValue = "count"
    baseline: str = ""
    target: str
    measurement_criteria: str
    measurement_method: str | None = None
    linked_recommendation_id: str | None = None

    @model_validator(mode="after")
    def sync_measurement_fields(self) -> "RecommendationKPI":
        """Keep legacy and structured KPI measurement fields aligned."""
        if self.measurement_method and not self.measurement_criteria:
            self.measurement_criteria = self.measurement_method
        elif self.measurement_criteria and not self.measurement_method:
            self.measurement_method = self.measurement_criteria
        return self


class TechnicalRecommendation(BaseModel):
    """Delivery-ready technical recommendation mapped to one or more missing features."""

    id: str
    related_feature_missing: list[str] = Field(default_factory=list)
    title: str
    description: str
    proposed_solution: str
    technology_stack: list[str] = Field(default_factory=list)
    priority: RecommendationPriorityValue = "medium"
    estimated_effort: Literal["S", "M", "L", "XL"] = "M"
    expected_impact: str
    dependencies: list[str] = Field(default_factory=list)
    prerequisite: bool = False


class OrganizationalRecommendation(BaseModel):
    """Organizational recommendation mapped to an identified resource need."""

    id: str
    related_resource_needed: str
    title: str
    action: str
    responsible_role: ResponsibleRoleValue = "Other"
    target_phase: TargetPhaseValue = "design"
    priority: RecommendationPriorityValue = "medium"


class PrerequisiteAction(BaseModel):
    """Blocking action required before full delivery can start."""

    id: str
    title: str
    description: str
    blocking_gap: str
    responsible_role: ResponsibleRoleValue = "Other"
    priority: Literal["high", "critical"] = "high"


class DxcAlignment(BaseModel):
    """Trace of DXC ecosystem consideration for delivery recommendations."""

    ecosystem_considered: list[Literal["Microsoft", "SAP", "ServiceNow", "AWS", "ITIL"]] = Field(default_factory=list)
    alignment_notes: str = ""


class CoverageValidation(BaseModel):
    """Post-generation validation that every detected gap/resource is covered."""

    features_missing_covered: bool = False
    resources_needed_covered: bool = False
    kpi_rules_satisfied: bool = False
    missing_coverage: list[str] = Field(default_factory=list)


class SolutionRecommendations(BaseModel):
    """Structured recommendations for one selected solution."""

    phase: Literal["SG-3"] = "SG-3"
    solution_id: str
    solution_name: str
    delivery_mode: DeliveryModeValue = "DELIVERY"
    technical_recommendations: list[TechnicalRecommendation] = Field(default_factory=list)
    organizational_recommendations: list[OrganizationalRecommendation] = Field(default_factory=list)
    kpis: list[RecommendationKPI]
    prerequisite_reason: str = ""
    prerequisite_actions: list[PrerequisiteAction] = Field(default_factory=list)
    dxc_alignment: DxcAlignment
    coverage_validation: CoverageValidation
    technical_recommendation_summaries: list[str] = Field(default_factory=list)
    organizational_recommendation_summaries: list[str] = Field(default_factory=list)
    mapping_audit: list[dict[str, str]] = Field(default_factory=list)


class RecommendationsResponse(BaseModel):
    """Response for the recommendations endpoint."""

    recommendations: list[SolutionRecommendations]


class ExportDeliverySolution(BaseModel):
    """Selected solution summary included in export payload."""

    id: str
    name: str
    relevance: float
    overall: float


class ExportSelectedSolution(BaseModel):
    """Enriched selected solution context used to build delivery reports."""

    id: str
    name: str
    relevance: float = 0
    overall: float = 0
    description: str | None = None
    source: str | None = None
    features: list[str] = Field(default_factory=list)
    business_impact: str | None = None
    maturity_level: str | None = None
    gap_analysis: GapAnalysisResponse | None = None


class ExportStageGateSummary(BaseModel):
    """Stage gate decisions included in the exported report."""

    gate: Literal["SG-1", "SG-2", "SG-3", "SG-4"]
    phase: str
    decision: Literal["GO", "REWORK", "ABANDON", "PENDING"]
    status_after: str | None = None
    comment: str | None = None


class ExportReportRequest(BaseModel):
    """Request body for document export endpoints."""

    recommendations: list[SolutionRecommendations]
    delivery_solutions: list[ExportDeliverySolution]
    selected_solutions: list[ExportSelectedSolution] = Field(default_factory=list)
    stage_gates: list[ExportStageGateSummary] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Tech Signals schemas
# ---------------------------------------------------------------------------

class TechSignal(BaseModel):
    """A single enriched tech signal returned by the tech-signals endpoint."""

    id: str                        # Tavily result URL — used as ChromaDB doc ID
    title: str
    url: str
    source: str                    # domain extracted from URL, "www." stripped
    published_date: str | None = None
    signal_type: str               # "patent"|"research"|"news"|"startup"|"trend"
    maturity_level: str            # "emerging"|"growing"|"mature"
    relevance_score: float         # 0.0 → 1.0 from Tavily score
    groq_insight: str              # 1-sentence enrichment from Groq, max 25 words
    raw_snippet: str               # original Tavily content snippet, max 400 chars


class TechSignalsResponse(BaseModel):
    """Response for the tech-signals endpoint."""

    signals: list[TechSignal]
    query_used: str                # the Tavily query (for transparency/debug)
    from_cache: bool               # True if returned from ChromaDB without Tavily call


class ABSAExtraction(BaseModel):
    """Single aspect-based sentiment extraction from client feedback."""

    aspect: Literal["expertise", "maturité", "durée", "données", "impact_business"]
    sentiment: Literal["positif", "négatif", "neutre"]
    intensité: Literal["faible", "moyen", "fort"]
    extrait: str


class StageGateDiffEntry(BaseModel):
    """Visible before/after change for a gate correction cycle."""

    field: str
    before: str
    after: str
    justification: str


class StageGateMessage(BaseModel):
    """One message in the conversational gate session history."""

    role: Literal["agent", "reviewer"]
    content: str


class StageGateSummaryItem(BaseModel):
    """Structured summary row shown by a stage gate."""

    label: str
    value: str


class StageGateInteractionRequest(BaseModel):
    """User input sent to a stage gate mini-agent."""

    gate: Literal["SG-1", "SG-3", "SG-4"]
    action: Literal["GO", "REWORK", "ABANDON", "SUMMARY"]
    comment: str | None = None
    snapshot: dict = Field(default_factory=dict)


class StageGateInteractionResponse(BaseModel):
    """Conversational state returned by a gate mini-agent."""

    gate: Literal["SG-1", "SG-3", "SG-4"]
    phase: str
    decision: Literal["GO", "REWORK", "ABANDON", "PENDING", "ESCALATE"]
    recommendation: str
    summary: list[StageGateSummaryItem] = Field(default_factory=list)
    actions: list[Literal["GO", "REWORK", "ABANDON"]] = Field(default_factory=list)
    messages: list[StageGateMessage] = Field(default_factory=list)
    aspect_feedback: list[ABSAExtraction] = Field(default_factory=list)
    diffs: list[StageGateDiffEntry] = Field(default_factory=list)
    corrected_snapshot: dict = Field(default_factory=dict)
    nb_reworks: int = 0
    escalated: bool = False
