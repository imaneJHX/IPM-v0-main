"""Seed the DXC product catalog into a dedicated ChromaDB collection.

Runs once at startup via the lifespan hook in main.py.
Each startup re-upserts catalog entries so JSON changes are reflected in search.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.core.chroma import get_collection
from app.core.embedding_client import embed_text

logger = logging.getLogger(__name__)

_CATALOG_PATH = Path(__file__).parent.parent / "data" / "catalog.json"
_COLLECTION_NAME = "dxc_catalog"

# Fields excluded from metadata (already captured in the embedded document text)
_EXCLUDE_FROM_META = {"description", "features", "business_impact", "use_cases"}


def _build_document(product: dict) -> str:
    """Concatenate product fields into the text string that gets embedded."""
    features: list[str] = product.get("features") or []
    business_impact: str = (product.get("business_impact") or "").strip()
    use_cases: str = (product.get("use_cases") or "").strip()

    parts = [
        f"{product['name']}.",
        (product.get("description") or "").strip() + ".",
    ]
    if features:
        parts.append(f"Features: {', '.join(features)}.")
    if business_impact:
        parts.append(f"Business impact: {business_impact}.")
    if use_cases:
        parts.append(f"Use cases: {use_cases}.")

    return " ".join(p for p in parts if p and p != ".")


def _build_metadata(product: dict) -> dict:
    """Return the product dict stripped of fields already in the document.

    ChromaDB requires metadata values to be str | int | float | bool.
    None values are converted to empty string.
    """
    meta = {
        k: (v if v is not None else "")
        for k, v in product.items()
        if k not in _EXCLUDE_FROM_META
    }
    return {k: (", ".join(v) if isinstance(v, list) else v) for k, v in meta.items()}


def seed_catalog() -> None:
    """Load catalog.json into the dxc_catalog ChromaDB collection."""
    with open(_CATALOG_PATH, encoding="utf-8") as f:
        products: list[dict] = json.load(f)

    collection = get_collection(_COLLECTION_NAME)

    upserted = 0
    for product in products:
        pid = product["id"]
        document = _build_document(product)
        embedding = embed_text(document, is_query=False)
        metadata = _build_metadata(product)

        collection.upsert(
            ids=[pid],
            embeddings=[embedding],
            documents=[document],
            metadatas=[metadata],
        )
        upserted += 1

    logger.info("Catalog seeding: %d products upserted into %s", upserted, _COLLECTION_NAME)
