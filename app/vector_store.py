from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import httpx

from app.embeddings import Embedder, cosine_similarity
from app.models import CatalogItem, Category, Gender

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
        genders: set[Gender] | None = None,
        limit: int = 8,
    ) -> list[SearchResult]: ...


class LocalJsonVectorStore:
    backend_name = "local_json"

    def __init__(self, embedder: Embedder, path: Path = Path("data/vector_store.json")) -> None:
        self.embedder = embedder
        self.path = path
        self._records: list[dict[str, Any]] = []

    async def ensure_index(self, items: list[CatalogItem]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        current_ids = {record["item"]["id"] for record in self._records}
        item_ids = {item.id for item in items}
        if self.path.exists() and (current_ids != item_ids or not self._records_match_embedder()):
            self._records = []
        if not self._records and self.path.exists():
            self._records = json.loads(self.path.read_text())
        current_ids = {record["item"]["id"] for record in self._records}
        if current_ids == item_ids and self._records_match_embedder():
            return
        self._records = [
            {
                "embedding_model": self.embedder.cache_key,
                "item": item.model_dump(mode="json"),
                "vector": self.embedder.embed(item.searchable_text),
            }
            for item in items
        ]
        self.path.write_text(json.dumps(self._records, indent=2))
        logger.info("Indexed %s catalog items into local JSON vector store", len(items))

    def _records_match_embedder(self) -> bool:
        if not self._records:
            return False
        for record in self._records[:3]:
            vector = record.get("vector", [])
            if record.get("embedding_model") != self.embedder.cache_key or len(vector) != self.embedder.dimensions:
                return False
        return True

    async def search(
        self,
        query: str,
        *,
        category: Category | None = None,
        max_price: float | None = None,
        colors: set[str] | None = None,
        genders: set[Gender] | None = None,
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
            if genders and item.gender not in genders:
                continue
            score = cosine_similarity(query_vector, record["vector"])
            results.append(SearchResult(item=item, score=score))
        return sorted(results, key=lambda result: result.score, reverse=True)[:limit]


class QdrantVectorStore:
    backend_name = "qdrant"

    def __init__(
        self,
        embedder: Embedder,
        *,
        url: str,
        api_key: str,
        collection: str,
        recreate_on_startup: bool = True,
    ) -> None:
        self.embedder = embedder
        self.url = url.rstrip("/")
        self.api_key = api_key
        self.collection = collection
        self.recreate_on_startup = recreate_on_startup

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
            should_upsert = True
            if response.status_code == 404:
                await self._create_collection(client, collection_url)
            elif response.status_code >= 400:
                response.raise_for_status()
            elif self.recreate_on_startup or not self._collection_matches_embedder(response.json()):
                delete_response = await client.delete(collection_url, headers=self._headers)
                delete_response.raise_for_status()
                await self._create_collection(client, collection_url)
            else:
                await self._ensure_payload_indexes(client, collection_url)
                count_response = await client.post(
                    f"{collection_url}/points/count",
                    headers=self._headers,
                    json={"exact": True},
                )
                count_response.raise_for_status()
                count = count_response.json().get("result", {}).get("count", 0)
                should_upsert = count < len(items)

            if not should_upsert:
                logger.info("Qdrant collection %s already has %s indexed items", self.collection, len(items))
                return

            points = []
            for idx, item in enumerate(items):
                points.append(
                    {
                        "id": idx + 1,
                        "vector": self.embedder.embed(item.searchable_text),
                        "payload": {
                            **item.model_dump(mode="json"),
                            "_embedding_model": self.embedder.cache_key,
                        },
                    }
                )
            upsert_response = await client.put(
                f"{collection_url}/points?wait=true",
                headers=self._headers,
                json={"points": points},
            )
            upsert_response.raise_for_status()
            await self._ensure_payload_indexes(client, collection_url)
            logger.info("Indexed %s catalog items into Qdrant collection %s", len(points), self.collection)

    async def _create_collection(self, client: httpx.AsyncClient, collection_url: str) -> None:
        create_payload = {
            "vectors": {"size": self.embedder.dimensions, "distance": "Cosine"},
            "optimizers_config": {"default_segment_number": 2},
        }
        create_response = await client.put(collection_url, headers=self._headers, json=create_payload)
        create_response.raise_for_status()

    async def _ensure_payload_indexes(self, client: httpx.AsyncClient, collection_url: str) -> None:
        indexes = {
            "category": "keyword",
            "color": "keyword",
            "gender": "keyword",
            "price": "float",
        }
        for field_name, field_schema in indexes.items():
            response = await client.put(
                f"{collection_url}/index",
                headers=self._headers,
                params={"wait": "true"},
                json={"field_name": field_name, "field_schema": field_schema},
            )
            if response.status_code not in {200, 409}:
                response.raise_for_status()

    def _collection_matches_embedder(self, collection_response: dict[str, Any]) -> bool:
        vectors = collection_response.get("result", {}).get("config", {}).get("params", {}).get("vectors", {})
        if isinstance(vectors, dict) and "size" in vectors:
            return vectors.get("size") == self.embedder.dimensions
        if isinstance(vectors, dict):
            first_config = next(iter(vectors.values()), {})
            if isinstance(first_config, dict):
                return first_config.get("size") == self.embedder.dimensions
        return False

    async def search(
        self,
        query: str,
        *,
        category: Category | None = None,
        max_price: float | None = None,
        colors: set[str] | None = None,
        genders: set[Gender] | None = None,
        limit: int = 8,
    ) -> list[SearchResult]:
        must: list[dict[str, Any]] = []
        if category:
            must.append({"key": "category", "match": {"value": category.value}})
        if max_price is not None:
            must.append({"key": "price", "range": {"lte": max_price}})
        if colors:
            must.append({"key": "color", "match": {"any": sorted(colors)}})
        if genders:
            must.append({"key": "gender", "match": {"any": sorted(g.value for g in genders)}})

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
