/**
 * SourcingShell — Orchestrates the 3-panel sourcing layout.
 * Manages state, integrates useAnalyze, and coordinates panels.
 * Updated for Phase 1: editable AI fields, new WorkflowBar integration.
 */

"use client";

import React, { useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAnalyze } from "@/hooks/useAnalyze";
import { getSuggestionApplyPayload } from "@/lib/smartSuggestions";
import { createNeed, getNeed, interactStageGate, updateNeedStatus } from "@/lib/api";
import { WorkflowBar } from "@/components/layout/WorkflowBar";
import { RecapPanel } from "@/components/sourcing/RecapPanel";
import { PitchPanel } from "@/components/sourcing/PitchPanel";
import { SuggestionsPanel } from "@/components/sourcing/SuggestionsPanel";
import { DuplicateBanner } from "@/components/sourcing/DuplicateBanner";
import type { BusinessNeed, Domain, DuplicateMatch, Horizon, Impact, Objectif, SmartSuggestion, StageGateInteractionResponse, Tags } from "@/lib/types";
import { HORIZON_LABELS, OBJECTIF_LABELS } from "@/lib/types";
import { Sg1ValidationPanel } from "@/components/sourcing/Sg1ValidationPanel";

type SuggestionTagOverrides = {
    objective?: Objectif;
    domains: Domain[];
    impacts: Impact[];
};

const EMPTY_SUGGESTION_OVERRIDES: SuggestionTagOverrides = { domains: [], impacts: [] };

function mergeUnique<T extends string>(current: T[], incoming: T[]): T[] {
    return Array.from(new Set([...current, ...incoming])) as T[];
}

function applySuggestionOverrides(tags: Tags, overrides: SuggestionTagOverrides): Tags {
    const nextObjective = overrides.objective ?? tags.objectif;
    const nextDomains = overrides.domains.length > 0 ? mergeUnique(tags.domaine, overrides.domains) : tags.domaine;
    const nextImpacts = overrides.impacts.length > 0 ? mergeUnique(tags.impact, overrides.impacts) : tags.impact;
    const nextDomainConfidence = { ...tags.domaine_confidence };
    const nextImpactConfidence = { ...tags.impact_confidence };

    for (const domain of overrides.domains) {
        nextDomainConfidence[domain] = nextDomainConfidence[domain] || "medium";
    }
    for (const impact of overrides.impacts) {
        nextImpactConfidence[impact] = nextImpactConfidence[impact] || "medium";
    }

    return {
        ...tags,
        objectif: nextObjective,
        objectif_confidence: overrides.objective ? "medium" : tags.objectif_confidence,
        domaine: nextDomains,
        impact: nextImpacts,
        domaine_confidence: nextDomainConfidence,
        impact_confidence: nextImpactConfidence,
    };
}

export function SourcingShell() {
    const router = useRouter();
    const [pitch, setPitch] = useState("");
    const [horizon, setHorizon] = useState<Horizon | null>(null);
    const [dismissedTags, setDismissedTags] = useState<Set<string>>(new Set());
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [duplicates, setDuplicates] = useState<DuplicateMatch[]>([]);
    const [showDuplicates, setShowDuplicates] = useState(false);

    // Summary metadata (editable via left SUMMARY panel)
    const [summaryObjectif, setSummaryObjectif] = useState("");
    const [summaryDomains, setSummaryDomains] = useState("");
    const [summaryImpact, setSummaryImpact] = useState("");
    const [suggestionOverrides, setSuggestionOverrides] = useState<SuggestionTagOverrides>(EMPTY_SUGGESTION_OVERRIDES);

    // Created need for this session (used for SG-1 validation flow)
    const [currentNeed, setCurrentNeed] = useState<BusinessNeed | null>(null);
    const [isValidationOpen, setIsValidationOpen] = useState(false);
    const [workflowStatus, setWorkflowStatus] = useState<"draft" | "submitted">("draft");
    const [sg1State, setSg1State] = useState<StageGateInteractionResponse | null>(null);

    const goToDiscoveryFromSg1 = useCallback(async (need: BusinessNeed) => {
        const updated = need.status === "submitted"
            ? need
            : await updateNeedStatus(need.id, { status: "submitted" });
        setCurrentNeed(updated);
        setWorkflowStatus("submitted");
        setShowDuplicates(false);
        setIsValidationOpen(false);
        router.push(`/discovery?id=${updated.id}`);
    }, [router]);

    const resolveNeedRoute = useCallback((need: BusinessNeed) => {
        if (need.status === "in_qualification") return `/evaluation?id=${need.id}`;
        if (need.status === "in_selection") return `/selection?id=${need.id}`;
        if (need.status === "delivery" || need.status === "export_ready") return `/recos?id=${need.id}`;
        return `/discovery?id=${need.id}`;
    }, []);

    const analyzeStatus = workflowStatus === "submitted" ? "Submitted" : "Draft";
    const { tags, suggestions, isAnalyzing, error: analyzeError, canSuggest } = useAnalyze(pitch, horizon, {
        objective: suggestionOverrides.objective ?? null,
        domains: suggestionOverrides.domains,
        impacts: suggestionOverrides.impacts,
        tags: [
            ...(suggestionOverrides.objective ? [suggestionOverrides.objective] : []),
            ...suggestionOverrides.domains,
            ...suggestionOverrides.impacts,
        ],
        phase: "SG-1",
        status: analyzeStatus,
    });

    // Auto-populate summary fields from AI tags when first detected
    useEffect(() => {
        if (!tags) return;

        if (!summaryObjectif && tags.objectif) {
            setSummaryObjectif(OBJECTIF_LABELS[tags.objectif]);
        }
        if (!summaryDomains && tags.domaine && tags.domaine.length > 0) {
            setSummaryDomains(tags.domaine.join(", "));
        }
        if (!summaryImpact && tags.impact && tags.impact.length > 0) {
            setSummaryImpact(tags.impact.join(", "));
        }
    }, [tags, summaryObjectif, summaryDomains, summaryImpact]);

    const canSubmit = pitch.trim().length >= 20 && horizon !== null && !isSubmitting;

    const handleDismissTag = (tagKey: string) => {
        setDismissedTags((prev) => {
            const next = new Set(prev);
            next.add(tagKey);
            return next;
        });
    };

    const handleApplySuggestion = (suggestion: SmartSuggestion) => {
        const payload = getSuggestionApplyPayload(suggestion);
        if (payload.nextPitch) {
            setPitch(payload.nextPitch);
        }
        if (payload.tagOverrides) {
            setSuggestionOverrides((prev) => {
                const merged: SuggestionTagOverrides = {
                    objective: payload.tagOverrides?.objective ?? prev.objective,
                    domains: mergeUnique(prev.domains, payload.tagOverrides?.domains || []),
                    impacts: mergeUnique(prev.impacts, payload.tagOverrides?.impacts || []),
                };
                if (merged.objective) {
                    setSummaryObjectif(OBJECTIF_LABELS[merged.objective]);
                }
                if (merged.domains.length > 0) {
                    setSummaryDomains(merged.domains.join(", "));
                }
                if (merged.impacts.length > 0) {
                    setSummaryImpact(merged.impacts.join(", "));
                }
                return merged;
            });
        }
    };

    // Create the need first, then open the SG-1 panel when ready
    const handleSubmit = async () => {
        if (!canSubmit || !horizon) return;

        // Need already created this session — just re-open the panel
        if (currentNeed) {
            setIsValidationOpen(true);
            return;
        }

        if (isSubmitting) return;

        setIsSubmitting(true);
        try {
            const precomputedTags = !isAnalyzing && tags ? applySuggestionOverrides(tags, suggestionOverrides) : undefined;
            const need = await createNeed({ pitch: pitch.trim(), horizon, tags: precomputedTags });
            setCurrentNeed(need);
            setSg1State(await interactStageGate(need.id, {
                gate: "SG-1",
                action: "SUMMARY",
                snapshot: { tags: need.tags, pitch: need.pitch, horizon: need.horizon },
            }));

            if (need.duplicate_matches && need.duplicate_matches.length > 0) {
                setDuplicates(need.duplicate_matches);
                setShowDuplicates(true);
            }

            // Open panel only once the need is persisted.
            // SG-1 is only completed once the user confirms GO and moves to Discovery.
            setIsValidationOpen(true);
        } catch {
            // submission failed — button returns to ready state, user can retry
        } finally {
            setIsSubmitting(false);
        }
    };

    const handleGo = useCallback(async () => {
        if (!currentNeed) return;
        setIsSubmitting(true);
        try {
            await goToDiscoveryFromSg1(currentNeed);
        } catch {
            setIsSubmitting(false);
        }
    }, [currentNeed, goToDiscoveryFromSg1]);

    const handleCloseValidation = useCallback(() => {
        setIsValidationOpen(false);
    }, []);

    const handleRework = useCallback(async (note?: string) => {
        if (!currentNeed || !note) return;
        const response = await interactStageGate(currentNeed.id, {
            gate: "SG-1",
            action: "REWORK",
            comment: note,
            snapshot: { tags: currentNeed.tags, pitch: currentNeed.pitch, horizon: currentNeed.horizon },
        });
        setSg1State(response);
        const correctedTags = response.corrected_snapshot.tags;
        if (correctedTags && typeof correctedTags === "object") {
            const next = { ...currentNeed, tags: correctedTags as BusinessNeed["tags"] };
            setCurrentNeed(next);
            if (typeof (correctedTags as { objectif?: string }).objectif === "string") {
                setSummaryObjectif((correctedTags as { objectif?: string }).objectif || "");
            }
            if (Array.isArray((correctedTags as { domaine?: string[] }).domaine)) {
                setSummaryDomains(((correctedTags as { domaine?: string[] }).domaine || []).join(", "));
            }
            if (Array.isArray((correctedTags as { impact?: string[] }).impact)) {
                setSummaryImpact(((correctedTags as { impact?: string[] }).impact || []).join(", "));
            }
        }
        setWorkflowStatus("draft");
    }, [currentNeed]);

    const handleAbandon = useCallback(async () => {
        // If no need was persisted yet, simply reset and go back to dashboard
        if (!currentNeed) {
            setPitch("");
            setHorizon(null);
            setSummaryObjectif("");
            setSummaryDomains("");
            setSummaryImpact("");
            setIsValidationOpen(false);
            router.push("/dashboard");
            return;
        }

        setIsSubmitting(true);
        try {
            await updateNeedStatus(currentNeed.id, { status: "abandoned" });
            setIsValidationOpen(false);
            router.push("/dashboard");
        } catch {
            setIsSubmitting(false);
        }
    }, [currentNeed, router]);

    return (
        <div className="app-shell">
            <WorkflowBar
                currentStep={showDuplicates && duplicates.length > 0 ? "business_need" : isValidationOpen ? "sg1" : "business_need"}
                status={workflowStatus}
                isInteractive={false}
            />

            <div className="app-content">
                <div className="glow-divider" />

                {showDuplicates && duplicates.length > 0 && (
                    <DuplicateBanner
                        matches={duplicates}
                        onDismiss={async () => {
                            if (!currentNeed) return;
                            setIsSubmitting(true);
                            try {
                                await goToDiscoveryFromSg1(currentNeed);
                            } finally {
                                setIsSubmitting(false);
                            }
                        }}
                        onViewDuplicate={async (id) => {
                            setIsSubmitting(true);
                            try {
                                const existingNeed = await getNeed(id);
                                const updated = existingNeed.status === "draft"
                                    ? await updateNeedStatus(id, { status: "submitted" })
                                    : existingNeed;
                                setShowDuplicates(false);
                                setIsValidationOpen(false);
                                router.push(resolveNeedRoute(updated));
                            } finally {
                                setIsSubmitting(false);
                            }
                        }}
                    />
                )}

                <div className="workspace">
                    <RecapPanel
                        pitch={pitch}
                        onPitchChange={setPitch}
                        tags={tags}
                        horizon={horizon}
                        summaryObjectif={summaryObjectif}
                        onSummaryObjectifChange={setSummaryObjectif}
                        summaryDomains={summaryDomains}
                        onSummaryDomainsChange={setSummaryDomains}
                        summaryImpact={summaryImpact}
                        onSummaryImpactChange={setSummaryImpact}
                        dismissedTags={dismissedTags}
                        onDismissTag={handleDismissTag}
                    />

                    <PitchPanel
                        pitch={pitch}
                        onPitchChange={setPitch}
                        horizon={horizon}
                        onHorizonChange={setHorizon}
                        canSubmit={canSubmit}
                        isSubmitting={isSubmitting}
                        onSubmit={handleSubmit}
                    />

                    <SuggestionsPanel
                        suggestions={suggestions}
                        isAnalyzing={isAnalyzing}
                        hasPitch={pitch.trim().length > 0}
                        canSuggest={canSuggest}
                        onApply={handleApplySuggestion}
                        error={analyzeError}
                    />
                </div>
            </div>

            <Sg1ValidationPanel
                open={isValidationOpen}
                isProcessing={isSubmitting}
                pitch={pitch}
                horizonLabel={horizon ? HORIZON_LABELS[horizon].label : "Not selected"}
                objectif={summaryObjectif}
                domains={summaryDomains}
                impact={summaryImpact}
                sourcingClassification={currentNeed?.tags.sourcing_classification ?? tags?.sourcing_classification ?? null}
                hasDuplicates={(currentNeed?.duplicate_matches?.length ?? 0) > 0}
                stageSummary={sg1State?.summary}
                stageDiffs={sg1State?.diffs}
                stageMessages={sg1State?.messages}
                escalated={sg1State?.escalated}
                onClose={handleCloseValidation}
                onGo={handleGo}
                onRework={handleRework}
                onAbandon={handleAbandon}
            />
        </div>
    );
}
