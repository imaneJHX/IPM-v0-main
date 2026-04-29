/**
 * TypeScript interfaces mirroring backend Pydantic schemas.
 */

export type Horizon = "court_terme" | "moyen_terme" | "long_terme";
export type Confidence = "low" | "medium" | "high";
export type SourcingSource =
    | "probleme_operationnel"
    | "demande_client"
    | "opportunite_marche"
    | "innovation_interne"
    | "autre";
export type SourcingDomain = "IA" | "Data" | "Process" | "Business" | "IT" | "autre";
export type SourcingObjective =
    | "optimisation_operationnelle"
    | "automatisation"
    | "reduction_couts"
    | "amelioration_qualite"
    | "transformation_strategique"
    | "innovation"
    | "autre";

export type Status =
    | "draft"
    | "submitted"
    | "in_qualification"
    | "in_selection"
    | "delivery"
    | "export_ready"
    | "abandoned";

export type Objectif = "cost_reduction" | "cx_improvement" | "risk_mitigation" | "market_opportunity";
export type Domain = "IA" | "Cloud" | "Cybersecurite" | "Data" | "RH" | "Finance" | "Operations" | "Autre";
export type Impact = "Revenue" | "Cost" | "Risk" | "CustomerExperience";

export type Origine = "enjeu_marche" | "probleme_operationnel" | "demande_client";
export type DataAvailability = "available" | "partial" | "unavailable";
export type DataQuality = "high" | "medium" | "low" | "unknown";
export type DataAccessibility = "direct" | "mediated" | "restricted" | "unknown";

export interface ClassifiedConstraint {
    value: string;
    confidence: Confidence;
    reason?: string | null;
}

export interface SourcingAmbiguityFlag {
    field: "source" | "domain" | "objective";
    confidence: "low" | "medium";
    reason: string;
}

export interface SourcingSourceTag {
    value: SourcingSource;
    confidence: Confidence;
    reason: string;
}

export interface SourcingDomainTag {
    value: SourcingDomain;
    confidence: Confidence;
    reason: string;
}

export interface SourcingObjectiveTag {
    value: SourcingObjective;
    confidence: Confidence;
    reason: string;
    influencedByHorizon: boolean;
}

export interface SourcingGapAnalysisConstraints {
    source: SourcingSource;
    domain: SourcingDomain;
    objective: SourcingObjective;
    horizon: Horizon | null;
    ambiguityFlags: SourcingAmbiguityFlag[];
}

export interface SourcingClassification {
    phase: "SG-1";
    source: SourcingSourceTag;
    domain: SourcingDomainTag;
    objective: SourcingObjectiveTag;
    constraintsForGapAnalysis: SourcingGapAnalysisConstraints;
}

export interface GapAnalysisConstraints {
    phase?: "SG-1";
    horizon: Horizon | null;
    objectif: ClassifiedConstraint;
    domaine: ClassifiedConstraint[];
    impact: ClassifiedConstraint[];
    origine: ClassifiedConstraint;
    constraintsForGapAnalysis?: SourcingGapAnalysisConstraints | null;
    inference_explicit: boolean;
    measurable_result_detected: boolean;
    named_client_detected: boolean;
    hard_rules: string[];
}

export interface DataContext {
    availability: DataAvailability;
    quality: DataQuality;
    accessibility: DataAccessibility;
    notes?: string | null;
}

export interface Tags {
    objectif: Objectif;
    domaine: Domain[];
    impact: Impact[];
    origine: Origine;
    objectif_confidence: Confidence;
    domaine_confidence: Partial<Record<Domain, Confidence>>;
    impact_confidence: Partial<Record<Impact, Confidence>>;
    origine_confidence: Confidence;
    data_context: DataContext | null;
    gap_analysis_constraints: GapAnalysisConstraints | null;
    sourcing_classification?: SourcingClassification | null;
}

export const CATEGORIES = ["Coût", "Expérience client", "Risque", "Opportunité marché"] as const;
export type Category = (typeof CATEGORIES)[number];

export interface DuplicateMatch {
    id: string;
    pitch: string;
    status: Status;
    similarity_score: number;
}

export type SmartSuggestionCategory =
    | "Business Framing"
    | "Value Angle"
    | "Data Readiness"
    | "KPI Definition"
    | "Risk Alert"
    | "Delivery Readiness"
    | "Cost Optimization"
    | "Customer Experience"
    | "Process Improvement";

export interface SmartSuggestion {
    id: string;
    title: string;
    category: SmartSuggestionCategory;
    explanation: string;
    improved_pitch?: string | null;
    next_action: string;
    confidence: Confidence;
    action_type?: "copy" | "apply_pitch" | "apply_tag" | "none";
    suggested_tags?: string[];
    label?: string | null;
    text?: string | null;
}

export interface AnalyzeRequest {
    pitch: string;
    horizon?: Horizon | null;
    objective?: string | null;
    domains?: string[];
    impacts?: string[];
    tags?: string[];
    phase?: string;
    status?: string;
}

export interface BusinessNeed {
    id: string;
    pitch: string;
    horizon: Horizon;
    tags: Tags;
    status: Status;
    rework_note?: string | null;
    duplicate_matches: DuplicateMatch[];
    created_at: string;
    updated_at: string;
}

export interface AnalyzeResponse {
    tags: Tags;
    suggestions: SmartSuggestion[];
}

export interface CreateNeedRequest {
    pitch: string;
    horizon: Horizon;
    tags?: Tags;
    data_context?: DataContext | null;
}

export interface UpdateStatusRequest {
    status: Status;
    note?: string;
}

export interface CatalogProduct {
    id: string;
    name: string;
    description: string;
    ipm_stage?: string;
    internal_external?: string;
    industry_focus?: string;
    ai_type?: string;
    ai_criticality?: string;
    maturity_level?: string;
    value_layer?: string;
    monetization_potential?: string;
    business_impact?: string;
    lead?: string;
    features: string[];
    relevance_score: number;
}

export interface CatalogSearchResponse {
    results: CatalogProduct[];
    total: number;
}

export interface ScoredDimension {
    score: number;
    justification: string;
    client_reassurance?: string | null;
    reassurance_message?: string | null;
}

export interface IVIScoring {
    maturite: ScoredDimension;
    expertise: ScoredDimension;
    duree: ScoredDimension;
    donnees: ScoredDimension;
    impact_business: ScoredDimension;
}

export interface QualificationScoreDimension {
    score: number;
    justification: string;
}

export interface QualificationScores {
    maturite: QualificationScoreDimension;
    expertise: QualificationScoreDimension;
    duree: QualificationScoreDimension;
    donnees: QualificationScoreDimension;
    impact_business: QualificationScoreDimension;
}

export interface RequiredProfile {
    profile_id: string;
    name: string;
    seniority_level: "junior" | "mid" | "senior";
    daily_capacity: number;
    estimated_people: number;
    matched_skills: string[];
    typical_tasks: string[];
    rationale: string;
}

export interface GapAnalysisAuditRule {
    code: string;
    applied: boolean;
    detail: string;
}

export interface GapContextCompressionAudit {
    domain_tags: string[];
    impact_tags: string[];
    objective_tags: string[];
    constraints_used: string[];
    retained_features: string[];
    retained_description_sentences: string[];
    retained_business_impact_sentences: string[];
    omitted_features_count: number;
    excluded_items_count: number;
    filter_reason: string;
    fallback_to_full_context: boolean;
    included_items: string[];
}

export interface GapAnalysisAudit {
    applied_rules: GapAnalysisAuditRule[];
    context_compression: GapContextCompressionAudit;
    nlp_constraints?: SourcingGapAnalysisConstraints | null;
    ambiguity_flags?: SourcingAmbiguityFlag[];
}

export interface GapFeatureMatch {
    name: string;
    evidence: string;
    impact: string;
}

export interface GapFeatureMissing {
    name: string;
    reason: string;
    impact: string;
}

export interface GapRisk {
    title: string;
    category: "technical" | "business" | "data" | "security" | "integration" | "adoption" | "other";
    severity: "low" | "medium" | "high";
    mitigation: string;
}

export interface GapResourceNeed {
    name: string;
    reason: string;
}

export interface SolutionContextFiltered {
    included_items: string[];
    excluded_count: number;
    filter_reason: string;
    fallback_to_full_context: boolean;
}

export interface GapCalibrationApplied {
    rule: string;
    field: string;
    previous_score: number;
    new_score: number;
    reason: string;
}

export interface GapRecommendation {
    decision: "go" | "go_with_conditions" | "no_go" | "needs_more_information";
    justification: string;
}

export interface GapAnalysisResponse {
    phase?: "SG-2";
    solution_name: string;
    fit_score: number;
    fit_justification: string;
    client_message: string;
    feasibility: ScoredDimension;
    ivi_scoring: IVIScoring;
    scores?: QualificationScores | null;
    ivi_score: number;
    prerequisite_mode: boolean;
    estimated_duration_months: number;
    duration_formula: string;
    required_profiles: RequiredProfile[];
    features_matching: string[];
    features_missing: string[];
    risks: string[];
    resources_needed: string[];
    features_matching_detail?: GapFeatureMatch[];
    features_missing_detail?: GapFeatureMissing[];
    risk_register?: GapRisk[];
    resources_needed_detail?: GapResourceNeed[];
    solution_context_filtered?: SolutionContextFiltered | null;
    calibration_applied?: GapCalibrationApplied[];
    recommendation?: GapRecommendation | null;
    audit: GapAnalysisAudit;
    evaluation_scores?: {
        fit: number;
        feasibility: number;
        cost: number;
        innovation: number;
    };
}

export interface GapAnalysisFeedbackRequest {
    comment: string;
}

export interface GapAnalysisFeedbackResponse {
    comment: string;
    aspect_feedback: ABSAExtraction[];
    diffs: StageGateDiffEntry[];
    gap_analysis: GapAnalysisResponse;
}

export interface RecommendationKPI {
    id?: string;
    name: string;
    linked_impact?: "Cost" | "CustomerExperience" | "Quality" | "Efficiency" | "Risk" | "Compliance" | "Other";
    metric_type?: "currency" | "percentage" | "duration" | "count" | "ratio";
    unit?: "€" | "%" | "minutes" | "hours" | "days" | "count" | "ratio";
    baseline?: string;
    target: string;
    measurement_criteria: string;
    measurement_method?: string | null;
    linked_recommendation_id?: string | null;
}

export interface TechnicalRecommendation {
    id: string;
    related_feature_missing: string[];
    title: string;
    description: string;
    proposed_solution: string;
    technology_stack: string[];
    priority: "low" | "medium" | "high" | "critical";
    estimated_effort: "S" | "M" | "L" | "XL";
    expected_impact: string;
    dependencies: string[];
    prerequisite?: boolean;
}

export interface OrganizationalRecommendation {
    id: string;
    related_resource_needed: string;
    title: string;
    action: string;
    responsible_role: "Project Manager" | "Product Owner" | "Solution Architect" | "Data Engineer" | "Business Analyst" | "Security Officer" | "Change Manager" | "Other";
    target_phase: "prerequisite" | "design" | "build" | "test" | "deployment" | "run";
    priority: "low" | "medium" | "high" | "critical";
}

export interface PrerequisiteAction {
    id: string;
    title: string;
    description: string;
    blocking_gap: string;
    responsible_role: "Project Manager" | "Product Owner" | "Solution Architect" | "Data Engineer" | "Business Analyst" | "Security Officer" | "Change Manager" | "Other";
    priority: "high" | "critical";
}

export interface DxcAlignment {
    ecosystem_considered: Array<"Microsoft" | "SAP" | "ServiceNow" | "AWS" | "ITIL">;
    alignment_notes: string;
}

export interface CoverageValidation {
    features_missing_covered: boolean;
    resources_needed_covered: boolean;
    kpi_rules_satisfied: boolean;
    missing_coverage: string[];
}

export interface SolutionRecommendations {
    phase?: "SG-3";
    solution_id: string;
    solution_name: string;
    delivery_mode?: "PREREQUISITE" | "DELIVERY";
    technical_recommendations: TechnicalRecommendation[];
    organizational_recommendations: OrganizationalRecommendation[];
    kpis: RecommendationKPI[];
    prerequisite_reason?: string;
    prerequisite_actions?: PrerequisiteAction[];
    dxc_alignment?: DxcAlignment | null;
    coverage_validation?: CoverageValidation | null;
    technical_recommendation_summaries?: string[];
    organizational_recommendation_summaries?: string[];
    mapping_audit: Array<Record<string, string>>;
}

export interface RecommendationsResponse {
    recommendations: SolutionRecommendations[];
}

export interface RecommendationsRequest {
    selected_solutions: Array<Record<string, unknown>>;
}

export interface ExportDeliverySolution {
    id: string;
    name: string;
    relevance: number;
    overall: number;
}

export interface ExportSelectedSolution {
    id: string;
    name: string;
    relevance: number;
    overall: number;
    description?: string;
    source?: string;
    features: string[];
    business_impact?: string;
    maturity_level?: string;
    gap_analysis?: GapAnalysisResponse | null;
}

export interface ExportStageGateSummary {
    gate: "SG-1" | "SG-2" | "SG-3" | "SG-4";
    phase: string;
    decision: "GO" | "REWORK" | "ABANDON" | "PENDING";
    status_after?: string | null;
    comment?: string | null;
}

export interface ExportReportRequest {
    recommendations: SolutionRecommendations[];
    delivery_solutions: ExportDeliverySolution[];
    selected_solutions?: ExportSelectedSolution[];
    stage_gates?: ExportStageGateSummary[];
}

export const HORIZON_LABELS: Record<Horizon, { label: string; detail: string }> = {
    court_terme: { label: "Short term", detail: "< 3 months" },
    moyen_terme: { label: "Mid term", detail: "6–12 months" },
    long_terme: { label: "Long term", detail: "> 1 year" },
};

export const STATUS_LABELS: Record<Status, string> = {
    draft: "Draft",
    submitted: "Submitted",
    in_qualification: "In Qualification",
    in_selection: "Selection",
    delivery: "Delivery",
    export_ready: "Export Ready",
    abandoned: "Abandoned",
};

export interface TechSignal {
    id: string;
    title: string;
    url: string;
    source: string;
    published_date: string | null;
    signal_type: "patent" | "research" | "news" | "startup" | "trend";
    maturity_level: "emerging" | "growing" | "mature";
    relevance_score: number;
    groq_insight: string;
    raw_snippet: string;
}

export interface TechSignalsResponse {
    signals: TechSignal[];
    query_used: string;
    from_cache: boolean;
}

export interface ABSAExtraction {
    aspect: "expertise" | "maturité" | "durée" | "données" | "impact_business";
    sentiment: "positif" | "négatif" | "neutre";
    intensité: "faible" | "moyen" | "fort";
    extrait: string;
}

export interface StageGateDiffEntry {
    field: string;
    before: string;
    after: string;
    justification: string;
}

export interface StageGateMessage {
    role: "agent" | "reviewer";
    content: string;
}

export interface StageGateSummaryItem {
    label: string;
    value: string;
}

export interface StageGateInteractionRequest {
    gate: "SG-1" | "SG-3" | "SG-4";
    action: "GO" | "REWORK" | "ABANDON" | "SUMMARY";
    comment?: string;
    snapshot: Record<string, unknown>;
}

export interface StageGateInteractionResponse {
    gate: "SG-1" | "SG-3" | "SG-4";
    phase: string;
    decision: "GO" | "REWORK" | "ABANDON" | "PENDING" | "ESCALATE";
    recommendation: string;
    summary: StageGateSummaryItem[];
    actions: Array<"GO" | "REWORK" | "ABANDON">;
    messages: StageGateMessage[];
    aspect_feedback: ABSAExtraction[];
    diffs: StageGateDiffEntry[];
    corrected_snapshot: Record<string, unknown>;
    nb_reworks: number;
    escalated: boolean;
}

export const SIGNAL_TYPE_LABELS: Record<TechSignal["signal_type"], string> = {
    patent:   "Patent",
    research: "Research",
    news:     "News",
    startup:  "Startup",
    trend:    "Trend",
};

export const SIGNAL_TYPE_TAG_CLASS: Record<TechSignal["signal_type"], string> = {
    patent:   "tag-amber",
    research: "tag-blue",
    news:     "tag-green",
    startup:  "tag-purple",
    trend:    "tag-orange",
};

export const MATURITY_LABELS: Record<TechSignal["maturity_level"], string> = {
    emerging: "Emerging",
    growing:  "Growing",
    mature:   "Mature",
};

export const MATURITY_TAG_CLASS: Record<TechSignal["maturity_level"], string> = {
    emerging: "tag-amber",
    growing:  "tag-blue",
    mature:   "tag-green",
};

export const OBJECTIF_LABELS: Record<Objectif, string> = {
    cost_reduction: "Cost Reduction",
    cx_improvement: "CX Improvement",
    risk_mitigation: "Risk Mitigation",
    market_opportunity: "Market Opportunity",
};
