from __future__ import annotations

import json
from pathlib import Path

from app.models import CatalogItem, Category


class CatalogRepository:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._items: list[CatalogItem] | None = None

    def load(self) -> list[CatalogItem]:
        if self._items is not None:
            return self._items
        if not self.path.exists():
            raise FileNotFoundError(f"Catalog file not found: {self.path}")
        raw_items = json.loads(self.path.read_text())
        self._items = [CatalogItem.model_validate(item) for item in raw_items]
        return self._items

    def counts_by_category(self) -> dict[str, int]:
        counts = {category.value: 0 for category in Category}
        for item in self.load():
            counts[item.category.value] = counts.get(item.category.value, 0) + 1
        return counts
