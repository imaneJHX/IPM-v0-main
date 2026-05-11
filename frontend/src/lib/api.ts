/**
 * Typed fetch wrapper for all IPM API endpoints.
 */

import type { AnalyzeRequest, AnalyzeResponse, BusinessNeed, CatalogProduct, CatalogSearchResponse, CreateNeedRequest, ExportReportRequest, GapAnalysisFeedbackRequest, GapAnalysisFeedbackResponse, GapAnalysisResponse, RecommendationsRequest, RecommendationsResponse, StageGateInteractionRequest, StageGateInteractionResponse, TechSignalsResponse, UpdateStatusRequest } from "./types";

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/+$/, "");

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const url = `${API_BASE}${path}`;
    const res = await fetch(url, {
        headers: { "Content-Type": "application/json", ...options.headers },
        ...options,
    });

    if (!res.ok) {
        const error = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(error.detail || `API error: ${res.status}`);
    }

    return res.json() as Promise<T>;
}

async function requestBlob(path: string, options: RequestInit = {}): Promise<Blob> {
    const url = `${API_BASE}${path}`;
    const res = await fetch(url, {
        headers: { "Content-Type": "application/json", ...options.headers },
        ...options,
    });

    if (!res.ok) {
        const error = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(error.detail || `API error: ${res.status}`);
    }

    return res.blob();
}

export function analyzePitch(body: AnalyzeRequest, signal?: AbortSignal): Promise<AnalyzeResponse> {
    return request<AnalyzeResponse>("/api/v1/needs/analyze", {
        method: "POST",
        body: JSON.stringify(body),
        signal,
    });
}

export function createNeed(data: CreateNeedRequest): Promise<BusinessNeed> {
    return request<BusinessNeed>("/api/v1/needs", {
        method: "POST",
        body: JSON.stringify(data),
    });
}

export function listNeeds(): Promise<BusinessNeed[]> {
    return request<BusinessNeed[]>("/api/v1/needs");
}

export function updateNeedStatus(id: string, data: UpdateStatusRequest): Promise<BusinessNeed> {
    return request<BusinessNeed>(`/api/v1/needs/${id}/status`, {
        method: "PATCH",
        body: JSON.stringify(data),
    });
}

export function getNeed(id: string): Promise<BusinessNeed> {
    return request<BusinessNeed>(`/api/v1/needs/${id}`);
}

export function searchCatalog(needId: string): Promise<CatalogSearchResponse> {
    return request<CatalogSearchResponse>(`/api/v1/needs/${needId}/catalog-search`, {
        method: "POST",
    });
}

export function getGapAnalysis(needId: string, selectedSolution: CatalogProduct): Promise<GapAnalysisResponse> {
    return request<GapAnalysisResponse>(`/api/v1/needs/${needId}/gap-analysis`, {
        method: "POST",
        body: JSON.stringify({ selected_solution: selectedSolution }),
    });
}

export function submitGapAnalysisFeedback(needId: string, body: GapAnalysisFeedbackRequest): Promise<GapAnalysisFeedbackResponse> {
    return request<GapAnalysisFeedbackResponse>(`/api/v1/needs/${needId}/gap-analysis/feedback`, {
        method: "POST",
        body: JSON.stringify(body),
    });
}

export function getTechSignals(needId: string): Promise<TechSignalsResponse> {
    return request<TechSignalsResponse>(`/api/v1/needs/${needId}/tech-signals`, {
        method: "POST",
    });
}

export function getRecommendations(needId: string, body: RecommendationsRequest): Promise<RecommendationsResponse> {
    return request<RecommendationsResponse>(`/api/v1/needs/${needId}/recommendations`, {
        method: "POST",
        body: JSON.stringify(body),
    });
}

export function interactStageGate(needId: string, body: StageGateInteractionRequest): Promise<StageGateInteractionResponse> {
    return request<StageGateInteractionResponse>(`/api/v1/needs/${needId}/stage-gates/interact`, {
        method: "POST",
        body: JSON.stringify(body),
    });
}

export function exportRecommendationsPdf(needId: string, body: ExportReportRequest): Promise<Blob> {
    return requestBlob(`/api/v1/needs/${needId}/export/pdf`, {
        method: "POST",
        body: JSON.stringify(body),
    });
}

export function exportRecommendationsDocx(needId: string, body: ExportReportRequest): Promise<Blob> {
    return requestBlob(`/api/v1/needs/${needId}/export/docx`, {
        method: "POST",
        body: JSON.stringify(body),
    });
}
