"use client";

import { useState } from "react";

import { submitGapAnalysisFeedback } from "@/lib/api";
import type { GapAnalysisResponse } from "@/lib/types";

type GapPanelState = {
    itemId: string | null;
    data: GapAnalysisResponse | null;
    loading: boolean;
    error: boolean;
};

interface GapAnalysisPanelProps {
    needId?: string;
    gap: GapPanelState;
    onGapAnalysisUpdate: (data: GapAnalysisResponse) => void;
}

function getGapScoreColor(score: number) {
    if (score >= 4) return { fill: "#22c55e", track: "rgba(34, 197, 94, 0.16)" };
    if (score === 3) return { fill: "#f97316", track: "rgba(249, 115, 22, 0.16)" };
    return { fill: "#ef4444", track: "rgba(239, 68, 68, 0.16)" };
}

function buildStaffingFallback(data: GapAnalysisResponse) {
    if (!data.required_profiles.length) {
        return "DXC mobilisera une équipe de 6 personnes : X Data Scientists, Y AI Engineers, Z Cloud Architects.";
    }
    const total = data.required_profiles.reduce((sum, profile) => sum + profile.estimated_people, 0);
    const composition = data.required_profiles
        .map((profile) => `${profile.estimated_people} ${profile.name}${profile.estimated_people > 1 ? "s" : ""}`)
        .join(", ");
    return `DXC mobilisera une équipe de ${total} personnes : ${composition}.`;
}

function getReassuranceMessage(
    key: "maturite" | "expertise" | "duree" | "donnees" | "impact_business",
    value: { reassurance_message?: string | null; client_reassurance?: string | null },
    data: GapAnalysisResponse,
) {
    if (value.reassurance_message) return value.reassurance_message;
    if (value.client_reassurance) return value.client_reassurance;

    switch (key) {
        case "maturite":
            return "Cette solution est en phase pilote chez DXC — validée mais en cours d'industrialisation.";
        case "expertise":
            return buildStaffingFallback(data);
        case "duree":
            return "Livraison estimée à J+30 / J+60 / J+90 avec buffer risque intégré.";
        case "donnees":
            return "Les données déclarées couvrent les prérequis de base. Un Data Assessment DXC est recommandé.";
        case "impact_business":
            return "L'impact estimé s'aligne avec l'objectif métier déclaré, basé sur des cas de référence DXC réels.";
        default:
            return "";
    }
}

function formatFeedbackDiff(field: string) {
    if (field.includes("maturite")) return "Maturité";
    if (field.includes("expertise")) return "Expertise";
    if (field.includes("duree")) return "Durée";
    if (field.includes("donnees")) return "Données";
    if (field.includes("impact_business")) return "Impact Business";
    if (field === "ivi_score") return "IVI global";
    return field;
}

export function DiscoveryGapAnalysisPanel({
    needId,
    gap,
    onGapAnalysisUpdate,
}: GapAnalysisPanelProps) {
    const [feedbackComment, setFeedbackComment] = useState("");
    const [feedbackLoading, setFeedbackLoading] = useState(false);
    const [feedbackError, setFeedbackError] = useState<string | null>(null);
    const [feedbackDiffs, setFeedbackDiffs] = useState<Array<{ label: string; before: number; after: number; delta: number }>>([]);

    if (gap.loading) {
        return (
            <div style={{
                padding: "16px 20px",
                fontSize: 14,
                color: "var(--wf-muted-fg)",
                animation: "amberPulse 1.5s ease-in-out infinite",
            }}>
                Analyzing fit...
            </div>
        );
    }
    if (gap.error) {
        return (
            <div style={{ padding: "16px 20px", fontSize: 14, color: "var(--wf-muted-fg)" }}>
                Gap analysis unavailable
            </div>
        );
    }
    if (!gap.data) return null;

    const { data } = gap;
    const iviRows = [
        { key: "maturite", label: "Maturité", value: data.ivi_scoring.maturite },
        { key: "expertise", label: "Expertise", value: data.ivi_scoring.expertise },
        { key: "duree", label: "Durée", value: data.ivi_scoring.duree },
        { key: "donnees", label: "Données", value: data.ivi_scoring.donnees },
        { key: "impact_business", label: "Impact Business", value: data.ivi_scoring.impact_business },
    ] as const;
    const retainedFeaturesCount = data.audit.context_compression.retained_features.length;

    const handleFeedbackSubmit = async () => {
        if (!needId || !feedbackComment.trim()) return;
        setFeedbackLoading(true);
        setFeedbackError(null);
        try {
            const response = await submitGapAnalysisFeedback(needId, { comment: feedbackComment.trim() });
            onGapAnalysisUpdate(response.gap_analysis);
            setFeedbackComment("");
            setFeedbackDiffs(
                response.diffs
                    .filter((diff) => diff.field.startsWith("ivi_scoring.") || diff.field === "ivi_score")
                    .map((diff) => {
                        const before = Number(diff.before);
                        const after = Number(diff.after);
                        return {
                            label: formatFeedbackDiff(diff.field),
                            before,
                            after,
                            delta: after - before,
                        };
                    }),
            );
        } catch (error) {
            setFeedbackError(error instanceof Error ? error.message : "Impossible de soumettre le feedback.");
        } finally {
            setFeedbackLoading(false);
        }
    };

    return (
        <div style={{
            padding: "16px 20px",
            display: "flex",
            flexDirection: "column",
            gap: 14,
            maxHeight: "calc(100vh - 240px)",
            overflowY: "auto",
        }}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 10 }}>
                <div style={{ padding: "10px 12px", borderRadius: 12, background: "var(--wf-bg-elevated, rgba(255,255,255,0.03))", border: "1px solid var(--wf-border, rgba(255,255,255,0.08))" }}>
                    <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--wf-muted-fg)" }}>Fit</div>
                    <div style={{ fontSize: 18, fontWeight: 700, color: "var(--wf-fg)" }}>{data.fit_score}/10</div>
                </div>
                <div style={{ padding: "10px 12px", borderRadius: 12, background: "var(--wf-bg-elevated, rgba(255,255,255,0.03))", border: "1px solid var(--wf-border, rgba(255,255,255,0.08))" }}>
                    <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--wf-muted-fg)" }}>Feasibility</div>
                    <div style={{ fontSize: 18, fontWeight: 700, color: "var(--wf-fg)" }}>{data.feasibility.score}/5</div>
                </div>
                <div style={{ padding: "10px 12px", borderRadius: 12, background: "var(--wf-bg-elevated, rgba(255,255,255,0.03))", border: "1px solid var(--wf-border, rgba(255,255,255,0.08))" }}>
                    <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--wf-muted-fg)" }}>IVI score</div>
                    <div style={{ fontSize: 18, fontWeight: 700, color: "var(--wf-fg)" }}>{data.ivi_score.toFixed(1)}/100</div>
                </div>
            </div>

            <div style={{
                padding: "12px 14px",
                borderRadius: 12,
                background: "rgba(110, 201, 164, 0.06)",
                border: "1px solid rgba(110, 201, 164, 0.18)",
                color: "var(--wf-muted-fg)",
                fontSize: 13,
                lineHeight: 1.65,
            }}>
                <div style={{ color: "var(--wf-fg)", fontWeight: 600, marginBottom: 6 }}>Message client DXC</div>
                {data.client_message}
            </div>

            <div style={{ display: "grid", gap: 8, padding: "10px 12px", borderRadius: 12, background: "var(--wf-bg-elevated, rgba(255,255,255,0.03))", border: "1px solid var(--wf-border, rgba(255,255,255,0.08))" }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--wf-fg)" }}>Fit justification</div>
                <div style={{ fontSize: 13, lineHeight: 1.6, color: "var(--wf-muted-fg)" }}>{data.fit_justification}</div>
                <div style={{ fontSize: 12, lineHeight: 1.6, color: "var(--wf-muted-fg)" }}>
                    Feasibility rationale: {data.feasibility.justification}
                </div>
            </div>

            <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--wf-fg)", marginBottom: 10 }}>
                    IVI scoring
                </div>
                <div style={{ display: "grid", gap: 10 }}>
                    {iviRows.map((row) => (
                        <div key={row.key} style={{ padding: "12px 14px", borderRadius: 14, background: "var(--wf-bg-elevated, rgba(255,255,255,0.03))", border: "1px solid var(--wf-border, rgba(255,255,255,0.08))", display: "grid", gap: 8 }}>
                            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
                                <div style={{ minWidth: 0, fontSize: 14, fontWeight: 700, color: "var(--wf-fg)" }}>{row.label}</div>
                                <div style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: 4,
                                    whiteSpace: "nowrap",
                                    flexShrink: 0,
                                    lineHeight: 1,
                                    fontSize: 13,
                                    fontWeight: 700,
                                    color: getGapScoreColor(row.value.score).fill,
                                }}>
                                    <span style={{ whiteSpace: "nowrap" }}>{`${row.value.score}/5`}</span>
                                </div>
                            </div>
                            <div style={{ height: 8, borderRadius: 999, background: getGapScoreColor(row.value.score).track, overflow: "hidden" }}>
                                <div style={{
                                    width: `${(row.value.score / 5) * 100}%`,
                                    height: "100%",
                                    borderRadius: 999,
                                    background: getGapScoreColor(row.value.score).fill,
                                }} />
                            </div>
                            <div style={{ fontSize: 12, lineHeight: 1.55, color: "var(--wf-muted-fg)" }}>{row.value.justification}</div>
                            <div style={{ fontSize: 12, lineHeight: 1.55, color: "rgba(222, 225, 240, 0.68)", fontStyle: "italic" }}>
                                {getReassuranceMessage(row.key, row.value, data)}
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            {retainedFeaturesCount === 0 && (
                <div style={{
                    padding: "12px 14px",
                    borderRadius: 12,
                    background: "rgba(255, 184, 77, 0.08)",
                    border: "1px solid rgba(255, 184, 77, 0.28)",
                    color: "#ffd38c",
                    fontSize: 13,
                    lineHeight: 1.55,
                }}>
                    ⚠️ Aucune feature retenue après compression de contexte — le scoring peut manquer de précision.
                </div>
            )}

            {data.features_matching.length > 0 && (
                <div style={{
                    padding: "12px 14px",
                    borderRadius: 12,
                    background: "var(--wf-bg-elevated, rgba(255,255,255,0.03))",
                    border: "1px solid rgba(110, 201, 164, 0.18)",
                    borderLeft: "4px solid #6ec9a4",
                }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "#6ec9a4", marginBottom: 8 }}>
                        ✓ Features matching
                    </div>
                    <div style={{ display: "grid", gap: 6 }}>
                        {data.features_matching.map((feature, index) => (
                            <div key={`${feature}-${index}`} style={{ fontSize: 13, color: "var(--wf-muted-fg)", lineHeight: 1.7 }}>• {feature}</div>
                        ))}
                    </div>
                </div>
            )}

            {data.features_missing.length > 0 && (
                <div style={{
                    padding: "12px 14px",
                    borderRadius: 12,
                    background: "var(--wf-bg-elevated, rgba(255,255,255,0.03))",
                    border: "1px solid rgba(255, 122, 122, 0.18)",
                    borderLeft: "4px solid #ff7a7a",
                }}>
                    <div style={{ fontSize: 14, fontWeight: 700, color: "#ffb84d", marginBottom: 8 }}>
                        ⚠ Gaps identifiés
                    </div>
                    <div style={{ display: "grid", gap: 7 }}>
                        {data.features_missing.map((feature, index) => (
                            <div key={`${feature}-${index}`} style={{ fontSize: 13, color: "var(--wf-muted-fg)", lineHeight: 1.7 }}>✗ {feature}</div>
                        ))}
                    </div>
                </div>
            )}

            {data.risks.length > 0 && (
                <div style={{
                    padding: "12px 14px",
                    borderRadius: 12,
                    background: "var(--wf-bg-elevated, rgba(255,255,255,0.03))",
                    border: "1px solid rgba(255, 184, 77, 0.18)",
                    borderLeft: "4px solid #ffb84d",
                }}>
                    <div style={{ fontSize: 14, fontWeight: 700, color: "#ffb84d", marginBottom: 8 }}>
                        ⚡ Risques détectés
                    </div>
                    <div style={{ display: "grid", gap: 7 }}>
                        {data.risks.map((risk, index) => (
                            <div key={`${risk}-${index}`} style={{ fontSize: 13, color: "var(--wf-muted-fg)", lineHeight: 1.7 }}>• {risk}</div>
                        ))}
                    </div>
                </div>
            )}

            {data.resources_needed.length > 0 && (
                <div style={{
                    padding: "12px 14px",
                    borderRadius: 12,
                    background: "var(--wf-bg-elevated, rgba(255,255,255,0.03))",
                    border: "1px solid rgba(110, 163, 255, 0.18)",
                    borderLeft: "4px solid #6aa3ff",
                }}>
                    <div style={{ fontSize: 14, fontWeight: 700, color: "#8cb7ff", marginBottom: 8 }}>
                        ⚙ Ressources requises
                    </div>
                    <div style={{ display: "grid", gap: 7 }}>
                        {data.resources_needed.map((resource, index) => (
                            <div key={`${resource}-${index}`} style={{ fontSize: 13, color: "var(--wf-muted-fg)", lineHeight: 1.7 }}>• {resource}</div>
                        ))}
                    </div>
                </div>
            )}

            <div style={{ fontSize: 12, lineHeight: 1.6, color: "var(--wf-muted-fg)" }}>
                Context compression retained {retainedFeaturesCount} feature(s) for scoring and prompt injection.
            </div>

            <div style={{
                padding: "12px 14px",
                borderRadius: 12,
                background: "var(--wf-bg-elevated, rgba(255,255,255,0.03))",
                border: "1px solid var(--wf-border, rgba(255,255,255,0.08))",
                display: "grid",
                gap: 10,
            }}>
                <div style={{ fontSize: 13, fontWeight: 700, color: "var(--wf-fg)" }}>Aspect Modeling feedback</div>
                <textarea
                    value={feedbackComment}
                    onChange={(event) => setFeedbackComment(event.target.value)}
                    placeholder="Votre commentaire sur cette analyse..."
                    style={{
                        width: "100%",
                        minHeight: 96,
                        borderRadius: 12,
                        border: "1px solid var(--wf-border, rgba(255,255,255,0.08))",
                        background: "rgba(8, 10, 18, 0.8)",
                        color: "var(--wf-fg)",
                        padding: 12,
                        resize: "vertical",
                        outline: "none",
                        boxSizing: "border-box",
                        fontFamily: "inherit",
                        fontSize: 13,
                    }}
                />
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
                    <div style={{ fontSize: 12, color: "var(--wf-muted-fg)" }}>
                        Soumettez un retour pour ajuster les scores IVI de manière transparente.
                    </div>
                    <button
                        type="button"
                        onClick={() => { void handleFeedbackSubmit(); }}
                        disabled={!needId || !feedbackComment.trim() || feedbackLoading}
                        style={{
                            padding: "10px 14px",
                            borderRadius: 10,
                            border: "1px solid rgba(255,255,255,0.08)",
                            background: !needId || !feedbackComment.trim() || feedbackLoading ? "rgba(255,255,255,0.05)" : "#6aa3ff",
                            color: !needId || !feedbackComment.trim() || feedbackLoading ? "var(--wf-muted-fg)" : "#07101f",
                            cursor: !needId || !feedbackComment.trim() || feedbackLoading ? "not-allowed" : "pointer",
                            fontWeight: 700,
                            fontSize: 12,
                            letterSpacing: "0.03em",
                        }}
                    >
                        {feedbackLoading ? "Soumission..." : "Soumettre feedback"}
                    </button>
                </div>

                {feedbackError && (
                    <div style={{ fontSize: 12, color: "#ff9b9b" }}>{feedbackError}</div>
                )}

                {feedbackDiffs.length > 0 && (
                    <div style={{ display: "grid", gap: 6 }}>
                        {feedbackDiffs.map((diff, index) => (
                            <div key={`${diff.label}-${index}`} style={{ fontSize: 12, color: "var(--wf-muted-fg)", lineHeight: 1.6 }}>
                                {diff.label}: {diff.before} → {diff.after} ({diff.delta > 0 ? `+${diff.delta}` : diff.delta})
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
