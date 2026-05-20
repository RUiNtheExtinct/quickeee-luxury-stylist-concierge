from __future__ import annotations

import logging

from app.agent import StylistAgent
from app.cache import SemanticCache
from app.catalog import CatalogRepository
from app.config import Settings, get_settings
from app.embeddings import HashingEmbedder
from app.vector_store import LocalJsonVectorStore, QdrantVectorStore, VectorStore

logger = logging.getLogger(__name__)


class AppContainer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.catalog = CatalogRepository(settings.catalog_path)
        self.embedder = HashingEmbedder()
        self.vector_store: VectorStore = self._build_vector_store(settings)
        self.cache = SemanticCache(settings.cache_path, self.embedder)
        self.agent = StylistAgent(
            vector_store=self.vector_store,
            cache=self.cache,
            llm_provider=settings.llm_provider,
            llm_api_key=settings.llm_api_key,
            llm_base_url=settings.llm_base_url,
            llm_model=settings.llm_model,
        )

    def _build_vector_store(self, settings: Settings) -> VectorStore:
        if settings.vector_backend == "qdrant":
            return QdrantVectorStore(
                self.embedder,
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key,
                collection=settings.qdrant_collection,
            )
        return LocalJsonVectorStore(self.embedder)

    async def startup(self) -> None:
        items = self.catalog.load()
        try:
            await self.vector_store.ensure_index(items)
        except Exception as exc:
            if not self.settings.allow_local_vector_fallback:
                raise
            logger.warning("Vector backend %s unavailable, falling back to local_json: %s", self.vector_store.backend_name, exc)
            self.vector_store = LocalJsonVectorStore(self.embedder)
            await self.vector_store.ensure_index(items)
            self.agent.vector_store = self.vector_store


container = AppContainer(get_settings())
