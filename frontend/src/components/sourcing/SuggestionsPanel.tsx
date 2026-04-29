/**
 * SuggestionsPanel - Right panel: live SG-1 smart suggestions.
 */

"use client";

import { useState } from "react";
import type { CSSProperties } from "react";

import { getSuggestionCopyText } from "@/lib/smartSuggestions";
import type { SmartSuggestion } from "@/lib/types";

interface SuggestionsPanelProps {
    suggestions: SmartSuggestion[];
    isAnalyzing: boolean;
    hasPitch: boolean;
    canSuggest: boolean;
    onApply: (suggestion: SmartSuggestion) => void;
    error?: string | null;
}

function confidenceStyle(confidence: SmartSuggestion["confidence"]): CSSProperties {
    if (confidence === "high") {
        return { background: "rgba(34, 197, 94, 0.14)", color: "#86efac", border: "1px solid rgba(34, 197, 94, 0.25)" };
    }
    if (confidence === "medium") {
        return { background: "rgba(249, 115, 22, 0.14)", color: "#fdba74", border: "1px solid rgba(249, 115, 22, 0.25)" };
    }
    return { background: "rgba(148, 163, 184, 0.14)", color: "#cbd5e1", border: "1px solid rgba(148, 163, 184, 0.25)" };
}

export function SuggestionsPanel({ suggestions, isAnalyzing, hasPitch, canSuggest, onApply, error }: SuggestionsPanelProps) {
    const [copiedKey, setCopiedKey] = useState<string | null>(null);
    const [expanded, setExpanded] = useState(false);
    const visibleSuggestions = expanded ? suggestions : suggestions.slice(0, 3);

    const handleCopy = async (cardKey: string, text: string) => {
        try {
            await navigator.clipboard.writeText(text);
            setCopiedKey(cardKey);
            window.setTimeout(() => {
                setCopiedKey((current) => current === cardKey ? null : current);
            }, 1500);
        } catch {
            setCopiedKey(null);
        }
    };

    return (
        <div className="panel panel-scroll">
            <div className="panel-title">AI SUGGESTIONS</div>

            {!hasPitch && !isAnalyzing && suggestions.length === 0 && (
                <div className="sug-empty">
                    <div className="sug-diamond">+</div>
                    <p>Start writing your pitch and smart suggestions will appear live.</p>
                </div>
            )}

            {hasPitch && !canSuggest && !isAnalyzing && suggestions.length === 0 && !error && (
                <div className="sug-empty">
                    <div className="sug-diamond">+</div>
                    <p>Add at least 3 meaningful words or 12 characters.</p>
                    <p className="sug-sub">Try describing the business outcome, the journey, or the KPI you want to improve.</p>
                </div>
            )}

            {isAnalyzing && (
                <div className="sug-skeleton-list">
                    <div className="sug-loading">
                        <span className="sug-spinner" />
                        <span>Generating smart suggestions...</span>
                    </div>
                    {Array.from({ length: 3 }).map((_, i) => (
                        <div key={i} className="sug-card sug-card-skeleton">
                            <div className="sug-label" />
                            <div className="sug-text" />
                            <div className="sug-use-btn" />
                        </div>
                    ))}
                </div>
            )}

            {error && !isAnalyzing && (
                <div className="sug-empty">
                    <div className="sug-diamond" style={{ opacity: 0.4, color: "#f87171" }}>+</div>
                    <p style={{ color: "#f87171", fontSize: 12 }}>Suggestion service unavailable</p>
                    <p className="sug-sub">Check whether the backend is running on port 8000.</p>
                </div>
            )}

            {hasPitch && canSuggest && !isAnalyzing && !error && suggestions.length === 0 && (
                <div className="sug-empty">
                    <div className="sug-diamond" style={{ opacity: 0.4 }}>+</div>
                    <p>No smart suggestions yet.</p>
                    <p className="sug-sub">Keep typing - the panel updates automatically as SG-1 context becomes clearer.</p>
                </div>
            )}

            {visibleSuggestions.map((suggestion, index) => {
                const cardKey = `${suggestion.id}-${index}`;
                const copyText = getSuggestionCopyText(suggestion);
                return (
                    <div
                        key={cardKey}
                        className="sug-card"
                        style={{ animationDelay: `${index * 65}ms` }}
                    >
                        <div className="sug-card-head">
                            <div className="sug-meta">
                                <div className="sug-label">{suggestion.category}</div>
                                <div className="sug-title">{suggestion.title}</div>
                            </div>
                            <span className="sug-confidence" style={confidenceStyle(suggestion.confidence)}>
                                {suggestion.confidence}
                            </span>
                        </div>

                        <div className="sug-text">{suggestion.explanation}</div>

                        {suggestion.improved_pitch && (
                            <div className="sug-block">
                                <div className="sug-block-label">Improved pitch</div>
                                <div className="sug-text">{suggestion.improved_pitch}</div>
                            </div>
                        )}

                        <div className="sug-block">
                            <div className="sug-block-label">Next action</div>
                            <div className="sug-text">{suggestion.next_action}</div>
                        </div>

                        {(suggestion.suggested_tags || []).length > 0 && (
                            <div className="sug-tag-row">
                                {(suggestion.suggested_tags || []).map((tag) => (
                                    <span key={`${cardKey}-${tag}`} className="tag-chip">{tag}</span>
                                ))}
                            </div>
                        )}

                        <div className="sug-actions">
                            <button
                                type="button"
                                className="sug-copy-btn"
                                onClick={(event) => {
                                    event.stopPropagation();
                                    void handleCopy(cardKey, copyText);
                                }}
                            >
                                {copiedKey === cardKey ? "Copied" : "Copy"}
                            </button>
                            <button
                                type="button"
                                className="sug-use-btn"
                                onClick={(event) => {
                                    event.stopPropagation();
                                    onApply(suggestion);
                                }}
                            >
                                Apply
                            </button>
                        </div>
                    </div>
                );
            })}

            {suggestions.length > 3 && (
                <button
                    type="button"
                    className="sug-show-more"
                    onClick={() => setExpanded((current) => !current)}
                >
                    {expanded ? "Show less" : `Show more (${suggestions.length - 3})`}
                </button>
            )}
        </div>
    );
}
