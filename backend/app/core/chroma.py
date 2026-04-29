"""Minimal local vector store used for local development."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from app.core.config import settings


def _cosine_distance(left: list[float], right: list[float]) -> float:
    """Return cosine distance between two vectors."""
    if not left or not right:
        return 1.0

    size = min(len(left), len(right))
    dot = sum(float(left[i]) * float(right[i]) for i in range(size))
    left_norm = math.sqrt(sum(float(left[i]) * float(left[i]) for i in range(size)))
    right_norm = math.sqrt(sum(float(right[i]) * float(right[i]) for i in range(size)))
    if left_norm == 0 or right_norm == 0:
        return 1.0

    similarity = dot / (left_norm * right_norm)
    similarity = max(-1.0, min(1.0, similarity))
    return 1.0 - similarity


class LocalCollection:
    """Small JSON-backed collection with a Chroma-like interface."""

    def __init__(self, name: str, base_path: Path):
        self.name = name
        self.path = base_path / f"{name}.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, dict[str, Any]] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if self.path.exists():
            self._data = json.loads(self.path.read_text(encoding="utf-8"))
        self._loaded = True

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._data), encoding="utf-8")

    def count(self) -> int:
        self._ensure_loaded()
        return len(self._data)

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str] | None = None,
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        self.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)

    def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str] | None = None,
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        self._ensure_loaded()
        documents = documents or []
        metadatas = metadatas or []

        for index, doc_id in enumerate(ids):
            self._data[doc_id] = {
                "id": doc_id,
                "embedding": embeddings[index],
                "document": documents[index] if index < len(documents) else "",
                "metadata": metadatas[index] if index < len(metadatas) else {},
            }

        self._save()

    def get(self, ids: list[str]) -> dict[str, list[Any]]:
        self._ensure_loaded()
        rows = [self._data[doc_id] for doc_id in ids if doc_id in self._data]
        return {
            "ids": [row["id"] for row in rows],
            "documents": [row.get("document", "") for row in rows],
            "metadatas": [row.get("metadata", {}) for row in rows],
            "embeddings": [row.get("embedding", []) for row in rows],
        }

    def query(
        self,
        query_embeddings: list[list[float]],
        n_results: int,
        include: list[str] | None = None,
    ) -> dict[str, list[list[Any]]]:
        self._ensure_loaded()
        include = include or []

        ids_result: list[list[str]] = []
        docs_result: list[list[str]] = []
        metas_result: list[list[dict[str, Any]]] = []
        distances_result: list[list[float]] = []

        rows = list(self._data.values())
        for query_embedding in query_embeddings:
            ranked = sorted(
                rows,
                key=lambda row: _cosine_distance(query_embedding, row.get("embedding", [])),
            )[:n_results]

            ids_result.append([row["id"] for row in ranked])
            if "documents" in include:
                docs_result.append([row.get("document", "") for row in ranked])
            if "metadatas" in include:
                metas_result.append([row.get("metadata", {}) for row in ranked])
            if "distances" in include:
                distances_result.append([
                    _cosine_distance(query_embedding, row.get("embedding", []))
                    for row in ranked
                ])

        payload: dict[str, list[list[Any]]] = {
            "ids": ids_result,
        }
        if "documents" in include:
            payload["documents"] = docs_result
        if "metadatas" in include:
            payload["metadatas"] = metas_result
        if "distances" in include:
            payload["distances"] = distances_result
        return payload


class LocalChromaClient:
    """Return collection objects backed by local JSON files."""

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._collections: dict[str, LocalCollection] = {}

    def get_or_create_collection(
        self,
        name: str,
        metadata: dict[str, Any] | None = None,
    ) -> LocalCollection:
        if name not in self._collections:
            self._collections[name] = LocalCollection(name=name, base_path=self.base_path)
        return self._collections[name]


_client: LocalChromaClient | None = None
_collections: dict[str, LocalCollection] = {}


def get_chroma_client() -> LocalChromaClient:
    """Return the local vector-store client."""
    global _client
    if _client is None:
        _client = LocalChromaClient(Path(settings.chroma_path).resolve())
    return _client


def get_collection(name: str = "business_needs") -> LocalCollection:
    """Return a collection by name, creating it if needed."""
    global _collections
    if name not in _collections:
        client = get_chroma_client()
        _collections[name] = client.get_or_create_collection(name=name, metadata={"space": "cosine"})
    return _collections[name]
