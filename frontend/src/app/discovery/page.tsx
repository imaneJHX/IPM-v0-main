/**
 * Discovery page — 2-panel progressive disclosure layout.
 * The proceed button and explore modal live inside DiscoveryPanel.
 */

"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { WorkflowBar } from "@/components/layout/WorkflowBar";
import { DiscoveryPanel } from "@/components/discovery/DiscoveryPanel";
import { Sg2ValidationPanel } from "@/components/sourcing/Sg2ValidationPanel";
import { updateNeedStatus, getNeed } from "@/lib/api";
import type { Status } from "@/lib/types";

function DiscoveryPageContent() {
    const searchParams = useSearchParams();
    const ipmId = searchParams.get("id") || undefined;
    const [cardStates, setCardStates] = useState<Record<string, string>>({});
    const [totalSelected, setTotalSelected] = useState(0);
    const [showSg2, setShowSg2] = useState(false);
    const [needStatus, setNeedStatus] = useState<Status>("submitted");
    const [statusLoaded, setStatusLoaded] = useState(false);
    const [transitionError, setTransitionError] = useState<string | null>(null);

    useEffect(() => {
        if (!ipmId) return;
        getNeed(ipmId)
            .then((need) => {
                setNeedStatus(need.status);
                setStatusLoaded(true);
            })
            .catch(() => {
                setNeedStatus("submitted");
                setStatusLoaded(true);
            });
    }, [ipmId]);

    const displayStatus = needStatus;
    const canEnterDiscovery = !statusLoaded || displayStatus === "submitted";

    useEffect(() => {
        const canvas = document.getElementById("bg-canvas") as HTMLCanvasElement | null;
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        const chars = "0123456789ABCDEF";
        ctx.fillStyle = "rgba(99, 91, 255, 0.03)";
        ctx.font = "11px DM Mono, monospace";
        for (let x = 0; x < canvas.width; x += 28) {
            for (let y = 0; y < canvas.height; y += 20) {
                ctx.fillText(chars[Math.floor(Math.random() * chars.length)], x + Math.random() * 8, y + Math.random() * 6);
            }
        }
    }, []);

    return (
        <div className="app-shell">
            <canvas id="bg-canvas" style={{ position: "fixed", top: 0, left: 0, zIndex: -1 }} />
            <WorkflowBar currentStep="discovery" status={displayStatus} ipmId={ipmId} />

            <div className="app-content" style={{ overflowY: "auto" }}>
                <div className="glow-divider" />

                {transitionError && (
                    <div style={{ margin: "16px 24px 0", padding: 14, borderRadius: 12, border: "1px solid rgba(220, 50, 50, 0.35)", background: "rgba(255, 88, 88, 0.08)", color: "var(--destructive)" }}>
                        {transitionError}
                    </div>
                )}

                <div style={{ padding: "20px 24px 0" }}>
                    <h1 style={{ fontSize: 22, fontWeight: 300 }}>Discovery</h1>
                    <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 2 }}>
                        Launch tools to surface relevant solutions, signals, and opportunities
                    </div>
                </div>

                <DiscoveryPanel
                    needId={ipmId}
                    onCardStatesChange={(states, total) => {
                        setCardStates(states as Record<string, string>);
                        setTotalSelected(total);
                    }}
                    onProceed={() => {
                        if (!canEnterDiscovery) return;
                        setTransitionError(null);
                        localStorage.setItem("ipm_sg2_state", JSON.stringify({ cardStates, totalSelected }));
                        setShowSg2(true);
                    }}
                />
            </div>

            <Sg2ValidationPanel
                open={showSg2}
                onGo={async () => {
                    if (!canEnterDiscovery) return;
                    setTransitionError(null);
                    if (ipmId) {
                        try {
                            const currentNeed = await getNeed(ipmId);
                            if (currentNeed.status === "in_qualification") {
                                setNeedStatus("in_qualification");
                                window.location.href = `/evaluation?id=${ipmId}`;
                                return;
                            }
                            if (currentNeed.status !== "submitted") {
                                throw new Error(
                                    `Cannot validate SG-2 from status '${currentNeed.status}'. The need must be submitted before Qualification.`
                                );
                            }
                            const updated = await updateNeedStatus(ipmId, { status: "in_qualification" });
                            setNeedStatus(updated.status);
                            window.location.href = `/evaluation?id=${ipmId}`;
                            return;
                        } catch (error) {
                            setTransitionError(error instanceof Error ? error.message : "Unable to validate SG-2.");
                            setShowSg2(false);
                            return;
                        }
                    }
                }}
                onRework={() => setShowSg2(false)}
                onAbandon={async () => {
                    if (ipmId) {
                        try {
                            await updateNeedStatus(ipmId, { status: "abandoned" });
                        } catch { /* ignore */ }
                    }
                    window.location.href = "/dashboard";
                }}
            />
        </div>
    );
}

export default function DiscoveryPage() {
    return (
        <Suspense fallback={<div className="app-shell" style={{ display: "flex", justifyContent: "center", alignItems: "center" }}>Loading...</div>}>
            <DiscoveryPageContent />
        </Suspense>
    );
}
