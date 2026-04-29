"""Business needs API endpoints."""

from __future__ import annotations

import logging
import re

import asyncio
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import llm_client
from app.core.config import settings
from app.core.database import get_db
from app.core.embedding_client import embed_text_async
from app.models.business_need import BusinessNeed
from app.schemas.business_need import (
    ABSAExtraction,
    AnalyzeRequest,
    AnalyzeResponse,
    BusinessNeedResponse,
    CatalogProduct,
    CatalogSearchResponse,
    ExportReportRequest,
    CreateNeedRequest,
    GapAnalysisFeedbackRequest,
    GapAnalysisFeedbackResponse,
    GapAnalysisRequest,
    GapAnalysisResponse,
    RecommendationsRequest,
    RecommendationsResponse,
    StageGateInteractionRequest,
    StageGateInteractionResponse,
    Tags,
    TechSignal,
    TechSignalsResponse,
    UpdateStatusRequest,
)
from tavily import TavilyClient
from urllib.parse import urlparse
import json
from datetime import datetime
from app.core.chroma import get_collection
from app.services import embedding_service, feedback_service, id_service, nlp_service, qualification_service, recommendation_service
from app.services.export_service import build_docx_report, build_pdf_report

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/needs", tags=["needs"])
_LAST_GAP_ANALYSIS_BY_NEED: dict[str, dict] = {}
_RECRUITMENT_TERMS = {
    "cv",
    "resume",
    "resumes",
    "candidate",
    "candidates",
    "recruitment",
    "recruiting",
    "hiring",
    "talent",
    "applicant",
    "screening",
    "shortlisting",
    "shortlist",
    "hr",
    "rh",
}

# ---------------------------------------------------------------------------
# Allowed status transitions
# ---------------------------------------------------------------------------
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"submitted", "abandoned"},
    "submitted": {"in_qualification", "abandoned"},
    "in_qualification": {"in_selection", "abandoned"},
    "in_selection": {"delivery", "abandoned"},
    "delivery": set(),          # terminal — Phase 2 may extend
    "abandoned": set(),         # terminal
}

ALLOWED_TRANSITIONS = {
    "draft": {"submitted", "abandoned"},
    "submitted": {"in_qualification", "abandoned"},
    "in_qualification": {"in_selection", "abandoned"},
    "in_selection": {"delivery", "abandoned"},
    "delivery": {"export_ready", "abandoned"},
    "export_ready": {"abandoned"},
    "abandoned": set(),
}


def _tokenize_catalog_text(value: str) -> set[str]:
    """Normalize free text into comparable lowercase tokens."""
    return set(re.findall(r"[a-z0-9]+", (value or "").lower()))


def _catalog_keyword_boost(query_text: str, product_name: str, product_text: str) -> float:
    """Add a small lexical boost when the query and product share specific hiring terms."""
    query_tokens = _tokenize_catalog_text(query_text)
    hiring_overlap = query_tokens & _RECRUITMENT_TERMS
    if not hiring_overlap:
        return 0.0

    product_tokens = _tokenize_catalog_text(f"{product_name} {product_text}")
    overlap_count = len(hiring_overlap & product_tokens)
    if overlap_count == 0:
        return 0.0

    boost = min(0.22, overlap_count * 0.05)

    if "cv" in query_tokens and "cv" in product_tokens:
        boost += 0.04
    if "resume" in query_tokens and "resume" in product_tokens:
        boost += 0.04
    if {"candidate", "screening"} <= query_tokens and {"candidate", "screening"} <= product_tokens:
        boost += 0.05

    return min(boost, 0.28)


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_pitch(request: AnalyzeRequest) -> AnalyzeResponse:
    """Analyze a pitch and return AI-generated tags and suggestions."""
    try:
        tags, suggestions = await nlp_service.analyze_pitch(
            request.pitch,
            request.horizon,
            objective=request.objective,
            domains=request.domains,
            impacts=request.impacts,
            tags=request.tags,
            phase=request.phase,
            status=request.status,
        )
        return AnalyzeResponse(tags=tags, suggestions=suggestions)
    except Exception as exc:
        logger.error("Failed to analyze pitch: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM analysis failed. Please try again.",
        ) from exc


@router.post("", response_model=BusinessNeedResponse, status_code=status.HTTP_201_CREATED)
async def create_need(
    request: CreateNeedRequest,
    db: AsyncSession = Depends(get_db),
) -> BusinessNeedResponse:
    """Create a new business need with AI enrichment and duplicate detection."""
    try:
        # 1. Generate embedding and reuse precomputed tags when provided by the client.
        if request.tags is not None:
            tags = nlp_service.normalize_tags(
                request.pitch,
                request.horizon,
                request.tags,
            )
            embedding = await embed_text_async(request.pitch, is_query=False)
        else:
            # Fallback: run LLM tagging + embedding concurrently.
            (tags, _suggestions), embedding = await asyncio.gather(
                nlp_service.analyze_pitch(request.pitch, request.horizon),
                embed_text_async(request.pitch, is_query=False),
            )

        if request.data_context is not None:
            tags = tags.model_copy(update={"data_context": request.data_context})

        # 2. Generate unique ID
        need_id = await id_service.generate_id(db)

        # 3. Upsert + duplicate search run concurrently. Both are blocking HTTP calls
        # to ChromaDB — offload to threads so they overlap instead of serializing.
        # `exclude_id=need_id` filters the just-upserted doc from results.
        _, duplicates = await asyncio.gather(
            asyncio.to_thread(
                embedding_service.upsert_embedding,
                need_id, request.pitch, "draft", embedding,
            ),
            asyncio.to_thread(
                embedding_service.search_duplicates,
                request.pitch, need_id, embedding,
            ),
        )

        # 5. Persist to PostgreSQL
        need = BusinessNeed(
            id=need_id,
            pitch=request.pitch,
            horizon=request.horizon,
            tags=tags.model_dump(),
            status="draft",
            duplicate_matches=[d.model_dump() for d in duplicates],
        )
        db.add(need)
        await db.flush()
        await db.refresh(need)

        return BusinessNeedResponse(
            id=need.id,
            pitch=need.pitch,
            horizon=need.horizon,
            tags=Tags(**need.tags),
            status=need.status,
            rework_note=need.rework_note,
            duplicate_matches=duplicates,
            created_at=need.created_at,
            updated_at=need.updated_at,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to create business need: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create business need: {str(exc)}",
        ) from exc


@router.get("", response_model=list[BusinessNeedResponse])
async def list_needs(
    db: AsyncSession = Depends(get_db),
) -> list[BusinessNeedResponse]:
    """Return all business needs ordered by creation date descending."""
    try:
        result = await db.execute(
            select(BusinessNeed).order_by(BusinessNeed.created_at.desc())
        )
        needs = result.scalars().all()

        return [
            BusinessNeedResponse(
                id=n.id,
                pitch=n.pitch,
                horizon=n.horizon,
                tags=Tags(**n.tags) if n.tags else Tags(
                    objectif="cost_reduction",
                    domaine=[],
                    impact=[],
                    origine="probleme_operationnel",
                ),
                status=n.status,
                rework_note=n.rework_note,
                duplicate_matches=n.duplicate_matches or [],
                created_at=n.created_at,
                updated_at=n.updated_at,
            )
            for n in needs
        ]
    except Exception as exc:
        logger.error("Failed to list business needs: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve business needs.",
        ) from exc


@router.get("/{need_id}", response_model=BusinessNeedResponse)
async def get_need(
    need_id: str,
    db: AsyncSession = Depends(get_db),
) -> BusinessNeedResponse:
    """Return a specific business need by ID."""
    try:
        result = await db.execute(
            select(BusinessNeed).where(BusinessNeed.id == need_id)
        )
        need = result.scalar_one_or_none()

        if need is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Business need '{need_id}' not found.",
            )

        return BusinessNeedResponse(
            id=need.id,
            pitch=need.pitch,
            horizon=need.horizon,
            tags=Tags(**need.tags) if need.tags else Tags(
                objectif="cost_reduction",
                domaine=[],
                impact=[],
                origine="probleme_operationnel",
            ),
            status=need.status,
            rework_note=need.rework_note,
            duplicate_matches=need.duplicate_matches or [],
            created_at=need.created_at,
            updated_at=need.updated_at,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to retrieve business need %s: %s", need_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve business need.",
        ) from exc


@router.patch("/{need_id}/status", response_model=BusinessNeedResponse)
async def update_status(
    need_id: str,
    request: UpdateStatusRequest,
    db: AsyncSession = Depends(get_db),
) -> BusinessNeedResponse:
    """Update the status of a business need, enforcing the transition rules."""
    try:
        result = await db.execute(
            select(BusinessNeed).where(BusinessNeed.id == need_id)
        )
        need = result.scalar_one_or_none()

        if need is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Business need '{need_id}' not found.",
            )

        is_same_step_rework = request.status == need.status

        if is_same_step_rework:
            if not request.note:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"A note is required to request rework while staying in "
                        f"the current step '{need.status}'."
                    ),
                )
        else:
            allowed = ALLOWED_TRANSITIONS.get(need.status, set())
            if request.status not in allowed:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Cannot transition from '{need.status}' to '{request.status}'. "
                           f"Allowed transitions: {sorted(allowed) if allowed else 'none'}.",
                )
            need.status = request.status

        if request.note:
            need.rework_note = request.note
        else:
            need.rework_note = None

        await db.flush()
        await db.refresh(need)

        # Update ChromaDB metadata
        try:
            embedding_service.upsert_embedding(need.id, need.pitch, need.status)
        except Exception as chroma_exc:
            logger.warning("Failed to update ChromaDB for %s: %s", need.id, chroma_exc)

        return BusinessNeedResponse(
            id=need.id,
            pitch=need.pitch,
            horizon=need.horizon,
            tags=Tags(**need.tags) if need.tags else Tags(
                objectif="cost_reduction",
                domaine=[],
                impact=[],
                origine="probleme_operationnel",
            ),
            status=need.status,
            rework_note=need.rework_note,
            duplicate_matches=need.duplicate_matches or [],
            created_at=need.created_at,
            updated_at=need.updated_at,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to update status for %s: %s", need_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update business need status.",
        ) from exc


@router.post("/{need_id}/catalog-search", response_model=CatalogSearchResponse)
async def catalog_search(
    need_id: str,
    db: AsyncSession = Depends(get_db),
) -> CatalogSearchResponse:
    """Return the top 5 DXC catalog products most similar to the business need."""
    try:
        result = await db.execute(
            select(BusinessNeed).where(BusinessNeed.id == need_id)
        )
        need = result.scalar_one_or_none()

        if need is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Business need '{need_id}' not found.",
            )

        # Build query text from pitch + AI-derived fields
        tags: dict = need.tags or {}

        OBJECTIF_LABELS = {
            "cost_reduction": "cost reduction efficiency savings",
            "cx_improvement": "customer experience improvement satisfaction",
            "risk_mitigation": "risk management compliance security",
            "market_opportunity": "market growth revenue expansion",
            "productivity": "productivity automation efficiency",
            "innovation": "innovation digital transformation modernization",
        }
        objectif_str = OBJECTIF_LABELS.get(tags.get("objectif", ""), "")

        domains_list: list = tags.get("domaine") or []
        domains_str = " ".join(domains_list)

        impact_parts = tags.get("impact") or []
        impact_str = (
            " ".join(impact_parts)
            if isinstance(impact_parts, list)
            else str(impact_parts)
        )

        query_text = " ".join(
            filter(None, [need.pitch, objectif_str, domains_str, impact_str])
        )
        query_text = query_text[:600].strip()

        # Embed — is_query=True applies the BGE retrieval prefix
        embedding = await embed_text_async(query_text, is_query=True)

        # Query dxc_catalog
        collection = get_collection("dxc_catalog")
        raw = collection.query(
            query_embeddings=[embedding],
            n_results=10,
            include=["metadatas", "documents", "distances"],
        )

        ids = raw["ids"][0]
        metadatas = raw["metadatas"][0]
        documents = raw["documents"][0]
        distances = raw["distances"][0]

        def _meta_val(meta: dict, key: str) -> str | None:
            """Return None for empty-string sentinel values stored in ChromaDB."""
            v = meta.get(key)
            return None if v == "" else v

        products: list[CatalogProduct] = []
        for pid, meta, doc, dist in zip(ids, metadatas, documents, distances):
            semantic_score = max(0.0, min(1.0, 1.0 - dist))
            score = round(
                max(
                    0.0,
                    min(
                        1.0,
                        semantic_score + _catalog_keyword_boost(query_text, meta.get("name", ""), doc),
                    ),
                ),
                2,
            )
            features_raw = meta.get("features")
            features: list[str] = (
                [f.strip() for f in features_raw.split(",") if f.strip()]
                if features_raw
                else []
            )
            products.append(CatalogProduct(
                id=pid,
                name=meta.get("name", ""),
                description=doc,
                ipm_stage=_meta_val(meta, "ipm_stage"),
                internal_external=_meta_val(meta, "internal_external"),
                industry_focus=_meta_val(meta, "industry_focus"),
                ai_type=_meta_val(meta, "ai_type"),
                ai_criticality=_meta_val(meta, "ai_criticality"),
                maturity_level=_meta_val(meta, "maturity_level"),
                value_layer=_meta_val(meta, "value_layer"),
                monetization_potential=_meta_val(meta, "monetization_potential"),
                business_impact=_meta_val(meta, "business_impact"),
                lead=_meta_val(meta, "lead"),
                features=features,
                relevance_score=score,
            ))

        products.sort(key=lambda p: p.relevance_score, reverse=True)

        return CatalogSearchResponse(results=products, total=len(products))

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to run catalog search for %s: %s", need_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Catalog search failed. Please try again.",
        ) from exc


@router.post("/{need_id}/gap-analysis", response_model=GapAnalysisResponse)
async def gap_analysis(
    need_id: str,
    body: GapAnalysisRequest,
    db: AsyncSession = Depends(get_db),
) -> GapAnalysisResponse:
    """Run a structured gap analysis between a business need and a selected DXC solution."""
    try:
        result = await db.execute(
            select(BusinessNeed).where(BusinessNeed.id == need_id)
        )
        need = result.scalar_one_or_none()

        if need is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Business need '{need_id}' not found.",
            )

        # Extract solution fields from request body
        sol = body.selected_solution
        name: str = sol.get("name", "Unknown")
        description: str = sol.get("description", "") or ""
        business_impact: str = sol.get("business_impact", "") or ""
        maturity_level: str = sol.get("maturity_level", "") or ""

        # Rebuild constraints defensively for older records.
        need_tags = nlp_service.normalize_tags(
            need.pitch,
            need.horizon,
            need.tags or {},
        )
        if need_tags.data_context:
            sol = {**sol, "data_context": need_tags.data_context.model_dump()}
        objectif: str = need_tags.objectif
        impact_list = need_tags.impact or []
        impact: str = ", ".join(impact_list) if impact_list else "Not specified"
        domains_list = need_tags.domaine or []
        domains: str = ", ".join(domains_list) if domains_list else "Not specified"
        constraints_json = json.dumps(
            need_tags.gap_analysis_constraints.model_dump()
            if need_tags.gap_analysis_constraints
            else {},
            ensure_ascii=False,
        )
        hard_constraint_text = (
            "HARD CONSTRAINTS (from NLP Tagging - do not override):\n"
            f"- Solution must match domain: {domains}\n"
            f"- Solution must address objective: {objectif}\n"
            f"- Solution must impact: {impact}\n"
            "- Any feature_missing must stay consistent with these sourcing domains and objectives only\n"
            "- fit_score must reflect these constraints strictly\n"
        )
        typed_constraints = (
            need_tags.sourcing_classification.constraintsForGapAnalysis
            if need_tags.sourcing_classification
            else None
        )
        ambiguity_flags = list(typed_constraints.ambiguityFlags) if typed_constraints else []
        compressed_context = qualification_service.compress_solution_context(
            need_pitch=need.pitch,
            objectif=objectif,
            domains_list=domains_list,
            impact_list=impact_list,
            solution=sol,
            nlp_constraints=typed_constraints,
        )
        compression_json = json.dumps(
            compressed_context.audit.model_dump(),
            ensure_ascii=False,
        )

        variables: dict[str, str] = {
            "pitch": need.pitch,
            "objectif": objectif,
            "impact": impact,
            "domains": domains,
            "horizon": need.horizon,
            "hard_constraints_text": hard_constraint_text,
            "classification_constraints_json": constraints_json,
            "context_compression_json": compression_json,
            "solution_name": name,
            "solution_description": compressed_context.description or description or "Not specified",
            "solution_features": ", ".join(compressed_context.features) if compressed_context.features else "Not listed",
            "solution_business_impact": compressed_context.business_impact or business_impact or "Not specified",
            "solution_maturity": maturity_level or "Not specified",
        }

        # Langfuse trace — create before LLM call, update after; silent if disabled
        _lf_trace = None
        try:
            from langfuse import Langfuse
            _lf = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
            )
            _lf_trace = _lf.trace(
                name="gap-analysis",
                input={
                    "need_id": need_id,
                    "need_pitch": need.pitch,
                    "solution_name": name,
                    "solution_maturity": maturity_level,
                },
                metadata={
                    "endpoint": "gap-analysis",
                    "need_id": need_id,
                    "solution_id": sol.get("id", "unknown"),
                    "solution_name": name,
                },
            )
        except Exception:
            pass

        # LLM call — replicates nlp_service.py pattern
        parsed: dict = {}
        try:
            llm_response = await llm_client.complete(
                prompt_name="gap-analysis",
                variables=variables,
                response_format="json",
            )
            parsed = llm_client.parse_json_response(llm_response)
        except Exception as llm_exc:
            logger.warning("Gap analysis LLM unavailable for %s, using fallback scoring: %s", need_id, llm_exc)
            parsed = {}
        response = qualification_service.build_gap_analysis_response(
            need_pitch=need.pitch,
            horizon=need.horizon,
            objectif=objectif,
            domains_list=domains_list,
            impact_list=impact_list,
            solution=sol,
            parsed=parsed if isinstance(parsed, dict) else {},
            compressed_context=compressed_context,
            nlp_constraints=typed_constraints,
            ambiguity_flags=ambiguity_flags,
        )
        _LAST_GAP_ANALYSIS_BY_NEED[need_id] = response.model_dump()

        # Update Langfuse trace with parsed output
        try:
            if _lf_trace:
                _lf_trace.update(output={
                    "fit_score": response.fit_score,
                    "ivi_score": response.ivi_score,
                    "features_matching_count": len(response.features_matching),
                    "features_missing_count": len(response.features_missing),
                    "risks_count": len(response.risks),
                    "resources_needed_count": len(response.resources_needed),
                })
        except Exception:
            pass

        return response

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Gap analysis failed for %s: %s", need_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gap analysis failed. Please try again.",
        ) from exc


@router.post("/{need_id}/gap-analysis/feedback", response_model=GapAnalysisFeedbackResponse)
async def gap_analysis_feedback(
    need_id: str,
    body: GapAnalysisFeedbackRequest,
    db: AsyncSession = Depends(get_db),
) -> GapAnalysisFeedbackResponse:
    """Apply aspect-based feedback to the latest gap-analysis result for this need."""
    result = await db.execute(
        select(BusinessNeed).where(BusinessNeed.id == need_id)
    )
    need = result.scalar_one_or_none()
    if need is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Business need '{need_id}' not found.",
        )

    snapshot = _LAST_GAP_ANALYSIS_BY_NEED.get(need_id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No gap analysis session is available yet for this need. Run gap analysis first.",
        )

    aspect_feedback = feedback_service.extract_absa(body.comment)
    corrected_snapshot, diffs = feedback_service.apply_ivi_feedback(snapshot, aspect_feedback)
    _LAST_GAP_ANALYSIS_BY_NEED[need_id] = corrected_snapshot

    return GapAnalysisFeedbackResponse(
        comment=body.comment,
        aspect_feedback=aspect_feedback,
        diffs=diffs,
        gap_analysis=GapAnalysisResponse.model_validate(corrected_snapshot),
    )


@router.post("/{need_id}/recommendations", response_model=RecommendationsResponse)
async def generate_recommendations(
    need_id: str,
    body: RecommendationsRequest,
    db: AsyncSession = Depends(get_db),
) -> RecommendationsResponse:
    """Generate delivery recommendations per selected solution."""
    try:
        result = await db.execute(
            select(BusinessNeed).where(BusinessNeed.id == need_id)
        )
        need = result.scalar_one_or_none()

        if need is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Business need '{need_id}' not found.",
            )

        if not body.selected_solutions:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="At least one selected solution is required.",
            )

        need_tags: dict = need.tags or {}
        objectif: str = need_tags.get("objectif", "") or "Not specified"
        impact_list = [str(item).strip() for item in (need_tags.get("impact", []) or []) if str(item).strip()]
        domains_list = [str(item).strip() for item in (need_tags.get("domaine", []) or []) if str(item).strip()]

        recommendations = await asyncio.gather(
            *[
                recommendation_service.generate_solution_recommendations(
                    need_pitch=need.pitch,
                    horizon=need.horizon or "not_specified",
                    objectif=objectif,
                    impact_list=impact_list,
                    domains_list=domains_list,
                    selected_solution=sol,
                )
                for sol in body.selected_solutions
            ]
        )

        return RecommendationsResponse(recommendations=list(recommendations))

        need_tags: dict = need.tags or {}
        objectif: str = need_tags.get("objectif", "") or "Not specified"
        impact_list: list = need_tags.get("impact", []) or []
        impact: str = ", ".join(impact_list) if impact_list else "Not specified"
        domains_list: list = need_tags.get("domaine", []) or []
        domains: str = ", ".join(domains_list) if domains_list else "Not specified"

        def _as_list(value: object) -> list[str]:
            if isinstance(value, list):
                return [str(v).strip() for v in value if str(v).strip()]
            return []

        def _safe_int(value: object, default: int) -> int:
            try:
                return int(value)
            except (TypeError, ValueError):
                return default

        def _ensure_feature_mapping(
            features_missing: list[str],
            technical: list[str],
        ) -> tuple[list[str], list[dict[str, str]]]:
            mapped = list(technical)
            audit: list[dict[str, str]] = []
            for feature in features_missing:
                if any(feature.lower() in item.lower() for item in mapped):
                    audit.append({"feature_missing": feature, "recommendation": "existing mapping found"})
                    continue
                recommendation = f"Address missing capability '{feature}' through an explicit design and delivery workstream."
                mapped.append(recommendation)
                audit.append({"feature_missing": feature, "recommendation": recommendation})
            return mapped[:6], audit

        def _ensure_kpis(impact_list: list[str], kpis: list[RecommendationKPI]) -> list[RecommendationKPI]:
            normalized = list(kpis)
            if "Cost" in impact_list and not any(("€" in item.target) or ("%" in item.target) for item in normalized):
                normalized.append(
                    RecommendationKPI(
                        name="Cost efficiency",
                        target="Reduce run cost by 15% or save €100k annually",
                        measurement_criteria="Compare annualized baseline operating cost against post-deployment run cost",
                    )
                )
            if "CustomerExperience" in impact_list and not any(
                any(token in item.target.lower() for token in ("hour", "day", "week", "minute"))
                for item in normalized
            ):
                normalized.append(
                    RecommendationKPI(
                        name="Response-time improvement",
                        target="Reduce response time by 30% within 90 days",
                        measurement_criteria="Track average end-user response time weekly from baseline to day 90",
                    )
                )
            return normalized[:5]

        async def _recommend_for_solution(sol: dict) -> SolutionRecommendations:
            solution_id = str(sol.get("id", "unknown"))
            solution_name = str(sol.get("name", "Unknown solution"))
            description = str(sol.get("description", "") or "")
            features = _as_list(sol.get("features"))
            business_impact = str(sol.get("business_impact", "") or "")
            maturity_level = str(sol.get("maturity_level", "") or "")

            gap = sol.get("gap_analysis") if isinstance(sol.get("gap_analysis"), dict) else {}
            features_matching = _as_list(gap.get("features_matching")) if isinstance(gap, dict) else []
            features_missing = _as_list(gap.get("features_missing")) if isinstance(gap, dict) else []
            risks = _as_list(gap.get("risks")) if isinstance(gap, dict) else []
            resources_needed = _as_list(gap.get("resources_needed")) if isinstance(gap, dict) else []
            fit_score = _safe_int(gap.get("fit_score") if isinstance(gap, dict) else None, 5)
            prerequisite_mode = bool(gap.get("prerequisite_mode")) if isinstance(gap, dict) else False

            evaluation_scores = sol.get("evaluation_scores")
            if not isinstance(evaluation_scores, dict) and isinstance(gap, dict):
                evaluation_scores = gap.get("evaluation_scores")
            if not isinstance(evaluation_scores, dict):
                evaluation_scores = {}

            feasibility = gap.get("feasibility") if isinstance(gap.get("feasibility"), dict) else {}
            ivi_scoring = gap.get("ivi_scoring") if isinstance(gap.get("ivi_scoring"), dict) else {}

            def _dimension_score(key: str, default: int) -> int:
                dimension = ivi_scoring.get(key)
                if isinstance(dimension, dict):
                    return max(1, min(5, _safe_int(dimension.get("score"), default)))
                return default

            derived_fit = _dimension_score("impact_business", max(1, min(5, round(fit_score / 2))))
            derived_feasibility = max(1, min(5, _safe_int(feasibility.get("score"), round((
                _dimension_score("maturite", 3)
                + _dimension_score("expertise", 3)
                + _dimension_score("duree", 3)
                + _dimension_score("donnees", 3)
            ) / 4))))
            derived_cost = _dimension_score("duree", 3)
            derived_innovation = max(
                _dimension_score("impact_business", 3),
                max(1, min(5, 6 - _dimension_score("maturite", 3))),
            )

            ivi_summary_parts: list[str] = []
            for key in ("maturite", "expertise", "duree", "donnees", "impact_business"):
                dimension = ivi_scoring.get(key)
                if not isinstance(dimension, dict):
                    continue
                label = key.replace("_", " ")
                score = max(1, min(5, _safe_int(dimension.get("score"), 3)))
                justification = str(dimension.get("justification", "") or "").strip()
                if justification:
                    ivi_summary_parts.append(f"{label}: {score}/5 - {justification}")
                else:
                    ivi_summary_parts.append(f"{label}: {score}/5")

            variables: dict[str, str] = {
                "pitch": need.pitch,
                "objectif": objectif,
                "impact": impact,
                "domains": domains,
                "solution_name": solution_name,
                "solution_description": description or "Not specified",
                "solution_features": ", ".join(features) if features else "Not listed",
                "solution_business_impact": business_impact or "Not specified",
                "solution_maturity": maturity_level or "Not specified",
                "features_matching": ", ".join(features_matching) if features_matching else "Not specified",
                "features_missing": ", ".join(features_missing) if features_missing else "Not specified",
                "risks": ", ".join(risks) if risks else "Not specified",
                "resources_needed": ", ".join(resources_needed) if resources_needed else "Not specified",
                "fit_score": str(max(1, min(10, fit_score))),
                "eval_fit": str(max(1, min(5, _safe_int(evaluation_scores.get("fit"), derived_fit)))),
                "eval_feasibility": str(max(1, min(5, _safe_int(evaluation_scores.get("feasibility"), derived_feasibility)))),
                "eval_cost": str(max(1, min(5, _safe_int(evaluation_scores.get("cost"), derived_cost)))),
                "eval_innovation": str(max(1, min(5, _safe_int(evaluation_scores.get("innovation"), derived_innovation)))),
                "ivi_score": str(max(0, min(100, round(float(gap.get("ivi_score", 0)) if isinstance(gap, dict) else 0)))),
                "ivi_summary": " | ".join(ivi_summary_parts) if ivi_summary_parts else "Not specified",
            }

            technical: list[str] = []
            organizational: list[str] = []
            kpis: list[RecommendationKPI] = []

            try:
                llm_response = await llm_client.complete(
                    prompt_name="solution-recommendations",
                    variables=variables,
                    response_format="json",
                )
                parsed = llm_client.parse_json_response(llm_response)

                if isinstance(parsed, dict):
                    tech_raw = parsed.get("technical_recommendations")
                    org_raw = parsed.get("organizational_recommendations")
                    kpi_raw = parsed.get("kpis")

                    if isinstance(tech_raw, list):
                        technical = [str(item).strip() for item in tech_raw if str(item).strip()]
                    if isinstance(org_raw, list):
                        organizational = [str(item).strip() for item in org_raw if str(item).strip()]
                    if isinstance(kpi_raw, list):
                        for item in kpi_raw:
                            if not isinstance(item, dict):
                                continue
                            name = str(item.get("name", "")).strip()
                            target = str(item.get("target", "")).strip()
                            criteria = str(item.get("measurement_criteria", "")).strip()
                            if name and target and criteria:
                                kpis.append(
                                    RecommendationKPI(
                                        name=name,
                                        target=target,
                                        measurement_criteria=criteria,
                                    )
                                )
            except Exception as rec_exc:
                logger.warning("Recommendations generation failed for %s/%s: %s", need_id, solution_id, rec_exc)

            if not technical:
                technical = [
                    "Define a target architecture and integration blueprint across core systems.",
                    "Prioritize API contracts and data mappings for critical business flows.",
                    "Plan dependencies and phased rollout milestones to reduce delivery risk.",
                    "Set data quality controls and monitoring for production readiness.",
                    "Track top technical risks with mitigation owners and trigger thresholds.",
                ]
            if prerequisite_mode or fit_score <= 4:
                technical.insert(0, "PREREQUIS mode: close prerequisite gaps before full implementation scope is committed.")

            technical, mapping_audit = _ensure_feature_mapping(features_missing, technical)

            if not organizational:
                organizational = [
                    "Assign a product owner, solution architect, and implementation lead.",
                    "Define required profiles, expected workload, and capacity by phase.",
                    "Set governance cadence for steering decisions and escalation paths.",
                    "Validate compliance, security, and data privacy checkpoints upfront.",
                    "Publish change-management and adoption responsibilities by team.",
                ]
            organizational = [
                item.replace("solution architect", "business analyst")
                for item in organizational
            ][:6]

            if not kpis:
                kpis = [
                    RecommendationKPI(
                        name="Time-to-value",
                        target="First measurable business outcome within 12 weeks",
                        measurement_criteria="Track weeks from project kickoff to first KPI uplift",
                    ),
                    RecommendationKPI(
                        name="Adoption rate",
                        target=">= 75% active usage among target users by quarter 1",
                        measurement_criteria="Monthly active users divided by targeted users",
                    ),
                    RecommendationKPI(
                        name="Operational impact",
                        target=">= 20% improvement on the primary operational metric",
                        measurement_criteria="Baseline vs post-go-live metric delta",
                    ),
                ]
            kpis = _ensure_kpis(impact_list, kpis)

            return SolutionRecommendations(
                solution_id=solution_id,
                solution_name=solution_name,
                technical_recommendations=technical[:6],
                organizational_recommendations=organizational[:6],
                kpis=kpis[:5],
                mapping_audit=mapping_audit,
            )

        recommendations = await asyncio.gather(
            *[_recommend_for_solution(sol) for sol in body.selected_solutions]
        )

        return RecommendationsResponse(recommendations=list(recommendations))

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Recommendations generation failed for %s: %s", need_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate recommendations. Please try again.",
        ) from exc


@router.post("/{need_id}/stage-gates/interact", response_model=StageGateInteractionResponse)
async def interact_stage_gate(
    need_id: str,
    body: StageGateInteractionRequest,
    db: AsyncSession = Depends(get_db),
) -> StageGateInteractionResponse:
    """Run a conversational stage-gate turn with lightweight in-memory session memory."""
    result = await db.execute(select(BusinessNeed).where(BusinessNeed.id == need_id))
    need = result.scalar_one_or_none()
    if need is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Business need '{need_id}' not found.",
        )

    snapshot = body.snapshot or {}
    if body.gate == "SG-1" and not snapshot:
        snapshot = {"tags": (need.tags or {}), "pitch": need.pitch, "horizon": need.horizon}

    response = feedback_service.interact_stage_gate(
        need_id=need_id,
        gate=body.gate,
        action=body.action,
        comment=body.comment,
        snapshot=snapshot,
    )
    return response


OBJECTIF_LABELS_SIGNALS = {
    "cost_reduction": "cost reduction efficiency savings",
    "cx_improvement": "customer experience improvement satisfaction",
    "risk_mitigation": "risk management compliance security",
    "market_opportunity": "market growth revenue expansion",
    "productivity": "productivity automation efficiency",
    "innovation": "innovation digital transformation modernization",
}


@router.post("/{need_id}/tech-signals", response_model=TechSignalsResponse)
async def get_tech_signals(
    need_id: str,
    db: AsyncSession = Depends(get_db),
) -> TechSignalsResponse:
    """Return AI-enriched tech signals (patents, research, news) for a business need.

    Results are cached permanently in ChromaDB — each unique need costs 1 Tavily credit
    on first call only. Subsequent calls return from_cache=True at 0 cost.
    """
    # ── STEP 1: API KEY GUARD ─────────────────────────────────────────────────
    if not settings.tavily_api_key:
        logger.warning("TAVILY_API_KEY not set — Tech Signals disabled")
        return TechSignalsResponse(signals=[], query_used="", from_cache=False)

    # ── STEP 2: FETCH NEED FROM DB ────────────────────────────────────────────
    result = await db.execute(select(BusinessNeed).where(BusinessNeed.id == need_id))
    need = result.scalar_one_or_none()
    if need is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Business need '{need_id}' not found.",
        )

    tags: dict = need.tags or {}

    # ── STEP 3: CHECK CHROMADB CACHE ──────────────────────────────────────────
    cache_id = f"need:{need_id}:tech-signals"
    try:
        collection = get_collection("tech_signals")
        cached = collection.get(ids=[cache_id])
        if cached and cached.get("ids") and len(cached["ids"]) > 0:
            metadata = cached["metadatas"][0]
            cached_signals = json.loads(metadata["signals_json"])
            return TechSignalsResponse(
                signals=[TechSignal(**s) for s in cached_signals],
                query_used=metadata["query"],
                from_cache=True,
            )
    except Exception as e:
        logger.warning(f"ChromaDB cache read failed: {e}")
        # continue — cache miss, proceed to Tavily

    # ── STEP 4: BUILD 3 TARGETED TAVILY SUB-QUERIES ───────────────────────────
    objectif_label = OBJECTIF_LABELS_SIGNALS.get(tags.get("objectif", ""), "")
    domains_str = " ".join((tags.get("domaine") or [])[:2])

    base_keywords = " ".join(filter(None, [
        need.pitch[:80] if need.pitch else "",
        objectif_label,
        domains_str,
    ])).strip()[:200]

    sub_queries = [
        f"{base_keywords} software platform vendor",
        f"{base_keywords} enterprise deployment case study",
        f"{base_keywords} B2B solution provider",
    ]
    query = base_keywords  # used for cache key + ChromaDB document

    # ── STEP 5: CALL TAVILY (3 sub-queries in parallel) ───────────────────────
    try:
        client = TavilyClient(api_key=settings.tavily_api_key)

        # Aggressive exclude list — block job boards, socials, generic news,
        # and well-known content farms that rarely surface real vendors.
        excluded_domains = [
            # Blogs / content farms
            "medium.com", "forbes.com", "hubspot.com", "blog.hubspot.com",
            "intercom.com", "helpscout.com", "zendesk.com", "salesforce.com/blog",
            "techcrunch.com", "businessinsider.com", "entrepreneur.com",
            "inc.com", "fastcompany.com", "wired.com", "cnbc.com",
            # Social / profiles
            "linkedin.com", "facebook.com", "twitter.com", "x.com",
            "instagram.com", "youtube.com", "reddit.com", "quora.com",
            # Job boards
            "jobtoday.com", "indeed.com", "glassdoor.com", "monster.com",
            "ziprecruiter.com", "simplyhired.com", "wellfound.com",
            # Generic reference
            "wikipedia.org", "scribd.com", "slideshare.net", "issuu.com",
        ]

        async def _search(q: str) -> list[dict]:
            result = await asyncio.to_thread(
                client.search,
                query=q,
                search_depth="basic",
                max_results=3,
                exclude_domains=excluded_domains,
            )
            return result.get("results", [])

        batches = await asyncio.gather(*[_search(q) for q in sub_queries])

        # Flatten + deduplicate by URL
        seen_urls: set[str] = set()
        raw_results: list[dict] = []
        for batch in batches:
            for r in batch:
                url = r.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    raw_results.append(r)

    except Exception as e:
        logger.warning(f"Tavily search failed: {e}")
        return TechSignalsResponse(signals=[], query_used=query, from_cache=False)

    if not raw_results:
        return TechSignalsResponse(signals=[], query_used=query, from_cache=False)

    # ── STEP 6: AI ENRICHMENT (single batch call) ───────────────────────────
    numbered_results = "\n\n".join([
        f"[{i+1}] Title: {r.get('title', '')}\n"
        f"    Snippet: {r.get('content', '')[:300]}\n"
        f"    URL: {r.get('url', '')}"
        for i, r in enumerate(raw_results)
    ])

    enrichment_map: dict = {}
    try:
        # Use the unified llm_client.complete which is more efficient
        response = await llm_client.complete(
            prompt_name="tech_signals_enrichment",
            variables={
                "pitch": need.pitch[:200],
                "numbered_results": numbered_results
            },
            response_format="json"
        )
        parsed = llm_client.parse_json_response(response)
        
        # In JSON mode, the LLM usually wraps the results in a dictionary like {"results": [...]}
        # but we iterate it safely here.
        enrichment_list = []
        if isinstance(parsed, list):
            enrichment_list = parsed
        elif isinstance(parsed, dict):
            # Try to find the array in common keys like "results", "signals", etc.
            # or just find any list in the values.
            enrichment_list = parsed.get("results") or parsed.get("signals") or parsed.get("enrichment")
            if not isinstance(enrichment_list, list):
                # Fallback: check if any value is a list
                for val in parsed.values():
                    if isinstance(val, list):
                        enrichment_list = val
                        break
        
        if isinstance(enrichment_list, list):
            enrichment_map = {
                item["index"]: item 
                for item in enrichment_list 
                if isinstance(item, dict) and "index" in item
            }
        else:
            logger.warning(f"Unexpected enrichment response structure for {need_id}: {type(parsed)}")
            enrichment_map = {}

    except Exception as e:
        logger.warning(f"Tech signals enrichment failed: {e}")
        enrichment_map = {}

    # ── STEP 7: BUILD TechSignal OBJECTS ──────────────────────────────────────
    # Only keep results the LLM explicitly classified as real implementations.
    # Anything not present in enrichment_map is considered junk (article, blog,
    # job posting, unrelated page) and is dropped entirely. This is the actual
    # content filter — the exclude_domains list is only a first-pass heuristic.
    if not enrichment_map:
        logger.warning(
            "Tech signals enrichment returned no real implementations for %s "
            "(raw=%d, enriched=0). Returning empty list.",
            need_id, len(raw_results),
        )

    signals: list[TechSignal] = []
    for i, r in enumerate(raw_results):
        enrichment = enrichment_map.get(i + 1)
        if not enrichment:
            continue  # LLM dropped this one — it's an article, not a real solution
        url = r.get("url", "")
        parsed_url = urlparse(url)
        source = parsed_url.netloc.replace("www.", "")
        signals.append(TechSignal(
            id=url,
            title=r.get("title", ""),
            url=url,
            source=source,
            published_date=r.get("published_date"),
            signal_type=enrichment.get("signal_type", "saas_product"),
            maturity_level=enrichment.get("maturity_level", "emerging"),
            relevance_score=round(float(r.get("score", 0.5)), 3),
            groq_insight=enrichment.get("insight", ""),
            raw_snippet=r.get("content", "")[:400],
        ))

    # ── STEP 8: STORE IN CHROMADB ─────────────────────────────────────────────
    try:
        collection = get_collection("tech_signals")
        collection.upsert(
            ids=[cache_id],
            documents=[query],
            metadatas=[{
                "need_id": need_id,
                "query": query,
                "signals_json": json.dumps([s.model_dump() for s in signals]),
                "created_at": datetime.utcnow().isoformat(),
            }]
        )
    except Exception as e:
        logger.warning(f"ChromaDB cache write failed: {e}")
        # continue — return results even if caching failed

    # ── STEP 9: RETURN ────────────────────────────────────────────────────────
    return TechSignalsResponse(signals=signals, query_used=query, from_cache=False)


@router.post("/{need_id}/export/pdf")
async def export_pdf(
    need_id: str,
    body: ExportReportRequest,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Generate and stream a professional PDF report."""
    try:
        result = await db.execute(select(BusinessNeed).where(BusinessNeed.id == need_id))
        need = result.scalar_one_or_none()
        if need is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Business need '{need_id}' not found.",
            )

        pdf_bytes = build_pdf_report(
            need_id=need_id,
            pitch=need.pitch,
            horizon=need.horizon,
            tags=need.tags or {},
            status=need.status,
            rework_note=need.rework_note,
            recommendations=[item.model_dump() for item in body.recommendations],
            delivery_solutions=[item.model_dump() for item in body.delivery_solutions],
            selected_solutions=[item.model_dump() for item in body.selected_solutions],
            stage_gates=[item.model_dump() for item in body.stage_gates],
        )

        filename = f"{need_id.lower()}-recommendations.pdf"
        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("PDF export failed for %s: %s", need_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate PDF report.",
        ) from exc


@router.post("/{need_id}/export/docx")
async def export_docx(
    need_id: str,
    body: ExportReportRequest,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Generate and stream a professional DOCX report."""
    try:
        result = await db.execute(select(BusinessNeed).where(BusinessNeed.id == need_id))
        need = result.scalar_one_or_none()
        if need is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Business need '{need_id}' not found.",
            )

        docx_bytes = build_docx_report(
            need_id=need_id,
            pitch=need.pitch,
            horizon=need.horizon,
            tags=need.tags or {},
            status=need.status,
            rework_note=need.rework_note,
            recommendations=[item.model_dump() for item in body.recommendations],
            delivery_solutions=[item.model_dump() for item in body.delivery_solutions],
            selected_solutions=[item.model_dump() for item in body.selected_solutions],
            stage_gates=[item.model_dump() for item in body.stage_gates],
        )

        filename = f"{need_id.lower()}-recommendations.docx"
        return StreamingResponse(
            BytesIO(docx_bytes),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("DOCX export failed for %s: %s", need_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate DOCX report.",
        ) from exc
