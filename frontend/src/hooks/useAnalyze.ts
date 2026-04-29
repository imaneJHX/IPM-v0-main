/**
 * Debounced hook for /needs/analyze — returns tags + suggestions.
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { analyzePitch } from "@/lib/api";
import { SMART_SUGGESTION_DEBOUNCE_MS, shouldCommitSuggestionResponse, shouldGenerateSmartSuggestions } from "@/lib/smartSuggestions";
import type { Horizon, SmartSuggestion, Tags } from "@/lib/types";

interface AnalyzeLiveContext {
    objective?: string | null;
    domains?: string[];
    impacts?: string[];
    tags?: string[];
    phase?: string;
    status?: string;
}

interface UseAnalyzeResult {
    tags: Tags | null;
    suggestions: SmartSuggestion[];
    isAnalyzing: boolean;
    error: string | null;
    canSuggest: boolean;
}

export function useAnalyze(
    pitch: string,
    horizon: Horizon | null,
    context: AnalyzeLiveContext = {},
): UseAnalyzeResult {
    const [tags, setTags] = useState<Tags | null>(null);
    const [suggestions, setSuggestions] = useState<SmartSuggestion[]>([]);
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const abortRef = useRef<AbortController | null>(null);
    const requestIdRef = useRef(0);
    const canSuggest = shouldGenerateSmartSuggestions(pitch);
    const domains = context.domains ?? [];
    const impacts = context.impacts ?? [];
    const liveTags = context.tags ?? [];
    const domainsKey = (context.domains ?? []).join("|");
    const impactsKey = (context.impacts ?? []).join("|");
    const tagsKey = (context.tags ?? []).join("|");

    const analyze = useCallback(async (text: string) => {
        if (!shouldGenerateSmartSuggestions(text)) {
            abortRef.current?.abort();
            setTags(null);
            setSuggestions([]);
            setError(null);
            setIsAnalyzing(false);
            return;
        }

        abortRef.current?.abort();
        const controller = new AbortController();
        abortRef.current = controller;
        requestIdRef.current += 1;
        const currentRequestId = requestIdRef.current;

        setIsAnalyzing(true);
        setError(null);

        try {
            const result = await analyzePitch({
                pitch: text,
                horizon,
                objective: context.objective ?? null,
                domains,
                impacts,
                tags: liveTags,
                phase: context.phase ?? "SG-1",
                status: context.status ?? "Draft",
            }, controller.signal);
            if (!shouldCommitSuggestionResponse(currentRequestId, requestIdRef.current)) {
                return;
            }
            setTags(result.tags);
            setSuggestions((result.suggestions || []).slice(0, 4));
        } catch (err) {
            if (err instanceof Error && err.name !== "AbortError" && shouldCommitSuggestionResponse(currentRequestId, requestIdRef.current)) {
                setError(err.message);
                setSuggestions([]);
            }
        } finally {
            if (shouldCommitSuggestionResponse(currentRequestId, requestIdRef.current)) {
                setIsAnalyzing(false);
            }
        }
    }, [context.objective, context.phase, context.status, domainsKey, impactsKey, tagsKey, horizon]);

    useEffect(() => {
        if (timerRef.current) clearTimeout(timerRef.current);

        timerRef.current = setTimeout(() => {
            analyze(pitch);
        }, SMART_SUGGESTION_DEBOUNCE_MS);

        return () => {
            if (timerRef.current) clearTimeout(timerRef.current);
            abortRef.current?.abort();
        };
    }, [pitch, analyze]);

    return { tags, suggestions, isAnalyzing, error, canSuggest };
}
