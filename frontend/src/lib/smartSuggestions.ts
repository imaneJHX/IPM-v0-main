import type { Domain, Impact, Objectif, SmartSuggestion } from "./types";

export const SMART_SUGGESTION_DEBOUNCE_MS = 600;

const OBJECTIF_TAGS: Objectif[] = [
    "cost_reduction",
    "cx_improvement",
    "risk_mitigation",
    "market_opportunity",
];
const DOMAIN_TAGS: Domain[] = [
    "IA",
    "Cloud",
    "Cybersecurite",
    "Data",
    "RH",
    "Finance",
    "Operations",
    "Autre",
];
const IMPACT_TAGS: Impact[] = ["Revenue", "Cost", "Risk", "CustomerExperience"];

export interface SuggestionTagOverrides {
    objective?: Objectif;
    domains: Domain[];
    impacts: Impact[];
}

export interface SuggestionApplyPayload {
    nextPitch?: string;
    tagOverrides?: SuggestionTagOverrides;
}

export function countMeaningfulWords(text: string): number {
    const matches = text.match(/[A-Za-z0-9][A-Za-z0-9/+_-]*/g) || [];
    return matches.filter((word) => word.length >= 2).length;
}

export function shouldGenerateSmartSuggestions(text: string): boolean {
    const trimmed = text.trim();
    return countMeaningfulWords(trimmed) >= 3 || trimmed.length >= 12;
}

export function getSuggestionCopyText(suggestion: SmartSuggestion): string {
    return suggestion.improved_pitch || suggestion.next_action || suggestion.explanation || suggestion.title;
}

export function buildSuggestionTagOverrides(suggestedTags: string[] | undefined): SuggestionTagOverrides | undefined {
    if (!suggestedTags || suggestedTags.length === 0) {
        return undefined;
    }

    const overrides: SuggestionTagOverrides = {
        domains: [],
        impacts: [],
    };

    for (const tag of suggestedTags) {
        if (OBJECTIF_TAGS.includes(tag as Objectif)) {
            overrides.objective = tag as Objectif;
            continue;
        }
        if (DOMAIN_TAGS.includes(tag as Domain) && !overrides.domains.includes(tag as Domain)) {
            overrides.domains.push(tag as Domain);
            continue;
        }
        if (IMPACT_TAGS.includes(tag as Impact) && !overrides.impacts.includes(tag as Impact)) {
            overrides.impacts.push(tag as Impact);
        }
    }

    if (!overrides.objective && overrides.domains.length === 0 && overrides.impacts.length === 0) {
        return undefined;
    }
    return overrides;
}

export function getSuggestionApplyPayload(suggestion: SmartSuggestion): SuggestionApplyPayload {
    if (suggestion.action_type === "apply_tag") {
        return { tagOverrides: buildSuggestionTagOverrides(suggestion.suggested_tags) };
    }
    if (suggestion.action_type === "apply_pitch" || suggestion.action_type === "copy") {
        return { nextPitch: getSuggestionCopyText(suggestion) };
    }
    return suggestion.improved_pitch ? { nextPitch: suggestion.improved_pitch } : {};
}

export function shouldCommitSuggestionResponse(resolvedRequestId: number, latestRequestId: number): boolean {
    return resolvedRequestId === latestRequestId;
}
