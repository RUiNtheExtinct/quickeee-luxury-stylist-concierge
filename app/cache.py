from __future__ import annotations

import json
import time
from pathlib import Path

from app.embeddings import Embedder, cosine_similarity
from app.models import StyleResponse


class SemanticCache:
    def __init__(self, path: Path, embedder: Embedder, threshold: float = 0.94, namespace: str = "style-agent-v3") -> None:
        self.path = path
        self.embedder = embedder
        self.threshold = threshold
        self.namespace = namespace
        self._entries: list[dict] = []
        self._loaded = False

    def get(self, prompt: str) -> StyleResponse | None:
        self._load()
        vector = self.embedder.embed(prompt)
        best = None
        best_score = -1.0
        for entry in self._entries:
            if entry.get("namespace") != self.namespace or entry.get("embedding_model") != self.embedder.cache_key:
                continue
            score = cosine_similarity(vector, entry["vector"])
            if score > best_score:
                best = entry
                best_score = score
        if best and best_score >= self.threshold:
            response = StyleResponse.model_validate(best["response"])
            return response.model_copy(update={"cache_hit": True})
        return None

    def put(self, prompt: str, response: StyleResponse) -> None:
        self._load()
        response_for_cache = response.model_copy(update={"cache_hit": False})
        self._entries.append(
            {
                "namespace": self.namespace,
                "embedding_model": self.embedder.cache_key,
                "prompt": prompt,
                "vector": self.embedder.embed(prompt),
                "created_at": int(time.time()),
                "response": response_for_cache.model_dump(mode="json"),
            }
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._entries[-100:], indent=2))

    def _load(self) -> None:
        if self._loaded:
            return
        if self.path.exists():
            self._entries = json.loads(self.path.read_text())
        self._loaded = True
