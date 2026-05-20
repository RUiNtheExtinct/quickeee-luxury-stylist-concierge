from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, field_validator


class Category(StrEnum):
    top = "top"
    bottom = "bottom"
    shoe = "shoe"
    accessory = "accessory"


class CatalogItem(BaseModel):
    id: str
    brand: str
    source: str
    name: str
    price: float = Field(ge=0)
    currency: str = "USD"
    image_url: str
    product_url: str
    category: Category
    description: str
    color: str = "unknown"
    material: str = "unknown"
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [part.strip().lower() for part in value.split(",") if part.strip()]
        return [str(part).strip().lower() for part in value if str(part).strip()]

    @property
    def searchable_text(self) -> str:
        parts = [
            self.brand,
            self.name,
            self.category.value,
            self.color,
            self.material,
            self.description,
            " ".join(self.tags),
        ]
        return " ".join(part for part in parts if part)


class StyleRequest(BaseModel):
    prompt: str = Field(min_length=5, max_length=1200)
    max_price: float | None = Field(default=None, ge=1)
    currency: str = "USD"
    include_trace: bool = True


class RecommendedItem(BaseModel):
    id: str
    brand: str
    name: str
    category: Category
    price: float
    currency: str
    image_url: str
    product_url: str
    color: str
    reason: str


class AgentTraceStep(BaseModel):
    step: str
    detail: str


class StyleResponse(BaseModel):
    request_id: str
    cache_hit: bool
    prompt: str
    recommended_items: list[RecommendedItem]
    total_price: float
    currency: str
    stylist_note: str
    token_strategy: str
    trace: list[AgentTraceStep] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    catalog_items: int
    vector_backend: str
    llm_provider: str
