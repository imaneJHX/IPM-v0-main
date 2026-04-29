/**
 * Recommendations and Output page (DELIVERY PHASE).
 * SG-4 gate must be passed before PDF/DOCX export buttons become active.
 */

"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { WorkflowBar } from "@/components/layout/WorkflowBar";
import { Sg4ValidationPanel } from "@/components/sourcing/Sg4ValidationPanel";
import { exportRecommendationsDocx, exportRecommendationsPdf, getNeed, getRecommendations, interactStageGate, updateNeedStatus } from "@/lib/api";
import type { BusinessNeed, ExportReportRequest, ExportStageGateSummary, GapAnalysisResponse, SolutionRecommendations, StageGateInteractionResponse, Status } from "@/lib/types";

type DeliverySelection = {
    id: string;
    name: string;
    relevance: number;
    overall: number;
};

type DiscoverySelectedSolution = {
    id: string;
    name: string;
    description?: string;
    source?: string;
    features?: string[];
    business_impact?: string;
    maturity_level?: string;
    gap_analysis?: GapAnalysisResponse | null;
};

function priorityBadgeStyle(priority: string): React.CSSProperties {
    if (priority === "critical") {
        return { background: "rgba(239, 68, 68, 0.16)", color: "#fca5a5", border: "1px solid rgba(239, 68, 68, 0.32)" };
    }
    if (priority === "high") {
        return { background: "rgba(249, 115, 22, 0.16)", color: "#fdba74", border: "1px solid rgba(249, 115, 22, 0.32)" };
    }
    if (priority === "medium") {
        return { background: "rgba(59, 130, 246, 0.16)", color: "#93c5fd", border: "1px solid rgba(59, 130, 246, 0.28)" };
    }
    return { background: "rgba(148, 163, 184, 0.14)", color: "#cbd5e1", border: "1px solid rgba(148, 163, 184, 0.26)" };
}

function phaseLabel(phase: string): string {
    return phase.charAt(0).toUpperCase() + phase.slice(1);
}

function truthChipStyle(active: boolean): React.CSSProperties {
    return active
        ? { background: "rgba(34, 197, 94, 0.16)", color: "#86efac", border: "1px solid rgba(34, 197, 94, 0.28)" }
        : { background: "rgba(239, 68, 68, 0.12)", color: "#fca5a5", border: "1px solid rgba(239, 68, 68, 0.24)" };
}

function RecosPageContent() {
    const searchParams = useSearchParams();
    const ipmId = searchParams.get("id") || undefined;
    const [showGate, setShowGate] = useState(false);
    const [gateCleared, setGateCleared] = useState(false);
    const [deliverySolutions, setDeliverySolutions] = useState<DeliverySelection[]>([]);
    const [selectedSolutions, setSelectedSolutions] = useState<DiscoverySelectedSolution[]>([]);
    const [recommendations, setRecommendations] = useState<SolutionRecommendations[]>([]);
    const [isGenerating, setIsGenerating] = useState(false);
    const [generationError, setGenerationError] = useState<string | null>(null);
    const [workflowStatus, setWorkflowStatus] = useState<Status>("delivery");
    const [needSummary, setNeedSummary] = useState<BusinessNeed | null>(null);
    const [isExportingPdf, setIsExportingPdf] = useState(false);
    const [isExportingDocx, setIsExportingDocx] = useState(false);
    const [exportError, setExportError] = useState<string | null>(null);
    const [sg4State, setSg4State] = useState<StageGateInteractionResponse | null>(null);

    useEffect(() => {
        const saved = localStorage.getItem("ipm_delivery_solutions");
        if (saved) {
            try {
                setDeliverySolutions(JSON.parse(saved));
            } catch {
                setDeliverySolutions([]);
            }
        }

        const savedSelected = localStorage.getItem("ipm_selected_solutions");
        if (savedSelected) {
            try {
                setSelectedSolutions(JSON.parse(savedSelected));
            } catch {
                setSelectedSolutions([]);
            }
        }

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

    useEffect(() => {
        if (!ipmId) return;
        getNeed(ipmId)
            .then((need) => {
                setNeedSummary(need);
                if (need.status === "delivery") {
                    setWorkflowStatus("delivery");
                } else if (need.status === "export_ready") {
                    setWorkflowStatus("export_ready");
                    setGateCleared(true);
                } else {
                    setWorkflowStatus(need.status);
                }
            })
            .catch(() => {
                setNeedSummary(null);
                setWorkflowStatus("delivery");
            });
    }, [ipmId]);

    useEffect(() => {
        if (!ipmId) return;
        void interactStageGate(ipmId, {
            gate: "SG-4",
            action: "SUMMARY",
            snapshot: {
                recommendations,
                export_ready: gateCleared || workflowStatus === "export_ready",
                roadmap: deliverySolutions.length > 0 ? "delivery roadmap in progress" : "",
                kpi_count: recommendations.reduce((sum, item) => sum + item.kpis.length, 0),
            },
        }).then(setSg4State).catch(() => undefined);
    }, [ipmId, recommendations, deliverySolutions, gateCleared, workflowStatus]);

    useEffect(() => {
        if (!ipmId || deliverySolutions.length === 0) {
            setRecommendations([]);
            return;
        }

        const selectedById = new Map(selectedSolutions.map((solution) => [solution.id, solution]));
        const payload = deliverySolutions.map((solution) => {
            const selectedContext = selectedById.get(solution.id);
            return {
                id: solution.id,
                name: solution.name,
                relevance: solution.relevance,
                overall: solution.overall,
                description: selectedContext?.description || "",
                source: selectedContext?.source || "",
                features: selectedContext?.features || [],
                business_impact: selectedContext?.business_impact || "",
                maturity_level: selectedContext?.maturity_level || "",
                gap_analysis: selectedContext?.gap_analysis || null,
                evaluation_scores: selectedContext?.gap_analysis?.evaluation_scores || null,
            };
        });

        let cancelled = false;

        const run = async () => {
            setIsGenerating(true);
            setGenerationError(null);
            try {
                const result = await getRecommendations(ipmId, { selected_solutions: payload });
                if (!cancelled) {
                    setRecommendations(result.recommendations || []);
                }
            } catch (error) {
                if (!cancelled) {
                    setGenerationError(error instanceof Error ? error.message : "Unable to generate recommendations.");
                    setRecommendations([]);
                }
            } finally {
                if (!cancelled) {
                    setIsGenerating(false);
                }
            }
        };

        run();

        return () => {
            cancelled = true;
        };
    }, [ipmId, deliverySolutions, selectedSolutions]);

    const triggerDownload = (blob: Blob, filename: string) => {
        const href = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = href;
        anchor.download = filename;
        document.body.appendChild(anchor);
        anchor.click();
        document.body.removeChild(anchor);
        URL.revokeObjectURL(href);
    };

    const buildStageGateSummary = (): ExportStageGateSummary[] => {
        const currentStatus = needSummary?.status || workflowStatus;
        const note = needSummary?.rework_note || null;
        const hasReached = (statuses: Status[]) => statuses.includes(currentStatus);

        return [
            {
                gate: "SG-1",
                phase: "Sourcing",
                decision: hasReached(["submitted", "in_qualification", "in_selection", "delivery", "export_ready"]) ? "GO" : "PENDING",
                status_after: hasReached(["submitted", "in_qualification", "in_selection", "delivery", "export_ready"]) ? "submitted" : "draft",
                comment: note && currentStatus === "submitted" ? note : null,
            },
            {
                gate: "SG-2",
                phase: "Discovery",
                decision: hasReached(["in_qualification", "in_selection", "delivery", "export_ready"]) ? "GO" : "PENDING",
                status_after: hasReached(["in_qualification", "in_selection", "delivery", "export_ready"]) ? "in_qualification" : "submitted",
                comment: note && currentStatus === "in_qualification" ? note : null,
            },
            {
                gate: "SG-3",
                phase: "Qualification",
                decision: hasReached(["in_selection", "delivery", "export_ready"]) ? "GO" : "PENDING",
                status_after: hasReached(["in_selection", "delivery", "export_ready"]) ? "in_selection" : "in_qualification",
                comment: note && currentStatus === "in_selection" ? note : null,
            },
            {
                gate: "SG-4",
                phase: "Delivery",
                decision: currentStatus === "export_ready" || gateCleared ? "GO" : "PENDING",
                status_after: currentStatus === "export_ready" || gateCleared ? "export_ready" : "delivery",
                comment: note && (currentStatus === "delivery" || currentStatus === "export_ready") ? note : null,
            },
        ];
    };

    const buildExportPayload = (): ExportReportRequest => {
        const deliveryIds = new Set(deliverySolutions.map((solution) => solution.id));
        const deliveryById = new Map(deliverySolutions.map((solution) => [solution.id, solution]));

        return {
            recommendations,
            delivery_solutions: deliverySolutions,
            selected_solutions: selectedSolutions
                .filter((solution) => deliveryIds.has(solution.id))
                .map((solution) => {
                    const delivery = deliveryById.get(solution.id);
                    return {
                        id: solution.id,
                        name: solution.name,
                        relevance: delivery?.relevance ?? 0,
                        overall: delivery?.overall ?? 0,
                        description: solution.description || "",
                        source: solution.source || "",
                        features: solution.features || [],
                        business_impact: solution.business_impact || "",
                        maturity_level: solution.maturity_level || "",
                        gap_analysis: solution.gap_analysis || null,
                    };
                }),
            stage_gates: buildStageGateSummary(),
        };
    };

    const handlePdfExport = async () => {
        if (!ipmId) return;
        setExportError(null);
        setIsExportingPdf(true);
        try {
            const blob = await exportRecommendationsPdf(ipmId, buildExportPayload());
            triggerDownload(blob, `${ipmId.toLowerCase()}-recommendations.pdf`);
        } catch (error) {
            setExportError(error instanceof Error ? error.message : "Failed to export PDF report.");
        } finally {
            setIsExportingPdf(false);
        }
    };

    const handleDocxExport = async () => {
        if (!ipmId) return;
        setExportError(null);
        setIsExportingDocx(true);
        try {
            const blob = await exportRecommendationsDocx(ipmId, buildExportPayload());
            triggerDownload(blob, `${ipmId.toLowerCase()}-recommendations.docx`);
        } catch (error) {
            setExportError(error instanceof Error ? error.message : "Failed to export DOCX proposal.");
        } finally {
            setIsExportingDocx(false);
        }
    };

    return (
        <div className="app-shell">
            <canvas id="bg-canvas" style={{ position: "fixed", top: 0, left: 0, zIndex: -1 }} />
            <WorkflowBar currentStep={gateCleared || workflowStatus === "export_ready" ? "export" : "recos"} status={workflowStatus} ipmId={ipmId} isInteractive={false} />

            <div className="app-content">
                <div className="glow-divider" />
                <div className="stub-page">
                    <div className="stub-page-header">
                        <h1 className="stub-page-title">{gateCleared ? "Recommendations & Export" : "Recommendations"}</h1>
                    </div>

                    {workflowStatus !== "delivery" && workflowStatus !== "export_ready" && (
                        <div style={{ padding: 14, borderRadius: 12, border: "1px solid rgba(255, 184, 77, 0.35)", background: "rgba(255, 184, 77, 0.08)", color: "var(--text-primary)" }}>
                            Recos belongs to the Delivery phase. Illegal step jumps are blocked until Selection has opened Delivery.
                        </div>
                    )}

                    {gateCleared && (
                        <>
                            <div className="stub-banner">
                                SG-4 validated. Generate your final delivery documents.
                            </div>

                            {exportError && (
                                <div style={{ padding: 14, borderRadius: 12, border: "1px solid rgba(220, 50, 50, 0.35)", background: "rgba(255, 88, 88, 0.08)", color: "var(--destructive)" }}>
                                    {exportError}
                                </div>
                            )}

                            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
                                <div style={{
                                    padding: "24px",
                                    background: "var(--bg-card)",
                                    border: "1px solid var(--border-default)",
                                    borderRadius: 12,
                                    textAlign: "center",
                                    opacity: 1,
                                    transition: "opacity 0.3s",
                                }}>
                                    <div style={{ fontWeight: 600, fontSize: 16 }}>PDF Report</div>
                                    <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 8 }}>Comprehensive recommendation with solution details and ROI.</div>
                                    <button
                                        className="action-btn"
                                        style={{ marginTop: 20, width: "100%", cursor: "pointer" }}
                                        onClick={handlePdfExport}
                                        disabled={isExportingPdf || recommendations.length === 0}
                                    >
                                        {isExportingPdf ? "Generating PDF..." : "Download PDF"}
                                    </button>
                                </div>
                                <div style={{
                                    padding: "24px",
                                    background: "var(--bg-card)",
                                    border: "1px solid var(--border-default)",
                                    borderRadius: 12,
                                    textAlign: "center",
                                    opacity: 1,
                                    transition: "opacity 0.3s",
                                }}>
                                    <div style={{ fontWeight: 600, fontSize: 16 }}>DOCX Proposal</div>
                                    <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 8 }}>Editable Word document for project launch and formalization.</div>
                                    <button
                                        className="action-btn"
                                        style={{ marginTop: 20, width: "100%", cursor: "pointer" }}
                                        onClick={handleDocxExport}
                                        disabled={isExportingDocx || recommendations.length === 0}
                                    >
                                        {isExportingDocx ? "Generating DOCX..." : "Download DOCX"}
                                    </button>
                                </div>
                            </div>
                        </>
                    )}

                    {isGenerating && (
                        <div style={{ padding: 14, borderRadius: 12, border: "1px solid var(--border-default)", background: "var(--bg-card)", color: "var(--text-secondary)" }}>
                            Generating technical, organizational, and KPI recommendations with AI for each selected solution...
                        </div>
                    )}

                    {generationError && (
                        <div style={{ padding: 14, borderRadius: 12, border: "1px solid rgba(220, 50, 50, 0.35)", background: "rgba(255, 88, 88, 0.08)", color: "var(--destructive)" }}>
                            {generationError}
                        </div>
                    )}

                    <div style={{ padding: 20, borderRadius: 20, border: "1px solid var(--border-default)", background: "var(--bg-card)", display: "grid", gap: 12 }}>
                        <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--text-muted)" }}>Delivery selection</div>
                        {deliverySolutions.length === 0 ? (
                            <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>No delivery solutions selected yet. Return to Selection to choose what moves forward.</div>
                        ) : (
                            <div style={{ display: "grid", gap: 10 }}>
                                {deliverySolutions.map((solution) => (
                                    <div key={solution.id} style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center", padding: "10px 12px", borderRadius: 12, background: "var(--bg-inner)", border: "1px solid var(--border-default)" }}>
                                        <div>
                                            <div style={{ fontSize: 13, fontWeight: 600 }}>{solution.name}</div>
                                            <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>Overall {solution.overall.toFixed(2)} · Relevance {solution.relevance}%</div>
                                        </div>
                                        <span className="tag-chip tag-green">Selected</span>
                                    </div>
                                ))}
                            </div>
                        )}

                        <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, flexWrap: "wrap" }}>
                            {!gateCleared && workflowStatus !== "export_ready" ? (
                                <button className="action-btn primary" style={{ minWidth: 180, fontWeight: 700 }} onClick={() => setShowGate(true)}>
                                    Validate SG-4
                                </button>
                            ) : (
                                <button className="action-btn" onClick={() => window.location.href = "/dashboard"}>
                                    Final Archive
                                </button>
                            )}
                        </div>
                    </div>

                    {recommendations.length > 0 && (
                        <div style={{ display: "grid", gap: 16 }}>
                            {recommendations.map((rec) => (
                                <div key={rec.solution_id} style={{ padding: 20, borderRadius: 20, border: "1px solid var(--border-default)", background: "var(--bg-card)", display: "grid", gap: 16 }}>
                                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                                        <div style={{ display: "grid", gap: 4 }}>
                                            <div style={{ fontSize: 12, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: 700 }}>
                                                Solution recommendation bundle
                                            </div>
                                            <div style={{ fontSize: 20, fontWeight: 700, color: "var(--text-primary)" }}>{rec.solution_name}</div>
                                        </div>
                                        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
                                            <span className="tag-chip tag-blue">AI generated</span>
                                            <span
                                                style={{
                                                    padding: "6px 10px",
                                                    borderRadius: 999,
                                                    fontSize: 11,
                                                    fontWeight: 700,
                                                    letterSpacing: "0.06em",
                                                    textTransform: "uppercase",
                                                    ...(rec.delivery_mode === "PREREQUISITE"
                                                        ? { background: "rgba(249, 115, 22, 0.18)", color: "#fdba74", border: "1px solid rgba(249, 115, 22, 0.3)" }
                                                        : { background: "rgba(34, 197, 94, 0.18)", color: "#86efac", border: "1px solid rgba(34, 197, 94, 0.3)" }),
                                                }}
                                            >
                                                {rec.delivery_mode === "PREREQUISITE" ? "PRÉ-REQUIS" : "DELIVERY"}
                                            </span>
                                        </div>
                                    </div>

                                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
                                        <div style={{ border: "1px solid var(--border-default)", borderRadius: 14, background: "var(--bg-inner)", padding: 14, display: "grid", gap: 6 }}>
                                            <div style={{ fontSize: 12, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                                                Delivery mode
                                            </div>
                                            <div style={{ fontSize: 16, fontWeight: 700, color: "var(--text-primary)" }}>
                                                {rec.delivery_mode === "PREREQUISITE" ? "Prerequisite package first" : "Ready for delivery planning"}
                                            </div>
                                            {rec.prerequisite_reason && (
                                                <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.55 }}>
                                                    {rec.prerequisite_reason}
                                                </div>
                                            )}
                                        </div>

                                        <div style={{ border: "1px solid var(--border-default)", borderRadius: 14, background: "var(--bg-inner)", padding: 14, display: "grid", gap: 8 }}>
                                            <div style={{ fontSize: 12, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                                                Coverage validation
                                            </div>
                                            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                                                <span style={{ padding: "6px 10px", borderRadius: 999, fontSize: 11, fontWeight: 700, ...truthChipStyle(Boolean(rec.coverage_validation?.features_missing_covered)) }}>
                                                    Gaps {rec.coverage_validation?.features_missing_covered ? "covered" : "open"}
                                                </span>
                                                <span style={{ padding: "6px 10px", borderRadius: 999, fontSize: 11, fontWeight: 700, ...truthChipStyle(Boolean(rec.coverage_validation?.resources_needed_covered)) }}>
                                                    Resources {rec.coverage_validation?.resources_needed_covered ? "covered" : "open"}
                                                </span>
                                                <span style={{ padding: "6px 10px", borderRadius: 999, fontSize: 11, fontWeight: 700, ...truthChipStyle(Boolean(rec.coverage_validation?.kpi_rules_satisfied)) }}>
                                                    KPI rules {rec.coverage_validation?.kpi_rules_satisfied ? "ok" : "pending"}
                                                </span>
                                            </div>
                                            {rec.coverage_validation?.missing_coverage && rec.coverage_validation.missing_coverage.length > 0 && (
                                                <div style={{ display: "grid", gap: 6 }}>
                                                    {rec.coverage_validation.missing_coverage.map((item, index) => (
                                                        <div key={`${rec.solution_id}-coverage-${index}`} style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.45 }}>
                                                            {item}
                                                        </div>
                                                    ))}
                                                </div>
                                            )}
                                        </div>

                                        <div style={{ border: "1px solid var(--border-default)", borderRadius: 14, background: "var(--bg-inner)", padding: 14, display: "grid", gap: 8 }}>
                                            <div style={{ fontSize: 12, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                                                DXC alignment
                                            </div>
                                            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                                                {(rec.dxc_alignment?.ecosystem_considered || []).map((item) => (
                                                    <span key={`${rec.solution_id}-${item}`} className="tag-chip">
                                                        {item}
                                                    </span>
                                                ))}
                                            </div>
                                            <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.55 }}>
                                                {rec.dxc_alignment?.alignment_notes || "DXC ecosystem alignment not provided."}
                                            </div>
                                        </div>
                                    </div>

                                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 14 }}>
                                        <div style={{ border: "1px solid var(--border-default)", borderRadius: 14, background: "var(--bg-inner)", padding: 14, display: "grid", gap: 10 }}>
                                            <div style={{ fontSize: 12, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                                                Technical recommendations
                                            </div>
                                            <div style={{ display: "grid", gap: 8 }}>
                                                {rec.technical_recommendations.map((item) => (
                                                    <div key={`${rec.solution_id}-${item.id}`} style={{ border: "1px solid var(--border-default)", borderRadius: 12, background: "var(--bg-card)", padding: "12px 14px", display: "grid", gap: 8 }}>
                                                        <div style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "flex-start", flexWrap: "wrap" }}>
                                                            <div style={{ display: "grid", gap: 4 }}>
                                                                <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)" }}>{item.title}</div>
                                                                <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>{item.id} · covers {item.related_feature_missing.join(", ")}</div>
                                                            </div>
                                                            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                                                                <span style={{ padding: "4px 8px", borderRadius: 999, fontSize: 11, fontWeight: 700, ...priorityBadgeStyle(item.priority) }}>{item.priority}</span>
                                                                <span className="tag-chip">{item.estimated_effort}</span>
                                                                {item.prerequisite && <span className="tag-chip">Prerequisite</span>}
                                                            </div>
                                                        </div>
                                                        <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.55 }}>{item.description}</div>
                                                        <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.55 }}>
                                                            <strong style={{ color: "var(--text-primary)" }}>Proposed solution:</strong> {item.proposed_solution}
                                                        </div>
                                                        <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.55 }}>
                                                            <strong style={{ color: "var(--text-primary)" }}>Expected impact:</strong> {item.expected_impact}
                                                        </div>
                                                        {item.technology_stack.length > 0 && (
                                                            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                                                                {item.technology_stack.map((stack) => (
                                                                    <span key={`${item.id}-${stack}`} className="tag-chip">{stack}</span>
                                                                ))}
                                                            </div>
                                                        )}
                                                        {item.dependencies.length > 0 && (
                                                            <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.45 }}>
                                                                Dependencies: {item.dependencies.join(" · ")}
                                                            </div>
                                                        )}
                                                    </div>
                                                ))}
                                            </div>
                                        </div>

                                        <div style={{ border: "1px solid var(--border-default)", borderRadius: 14, background: "var(--bg-inner)", padding: 14, display: "grid", gap: 10 }}>
                                            <div style={{ fontSize: 12, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                                                Organizational recommendations
                                            </div>
                                            <div style={{ display: "grid", gap: 8 }}>
                                                {rec.organizational_recommendations.map((item) => (
                                                    <div key={`${rec.solution_id}-${item.id}`} style={{ border: "1px solid var(--border-default)", borderRadius: 12, background: "var(--bg-card)", padding: "12px 14px", display: "grid", gap: 8 }}>
                                                        <div style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "flex-start", flexWrap: "wrap" }}>
                                                            <div style={{ display: "grid", gap: 4 }}>
                                                                <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)" }}>{item.title}</div>
                                                                <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>{item.id} · resource {item.related_resource_needed}</div>
                                                            </div>
                                                            <span style={{ padding: "4px 8px", borderRadius: 999, fontSize: 11, fontWeight: 700, ...priorityBadgeStyle(item.priority) }}>{item.priority}</span>
                                                        </div>
                                                        <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.55 }}>{item.action}</div>
                                                        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                                                            <span className="tag-chip">{item.responsible_role}</span>
                                                            <span className="tag-chip">{phaseLabel(item.target_phase)}</span>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    </div>

                                    <div style={{ border: "1px solid var(--border-default)", borderRadius: 14, background: "var(--bg-inner)", padding: 14, display: "grid", gap: 10 }}>
                                        <div style={{ fontSize: 12, fontWeight: 700, color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                                            Target KPIs and measurable criteria
                                        </div>
                                        <div style={{ display: "grid", gap: 10 }}>
                                            {rec.kpis.map((kpi, index) => (
                                                <div key={`${rec.solution_id}-kpi-${kpi.id || index}`} style={{ border: "1px solid var(--border-default)", borderRadius: 12, background: "var(--bg-card)", padding: "10px 12px", display: "grid", gap: 4 }}>
                                                    <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)" }}>{kpi.name}</div>
                                                    <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                                                        {kpi.linked_impact && <span className="tag-chip">{kpi.linked_impact}</span>}
                                                        {kpi.metric_type && <span className="tag-chip">{kpi.metric_type}</span>}
                                                        {kpi.unit && <span className="tag-chip">{kpi.unit}</span>}
                                                        {kpi.linked_recommendation_id && <span className="tag-chip">{kpi.linked_recommendation_id}</span>}
                                                    </div>
                                                    {kpi.baseline && <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>Baseline: {kpi.baseline}</div>}
                                                    <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>Target: {kpi.target}</div>
                                                    <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>Measure: {kpi.measurement_method || kpi.measurement_criteria}</div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>

                                    {rec.delivery_mode === "PREREQUISITE" && (rec.prerequisite_actions?.length || 0) > 0 && (
                                        <div style={{ border: "1px solid rgba(249, 115, 22, 0.28)", borderRadius: 14, background: "rgba(249, 115, 22, 0.08)", padding: 14, display: "grid", gap: 10 }}>
                                            <div style={{ fontSize: 12, fontWeight: 700, color: "#fdba74", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                                                Prerequisite actions
                                            </div>
                                            <div style={{ display: "grid", gap: 8 }}>
                                                {(rec.prerequisite_actions || []).map((item) => (
                                                    <div key={`${rec.solution_id}-${item.id}`} style={{ borderLeft: "3px solid rgba(249, 115, 22, 0.65)", paddingLeft: 12, display: "grid", gap: 4 }}>
                                                        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                                                            <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)" }}>{item.title}</div>
                                                            <span style={{ padding: "4px 8px", borderRadius: 999, fontSize: 11, fontWeight: 700, ...priorityBadgeStyle(item.priority) }}>{item.priority}</span>
                                                        </div>
                                                        <div style={{ fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.55 }}>{item.description}</div>
                                                        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                                                            <span className="tag-chip">{item.blocking_gap}</span>
                                                            <span className="tag-chip">{item.responsible_role}</span>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {showGate && (
                <Sg4ValidationPanel
                    open={showGate}
                    deliverySolutions={deliverySolutions}
                    hasRecommendations={recommendations.length > 0}
                    stageSummary={sg4State?.summary}
                    stageDiffs={sg4State?.diffs}
                    stageMessages={sg4State?.messages}
                    escalated={sg4State?.escalated}
                    onGo={async () => {
                        if (!ipmId) return;
                        try {
                            const updated = await updateNeedStatus(ipmId, { status: "export_ready" });
                            setGateCleared(true);
                            setWorkflowStatus(updated.status);
                            setShowGate(false);
                        } catch {
                            setShowGate(false);
                        }
                    }}
                    onRework={async (note?: string) => {
                        if (!ipmId || !note) return;
                        const response = await interactStageGate(ipmId, {
                            gate: "SG-4",
                            action: "REWORK",
                            comment: note,
                            snapshot: {
                                recommendations,
                                export_ready: gateCleared || workflowStatus === "export_ready",
                                roadmap: deliverySolutions.length > 0 ? "delivery roadmap in progress" : "",
                                kpi_count: recommendations.reduce((sum, item) => sum + item.kpis.length, 0),
                                gap_analysis: selectedSolutions[0]?.gap_analysis || null,
                            },
                        });
                        setSg4State(response);
                    }}
                    onAbandon={() => {
                        window.location.href = "/dashboard";
                    }}
                    onClose={() => setShowGate(false)}
                />
            )}
        </div>
    );
}

export default function RecosPage() {
    return (
        <Suspense fallback={<div className="app-shell" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center' }}>Loading...</div>}>
            <RecosPageContent />
        </Suspense>
    );
}
