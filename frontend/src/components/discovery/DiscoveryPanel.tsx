/**
 * DiscoveryPanel — 2-panel progressive disclosure layout.
 *
 * LEFT COLUMN  : DXC Internal Catalog → (after done) Tech Signals
 *                → (if launched from modal) Startups / Tech Watch
 * RIGHT COLUMN : Gap analysis panel (slides in on catalog item select)
 *                + Tech signals recap (when tech signals done + selected)
 * BOTTOM BAR   : "For More Exploration" modal trigger | "Proceed to Qualification →"
 *
 * Panel 1 (DXC Internal Catalog) is live:
 *   - Launch  → POST /api/v1/needs/{id}/catalog-search
 *   - Select  → POST /api/v1/needs/{id}/gap-analysis (right panel)
 * Panels 2-4 remain stubs.
 */

"use client";

import { Fragment, useState, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ALL_SOURCES, type DiscoveryItem, type DiscoverySource } from "@/lib/discoveryStubs";
import { searchCatalog, getGapAnalysis, getTechSignals } from "@/lib/api";
import { DiscoveryGapAnalysisPanel } from "@/components/discovery/GapAnalysisPanel";
import type { CatalogProduct, GapAnalysisResponse, TechSignal } from "@/lib/types";
import {
    SIGNAL_TYPE_LABELS,
    SIGNAL_TYPE_TAG_CLASS,
    MATURITY_LABELS,
    MATURITY_TAG_CLASS,
} from "@/lib/types";

type CardState = "idle" | "active" | "done";

const TOOL_META: Record<string, { icon: string; description: string }> = {
    dxc_catalog:  { icon: "⬡", description: "Search DXC's internal AI product catalog for existing solutions." },
    tech_signals: { icon: "◈", description: "Scan patents, research papers, and industry trend signals." },
    startups:     { icon: "◎", description: "Discover relevant startups via StartupConnect AI matching." },
    tech_watch:   { icon: "◉", description: "Browse curated AI Watch market & regulatory intelligence." },
};

interface GapState {
    itemId: string | null;
    data: GapAnalysisResponse | null;
    loading: boolean;
    error: boolean;
}

type StoredSelectedSolution = {
    id: string;
    name: string;
    relevance: number;
    description?: string;
    features?: string[];
    business_impact?: string;
    maturity_level?: string;
    gap_analysis: GapAnalysisResponse | null;
};

interface DiscoveryPanelProps {
    needId?: string;
    onSelectionChange?: (selected: DiscoveryItem[]) => void;
    onCardStatesChange?: (states: Record<string, CardState>, totalSelected: number) => void;
    onProceed?: () => void;
}

// ---------------------------------------------------------------------------
// Gap Analysis Right Panel
// Uses only existing disc-card, disc-item-score CSS classes.
// ---------------------------------------------------------------------------

function GapAnalysisPanel({ gap }: { gap: GapState }) {
    if (gap.loading) {
        return (
            <div style={{
                padding: "16px 20px",
                fontSize: 14,
                color: "var(--wf-muted-fg)",
                animation: "amberPulse 1.5s ease-in-out infinite",
            }}>
                Analyzing fit…
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
        { key: "maturite", label: "Maturite", value: data.ivi_scoring.maturite },
        { key: "expertise", label: "Expertise", value: data.ivi_scoring.expertise },
        { key: "duree", label: "Duree", value: data.ivi_scoring.duree },
        { key: "donnees", label: "Donnees", value: data.ivi_scoring.donnees },
        { key: "impact_business", label: "Impact business", value: data.ivi_scoring.impact_business },
    ] as const;

    return (
        <div style={{ padding: "16px 20px", display: "flex", flexDirection: "column", gap: 12 }}>
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

            <div style={{ display: "grid", gap: 8, padding: "10px 12px", borderRadius: 12, background: "var(--wf-bg-elevated, rgba(255,255,255,0.03))", border: "1px solid var(--wf-border, rgba(255,255,255,0.08))" }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--wf-fg)" }}>Fit justification</div>
                <div style={{ fontSize: 13, lineHeight: 1.6, color: "var(--wf-muted-fg)" }}>{data.fit_justification}</div>
                <div style={{ fontSize: 12, lineHeight: 1.6, color: "var(--wf-muted-fg)" }}>
                    Feasibility rationale: {data.feasibility.justification}
                </div>
            </div>

            <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--wf-fg)", marginBottom: 8 }}>
                    IVI scoring
                </div>
                <div style={{ display: "grid", gap: 8 }}>
                    {iviRows.map((row) => (
                        <div key={row.key} style={{ padding: "10px 12px", borderRadius: 12, background: "var(--wf-bg-elevated, rgba(255,255,255,0.03))", border: "1px solid var(--wf-border, rgba(255,255,255,0.08))", display: "grid", gap: 4 }}>
                            <div style={{ display: "flex", justifyContent: "space-between", gap: 12, alignItems: "center" }}>
                                <div style={{ minWidth: 0, fontSize: 13, fontWeight: 600, color: "var(--wf-fg)" }}>{row.label}</div>
                                <div style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: 4,
                                    whiteSpace: "nowrap",
                                    flexShrink: 0,
                                    lineHeight: 1,
                                    fontSize: 13,
                                    fontWeight: 700,
                                    color: row.value.score >= 4 ? "#22c55e" : row.value.score === 3 ? "#f97316" : "#ef4444",
                                }}>
                                    <span style={{ whiteSpace: "nowrap" }}>{`${row.value.score}/5`}</span>
                                </div>
                            </div>
                            <div style={{ fontSize: 12, lineHeight: 1.55, color: "var(--wf-muted-fg)" }}>{row.value.justification}</div>
                        </div>
                    ))}
                </div>
            </div>

            {data.features_matching.length > 0 && (
                <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "#6ec9a4", marginBottom: 5 }}>
                        ✓ Features matching
                    </div>
                    {data.features_matching.map((f, i) => (
                        <div key={i} style={{ fontSize: 13, color: "var(--wf-muted-fg)", paddingLeft: 10, lineHeight: 1.7 }}>• {f}</div>
                    ))}
                </div>
            )}

            {data.features_missing.length > 0 && (
                <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "var(--wf-destructive)", marginBottom: 5 }}>
                        ✗ Features missing
                    </div>
                    {data.features_missing.map((f, i) => (
                        <div key={i} style={{ fontSize: 13, color: "var(--wf-muted-fg)", paddingLeft: 10, lineHeight: 1.7 }}>• {f}</div>
                    ))}
                </div>
            )}

            {data.risks.length > 0 && (
                <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "#ffb84d", marginBottom: 5 }}>
                        Risks
                    </div>
                    {data.risks.map((risk, i) => (
                        <div key={i} style={{ fontSize: 13, color: "var(--wf-muted-fg)", paddingLeft: 10, lineHeight: 1.7 }}>• {risk}</div>
                    ))}
                </div>
            )}

            {data.resources_needed.length > 0 && (
                <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "var(--wf-muted-fg)", marginBottom: 5 }}>
                        ⚙ Resources needed
                    </div>
                    {data.resources_needed.map((r, i) => (
                        <div key={i} style={{ fontSize: 13, color: "var(--wf-muted-fg)", paddingLeft: 10, lineHeight: 1.7 }}>• {r}</div>
                    ))}
                </div>
            )}

            <div style={{ fontSize: 12, lineHeight: 1.6, color: "var(--wf-muted-fg)" }}>
                Context compression retained {data.audit.context_compression.retained_features.length} feature(s) for scoring and prompt injection.
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// DiscoveryPanel
// ---------------------------------------------------------------------------

export function DiscoveryPanel({ needId, onSelectionChange, onCardStatesChange, onProceed }: DiscoveryPanelProps) {
    const [sources] = useState<DiscoverySource[]>(ALL_SOURCES);
    const [cardStates, setCardStates] = useState<Record<string, CardState>>(
        Object.fromEntries(ALL_SOURCES.map((s) => [s.key, "idle"]))
    );
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [refreshedKeys, setRefreshedKeys] = useState<Set<string>>(new Set());
    const [showExploreModal, setShowExploreModal] = useState(false);

    // Panel 1 — API-fetched items + gap analysis state
    const [catalog1Items, setCatalog1Items] = useState<DiscoveryItem[]>([]);
    const [catalog1Products, setCatalog1Products] = useState<CatalogProduct[]>([]);
    const [catalog1Loading, setCatalog1Loading] = useState(false);
    const [gapAnalysis, setGapAnalysis] = useState<GapState>({
        itemId: null, data: null, loading: false, error: false,
    });
    const [gapAnalysesById, setGapAnalysesById] = useState<Record<string, GapAnalysisResponse>>({});

    // Panel 2 — Tech Signals (real API)
    const [techSignals, setTechSignals] = useState<TechSignal[]>([]);
    const [techSignalsLoading, setTechSignalsLoading] = useState(false);
    const [techSignalsError, setTechSignalsError] = useState<string | null>(null);
    const [techSignalsFromCache, setTechSignalsFromCache] = useState(false);

    // Derived card states
    const catalogState = cardStates["dxc_catalog"];
    const catalogDone = catalogState === "done";
    const techSignalsState = cardStates["tech_signals"];
    const techSignalsDone = techSignalsState === "done";
    const startupsState = cardStates["startups"];
    const techWatchState = cardStates["tech_watch"];
    const showStartups = startupsState === "active" || startupsState === "done";
    const showTechWatch = techWatchState === "active" || techWatchState === "done";

    // Source refs
    const techSignalsSource = sources.find(s => s.key === "tech_signals")!;
    const startupsSource = sources.find(s => s.key === "startups")!;
    const techWatchSource = sources.find(s => s.key === "tech_watch")!;

    const catalogSelectedCount = catalog1Items.filter(i => selectedIds.has(i.id)).length;
    const proceedEnabled = selectedIds.size > 0;

    // Items from panels 3-4 (Startups, Tech Watch) are stable stubs
    const otherItems = sources.filter(s => s.key !== "dxc_catalog" && s.key !== "tech_signals").flatMap(s => s.items);
    const allItems = [...catalog1Items, ...otherItems];

    useEffect(() => {
        onCardStatesChange?.(cardStates, selectedIds.size);
    }, [cardStates, selectedIds, onCardStatesChange]);

    // Persist selected catalog solutions to localStorage for SG-2 recap
    useEffect(() => {
        const selectedSolutions: StoredSelectedSolution[] = catalog1Items
            .filter(i => selectedIds.has(i.id))
            .map(i => {
                const product = catalog1Products.find((candidate) => candidate.id === i.id);
                return {
                    id: i.id,
                    name: i.name,
                    relevance: i.relevance,
                    description: i.description,
                    features: product?.features || [],
                    business_impact: product?.business_impact || "",
                    maturity_level: product?.maturity_level || "",
                    gap_analysis: gapAnalysesById[i.id] || null,
                };
            });
        localStorage.setItem("ipm_selected_solutions", JSON.stringify(selectedSolutions));
    }, [selectedIds, catalog1Items, catalog1Products, gapAnalysesById]);

    const setCardState = (key: string, state: CardState) =>
        setCardStates((prev) => ({ ...prev, [key]: state }));

    // Panel 1 — launch: call catalog-search API; fall back silently on error or missing needId
    const handleCatalogLaunch = useCallback(async () => {
        setCardState("dxc_catalog", "active");
        if (!needId) return;
        setCatalog1Loading(true);
        try {
            const resp = await searchCatalog(needId);
            setCatalog1Items(resp.results.map(p => ({
                id: p.id,
                name: p.name,
                description: p.description,
                relevance: Math.round(p.relevance_score * 100),
            })));
            setCatalog1Products(resp.results);
        } catch {
            // fall back to empty items silently
        } finally {
            setCatalog1Loading(false);
        }
    }, [needId]);

    // Panel 2 — Tech Signals fetch (called only on explicit card activation)
    const fetchTechSignals = async () => {
        if (!needId) return;
        setTechSignalsLoading(true);
        setTechSignalsError(null);
        try {
            const data = await getTechSignals(needId);
            setTechSignals(data.signals);
            setTechSignalsFromCache(data.from_cache);
        } catch {
            setTechSignalsError("Unable to load tech signals. Please try again.");
        } finally {
            setTechSignalsLoading(false);
        }
    };

    // Panel 1 — item toggle: maintains selection + triggers/clears gap analysis
    const handleCatalogItemToggle = useCallback((itemId: string) => {
        const wasSelected = selectedIds.has(itemId);

        setSelectedIds((prev) => {
            const next = new Set(prev);
            next.has(itemId) ? next.delete(itemId) : next.add(itemId);
            const catSelected = catalog1Items.filter(i => next.has(i.id));
            const othSelected = otherItems.filter(i => next.has(i.id));
            onSelectionChange?.([...catSelected, ...othSelected]);
            return next;
        });

        if (wasSelected) {
            setGapAnalysis({ itemId: null, data: null, loading: false, error: false });
        } else if (needId) {
            const product = catalog1Products.find(p => p.id === itemId);
            if (product) {
                setGapAnalysis({ itemId, data: null, loading: true, error: false });
                getGapAnalysis(needId, product)
                    .then(data => {
                        setGapAnalysesById((prev) => ({ ...prev, [itemId]: data }));
                        setGapAnalysis(g => g.itemId === itemId
                            ? { itemId, data, loading: false, error: false }
                            : g);
                    })
                    .catch(() => setGapAnalysis(g => g.itemId === itemId
                        ? { itemId, data: null, loading: false, error: true }
                        : g));
            }
        }
    }, [selectedIds, needId, catalog1Items, catalog1Products, otherItems, onSelectionChange]);

    // Panels 2-4 toggle — unchanged behavior
    const toggleItem = useCallback((itemId: string) => {
        setSelectedIds((prev) => {
            const next = new Set(prev);
            next.has(itemId) ? next.delete(itemId) : next.add(itemId);
            onSelectionChange?.(allItems.filter((i) => next.has(i.id)));
            return next;
        });
    }, [allItems, onSelectionChange]);

    const handleRefresh = (key: string) =>
        setRefreshedKeys((prev) => new Set(prev).add(key));

    // Tech signals — no per-item selection; badge count uses fetched signals length

    // ── Shared render helpers ────────────────────────────────────────────────

    function renderItemList(items: DiscoveryItem[], onToggle: (id: string) => void) {
        return items.map((item) => (
            <label key={item.id} className="disc-item">
                <input
                    type="checkbox"
                    className="discovery-item-checkbox"
                    checked={selectedIds.has(item.id)}
                    onChange={() => onToggle(item.id)}
                />
                <div className="disc-item-info">
                    <div className="disc-item-name">{item.name}</div>
                    <div className="disc-item-desc">{item.description}</div>
                </div>
                <span className={`disc-item-score ${item.relevance >= 80 ? "high" : item.relevance >= 65 ? "mid" : "low"}`}>
                    {item.relevance}%
                </span>
            </label>
        ));
    }

    function renderCardActions(sourceKey: string, hasSelection: boolean) {
        return (
            <div className="disc-card-actions">
                <button className="disc-action-ghost" onClick={() => handleRefresh(sourceKey)}>
                    ↻ Refresh
                </button>
                <button className="disc-action-done" onClick={() => setCardState(sourceKey, "done")}>
                    {hasSelection ? "Confirm selection ✓" : "✓ Done"}
                </button>
            </div>
        );
    }

    function renderDoneChips(displayItems: DiscoveryItem[], onToggle: (id: string) => void) {
        const selected = displayItems.filter(i => selectedIds.has(i.id));
        return (
            <div className="disc-card-summary">
                {selected.length > 0 ? (
                    selected.map((i) => (
                        <span key={i.id} className="disc-summary-chip">
                            {i.name}
                            <button onClick={() => onToggle(i.id)}>×</button>
                        </span>
                    ))
                ) : (
                    <span className="disc-summary-none">No items selected</span>
                )}
            </div>
        );
    }

    // ── Main render ──────────────────────────────────────────────────────────

    return (
        <div className="disc-layout">

            {/* ── Two-column responsive grid ── */}
            <div
                className="disc-two-col"
                style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24, alignItems: "start" }}
            >

                {/* ════ LEFT COLUMN ════ */}
                <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>

                    {/* ── DXC Internal Catalog ── */}
                    <div className={`disc-card ${catalogState}`}>
                        <div className="disc-card-header">
                            <div className="disc-card-icon">{TOOL_META.dxc_catalog.icon}</div>
                            <div className="disc-card-titles">
                                <div className="disc-card-title">DXC Internal Catalog</div>
                                <div className="disc-card-source">DAIC / AI Catalog</div>
                            </div>
                            {catalogState === "done" && catalogSelectedCount > 0 && (
                                <span className="disc-card-badge">{catalogSelectedCount} selected</span>
                            )}
                            {(catalogState === "active" || catalogState === "done") && (
                                <button
                                    className="disc-card-toggle"
                                    onClick={() => setCardState("dxc_catalog", catalogState === "active" ? "done" : "active")}
                                    title={catalogState === "active" ? "Collapse" : "Expand"}
                                >
                                    {catalogState === "active" ? "↑" : "↓"}
                                </button>
                            )}
                        </div>

                        {catalogState === "idle" && (
                            <div className="disc-card-idle">
                                <p className="disc-card-desc">{TOOL_META.dxc_catalog.description}</p>
                                <button className="disc-launch-btn" onClick={handleCatalogLaunch}>
                                    ▶ Launch Tool
                                </button>
                            </div>
                        )}

                        {catalogState === "active" && (
                            <div className="disc-card-results">
                                {catalog1Loading ? (
                                    <div className="disc-item" style={{ justifyContent: "center", borderBottom: "none" }}>
                                        <span style={{ fontSize: 12, color: "var(--text-muted)" }}>Loading catalog…</span>
                                    </div>
                                ) : (
                                    catalog1Items.map((item) => (
                                        <Fragment key={item.id}>
                                            <label className="disc-item">
                                                <input
                                                    type="checkbox"
                                                    className="discovery-item-checkbox"
                                                    checked={selectedIds.has(item.id)}
                                                    onChange={() => handleCatalogItemToggle(item.id)}
                                                />
                                                <div className="disc-item-info">
                                                    <div className="disc-item-name">{item.name}</div>
                                                    <div className="disc-item-desc">{item.description}</div>
                                                </div>
                                                <span className={`disc-item-score ${item.relevance >= 80 ? "high" : item.relevance >= 65 ? "mid" : "low"}`}>
                                                    {item.relevance}%
                                                </span>
                                            </label>
                                        </Fragment>
                                    ))
                                )}
                                {renderCardActions("dxc_catalog", catalogSelectedCount > 0)}
                            </div>
                        )}

                        {catalogState === "done" && renderDoneChips(catalog1Items, handleCatalogItemToggle)}
                    </div>

                    {/* ── Tech Signals (appears after catalog done) ── */}
                    {catalogDone && (
                        <div className={`disc-card ${techSignalsState}`}>
                            <div className="disc-card-header">
                                <div className="disc-card-icon">{TOOL_META.tech_signals.icon}</div>
                                <div className="disc-card-titles">
                                    <div className="disc-card-title">Tech Signals</div>
                                    <div className="disc-card-source">Patents & Trends</div>
                                </div>
                                {techSignalsState === "done" && techSignals.length > 0 && (
                                    <span className="disc-card-badge">{techSignals.length} signals</span>
                                )}
                                {(techSignalsState === "active" || techSignalsState === "done") && (
                                    <button
                                        className="disc-card-toggle"
                                        onClick={() => setCardState("tech_signals", techSignalsState === "active" ? "done" : "active")}
                                        title={techSignalsState === "active" ? "Collapse" : "Expand"}
                                    >
                                        {techSignalsState === "active" ? "↑" : "↓"}
                                    </button>
                                )}
                            </div>

                            {techSignalsState === "idle" && (
                                <div className="disc-card-idle">
                                    <p className="disc-card-desc">{TOOL_META.tech_signals.description}</p>
                                    <button className="disc-launch-btn" onClick={() => {
                                        setCardState("tech_signals", "active");
                                        fetchTechSignals();
                                    }}>
                                        ▶ Launch Tool
                                    </button>
                                </div>
                            )}

                            {techSignalsState === "active" && (
                                <div className="disc-card-results">
                                    {/* Loading: 3 shimmer skeleton rows */}
                                    {techSignalsLoading && (
                                        <>
                                            {[0, 1, 2].map((n) => (
                                                <div key={n} className="disc-item" style={{ opacity: 0.5 }}>
                                                    <div className="shimmer" style={{ height: 16, borderRadius: 4, marginBottom: 6, width: "60%" }} />
                                                    <div className="shimmer" style={{ height: 12, borderRadius: 4, width: "40%" }} />
                                                </div>
                                            ))}
                                        </>
                                    )}

                                    {/* Error state */}
                                    {!techSignalsLoading && techSignalsError && (
                                        <div className="disc-item">
                                            <p style={{ color: "var(--destructive)", fontSize: 13 }}>{techSignalsError}</p>
                                            <button className="disc-action-ghost" onClick={fetchTechSignals}>Retry</button>
                                        </div>
                                    )}

                                    {/* Empty state */}
                                    {!techSignalsLoading && !techSignalsError && techSignals.length === 0 && (
                                        <div className="disc-item">
                                            <p style={{ color: "var(--text-muted)", fontSize: 13 }}>No signals found for this business need.</p>
                                        </div>
                                    )}

                                    {/* Results */}
                                    {!techSignalsLoading && techSignals.map((signal) => (
                                        <div key={signal.id} className="disc-item">
                                            <a href={signal.url} target="_blank" rel="noopener noreferrer"
                                               style={{ fontWeight: 600, fontSize: 13, color: "var(--text-primary)", textDecoration: "none" }}>
                                                {signal.title}
                                            </a>
                                            <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 2 }}>
                                                <span style={{ fontSize: 11, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                                                    {signal.source}
                                                </span>
                                                {signal.published_date && (
                                                    <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
                                                        · {signal.published_date}
                                                    </span>
                                                )}
                                            </div>
                                            <div style={{ display: "flex", gap: 6, marginTop: 6, flexWrap: "wrap" }}>
                                                <span className={`tag-chip ${SIGNAL_TYPE_TAG_CLASS[signal.signal_type]}`}>
                                                    {SIGNAL_TYPE_LABELS[signal.signal_type]}
                                                </span>
                                                <span className={`tag-chip ${MATURITY_TAG_CLASS[signal.maturity_level]}`}>
                                                    {MATURITY_LABELS[signal.maturity_level]}
                                                </span>
                                            </div>
                                            <p style={{ fontSize: 12, color: "var(--text-secondary)", fontStyle: "italic", marginTop: 6, lineHeight: 1.5 }}>
                                                {signal.groq_insight}
                                            </p>
                                            <div className={`disc-item-score ${signal.relevance_score > 0.7 ? "high" : signal.relevance_score > 0.4 ? "mid" : "low"}`}>
                                                {Math.round(signal.relevance_score * 100)}% relevance
                                            </div>
                                        </div>
                                    ))}

                                    {renderCardActions("tech_signals", false)}
                                </div>
                            )}

                            {techSignalsState === "done" && (
                                <div className="disc-card-summary">
                                    {techSignalsFromCache && (
                                        <span className="disc-summary-chip" style={{ opacity: 0.7 }}>⚡ Cached</span>
                                    )}
                                    <span className="disc-summary-none">{techSignals.length} signal{techSignals.length !== 1 ? "s" : ""} retrieved</span>
                                </div>
                            )}
                        </div>
                    )}

                    {/* ── Startups (launched from modal) ── */}
                    {showStartups && (
                        <div className={`disc-card ${startupsState}`}>
                            <div className="disc-card-header">
                                <div className="disc-card-icon">{TOOL_META.startups.icon}</div>
                                <div className="disc-card-titles">
                                    <div className="disc-card-title">Startups</div>
                                    <div className="disc-card-source">StartupConnect AI</div>
                                </div>
                                {startupsState === "done" && startupsSource.items.filter(i => selectedIds.has(i.id)).length > 0 && (
                                    <span className="disc-card-badge">{startupsSource.items.filter(i => selectedIds.has(i.id)).length} selected</span>
                                )}
                                {(startupsState === "active" || startupsState === "done") && (
                                    <button
                                        className="disc-card-toggle"
                                        onClick={() => setCardState("startups", startupsState === "active" ? "done" : "active")}
                                        title={startupsState === "active" ? "Collapse" : "Expand"}
                                    >
                                        {startupsState === "active" ? "↑" : "↓"}
                                    </button>
                                )}
                            </div>

                            {startupsState === "active" && (
                                <div className="disc-card-results">
                                    {renderItemList(startupsSource.items, toggleItem)}
                                    {renderCardActions("startups", startupsSource.items.filter(i => selectedIds.has(i.id)).length > 0)}
                                </div>
                            )}

                            {startupsState === "done" && renderDoneChips(startupsSource.items, toggleItem)}
                        </div>
                    )}

                    {/* ── Tech Watch (launched from modal) ── */}
                    {showTechWatch && (
                        <div className={`disc-card ${techWatchState}`}>
                            <div className="disc-card-header">
                                <div className="disc-card-icon">{TOOL_META.tech_watch.icon}</div>
                                <div className="disc-card-titles">
                                    <div className="disc-card-title">Tech Watch</div>
                                    <div className="disc-card-source">AI Watch</div>
                                </div>
                                {techWatchState === "done" && techWatchSource.items.filter(i => selectedIds.has(i.id)).length > 0 && (
                                    <span className="disc-card-badge">{techWatchSource.items.filter(i => selectedIds.has(i.id)).length} selected</span>
                                )}
                                {(techWatchState === "active" || techWatchState === "done") && (
                                    <button
                                        className="disc-card-toggle"
                                        onClick={() => setCardState("tech_watch", techWatchState === "active" ? "done" : "active")}
                                        title={techWatchState === "active" ? "Collapse" : "Expand"}
                                    >
                                        {techWatchState === "active" ? "↑" : "↓"}
                                    </button>
                                )}
                            </div>

                            {techWatchState === "active" && (
                                <div className="disc-card-results">
                                    {renderItemList(techWatchSource.items, toggleItem)}
                                    {renderCardActions("tech_watch", techWatchSource.items.filter(i => selectedIds.has(i.id)).length > 0)}
                                </div>
                            )}

                            {techWatchState === "done" && renderDoneChips(techWatchSource.items, toggleItem)}
                        </div>
                    )}
                </div>

                {/* ════ RIGHT COLUMN ════ */}
                <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>

                    {/* Gap analysis panel — slides in when a catalog item is selected */}
                    <AnimatePresence>
                        {gapAnalysis.itemId && (
                            <motion.div
                                key="gap-panel"
                                initial={{ opacity: 0, x: 24 }}
                                animate={{ opacity: 1, x: 0 }}
                                exit={{ opacity: 0, x: 24 }}
                                transition={{ type: "spring", stiffness: 280, damping: 28 }}
                            >
                                <div className="disc-card active">
                                    <div className="disc-card-header">
                                        <div className="disc-card-icon">◐</div>
                                        <div className="disc-card-titles">
                                            <div className="disc-card-title">Gap Analysis</div>
                                            {gapAnalysis.data && (
                                                <div className="disc-card-source">{gapAnalysis.data.solution_name}</div>
                                            )}
                                        </div>
                                        {gapAnalysis.data && (
                                            <span className={`disc-item-score ${gapAnalysis.data.fit_score >= 8 ? "high" : gapAnalysis.data.fit_score >= 5 ? "mid" : "low"}`}>
                                                {gapAnalysis.data.fit_score}/10
                                            </span>
                                        )}
                                    </div>
                                    <DiscoveryGapAnalysisPanel
                                        needId={needId}
                                        gap={gapAnalysis}
                                        onGapAnalysisUpdate={(nextData) => {
                                            setGapAnalysesById((prev) => (
                                                gapAnalysis.itemId
                                                    ? { ...prev, [gapAnalysis.itemId]: nextData }
                                                    : prev
                                            ));
                                            setGapAnalysis((prev) => ({ ...prev, data: nextData, loading: false, error: false }));
                                        }}
                                    />
                                </div>
                            </motion.div>
                        )}
                    </AnimatePresence>

                    {/* Tech signals recap — appears when tech signals done with results */}
                    {techSignalsDone && techSignals.length > 0 && (
                        <div className="disc-recap">
                            <div className="disc-recap-label">
                                <span className="disc-recap-dot" />
                                Tech Signals{techSignalsFromCache ? " ⚡" : ""}
                            </div>
                            <div className="disc-recap-groups">
                                <div className="disc-recap-group">
                                    <span className="disc-recap-item">{techSignals.length} signal{techSignals.length !== 1 ? "s" : ""} retrieved</span>
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* ── Bottom bar ── */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "4px 0 8px" }}>
                <button
                    className="disc-action-ghost"
                    style={{ fontSize: 12, padding: "8px 18px" }}
                    onClick={() => setShowExploreModal(true)}
                >
                    ⊕ For More Exploration
                </button>
                <button
                    className={`disc-proceed-btn${proceedEnabled ? " ready" : ""}`}
                    disabled={!proceedEnabled}
                    onClick={onProceed}
                >
                    Proceed to Qualification →
                </button>
            </div>

            {/* ── For More Exploration Modal ── */}
            <AnimatePresence>
                {showExploreModal && (
                    <>
                        {/* Backdrop */}
                        <motion.div
                            style={{
                                position: "fixed",
                                inset: 0,
                                background: "rgba(10, 11, 16, 0.6)",
                                backdropFilter: "blur(4px)",
                                zIndex: 40,
                            }}
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            onClick={() => setShowExploreModal(false)}
                        />

                        {/* Modal panel — centered */}
                        <motion.div
                            style={{
                                position: "fixed",
                                top: "50%",
                                left: "50%",
                                x: "-50%",
                                y: "-50%",
                                zIndex: 50,
                                width: "calc(100% - 48px)",
                                maxWidth: 560,
                                background: "var(--wf-card)",
                                border: "1px solid var(--wf-border)",
                                borderRadius: 16,
                                padding: 24,
                                display: "flex",
                                flexDirection: "column",
                                gap: 20,
                            }}
                            initial={{ opacity: 0, scale: 0.96 }}
                            animate={{ opacity: 1, scale: 1 }}
                            exit={{ opacity: 0, scale: 0.96 }}
                            transition={{ type: "spring", stiffness: 300, damping: 30 }}
                        >
                            {/* Modal header */}
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                                <div>
                                    <div style={{ fontSize: 14, fontWeight: 500, color: "var(--text-primary)" }}>
                                        For More Exploration
                                    </div>
                                    <div style={{ fontSize: 11, color: "var(--wf-muted-fg)", marginTop: 3 }}>
                                        Optional tools to deepen your discovery
                                    </div>
                                </div>
                                <button
                                    onClick={() => setShowExploreModal(false)}
                                    style={{
                                        background: "none",
                                        border: "1px solid var(--wf-border)",
                                        borderRadius: 6,
                                        color: "var(--wf-muted-fg)",
                                        cursor: "pointer",
                                        fontSize: 16,
                                        width: 28,
                                        height: 28,
                                        display: "flex",
                                        alignItems: "center",
                                        justifyContent: "center",
                                        flexShrink: 0,
                                    }}
                                >
                                    ×
                                </button>
                            </div>

                            {/* Two tool cards side by side */}
                            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>

                                {/* Startups */}
                                <div className="disc-card">
                                    <div className="disc-card-header">
                                        <div className="disc-card-icon">{TOOL_META.startups.icon}</div>
                                        <div className="disc-card-titles">
                                            <div className="disc-card-title">Startups</div>
                                            <div className="disc-card-source">StartupConnect AI</div>
                                        </div>
                                    </div>
                                    <div className="disc-card-idle">
                                        <p className="disc-card-desc">{TOOL_META.startups.description}</p>
                                        <button
                                            className="disc-launch-btn"
                                            onClick={() => {
                                                setShowExploreModal(false);
                                                setCardState("startups", "active");
                                            }}
                                        >
                                            Open StartupConnect AI →
                                        </button>
                                    </div>
                                </div>

                                {/* Tech Watch */}
                                <div className="disc-card">
                                    <div className="disc-card-header">
                                        <div className="disc-card-icon">{TOOL_META.tech_watch.icon}</div>
                                        <div className="disc-card-titles">
                                            <div className="disc-card-title">Tech Watch</div>
                                            <div className="disc-card-source">AI Watch</div>
                                        </div>
                                    </div>
                                    <div className="disc-card-idle">
                                        <p className="disc-card-desc">{TOOL_META.tech_watch.description}</p>
                                        <button
                                            className="disc-launch-btn"
                                            onClick={() => {
                                                setShowExploreModal(false);
                                                setCardState("tech_watch", "active");
                                            }}
                                        >
                                            Open AI Watch →
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </motion.div>
                    </>
                )}
            </AnimatePresence>
        </div>
    );
}
