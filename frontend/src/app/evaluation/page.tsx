/**
 * Evaluation / Qualification page.
 * Reads the solutions selected in Discovery and renders the SG-2 scorecard.
 */

"use client";

import React, { Suspense, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { WorkflowBar } from "@/components/layout/WorkflowBar";
import { getNeed, updateNeedStatus } from "@/lib/api";
import type {
    GapAnalysisResponse,
    GapCalibrationApplied,
    GapFeatureMatch,
    GapFeatureMissing,
    GapRecommendation,
    GapResourceNeed,
    GapRisk,
    QualificationScoreDimension,
    Status,
} from "@/lib/types";

type SelectedSolution = {
    id: string;
    name: string;
    relevance: number;
    description: string | undefined;
    source: string | undefined;
    gap_analysis: GapAnalysisResponse | null;
};

type ScoreKey = "maturite" | "expertise" | "duree" | "donnees" | "impact_business";
type EvaluationScores = Record<ScoreKey, number>;
type StructuredScoreMap = Partial<Record<ScoreKey, QualificationScoreDimension>>;

type Sg2State = {
    cardStates: Record<string, string>;
    totalSelected: number;
};

const CRITERIA: Array<{ key: ScoreKey; label: string; helper: string }> = [
    { key: "maturite", label: "Maturite", helper: "Delivery readiness and solution industrialization level." },
    { key: "expertise", label: "Expertise", helper: "How manageable the required skill set is for delivery." },
    { key: "duree", label: "Duree", helper: "How well the delivery timeline fits the expected horizon." },
    { key: "donnees", label: "Donnees", helper: "How ready the data and integration foundations are." },
    { key: "impact_business", label: "Impact business", helper: "How strongly the solution aligns with expected business value." },
];

function round(value: number) {
    return Math.round(value * 100) / 100;
}

function clampScore(value: number) {
    return Math.min(10, Math.max(1, Math.round(value)));
}

function buildInitialScores(solution: SelectedSolution): EvaluationScores {
    const base = clampScore(solution.relevance / 10);
    return {
        maturite: base,
        expertise: base,
        duree: base,
        donnees: base,
        impact_business: clampScore(base + (solution.relevance >= 80 ? 1 : 0)),
    };
}

function getStructuredScores(gap: GapAnalysisResponse | null): StructuredScoreMap {
    return (gap?.scores ?? null) || {};
}

function getStructuredScoreValue(gap: GapAnalysisResponse | null, key: ScoreKey): number | null {
    const primary = getStructuredScores(gap)[key]?.score;
    if (typeof primary === "number") return clampScore(primary);

    const legacy = gap?.ivi_scoring?.[key]?.score;
    if (typeof legacy === "number") return clampScore(legacy * 2);

    return null;
}

function getStructuredJustification(gap: GapAnalysisResponse | null, key: ScoreKey, fallback: string) {
    return getStructuredScores(gap)[key]?.justification || gap?.ivi_scoring?.[key]?.justification || fallback;
}

function getStructuredMatches(gap: GapAnalysisResponse | null): GapFeatureMatch[] {
    if (gap?.features_matching_detail?.length) return gap.features_matching_detail;
    return (gap?.features_matching || []).map((name) => ({
        name,
        evidence: "Legacy gap-analysis snapshot retained this capability as covered.",
        impact: "Supports the declared business objective.",
    }));
}

function getStructuredMissing(gap: GapAnalysisResponse | null): GapFeatureMissing[] {
    if (gap?.features_missing_detail?.length) return gap.features_missing_detail;
    return (gap?.features_missing || []).map((name) => ({
        name,
        reason: name,
        impact: "Leaves part of the expected value path uncovered.",
    }));
}

function getStructuredRisks(gap: GapAnalysisResponse | null): GapRisk[] {
    if (gap?.risk_register?.length) return gap.risk_register;
    return (gap?.risks || []).map((title) => ({
        title,
        category: "other",
        severity: "medium",
        mitigation: "Review and mitigate this legacy risk before moving forward.",
    }));
}

function getStructuredResources(gap: GapAnalysisResponse | null): GapResourceNeed[] {
    if (gap?.resources_needed_detail?.length) return gap.resources_needed_detail;
    return (gap?.resources_needed || []).map((name) => ({
        name,
        reason: "Delivery dependency inherited from the existing qualification snapshot.",
    }));
}

function buildScoresFromGap(solution: SelectedSolution): { scores: EvaluationScores; source: "gap-analysis" | "fallback" } {
    const gap = solution.gap_analysis;
    if (!gap) {
        return { scores: buildInitialScores(solution), source: "fallback" };
    }

    if (gap.scores) {
        return {
            scores: {
                maturite: getStructuredScoreValue(gap, "maturite") ?? 1,
                expertise: getStructuredScoreValue(gap, "expertise") ?? 1,
                duree: getStructuredScoreValue(gap, "duree") ?? 1,
                donnees: getStructuredScoreValue(gap, "donnees") ?? 1,
                impact_business: getStructuredScoreValue(gap, "impact_business") ?? 1,
            },
            source: "gap-analysis",
        };
    }

    if (gap.ivi_scoring) {
        return {
            scores: {
                maturite: clampScore(gap.ivi_scoring.maturite.score * 2),
                expertise: clampScore(gap.ivi_scoring.expertise.score * 2),
                duree: clampScore(gap.ivi_scoring.duree.score * 2),
                donnees: clampScore(gap.ivi_scoring.donnees.score * 2),
                impact_business: clampScore(gap.ivi_scoring.impact_business.score * 2),
            },
            source: "gap-analysis",
        };
    }

    if (gap.evaluation_scores) {
        return {
            scores: {
                maturite: clampScore(gap.evaluation_scores.feasibility * 2),
                expertise: clampScore(gap.evaluation_scores.fit * 2),
                duree: clampScore(gap.evaluation_scores.cost * 2),
                donnees: clampScore(gap.evaluation_scores.feasibility * 2),
                impact_business: clampScore(((gap.evaluation_scores.fit + gap.evaluation_scores.innovation) / 2) * 2),
            },
            source: "gap-analysis",
        };
    }

    const matching = gap.features_matching.length;
    const missing = gap.features_missing.length;
    const resources = gap.resources_needed.length;
    const risks = gap.risks?.length || 0;
    const fit = clampScore(gap.fit_score);

    return {
        scores: {
            maturite: clampScore(((gap.feasibility?.score || Math.round(fit / 2)) * 2) - (risks > 2 ? 1 : 0)),
            expertise: clampScore(10 - (missing * 0.7) - (resources * 0.4)),
            duree: clampScore(10 - (missing * 0.8) - (resources * 0.6) - (risks * 0.3)),
            donnees: clampScore(10 - (risks * 0.5) - (missing * 0.3) + (matching * 0.2)),
            impact_business: clampScore(fit + Math.min(2, matching * 0.3)),
        },
        source: "gap-analysis",
    };
}

function scoreSolution(scores: EvaluationScores) {
    return round(((scores.maturite + scores.expertise + scores.duree + scores.donnees + scores.impact_business) / 50) * 100);
}

function normalizeSolutions(value: unknown): SelectedSolution[] {
    if (!Array.isArray(value)) return [];
    return value.flatMap((item) => {
        if (!item || typeof item !== "object") return [];
        const candidate = item as Partial<SelectedSolution>;
        if (typeof candidate.id !== "string" || typeof candidate.name !== "string") return [];
        return [{
            id: candidate.id,
            name: candidate.name,
            relevance: typeof candidate.relevance === "number" ? candidate.relevance : 0,
            description: candidate.description,
            source: candidate.source,
            gap_analysis: candidate.gap_analysis || null,
        } satisfies SelectedSolution];
    });
}

function formatTimestamp(value: string | null) {
    if (!value) return "Not saved yet";
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString();
}

function getScoreColor(score: number) {
    if (score >= 8) return "#22c55e";
    if (score >= 6) return "#f59e0b";
    return "#ef4444";
}

function getRiskSeverityStyle(severity: GapRisk["severity"]) {
    if (severity === "high") {
        return { bg: "rgba(239, 68, 68, 0.12)", border: "rgba(239, 68, 68, 0.28)", text: "#fca5a5" };
    }
    if (severity === "medium") {
        return { bg: "rgba(249, 115, 22, 0.12)", border: "rgba(249, 115, 22, 0.28)", text: "#fdba74" };
    }
    return { bg: "rgba(34, 197, 94, 0.12)", border: "rgba(34, 197, 94, 0.28)", text: "#86efac" };
}

function getRecommendationStyle(decision?: GapRecommendation["decision"]) {
    switch (decision) {
        case "go":
            return { bg: "rgba(34, 197, 94, 0.08)", border: "rgba(34, 197, 94, 0.22)", text: "#86efac", label: "GO" };
        case "go_with_conditions":
            return { bg: "rgba(249, 115, 22, 0.08)", border: "rgba(249, 115, 22, 0.22)", text: "#fdba74", label: "GO with conditions" };
        case "no_go":
            return { bg: "rgba(239, 68, 68, 0.08)", border: "rgba(239, 68, 68, 0.22)", text: "#fca5a5", label: "No-go" };
        default:
            return { bg: "rgba(96, 165, 250, 0.08)", border: "rgba(96, 165, 250, 0.22)", text: "#93c5fd", label: "Needs more information" };
    }
}

function EvaluationPageContent() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const ipmId = searchParams.get("id") || undefined;

    const [solutions, setSolutions] = useState<SelectedSolution[]>([]);
    const [sg2State, setSg2State] = useState<Sg2State>({ cardStates: {}, totalSelected: 0 });
    const [activeId, setActiveId] = useState<string | null>(null);
    const [evaluationUpdatedAt, setEvaluationUpdatedAt] = useState<string | null>(null);
    const [workflowStatus, setWorkflowStatus] = useState<Status>("in_qualification");
    const [statusLoaded, setStatusLoaded] = useState(false);

    useEffect(() => {
        if (!ipmId) {
            setStatusLoaded(true);
            return;
        }

        getNeed(ipmId)
            .then((need) => {
                setWorkflowStatus(need.status);
                setStatusLoaded(true);
            })
            .catch(() => {
                setWorkflowStatus("in_qualification");
                setStatusLoaded(true);
            });
    }, [ipmId]);

    useEffect(() => {
        let parsedSolutions: SelectedSolution[] = [];
        const savedSolutions = localStorage.getItem("ipm_selected_solutions");
        if (savedSolutions) {
            try {
                parsedSolutions = normalizeSolutions(JSON.parse(savedSolutions));
            } catch {
                parsedSolutions = [];
            }
        }

        const savedSg2State = localStorage.getItem("ipm_sg2_state");
        if (savedSg2State) {
            try {
                setSg2State(JSON.parse(savedSg2State) as Sg2State);
            } catch {
                setSg2State({ cardStates: {}, totalSelected: parsedSolutions.length });
            }
        } else {
            setSg2State({ cardStates: {}, totalSelected: parsedSolutions.length });
        }

        setSolutions(parsedSolutions);
        setActiveId(parsedSolutions[0]?.id || null);

        const savedEvaluation = localStorage.getItem("ipm_evaluation_state");
        if (savedEvaluation) {
            try {
                const parsed = JSON.parse(savedEvaluation) as { updated_at?: string };
                setEvaluationUpdatedAt(parsed.updated_at || null);
            } catch {
                setEvaluationUpdatedAt(null);
            }
        }
    }, []);

    useEffect(() => {
        const canvas = document.getElementById("bg-canvas") as HTMLCanvasElement | null;
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        ctx.fillStyle = "rgba(180, 120, 60, 0.045)";
        ctx.font = "11px DM Mono, monospace";
        const chars = "0123456789ABCDEF";
        for (let x = 0; x < canvas.width; x += 28) {
            for (let y = 0; y < canvas.height; y += 20) {
                ctx.fillText(chars[Math.floor(Math.random() * chars.length)], x + Math.random() * 8, y + Math.random() * 6);
            }
        }
    }, []);

    const rows = useMemo(() => {
        return solutions
            .map((solution) => {
                const auto = buildScoresFromGap(solution);
                return {
                    solution,
                    scores: auto.scores,
                    overall: scoreSolution(auto.scores),
                    score_source: auto.source,
                };
            })
            .sort((a, b) => b.overall - a.overall);
    }, [solutions]);

    useEffect(() => {
        if (!rows.length) return;
        setActiveId((current) => (current && rows.some((row) => row.solution.id === current) ? current : rows[0].solution.id));
    }, [rows]);

    useEffect(() => {
        if (!rows.length) return;
        localStorage.setItem(
            "ipm_evaluation_state",
            JSON.stringify({
                activeId: activeId || rows[0].solution.id,
                rows: rows.map((row) => ({
                    id: row.solution.id,
                    name: row.solution.name,
                    relevance: row.solution.relevance,
                    overall: row.overall,
                    score_source: row.score_source,
                    gap_analysis: row.solution.gap_analysis,
                    scores: row.scores,
                })),
                updated_at: new Date().toISOString(),
            }),
        );
        setEvaluationUpdatedAt(new Date().toISOString());
    }, [activeId, rows]);

    const activeRow = rows.find((row) => row.solution.id === activeId) || rows[0] || null;
    const averageScore = rows.length ? round(rows.reduce((sum, row) => sum + row.overall, 0) / rows.length) : 0;
    const selectedCount = rows.length;
    const canOpenSelection = Boolean(ipmId) && selectedCount > 0 && workflowStatus === "in_qualification";

    const activeGap = activeRow?.solution.gap_analysis || null;
    const activeMatches = getStructuredMatches(activeGap);
    const activeMissing = getStructuredMissing(activeGap);
    const activeRisks = getStructuredRisks(activeGap);
    const activeResources = getStructuredResources(activeGap);
    const activeCalibrations = activeGap?.calibration_applied || [];
    const activeContextFiltered = activeGap?.solution_context_filtered || {
        included_items: activeGap?.audit?.context_compression?.included_items || [],
        excluded_count: activeGap?.audit?.context_compression?.excluded_items_count || 0,
        filter_reason: activeGap?.audit?.context_compression?.filter_reason || "Legacy qualification snapshot.",
        fallback_to_full_context: activeGap?.audit?.context_compression?.fallback_to_full_context || false,
    };
    const activeRecommendationStyle = getRecommendationStyle(activeGap?.recommendation?.decision);

    const proceedToSelection = async () => {
        if (!ipmId || selectedCount === 0 || !canOpenSelection) return;

        if (workflowStatus === "in_qualification") {
            const updated = await getNeed(ipmId);
            if (updated.status !== "in_qualification") {
                setWorkflowStatus(updated.status);
                throw new Error(`SG-3 cannot be validated from status '${updated.status}'.`);
            }
        }

        if (workflowStatus === "in_qualification") {
            const updated = await updateNeedStatus(ipmId, { status: "in_selection" });
            setWorkflowStatus(updated.status);
        }

        router.push(`/selection?id=${ipmId}`);
    };

    return (
        <div className="app-shell">
            <canvas id="bg-canvas" style={{ position: "fixed", top: 0, left: 0, zIndex: -1 }} />
            <WorkflowBar currentStep="evaluation" status={workflowStatus} ipmId={ipmId} />

            <div className="app-content" style={{ overflowY: "auto" }}>
                <div className="glow-divider" />
                <div style={{ padding: "20px 24px 32px", display: "grid", gap: 20 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 16, flexWrap: "wrap", alignItems: "flex-start" }}>
                        <div style={{ display: "grid", gap: 8, maxWidth: 780 }}>
                            <div style={{ display: "inline-flex", width: "fit-content", padding: "6px 10px", borderRadius: 999, background: "var(--accent-subtle)", color: "var(--accent-light)", fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase" }}>
                                Evaluation step
                            </div>
                            <h1 style={{ fontSize: 28, lineHeight: 1.1, margin: 0, fontWeight: 600 }}>Evaluate the solutions carried forward from Discovery.</h1>
                            <div style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.7 }}>
                                This page is the Qualification scorecard for SG-2. It loads the solutions selected in Discovery, renders the five IVI dimensions, and prepares the shortlist for Selection.
                            </div>
                        </div>

                        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                            <button type="button" className="action-btn" onClick={() => router.push(ipmId ? `/discovery?id=${ipmId}` : "/discovery")} disabled={!ipmId}>
                                Back to Discovery
                            </button>
                            <button type="button" className="action-btn primary" onClick={() => { void proceedToSelection(); }} disabled={!canOpenSelection}>
                                {workflowStatus === "in_qualification" ? "Validate SG-3 and open Selection ->" : "Open Selection step ->"}
                            </button>
                        </div>
                    </div>

                    {!ipmId && (
                        <div style={{ padding: 16, borderRadius: 14, background: "rgba(255, 88, 88, 0.08)", color: "var(--destructive)" }}>
                            Open a saved initiative before starting evaluation.
                        </div>
                    )}

                    {statusLoaded && ipmId && workflowStatus !== "in_qualification" && (
                        <div style={{ padding: 16, borderRadius: 14, background: "rgba(255, 184, 77, 0.08)", color: "var(--text-primary)" }}>
                            This initiative is not currently at the Qualification stage. Illegal step jumps are blocked until SG-2 has been validated.
                        </div>
                    )}

                    {ipmId && !selectedCount && (
                        <div style={{ padding: 16, borderRadius: 14, background: "rgba(255, 184, 77, 0.08)", color: "var(--text-primary)" }}>
                            No selected solutions were found from Discovery. Go back and choose at least one solution to evaluate.
                        </div>
                    )}

                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16 }}>
                        <div style={{ padding: 20, borderRadius: 20, border: "1px solid var(--border-default)", background: "var(--bg-card)", display: "grid", gap: 8 }}>
                            <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: 700 }}>Loaded from Discovery</div>
                            <div style={{ fontSize: 28, fontWeight: 700 }}>{selectedCount}</div>
                            <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>Solutions carried forward from <strong style={{ color: "var(--text-primary)" }}>ipm_selected_solutions</strong>.</div>
                        </div>
                        <div style={{ padding: 20, borderRadius: 20, border: "1px solid var(--border-default)", background: "var(--bg-card)", display: "grid", gap: 8 }}>
                            <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: 700 }}>Average evaluation</div>
                            <div style={{ fontSize: 28, fontWeight: 700 }}>{averageScore.toFixed(2)}</div>
                            <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>Local ranking computed from the five IVI qualification dimensions on the SG-2 scorecard.</div>
                        </div>
                        <div style={{ padding: 20, borderRadius: 20, border: "1px solid var(--border-default)", background: "var(--bg-card)", display: "grid", gap: 8 }}>
                            <div style={{ fontSize: 11, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: 700 }}>SG-2 context</div>
                            <div style={{ fontSize: 28, fontWeight: 700 }}>{sg2State.totalSelected}</div>
                            <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>Last evaluation refresh: {formatTimestamp(evaluationUpdatedAt)}</div>
                        </div>
                    </div>

                    <div style={{ padding: 20, borderRadius: 20, border: "1px solid var(--border-default)", background: "var(--bg-card)", display: "grid", gap: 16 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
                            <div>
                                <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--text-muted)" }}>Evaluation matrix</div>
                                <div style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 4 }}>Scores are AI-generated by the backend from Qualification gap-analysis across the five IVI dimensions.</div>
                            </div>
                            {activeRow && (
                                <div style={{ padding: "8px 12px", borderRadius: 999, background: "var(--accent-subtle)", color: "var(--accent-light)", fontSize: 12, fontWeight: 700 }}>
                                    Focus: {activeRow.solution.name}
                                </div>
                            )}
                        </div>

                        <div style={{ overflowX: "auto" }}>
                            <div style={{ minWidth: 1060, display: "grid", gap: 1, background: "var(--border-default)", borderRadius: 14, overflow: "hidden" }}>
                                <div style={{ display: "grid", gridTemplateColumns: "240px repeat(5, minmax(140px, 1fr)) 120px", background: "var(--bg-inner)" }}>
                                    <div style={{ padding: "12px 14px", fontSize: 12, fontWeight: 700 }}>Solution</div>
                                    {CRITERIA.map((criterion) => (
                                        <div key={criterion.key} style={{ padding: "12px 14px", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", textAlign: "center" }}>
                                            {criterion.label}
                                        </div>
                                    ))}
                                    <div style={{ padding: "12px 14px", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", textAlign: "center" }}>Overall</div>
                                </div>

                                {rows.map((row) => {
                                    const isActive = activeRow?.solution.id === row.solution.id;
                                    return (
                                        <div key={row.solution.id} style={{ display: "grid", gridTemplateColumns: "240px repeat(5, minmax(140px, 1fr)) 120px", background: isActive ? "rgba(255, 153, 51, 0.05)" : "var(--bg-card)" }}>
                                            <button
                                                type="button"
                                                onClick={() => setActiveId(row.solution.id)}
                                                style={{
                                                    padding: "14px",
                                                    background: "transparent",
                                                    border: "none",
                                                    textAlign: "left",
                                                    cursor: "pointer",
                                                    display: "grid",
                                                    gap: 4,
                                                }}
                                            >
                                                <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)" }}>{row.solution.name}</div>
                                                <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>Discovery relevance {row.solution.relevance}%</div>
                                                <div style={{ fontSize: 11, color: "var(--text-muted)" }}>
                                                    {row.score_source === "gap-analysis" ? "AI scored from gap-analysis" : "Fallback score (gap-analysis missing)"}
                                                </div>
                                            </button>
                                            {CRITERIA.map((criterion) => (
                                                <div key={`${row.solution.id}-${criterion.key}`} style={{ padding: 12, display: "flex", flexDirection: "column", gap: 6 }}>
                                                    <div style={{ width: "100%", borderRadius: 12, border: "1px solid var(--border-input)", background: "var(--bg-input)", color: "var(--text-primary)", padding: 10, fontWeight: 700, textAlign: "center" }}>
                                                        {row.scores[criterion.key]} / 10
                                                    </div>
                                                    <div style={{ fontSize: 11, color: "var(--text-muted)", lineHeight: 1.4 }}>{criterion.helper}</div>
                                                </div>
                                            ))}
                                            <div style={{ padding: 12, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, color: isActive ? "var(--accent-light)" : "var(--text-primary)" }}>
                                                {row.overall.toFixed(2)}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    </div>

                    {activeRow && (
                        <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.4fr) minmax(300px, 0.8fr)", gap: 16, alignItems: "start" }}>
                            <div style={{ padding: 20, borderRadius: 20, border: "1px solid var(--border-default)", background: "var(--bg-card)", display: "grid", gap: 14 }}>
                                <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--text-muted)" }}>Qualification focus</div>
                                <div style={{ fontSize: 22, fontWeight: 700 }}>{activeRow.solution.name}</div>
                                <div style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.7 }}>
                                    {activeRow.solution.description || "This solution was selected from Discovery and automatically evaluated during qualification."}
                                </div>
                                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                                    <span className="tag-chip tag-gray">Relevance {activeRow.solution.relevance}%</span>
                                    <span className="tag-chip tag-green">Evaluation {activeRow.overall.toFixed(2)}</span>
                                    {activeGap && typeof activeGap.ivi_score === "number" && (
                                        <span className="tag-chip tag-blue">IVI {activeGap.ivi_score.toFixed(1)}/100</span>
                                    )}
                                    <span className="tag-chip tag-amber">{selectedCount} candidate{selectedCount > 1 ? "s" : ""}</span>
                                    <span className={`tag-chip ${activeRow.score_source === "gap-analysis" ? "tag-blue" : "tag-orange"}`}>
                                        {activeRow.score_source === "gap-analysis" ? "AI gap-analysis score" : "Fallback score"}
                                    </span>
                                </div>
                                {activeGap && (
                                    <div style={{ display: "grid", gap: 10, padding: "12px 14px", borderRadius: 14, background: "var(--bg-inner)", border: "1px solid var(--border-default)" }}>
                                        <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
                                            <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                                                Gap fit: <strong style={{ color: "var(--text-primary)" }}>{activeGap.fit_score}/10</strong>
                                            </div>
                                            <div style={{
                                                padding: "6px 10px",
                                                borderRadius: 999,
                                                background: activeRecommendationStyle.bg,
                                                border: `1px solid ${activeRecommendationStyle.border}`,
                                                color: activeRecommendationStyle.text,
                                                fontSize: 11,
                                                fontWeight: 700,
                                                letterSpacing: "0.05em",
                                                textTransform: "uppercase",
                                            }}>
                                                {activeRecommendationStyle.label}
                                            </div>
                                        </div>
                                        <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                                            Feasibility: <strong style={{ color: "var(--text-primary)" }}>{activeGap.feasibility?.score ?? "-"}/5</strong> - Matching: {activeMatches.length} - Missing: {activeMissing.length} - Risks: {activeRisks.length}
                                        </div>
                                        {activeGap.fit_justification && (
                                            <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.6 }}>
                                                {activeGap.fit_justification}
                                            </div>
                                        )}
                                        {activeGap.recommendation?.justification && (
                                            <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.6 }}>
                                                {activeGap.recommendation.justification}
                                            </div>
                                        )}
                                    </div>
                                )}
                                <div style={{ display: "grid", gap: 10 }}>
                                    {CRITERIA.map((criterion) => (
                                        <div key={criterion.key} style={{ padding: "12px 14px", borderRadius: 14, background: "var(--bg-inner)", border: "1px solid var(--border-default)", display: "grid", gap: 8 }}>
                                            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
                                                <div style={{ fontSize: 13, fontWeight: 600 }}>{criterion.label}</div>
                                                <div style={{ fontSize: 16, fontWeight: 700, color: getScoreColor(activeRow.scores[criterion.key]) }}>
                                                    {activeRow.scores[criterion.key]} / 10
                                                </div>
                                            </div>
                                            <div style={{ height: 8, borderRadius: 999, background: "rgba(255,255,255,0.08)", overflow: "hidden" }}>
                                                <div style={{
                                                    width: `${(activeRow.scores[criterion.key] / 10) * 100}%`,
                                                    height: "100%",
                                                    borderRadius: 999,
                                                    background: getScoreColor(activeRow.scores[criterion.key]),
                                                }} />
                                            </div>
                                            <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.6 }}>
                                                {getStructuredJustification(activeGap, criterion.key, criterion.helper)}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                                {activeGap?.audit?.ambiguity_flags?.length ? (
                                    <div style={{ padding: "12px 14px", borderRadius: 14, border: "1px solid rgba(255, 184, 77, 0.22)", background: "rgba(255, 184, 77, 0.08)", display: "grid", gap: 6 }}>
                                        <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "#fdba74" }}>Ambiguity flags</div>
                                        {activeGap.audit.ambiguity_flags.map((flag) => (
                                            <div key={`${flag.field}-${flag.reason}`} style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.6 }}>
                                                <strong style={{ color: "var(--text-primary)" }}>{flag.field}</strong>: {flag.confidence} confidence - {flag.reason}
                                            </div>
                                        ))}
                                    </div>
                                ) : null}
                                <div style={{ padding: "12px 14px", borderRadius: 14, border: "1px solid var(--border-default)", background: "rgba(255,255,255,0.02)", display: "grid", gap: 6 }}>
                                    <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--text-muted)" }}>Context compression</div>
                                    <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.6 }}>
                                        {activeContextFiltered.filter_reason}
                                    </div>
                                    <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                                        Included {activeContextFiltered.included_items.length} item(s) - Excluded {activeContextFiltered.excluded_count}
                                    </div>
                                    {activeContextFiltered.fallback_to_full_context && (
                                        <div style={{ fontSize: 12, color: "#fdba74" }}>
                                            Fallback to broader solution context applied because no strong subset was detected.
                                        </div>
                                    )}
                                </div>
                            </div>

                            <div style={{ display: "grid", gap: 16 }}>
                                <div style={{ padding: 20, borderRadius: 20, border: "1px solid var(--border-default)", background: "var(--bg-card)", display: "grid", gap: 14 }}>
                                    <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--text-muted)" }}>Coverage and risks</div>

                                    <div style={{ padding: "12px 14px", borderRadius: 14, background: "rgba(34, 197, 94, 0.06)", border: "1px solid rgba(34, 197, 94, 0.18)" }}>
                                        <div style={{ fontSize: 13, fontWeight: 700, color: "#86efac", marginBottom: 8 }}>Features matching</div>
                                        {activeMatches.length ? activeMatches.map((item) => (
                                            <div key={`${item.name}-${item.evidence}`} style={{ display: "grid", gap: 2, marginBottom: 8 }}>
                                                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>{item.name}</div>
                                                <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.55 }}>{item.evidence}</div>
                                                <div style={{ fontSize: 12, color: "var(--text-muted)", lineHeight: 1.55 }}>{item.impact}</div>
                                            </div>
                                        )) : <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>No matching feature was captured for this snapshot.</div>}
                                    </div>

                                    <div style={{ padding: "12px 14px", borderRadius: 14, background: "rgba(239, 68, 68, 0.06)", border: "1px solid rgba(239, 68, 68, 0.18)" }}>
                                        <div style={{ fontSize: 13, fontWeight: 700, color: "#fdba74", marginBottom: 8 }}>Features missing</div>
                                        {activeMissing.length ? activeMissing.map((item) => (
                                            <div key={`${item.name}-${item.reason}`} style={{ display: "grid", gap: 2, marginBottom: 8 }}>
                                                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>{item.name}</div>
                                                <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.55 }}>{item.reason}</div>
                                                <div style={{ fontSize: 12, color: "var(--text-muted)", lineHeight: 1.55 }}>{item.impact}</div>
                                            </div>
                                        )) : <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>No uncovered feature was identified.</div>}
                                    </div>

                                    <div style={{ padding: "12px 14px", borderRadius: 14, background: "rgba(249, 115, 22, 0.06)", border: "1px solid rgba(249, 115, 22, 0.18)" }}>
                                        <div style={{ fontSize: 13, fontWeight: 700, color: "#fdba74", marginBottom: 8 }}>Risks</div>
                                        {activeRisks.length ? activeRisks.map((risk) => {
                                            const style = getRiskSeverityStyle(risk.severity);
                                            return (
                                                <div key={`${risk.title}-${risk.category}`} style={{ display: "grid", gap: 6, marginBottom: 10 }}>
                                                    <div style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
                                                        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>{risk.title}</div>
                                                        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                                                            <span style={{ padding: "4px 8px", borderRadius: 999, background: style.bg, border: `1px solid ${style.border}`, color: style.text, fontSize: 11, fontWeight: 700 }}>{risk.severity}</span>
                                                            <span style={{ padding: "4px 8px", borderRadius: 999, background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", color: "var(--text-secondary)", fontSize: 11 }}>{risk.category}</span>
                                                        </div>
                                                    </div>
                                                    <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.55 }}>{risk.mitigation}</div>
                                                </div>
                                            );
                                        }) : <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>No explicit risk was recorded.</div>}
                                    </div>

                                    <div style={{ padding: "12px 14px", borderRadius: 14, background: "rgba(96, 165, 250, 0.06)", border: "1px solid rgba(96, 165, 250, 0.18)" }}>
                                        <div style={{ fontSize: 13, fontWeight: 700, color: "#93c5fd", marginBottom: 8 }}>Resources needed</div>
                                        {activeResources.length ? activeResources.map((item) => (
                                            <div key={`${item.name}-${item.reason}`} style={{ display: "grid", gap: 2, marginBottom: 8 }}>
                                                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>{item.name}</div>
                                                <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.55 }}>{item.reason}</div>
                                            </div>
                                        )) : <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>No additional delivery dependency was highlighted.</div>}
                                    </div>
                                </div>

                                <div style={{ padding: 20, borderRadius: 20, border: "1px solid var(--border-default)", background: "var(--bg-card)", display: "grid", gap: 14 }}>
                                    <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--text-muted)" }}>Calibration and next step</div>
                                    {activeCalibrations.length ? (
                                        <div style={{ display: "grid", gap: 8 }}>
                                            {activeCalibrations.map((item: GapCalibrationApplied) => (
                                                <div key={`${item.field}-${item.rule}`} style={{ padding: "10px 12px", borderRadius: 12, background: "var(--bg-inner)", border: "1px solid var(--border-default)" }}>
                                                    <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>{item.field}</div>
                                                    <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.55 }}>
                                                        {item.previous_score}{" -> "}{item.new_score} - {item.reason}
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    ) : (
                                        <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                                            No business-rule calibration was required for this qualification snapshot.
                                        </div>
                                    )}
                                    <div style={{ padding: "12px 14px", borderRadius: 14, background: activeRecommendationStyle.bg, border: `1px solid ${activeRecommendationStyle.border}`, display: "grid", gap: 6 }}>
                                        <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: activeRecommendationStyle.text }}>
                                            {activeRecommendationStyle.label}
                                        </div>
                                        <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.6 }}>
                                            {activeGap?.recommendation?.justification || "Recommendation is unavailable for this legacy qualification snapshot."}
                                        </div>
                                    </div>
                                    <div style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.7 }}>
                                        Once you are satisfied with the ranking, move to the Selection step to choose delivery candidates and run SG-3 there.
                                    </div>
                                    <button type="button" className="action-btn primary" onClick={() => { void proceedToSelection(); }} disabled={!canOpenSelection}>
                                        {workflowStatus === "in_qualification" ? "Validate SG-3 and open Selection ->" : "Open Selection step ->"}
                                    </button>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

export default function EvaluationPage() {
    return (
        <Suspense fallback={<div className="app-shell" style={{ display: "flex", justifyContent: "center", alignItems: "center" }}>Loading...</div>}>
            <EvaluationPageContent />
        </Suspense>
    );
}
