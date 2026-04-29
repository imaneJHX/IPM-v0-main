"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import type { StageGateDiffEntry, StageGateMessage, StageGateSummaryItem } from "@/lib/types";

type DeliverySolution = {
    id: string;
    name: string;
    relevance: number;
    overall: number;
};

interface Sg4ValidationPanelProps {
    open: boolean;
    deliverySolutions: DeliverySolution[];
    hasRecommendations: boolean;
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

export function Sg4ValidationPanel({
    open,
    deliverySolutions,
    hasRecommendations,
    stageSummary = [],
    stageDiffs = [],
    stageMessages = [],
    escalated = false,
    onClose,
    onGo,
    onRework,
    onAbandon,
}: Sg4ValidationPanelProps) {
    const [mode, setMode] = useState<"idle" | "rework" | "stop">("idle");
    const [noteText, setNoteText] = useState("");

    const checklist = [
        { label: "At least one delivery solution selected", met: deliverySolutions.length > 0 },
        { label: "Recommendations generated and reviewed", met: hasRecommendations },
        { label: "Ready to unlock final export", met: deliverySolutions.length > 0 },
    ];

    const allMet = checklist.every((item) => item.met);

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

    return (
        <AnimatePresence>
            {open && (
                <>
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
                        onClick={onClose}
                    />

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
                        <div style={{ padding: 24, borderBottom: "1px solid var(--wf-border)" }}>
                            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                                <span style={{
                                    fontFamily: "var(--font-mono)",
                                    fontSize: 10,
                                    color: "var(--wf-muted-fg)",
                                    letterSpacing: "0.08em",
                                    textTransform: "uppercase",
                                }}>
                                    SG-4
                                </span>
                                <button
                                    onClick={onClose}
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
                                    X
                                </button>
                            </div>

                            {stageSummary.length > 0 && (
                                <div>
                                    <span style={{
                                        fontFamily: "var(--font-mono)", fontSize: 10, letterSpacing: "0.08em", textTransform: "uppercase",
                                        fontWeight: 500, color: "var(--wf-muted-fg)", display: "block", marginBottom: 14,
                                    }}>
                                        Gate Agent Summary
                                    </span>
                                    <div style={{ background: "var(--wf-muted)", border: "1px solid var(--wf-border)", borderRadius: 8, padding: 16, display: "grid", gap: 8 }}>
                                        {stageSummary.map((item) => (
                                            <div key={item.label} style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                                                <span style={{ fontSize: 12, color: "var(--wf-muted-fg)" }}>{item.label}</span>
                                                <span style={{ fontSize: 13, color: "var(--wf-fg)" }}>{item.value}</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {stageMessages.length > 0 && (
                                <div style={{ display: "grid", gap: 8 }}>
                                    {stageMessages.slice(-3).map((message, index) => (
                                        <div key={`${message.role}-${index}`} style={{ padding: 12, borderRadius: 6, background: "var(--wf-muted)", border: "1px solid var(--wf-border)", fontSize: 13, lineHeight: 1.5 }}>
                                            <strong style={{ textTransform: "uppercase", fontSize: 10, letterSpacing: "0.06em" }}>{message.role}</strong><br />
                                            {message.content}
                                        </div>
                                    ))}
                                </div>
                            )}

                            {stageDiffs.length > 0 && (
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
                            )}

                            {escalated && (
                                <div style={{ padding: 12, borderRadius: 6, background: "var(--wf-stop-hover-bg)", border: "1px solid rgba(220, 50, 50, 0.35)", color: "var(--wf-destructive)", fontSize: 13 }}>
                                    Auto-escalation triggered after 3 reworks without GO.
                                </div>
                            )}
                            <h2 style={{ fontSize: 18, fontWeight: 600, color: "var(--wf-fg)", margin: 0 }}>
                                Final Validation before Export
                            </h2>
                            <p style={{ fontSize: 13, color: "var(--wf-muted-fg)", marginTop: 4, marginBottom: 0, lineHeight: 1.5 }}>
                                Validate delivery recommendations and unlock final document generation.
                            </p>
                        </div>

                        <div style={{ flex: 1, overflowY: "auto", padding: 24, display: "flex", flexDirection: "column", gap: 24 }}>
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
                                    Delivery solutions
                                </span>
                                {deliverySolutions.length === 0 ? (
                                    <div style={{
                                        background: "var(--wf-muted)",
                                        border: "1px solid var(--wf-border)",
                                        borderRadius: 8,
                                        padding: 16,
                                        fontSize: 13,
                                        color: "var(--wf-muted-fg)",
                                        fontStyle: "italic",
                                    }}>
                                        No delivery solutions selected yet
                                    </div>
                                ) : (
                                    <div style={{ background: "var(--wf-muted)", border: "1px solid var(--wf-border)", borderRadius: 8, overflow: "hidden" }}>
                                        {deliverySolutions.map((solution, index) => (
                                            <motion.div
                                                key={solution.id}
                                                style={{
                                                    display: "flex",
                                                    alignItems: "center",
                                                    justifyContent: "space-between",
                                                    padding: "10px 16px",
                                                    borderBottom: index < deliverySolutions.length - 1 ? "1px solid var(--wf-border)" : "none",
                                                    gap: 12,
                                                }}
                                                initial={{ opacity: 0, x: 20 }}
                                                animate={{ opacity: 1, x: 0 }}
                                                transition={{ delay: 0.15 + index * 0.06 }}
                                            >
                                                <span style={{ fontSize: 13, fontWeight: 500, color: "var(--wf-fg)" }}>{solution.name}</span>
                                                <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
                                                    <span style={{
                                                        fontFamily: "var(--font-mono)",
                                                        fontSize: 11,
                                                        color: solution.relevance >= 80
                                                            ? "var(--wf-qualification)"
                                                            : solution.relevance >= 65
                                                            ? "var(--wf-sourcing)"
                                                            : "var(--wf-muted-fg)",
                                                    }}>
                                                        {solution.relevance}%
                                                    </span>
                                                    <span style={{
                                                        fontSize: 10,
                                                        fontFamily: "var(--font-mono)",
                                                        color: "var(--wf-muted-fg)",
                                                        background: "var(--wf-badge-bg)",
                                                        border: "1px solid var(--wf-badge-border)",
                                                        padding: "2px 8px",
                                                        borderRadius: 4,
                                                        letterSpacing: "0.04em",
                                                    }}>
                                                        Score {solution.overall.toFixed(2)}
                                                    </span>
                                                </div>
                                            </motion.div>
                                        ))}
                                    </div>
                                )}
                            </div>

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
                                    {checklist.map((item, index) => (
                                        <motion.div
                                            key={index}
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
                                            transition={{ delay: 0.3 + index * 0.08 }}
                                        >
                                            <CheckIcon met={item.met} />
                                            <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
                                                <span style={{ fontSize: 13, color: "var(--wf-fg)", lineHeight: 1.5, opacity: item.met ? 1 : 0.6 }}>
                                                    {item.label}
                                                </span>
                                            </div>
                                        </motion.div>
                                    ))}
                                </div>
                            </div>

                            {mode !== "idle" && (
                                <div>
                                    <div style={{ fontSize: 11, color: "var(--text-muted)", marginBottom: 6 }}>
                                        {mode === "rework" ? "Rework note (required):" : "Reason for stopping (required):"}
                                    </div>
                                    <textarea
                                        className="gate-note-field"
                                        value={noteText}
                                        onChange={(e) => setNoteText(e.target.value)}
                                        placeholder={mode === "rework" ? "Explain what needs to be reworked…" : "Explain why this initiative is being abandoned…"}
                                        autoFocus
                                    />
                                </div>
                            )}
                        </div>

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
                                        disabled={!allMet}
                                        style={{
                                            width: "100%",
                                            padding: "11px 16px",
                                            borderRadius: 6,
                                            background: !allMet ? "var(--wf-success-bg-disabled)" : "var(--wf-success-bg)",
                                            color: "var(--wf-btn-strong-fg)",
                                            fontWeight: 700,
                                            fontSize: 14,
                                            border: "none",
                                            cursor: !allMet ? "not-allowed" : "pointer",
                                            fontFamily: "var(--font-mono)",
                                            letterSpacing: "0.06em",
                                            transition: "filter 0.15s",
                                        }}
                                        onMouseOver={(e) => { if (allMet) e.currentTarget.style.filter = "brightness(1.1)"; }}
                                        onMouseOut={(e) => (e.currentTarget.style.filter = "")}
                                    >
                                        GO
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
                                            transition: "all 0.15s",
                                        }}
                                        onMouseOver={(e) => { e.currentTarget.style.color = "var(--wf-fg)"; e.currentTarget.style.borderColor = "var(--wf-muted-fg)"; }}
                                        onMouseOut={(e) => { e.currentTarget.style.color = "var(--wf-muted-fg)"; e.currentTarget.style.borderColor = "var(--wf-border)"; }}
                                    >
                                        REQUEST CHANGES
                                    </button>
                                    <button
                                        onClick={() => setMode("stop")}
                                        style={{
                                            width: "100%",
                                            padding: "11px 16px",
                                            borderRadius: 6,
                                            background: "transparent",
                                            color: "var(--wf-destructive)",
                                            fontSize: 14,
                                            border: "1px solid rgba(220, 50, 50, 0.35)",
                                            cursor: "pointer",
                                            fontFamily: "var(--font-mono)",
                                            letterSpacing: "0.06em",
                                            transition: "background 0.15s, border-color 0.15s",
                                        }}
                                        onMouseOver={(e) => {
                                            e.currentTarget.style.background = "var(--wf-stop-hover-bg)";
                                            e.currentTarget.style.borderColor = "var(--wf-destructive)";
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
