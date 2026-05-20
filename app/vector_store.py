from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import httpx

from app.embeddings import HashingEmbedder, cosine_similarity
from app.models import CatalogItem, Category

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    item: CatalogItem
    score: float


class VectorStore(Protocol):
    backend_name: str

    async def ensure_index(self, items: list[CatalogItem]) -> None: ...

    async def search(
        self,
        query: str,
        *,
        category: Category | None = None,
        max_price: float | None = None,
        colors: set[str] | None = None,
        limit: int = 8,
    ) -> list[SearchResult]: ...


class LocalJsonVectorStore:
    backend_name = "local_json"

    def __init__(self, embedder: HashingEmbedder, path: Path = Path("data/vector_store.json")) -> None:
        self.embedder = embedder
        self.path = path
        self._records: list[dict[str, Any]] = []

    async def ensure_index(self, items: list[CatalogItem]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        current_ids = {record["item"]["id"] for record in self._records}
        item_ids = {item.id for item in items}
        if self.path.exists() and current_ids != item_ids:
            self._records = []
        if not self._records and self.path.exists():
            self._records = json.loads(self.path.read_text())
        current_ids = {record["item"]["id"] for record in self._records}
        if current_ids == item_ids:
            return
        self._records = [
            {"item": item.model_dump(mode="json"), "vector": self.embedder.embed(item.searchable_text)}
            for item in items
        ]
        self.path.write_text(json.dumps(self._records, indent=2))
        logger.info("Indexed %s catalog items into local JSON vector store", len(items))

    async def search(
        self,
        query: str,
        *,
        category: Category | None = None,
        max_price: float | None = None,
        colors: set[str] | None = None,
        limit: int = 8,
    ) -> list[SearchResult]:
        query_vector = self.embedder.embed(query)
        results: list[SearchResult] = []
        for record in self._records:
            item = CatalogItem.model_validate(record["item"])
            if category and item.category != category:
                continue
            if max_price is not None and item.price > max_price:
                continue
            if colors and item.color.lower() not in colors:
                continue
            score = cosine_similarity(query_vector, record["vector"])
            results.append(SearchResult(item=item, score=score))
        return sorted(results, key=lambda result: result.score, reverse=True)[:limit]


class QdrantVectorStore:
    backend_name = "qdrant"

    def __init__(
        self,
        embedder: HashingEmbedder,
        *,
        url: str,
        api_key: str,
        collection: str,
    ) -> None:
        self.embedder = embedder
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.collection = collection

    @property
    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["api-key"] = self.api_key
        return headers

    async def ensure_index(self, items: list[CatalogItem]) -> None:
        async with httpx.AsyncClient(timeout=30) as client:
            collection_url = f"{self.url}/collections/{self.collection}"
            response = await client.get(collection_url, headers=self._headers)
            if response.status_code == 404:
                create_payload = {
                    "vectors": {"size": self.embedder.dimensions, "distance": "Cosine"},
                    "optimizers_config": {"default_segment_number": 2},
                }
                create_response = await client.put(collection_url, headers=self._headers, json=create_payload)
                create_response.raise_for_status()
            elif response.status_code >= 400:
                response.raise_for_status()

            count_response = await client.post(
                f"{collection_url}/points/count",
                headers=self._headers,
                json={"exact": True},
            )
            count_response.raise_for_status()
            count = count_response.json().get("result", {}).get("count", 0)
            if count >= len(items):
                return

            points = []
            for idx, item in enumerate(items):
                points.append(
                    {
                        "id": idx + 1,
                        "vector": self.embedder.embed(item.searchable_text),
                        "payload": item.model_dump(mode="json"),
                    }
                )
            upsert_response = await client.put(
                f"{collection_url}/points?wait=true",
                headers=self._headers,
                json={"points": points},
            )
            upsert_response.raise_for_status()
            logger.info("Indexed %s catalog items into Qdrant collection %s", len(points), self.collection)

    async def search(
        self,
        query: str,
        *,
        category: Category | None = None,
        max_price: float | None = None,
        colors: set[str] | None = None,
        limit: int = 8,
    ) -> list[SearchResult]:
        must: list[dict[str, Any]] = []
        if category:
            must.append({"key": "category", "match": {"value": category.value}})
        if max_price is not None:
            must.append({"key": "price", "range": {"lte": max_price}})
        if colors:
            must.append({"key": "color", "match": {"any": sorted(colors)}})

        payload: dict[str, Any] = {
            "vector": self.embedder.embed(query),
            "limit": limit,
            "with_payload": True,
        }
        if must:
            payload["filter"] = {"must": must}

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{self.url}/collections/{self.collection}/points/search",
                headers=self._headers,
                json=payload,
            )
            response.raise_for_status()
        results = []
        for point in response.json().get("result", []):
            results.append(SearchResult(item=CatalogItem.model_validate(point["payload"]), score=point["score"]))
        return results
