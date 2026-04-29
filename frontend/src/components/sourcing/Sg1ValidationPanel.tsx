"use client";

/**
 * Sg1ValidationPanel — Right-side slide panel for SG-1 gate decision.
 * Matches GateModal design: card-style checklist, filled summary, note textarea.
 */

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { SourcingClassification, StageGateDiffEntry, StageGateMessage, StageGateSummaryItem } from "@/lib/types";

interface Sg1ValidationPanelProps {
    open: boolean;
    isProcessing: boolean;
    pitch: string;
    horizonLabel: string;
    objectif: string;
    domains: string;
    impact: string;
    sourcingClassification?: SourcingClassification | null;
    hasDuplicates?: boolean;
    stageSummary?: StageGateSummaryItem[];
    stageDiffs?: StageGateDiffEntry[];
    stageMessages?: StageGateMessage[];
    escalated?: boolean;
    onClose: () => void;
    onGo: () => void;
    onRework: (note?: string) => void;
    onAbandon: () => void;
}

const CheckIcon = ({ met }: { met: boolean }) => (
    <div style={{
        width: 18,
        height: 18,
        borderRadius: 4,
        border: met ? "none" : "1px solid var(--wf-muted-fg)",
        background: met ? "var(--wf-success-bg)" : "transparent",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
        marginTop: 1,
        opacity: met ? 1 : 0.35,
        transition: "all 0.2s",
    }}>
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
            <path d="M2 5L4 7L8 3" stroke={met ? "var(--wf-btn-on-color)" : "var(--wf-qualification)"} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
    </div>
);

const SummaryRow = ({ label, value }: { label: string; value: string }) => (
    <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
        <span style={{
            fontFamily: "var(--font-mono)",
            fontSize: 10,
            letterSpacing: "0.07em",
            textTransform: "uppercase",
            color: "var(--wf-muted-fg)",
        }}>
            {label}
        </span>
        <span style={{ fontSize: 13, color: "var(--wf-fg)", lineHeight: 1.5 }}>
            {value || <span style={{ opacity: 0.4, fontStyle: "italic" }}>Not specified</span>}
        </span>
    </div>
);

const CONFIDENCE_LABELS = {
    high: "Confiance elevee",
    medium: "Confiance moyenne",
    low: "Confiance faible",
} as const;

const CONFIDENCE_STYLES = {
    high: { color: "var(--wf-success-fg, #9fe6c0)", border: "1px solid rgba(91, 199, 141, 0.28)", background: "rgba(91, 199, 141, 0.08)" },
    medium: { color: "#f8c36c", border: "1px solid rgba(248, 195, 108, 0.28)", background: "rgba(248, 195, 108, 0.08)" },
    low: { color: "#f09393", border: "1px solid rgba(240, 147, 147, 0.28)", background: "rgba(240, 147, 147, 0.08)" },
} as const;

const SourcingTagCard = ({
    label,
    value,
    confidence,
    reason,
    horizonNote,
}: {
    label: string;
    value: string;
    confidence: "low" | "medium" | "high";
    reason?: string | null;
    horizonNote?: string | null;
}) => (
    <div style={{
        padding: 12,
        borderRadius: 8,
        background: "var(--wf-muted)",
        border: "1px solid var(--wf-border)",
        display: "grid",
        gap: 6,
    }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "center" }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: "var(--wf-fg)" }}>{label}</div>
            <span style={{
                ...CONFIDENCE_STYLES[confidence],
                borderRadius: 999,
                padding: "4px 8px",
                fontSize: 10,
                fontFamily: "var(--font-mono)",
                letterSpacing: "0.04em",
                textTransform: "uppercase",
                whiteSpace: "nowrap",
            }}>
                {CONFIDENCE_LABELS[confidence]}
            </span>
        </div>
        <div style={{ fontSize: 13, color: "var(--wf-fg)", lineHeight: 1.45 }}>{value}</div>
        {reason && (
            <div style={{ fontSize: 12, color: "var(--wf-muted-fg)", lineHeight: 1.55 }}>
                {reason}
            </div>
        )}
        {horizonNote && (
            <div style={{ fontSize: 11, color: "var(--wf-muted-fg)", lineHeight: 1.45 }}>
                {horizonNote}
            </div>
        )}
    </div>
);

export function Sg1ValidationPanel({
    open,
    isProcessing,
    pitch,
    horizonLabel,
    objectif,
    domains,
    impact,
    sourcingClassification = null,
    hasDuplicates = false,
    stageSummary = [],
    stageDiffs = [],
    stageMessages = [],
    escalated = false,
    onClose,
    onGo,
    onRework,
    onAbandon,
}: Sg1ValidationPanelProps) {
    const [mode, setMode] = useState<"idle" | "rework" | "stop">("idle");
    const [noteText, setNoteText] = useState("");
    const isCommittedRequest = mode !== "idle";

    const stateDescriptor = isCommittedRequest
        ? {
            label: mode === "rework" ? "Submitted - formal rework request" : "Submitted - formal abandon request",
            detail: "This is submitted. Changes require confirming a formal request with rationale.",
        }
        : {
            label: "Under review - rework available",
            detail: "You can still make changes: choose Request changes to return this need for revision.",
        };

    const handleConfirm = () => {
        if (!noteText.trim()) return;
        if (mode === "rework") onRework(noteText.trim());
        if (mode === "stop") onAbandon();
        setMode("idle");
        setNoteText("");
    };

    const handleCancel = () => {
        setMode("idle");
        setNoteText("");
    };

    const checklist: { label: string; met: boolean }[] = [
        {
            label: "Business need fully analyzed",
            met: pitch.trim().length > 20 && objectif.trim() !== "" && domains.trim() !== "" && impact.trim() !== "",
        },
        { label: "No duplicate detected", met: !hasDuplicates },
    ];

    const allMet = checklist.every((c) => c.met);
    const sourcingCards = sourcingClassification ? [
        {
            key: "source",
            label: "Source",
            value: sourcingClassification.source.value,
            confidence: sourcingClassification.source.confidence,
            reason: sourcingClassification.source.reason,
            horizonNote: null,
        },
        {
            key: "domain",
            label: "Domain",
            value: sourcingClassification.domain.value,
            confidence: sourcingClassification.domain.confidence,
            reason: sourcingClassification.domain.reason,
            horizonNote: null,
        },
        {
            key: "objective",
            label: "Objective",
            value: sourcingClassification.objective.value,
            confidence: sourcingClassification.objective.confidence,
            reason: sourcingClassification.objective.reason,
            horizonNote: sourcingClassification.objective.influencedByHorizon
                ? `Influence horizon: ${sourcingClassification.constraintsForGapAnalysis.horizon ?? "not specified"}`
                : null,
        },
    ] as const : [];

    return (
        <AnimatePresence>
            {open && (
                <>
                    {/* Backdrop */}
                    <motion.div
                        style={{
                            position: "fixed",
                            inset: 0,
                            background: "var(--wf-overlay-bg)",
                            backdropFilter: "blur(4px)",
                            zIndex: 40,
                        }}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        onClick={() => !isProcessing && onClose()}
                    />

                    {/* Panel */}
                    <motion.div
                        style={{
                            position: "fixed",
                            right: 0,
                            top: 0,
                            height: "100%",
                            width: "100%",
                            maxWidth: 480,
                            background: "var(--wf-card)",
                            borderLeft: "1px solid var(--wf-border)",
                            zIndex: 50,
                            display: "flex",
                            flexDirection: "column",
                        }}
                        initial={{ x: "100%" }}
                        animate={{ x: 0 }}
                        exit={{ x: "100%" }}
                        transition={{ ease: [0.16, 1, 0.3, 1], duration: 0.5 }}
                    >
                        {/* Header */}
                        <div style={{ padding: 24, borderBottom: "1px solid var(--wf-border)" }}>
                            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                                <span style={{
                                    fontFamily: "var(--font-mono)",
                                    fontSize: 10,
                                    color: "var(--wf-muted-fg)",
                                    letterSpacing: "0.08em",
                                    textTransform: "uppercase",
                                }}>
                                    SG-1
                                </span>
                                <button
                                    onClick={() => !isProcessing && onClose()}
                                    style={{
                                        background: "none",
                                        border: "none",
                                        color: "var(--wf-muted-fg)",
                                        cursor: "pointer",
                                        fontSize: 14,
                                        padding: 4,
                                        lineHeight: 1,
                                    }}
                                >
                                    ✕
                                </button>
                            </div>

                            {stageSummary.length > 0 && (
                                <div>
                                    <span style={{
                                        fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.08em",
                                        textTransform: "uppercase", fontWeight: 500, color: "var(--wf-muted-fg)", display: "block", marginBottom: 14,
                                    }}>
                                        Gate Agent Summary
                                    </span>
                                    <div style={{ background: "var(--wf-muted)", border: "1px solid var(--wf-border)", borderRadius: 8, padding: 16, display: "grid", gap: 10 }}>
                                        {stageSummary.map((item) => (
                                            <SummaryRow key={item.label} label={item.label} value={item.value} />
                                        ))}
                                    </div>
                                </div>
                            )}

                            {stageMessages.length > 0 && (
                                <div>
                                    <span style={{
                                        fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.08em",
                                        textTransform: "uppercase", fontWeight: 500, color: "var(--wf-muted-fg)", display: "block", marginBottom: 14,
                                    }}>
                                        Conversation
                                    </span>
                                    <div style={{ display: "grid", gap: 8 }}>
                                        {stageMessages.slice(-3).map((message, index) => (
                                            <div key={`${message.role}-${index}`} style={{ padding: 12, borderRadius: 6, background: "var(--wf-muted)", border: "1px solid var(--wf-border)", fontSize: 13, lineHeight: 1.5 }}>
                                                <strong style={{ textTransform: "uppercase", fontSize: 10, letterSpacing: "0.06em" }}>{message.role}</strong><br />
                                                {message.content}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {stageDiffs.length > 0 && (
                                <div>
                                    <span style={{
                                        fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.08em",
                                        textTransform: "uppercase", fontWeight: 500, color: "var(--wf-muted-fg)", display: "block", marginBottom: 14,
                                    }}>
                                        Before / After Diff
                                    </span>
                                    <div style={{ display: "grid", gap: 8 }}>
                                        {stageDiffs.map((diff) => (
                                            <div key={diff.field} style={{ padding: 12, borderRadius: 6, background: "var(--wf-muted)", border: "1px solid var(--wf-border)", display: "grid", gap: 4 }}>
                                                <div style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: "var(--wf-muted-fg)" }}>{diff.field}</div>
                                                <div style={{ fontSize: 12, color: "var(--wf-muted-fg)" }}>Before: {diff.before}</div>
                                                <div style={{ fontSize: 13, color: "var(--wf-fg)" }}>After: {diff.after}</div>
                                                <div style={{ fontSize: 12, color: "var(--wf-muted-fg)" }}>{diff.justification}</div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {escalated && (
                                <div style={{ padding: 12, borderRadius: 6, background: "var(--wf-stop-hover-bg)", border: "1px solid rgba(220, 50, 50, 0.35)", color: "var(--wf-destructive)", fontSize: 13 }}>
                                    Auto-escalation triggered after 3 reworks without GO.
                                </div>
                            )}
                            <h2 style={{ fontSize: 18, fontWeight: 600, color: "var(--wf-fg)", margin: 0 }}>
                                Validation of Business Need
                            </h2>
                            <p style={{ fontSize: 13, color: "var(--wf-muted-fg)", marginTop: 4, marginBottom: 0, lineHeight: 1.5 }}>
                                Review and confirm the business need before proceeding to discovery.
                            </p>
                            <div style={{
                                marginTop: 10,
                                padding: "8px 10px",
                                borderRadius: 6,
                                border: `1px solid ${isCommittedRequest ? "var(--wf-border)" : "var(--wf-badge-border)"}`,
                                background: isCommittedRequest ? "var(--wf-muted)" : "var(--wf-badge-bg)",
                            }}>
                                <p style={{
                                    margin: 0,
                                    fontFamily: "var(--font-mono)",
                                    fontSize: 10,
                                    letterSpacing: "0.05em",
                                    textTransform: "uppercase",
                                    color: "var(--wf-fg)",
                                }}>
                                    {stateDescriptor.label}
                                </p>
                                <p style={{
                                    margin: "4px 0 0",
                                    fontSize: 12,
                                    lineHeight: 1.45,
                                    color: "var(--wf-muted-fg)",
                                }}>
                                    {stateDescriptor.detail}
                                </p>
                            </div>
                        </div>

                        {/* Scrollable body */}
                        <div style={{ flex: 1, overflowY: "auto", padding: 24, display: "flex", flexDirection: "column", gap: 24 }}>

                            {/* SUMMARY */}
                            <div>
                                <span style={{
                                    fontFamily: "var(--font-mono)",
                                    fontSize: 10,
                                    letterSpacing: "0.08em",
                                    textTransform: "uppercase",
                                    fontWeight: 500,
                                    color: "var(--wf-muted-fg)",
                                    display: "block",
                                    marginBottom: 14,
                                }}>
                                    Summary
                                </span>
                                <div style={{
                                    background: "var(--wf-muted)",
                                    border: "1px solid var(--wf-border)",
                                    borderRadius: 8,
                                    padding: 16,
                                    display: "flex",
                                    flexDirection: "column",
                                    gap: 14,
                                }}>
                                    <SummaryRow label="Pitch" value={pitch} />
                                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
                                        <SummaryRow label="Time Horizon" value={horizonLabel} />
                                        <SummaryRow label="Objective" value={objectif} />
                                    </div>
                                    <SummaryRow label="Domains" value={domains} />
                                    <SummaryRow label="Impact" value={impact} />
                                </div>
                            </div>

                            {sourcingCards.length > 0 && (
                                <div>
                                    <span style={{
                                        fontFamily: "var(--font-mono)",
                                        fontSize: 10,
                                        letterSpacing: "0.08em",
                                        textTransform: "uppercase",
                                        fontWeight: 500,
                                        color: "var(--wf-muted-fg)",
                                        display: "block",
                                        marginBottom: 14,
                                    }}>
                                        NLP Tagging Confidence
                                    </span>
                                    <div style={{ display: "grid", gap: 10 }}>
                                        {sourcingCards.map((card) => (
                                            <SourcingTagCard
                                                key={card.key}
                                                label={card.label}
                                                value={card.value}
                                                confidence={card.confidence}
                                                reason={card.reason}
                                                horizonNote={card.horizonNote}
                                            />
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* CHECKLIST */}
                            <div>
                                <span style={{
                                    fontFamily: "var(--font-mono)",
                                    fontSize: 10,
                                    letterSpacing: "0.08em",
                                    textTransform: "uppercase",
                                    fontWeight: 500,
                                    color: "var(--wf-muted-fg)",
                                    display: "block",
                                    marginBottom: 14,
                                }}>
                                    Checklist
                                </span>
                                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                                    {checklist.map((item, i) => (
                                        <motion.div
                                            key={i}
                                            style={{
                                                display: "flex",
                                                alignItems: "flex-start",
                                                gap: 12,
                                                padding: 12,
                                                borderRadius: 6,
                                                background: "var(--wf-muted)",
                                                border: `1px solid ${item.met ? "var(--wf-success-border)" : "var(--wf-border)"}`,
                                            }}
                                            initial={{ opacity: 0, x: 20 }}
                                            animate={{ opacity: 1, x: 0 }}
                                            transition={{ delay: 0.3 + i * 0.08 }}
                                        >
                                            <CheckIcon met={item.met} />
                                            <span style={{ fontSize: 13, color: "var(--wf-fg)", lineHeight: 1.5, opacity: item.met ? 1 : 0.6 }}>
                                                {item.label}
                                            </span>
                                        </motion.div>
                                    ))}
                                </div>
                            </div>

                            {/* Note textarea — REWORK or STOP mode */}
                            {mode !== "idle" && (
                                <motion.div
                                    initial={{ opacity: 0, height: 0 }}
                                    animate={{ opacity: 1, height: "auto" }}
                                >
                                    <span style={{
                                        fontFamily: "var(--font-mono)",
                                        fontSize: 10,
                                        letterSpacing: "0.08em",
                                        textTransform: "uppercase",
                                        fontWeight: 500,
                                        color: "var(--wf-muted-fg)",
                                        display: "block",
                                        marginBottom: 8,
                                    }}>
                                        {mode === "rework" ? "Change Request Note (required)" : "Reason for Abandon (required)"}
                                    </span>
                                    <textarea
                                        value={noteText}
                                        onChange={(e) => setNoteText(e.target.value)}
                                        placeholder={mode === "rework"
                                            ? "Explain what should change and why…"
                                            : "Explain why this business need is being abandoned…"
                                        }
                                        autoFocus
                                        style={{
                                            width: "100%",
                                            minHeight: 80,
                                            padding: 12,
                                            borderRadius: 6,
                                            border: "1px solid var(--wf-border)",
                                            background: "var(--wf-bg)",
                                            color: "var(--wf-fg)",
                                            fontFamily: "var(--font-sans)",
                                            fontSize: 13,
                                            outline: "none",
                                            resize: "vertical",
                                            boxSizing: "border-box",
                                        }}
                                    />
                                </motion.div>
                            )}
                        </div>

                        {/* Actions */}
                        <div style={{
                            padding: 24,
                            borderTop: "1px solid var(--wf-border)",
                            display: "flex",
                            flexDirection: "column",
                            gap: 8,
                        }}>
                            {mode === "idle" ? (
                                <>
                                    <button
                                        onClick={onGo}
                                        disabled={isProcessing || !allMet}
                                        style={{
                                            width: "100%",
                                            padding: "11px 16px",
                                            borderRadius: 6,
                                            background: (isProcessing || !allMet) ? "var(--wf-success-bg-disabled)" : "var(--wf-success-bg)",
                                            color: "var(--wf-btn-strong-fg)",
                                            fontWeight: 700,
                                            fontSize: 14,
                                            border: "none",
                                            cursor: (isProcessing || !allMet) ? "not-allowed" : "pointer",
                                            fontFamily: "var(--font-mono)",
                                            letterSpacing: "0.06em",
                                            transition: "filter 0.15s",
                                        }}
                                        onMouseOver={(e) => { if (!isProcessing && allMet) e.currentTarget.style.filter = "brightness(1.1)"; }}
                                        onMouseOut={(e) => (e.currentTarget.style.filter = "")}
                                    >
                                        {isProcessing ? "Processing…" : "GO"}
                                    </button>
                                    {!allMet && (
                                        <span style={{
                                            fontSize: 11,
                                            color: "var(--wf-muted-fg)",
                                            textAlign: "center",
                                            lineHeight: 1.4,
                                        }}>
                                            Complete all checklist items to proceed
                                        </span>
                                    )}
                                    <button
                                        onClick={() => setMode("rework")}
                                        disabled={isProcessing}
                                        style={{
                                            width: "100%",
                                            padding: "11px 16px",
                                            borderRadius: 6,
                                            background: "transparent",
                                            color: "var(--wf-muted-fg)",
                                            fontSize: 14,
                                            border: "1px solid var(--wf-border)",
                                            cursor: isProcessing ? "not-allowed" : "pointer",
                                            fontFamily: "var(--font-mono)",
                                            letterSpacing: "0.06em",
                                            transition: "all 0.15s",
                                        }}
                                        onMouseOver={(e) => { if (!isProcessing) { e.currentTarget.style.color = "var(--wf-fg)"; e.currentTarget.style.borderColor = "var(--wf-muted-fg)"; } }}
                                        onMouseOut={(e) => { e.currentTarget.style.color = "var(--wf-muted-fg)"; e.currentTarget.style.borderColor = "var(--wf-border)"; }}
                                    >
                                        REQUEST CHANGES
                                    </button>
                                    <button
                                        onClick={() => setMode("stop")}
                                        disabled={isProcessing}
                                        style={{
                                            width: "100%",
                                            padding: "11px 16px",
                                            borderRadius: 6,
                                            background: "transparent",
                                            color: "var(--wf-destructive)",
                                            fontSize: 14,
                                            border: "1px solid rgba(220, 50, 50, 0.35)",
                                            cursor: isProcessing ? "not-allowed" : "pointer",
                                            fontFamily: "var(--font-mono)",
                                            letterSpacing: "0.06em",
                                            transition: "background 0.15s, border-color 0.15s",
                                        }}
                                        onMouseOver={(e) => {
                                            if (!isProcessing) {
                                                e.currentTarget.style.background = "var(--wf-stop-hover-bg)";
                                                e.currentTarget.style.borderColor = "var(--wf-destructive)";
                                            }
                                        }}
                                        onMouseOut={(e) => {
                                            e.currentTarget.style.background = "transparent";
                                            e.currentTarget.style.borderColor = "rgba(220, 50, 50, 0.35)";
                                        }}
                                    >
                                        STOP / ABANDON
                                    </button>
                                </>
                            ) : (
                                <>
                                    <button
                                        onClick={handleConfirm}
                                        disabled={!noteText.trim()}
                                        style={{
                                            width: "100%",
                                            padding: "11px 16px",
                                            borderRadius: 6,
                                            background: mode === "rework" ? "var(--wf-sourcing)" : "var(--wf-destructive)",
                                            color: "var(--wf-btn-on-color)",
                                            fontWeight: 600,
                                            fontSize: 14,
                                            border: "none",
                                            cursor: noteText.trim() ? "pointer" : "not-allowed",
                                            fontFamily: "var(--font-mono)",
                                            letterSpacing: "0.06em",
                                            opacity: noteText.trim() ? 1 : 0.4,
                                            transition: "opacity 0.15s",
                                        }}
                                    >
                                        Confirm {mode === "rework" ? "Change Request" : "Abandon"}
                                    </button>
                                    <button
                                        onClick={handleCancel}
                                        style={{
                                            width: "100%",
                                            padding: "11px 16px",
                                            borderRadius: 6,
                                            background: "transparent",
                                            color: "var(--wf-muted-fg)",
                                            fontSize: 14,
                                            border: "1px solid var(--wf-border)",
                                            cursor: "pointer",
                                            fontFamily: "var(--font-mono)",
                                            letterSpacing: "0.06em",
                                        }}
                                    >
                                        Cancel
                                    </button>
                                </>
                            )}
                        </div>
                    </motion.div>
                </>
            )}
        </AnimatePresence>
    );
}
