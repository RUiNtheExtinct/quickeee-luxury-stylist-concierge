from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, field_validator


class Category(StrEnum):
    top = "top"
    bottom = "bottom"
    shoe = "shoe"
    accessory = "accessory"


class Gender(StrEnum):
    men = "men"
    women = "women"
    unisex = "unisex"


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
    gender: Gender = Gender.unisex
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
            f"{self.gender.value}'s" if self.gender != Gender.unisex else "unisex",
            self.color,
            self.material,
            self.description,
            " ".join(self.tags),
        ]
        return " ".join(part for part in parts if part)


class StylingFor(StrEnum):
    """Who the look is being styled for. `either` lets the prompt decide."""

    men = "men"
    women = "women"
    either = "either"


class AccessoryMode(StrEnum):
    """Whether to add a finishing accessory to the outfit.

    auto  — add one only when the prompt implies it (and avoid bags/totes
            unless the prompt mentions one).
    on    — always add a finishing accessory.
    off   — never add an accessory.
    """

    auto = "auto"
    on = "on"
    off = "off"


class StyleRequest(BaseModel):
    prompt: str = Field(min_length=5, max_length=1200)
    max_price: float | None = Field(default=None, ge=1)
    currency: str = "USD"
    gender: StylingFor = StylingFor.either
    accessories: AccessoryMode = AccessoryMode.auto
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
    gender: Gender = Gender.unisex
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
    embedding_provider: str
    embedding_model: str
    llm_provider: str
