from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable


TOKEN_RE = re.compile(r"[a-z0-9]+")


class HashingEmbedder:
    """Small deterministic embedder for frugal demos and free deployments.

    It avoids a paid embedding API while still producing vectors that Qdrant can
    filter and rank. The assignment can be upgraded to hosted embeddings by
    swapping this class behind the same interface.
    """

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in self._tokens(text):
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign * self._weight(token)
        return normalize(vector)

    def embed_many(self, texts: Iterable[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]

    def _tokens(self, text: str) -> list[str]:
        tokens = TOKEN_RE.findall(text.lower())
        expanded = []
        for token in tokens:
            expanded.append(token)
            expanded.extend(SYNONYMS.get(token, []))
        return expanded

    def _weight(self, token: str) -> float:
        if token in STYLE_TERMS:
            return 1.8
        if token in COLOR_TERMS:
            return 1.5
        return 1.0


def cosine_similarity(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=False))


def normalize(vector: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0:
        return vector
    return [value / magnitude for value in vector]


COLOR_TERMS = {
    "black",
    "blue",
    "brown",
    "charcoal",
    "cream",
    "ecru",
    "green",
    "grey",
    "indigo",
    "ivory",
    "khaki",
    "navy",
    "olive",
    "sand",
    "stone",
    "tan",
    "white",
}

STYLE_TERMS = {
    "beach",
    "business",
    "casual",
    "chino",
    "cocktail",
    "cotton",
    "dinner",
    "linen",
    "loafers",
    "luxury",
    "party",
    "polo",
    "resort",
    "shirt",
    "shorts",
    "summer",
    "tailored",
    "tshirt",
    "yacht",
}

SYNONYMS = {
    "tee": ["tshirt", "top", "cotton"],
    "t": ["tshirt", "tee"],
    "tshirt": ["tee", "top"],
    "trouser": ["pants", "bottom"],
    "trousers": ["pants", "bottom"],
    "pants": ["bottom", "chino"],
    "chinos": ["chino", "pants", "bottom"],
    "sneakers": ["shoe", "casual"],
    "shoes": ["shoe", "loafers"],
    "boat": ["yacht", "resort"],
    "marine": ["navy", "yacht"],
    "warm": ["summer", "linen"],
    "hot": ["summer", "linen"],
    "premium": ["luxury", "tailored"],
}
