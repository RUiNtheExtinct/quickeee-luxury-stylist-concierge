from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass

import httpx

from app.cache import SemanticCache
from app.models import (
    AccessoryMode,
    AgentTraceStep,
    CatalogItem,
    Category,
    Gender,
    RecommendedItem,
    StyleRequest,
    StyleResponse,
    StylingFor,
)
from app.vector_store import SearchResult, VectorStore

logger = logging.getLogger(__name__)


COLOR_WORDS = {
    "black",
    "blue",
    "brown",
    "charcoal",
    "cream",
    "ecru",
    "green",
    "grey",
    "gray",
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

OCCASION_WORDS = {
    "beach",
    "brunch",
    "business",
    "casual",
    "cocktail",
    "date",
    "dinner",
    "office",
    "party",
    "resort",
    "summer",
    "travel",
    "wedding",
    "weekend",
    "yacht",
}

STYLE_SIGNALS = {
    "tech": {
        "terms": {"minimal", "clean", "modern", "black", "navy", "grey", "sneaker", "backpack", "crew", "oxford"},
        "colors": {"black", "navy", "blue", "grey", "white"},
        "label": "tech-forward",
    },
    "tech bro": {
        "terms": {"startup", "modern", "premium", "clean", "sneaker", "tee", "chino", "backpack"},
        "colors": {"black", "navy", "blue", "white", "grey"},
        "label": "tech-forward",
    },
    "pro": {
        "terms": {"polished", "tailored", "oxford", "shirt", "trouser", "loafer", "leather"},
        "colors": {"navy", "black", "grey", "white", "brown"},
        "label": "professional",
    },
    "suave": {
        "terms": {"polished", "smooth", "silk", "suede", "loafer", "shirt", "polo", "leather"},
        "colors": {"black", "navy", "white", "ivory", "brown"},
        "label": "suave",
    },
    "cool": {
        "terms": {"relaxed", "modern", "minimal", "sneaker", "black", "charcoal", "logo", "denim"},
        "colors": {"black", "navy", "blue", "white", "charcoal"},
        "label": "cool",
    },
    "nerdy": {
        "terms": {"precise", "clean", "crew", "oxford", "backpack", "beanie", "sneaker", "structured"},
        "colors": {"blue", "navy", "grey", "black", "white"},
        "label": "smart-nerdy",
    },
    "founder": {
        "terms": {"polished", "startup", "tailored", "minimal", "sneaker", "loafer"},
        "colors": {"navy", "black", "white", "grey", "brown"},
        "label": "founder",
    },
}

OWNED_BOTTOM_PATTERNS = [
    re.compile(r"\bi have\b.*\b(chinos?|pants|trousers|jeans|shorts)\b", re.I),
    re.compile(r"\bwith my\b.*\b(chinos?|pants|trousers|jeans|shorts)\b", re.I),
]

WOMEN_INTENT = re.compile(
    r"\b(women|woman|women's|womens|her|she|girlfriend|wife|female|ladies|lady|dress|skirt|gown|heels)\b", re.I
)
MEN_INTENT = re.compile(r"\b(men|man|men's|mens|him|his|boyfriend|husband|male|guy|gentleman)\b", re.I)


@dataclass(frozen=True)
class Intent:
    colors: set[str]
    occasions: set[str]
    style_signals: set[str]
    query_terms: set[str]
    owned_bottom: bool
    needs: list[Category]
    max_price: float | None
    gender: Gender
    avoid_bags: bool = False


class StylistAgent:
    def __init__(
        self,
        *,
        vector_store: VectorStore,
        cache: SemanticCache,
        llm_provider: str = "local",
        llm_api_key: str = "",
        llm_base_url: str = "",
        llm_model: str = "",
        embedding_label: str = "local",
    ) -> None:
        self.vector_store = vector_store
        self.cache = cache
        self.llm_provider = llm_provider
        self.llm_api_key = llm_api_key
        self.llm_base_url = llm_base_url.rstrip("/")
        self.llm_model = llm_model
        self.embedding_label = embedding_label

    async def recommend(self, request: StyleRequest) -> StyleResponse:
        # Scope the cache by the request knobs so different prefs never collide
        # on the same prompt text.
        variant = self._cache_variant(request)
        cached = self.cache.get(request.prompt, variant=variant)
        if cached:
            logger.info("semantic_cache_hit prompt=%r variant=%s", request.prompt, variant)
            return cached

        trace: list[AgentTraceStep] = []
        request_id = str(uuid.uuid4())
        intent = self._extract_intent(request)
        trace.append(
            AgentTraceStep(
                step="intent",
                detail=(
                    f"gender={intent.gender.value}, colors={sorted(intent.colors) or 'open'}, "
                    f"occasions={sorted(intent.occasions) or 'general'}, "
                    f"style_signals={sorted(intent.style_signals) or 'none'}, "
                    f"query_terms={sorted(intent.query_terms) or 'none'}, "
                    f"owned_bottom={intent.owned_bottom}, needs={[need.value for need in intent.needs]}, "
                    f"max_price={intent.max_price or 'none'}, "
                    f"gender_source={'override' if request.gender != StylingFor.either else 'inferred'}, "
                    f"accessories={request.accessories.value}, avoid_bags={intent.avoid_bags}"
                ),
            )
        )

        gender_filter = self._gender_filter(intent.gender)
        candidate_map: dict[Category, list[SearchResult]] = {}
        for category in intent.needs:
            query = self._query_for_category(request.prompt, category, intent)
            candidates = await self.vector_store.search(
                query,
                category=category,
                max_price=intent.max_price,
                genders=gender_filter,
                limit=10,
            )
            ranked = self._rerank(candidates, intent)
            if category == Category.accessory and intent.avoid_bags:
                non_bags = [r for r in ranked if not self._is_bag(r.item)]
                # Only drop bags if non-bag accessories remain, so we never empty the slot.
                ranked = non_bags or ranked
            candidate_map[category] = ranked
            trace.append(
                AgentTraceStep(
                    step=f"retrieve_{category.value}",
                    detail=f"kept {len(candidate_map[category])} {intent.gender.value}/unisex candidates for query={query!r}",
                )
            )

        selected = await self._select_outfit(request.prompt, candidate_map, intent, trace)
        trace.append(
            AgentTraceStep(
                step="rank",
                detail="selected " + ", ".join(f"{item.category.value}:{item.name}" for item in selected),
            )
        )

        note = await self._stylist_note(request.prompt, selected, trace, intent)
        recommended_items = [self._to_recommendation(item, intent) for item in selected]
        response = StyleResponse(
            request_id=request_id,
            cache_hit=False,
            prompt=request.prompt,
            recommended_items=recommended_items,
            total_price=round(sum(item.price for item in selected), 2),
            currency=request.currency,
            stylist_note=note,
            token_strategy=(
                f"Semantic cache checked before retrieval; catalog and prompt vectors use {self.embedding_label}; "
                "LLM context is compressed to selected item facts and detected style signals."
            ),
            trace=trace if request.include_trace else [],
        )
        self.cache.put(request.prompt, response, variant=variant)
        logger.info("agent_response request_id=%s total=%.2f items=%s", request_id, response.total_price, len(selected))
        return response

    def _cache_variant(self, request: StyleRequest) -> str:
        # Bucket price so near-identical budgets still share a cache entry.
        price_bucket = int(request.max_price // 50) if request.max_price else 0
        return f"g={request.gender.value};a={request.accessories.value};p={price_bucket};cur={request.currency}"

    def _extract_intent(self, request: StyleRequest) -> Intent:
        prompt = request.prompt.lower()
        colors = {word for word in COLOR_WORDS if re.search(rf"\b{re.escape(word)}\b", prompt)}
        if "gray" in colors:
            colors.remove("gray")
            colors.add("grey")
        occasions = {word for word in OCCASION_WORDS if re.search(rf"\b{re.escape(word)}\b", prompt)}
        style_signals = self._extract_style_signals(prompt)
        query_terms = self._style_query_terms(style_signals)
        for signal in style_signals:
            colors.update(STYLE_SIGNALS.get(signal, {}).get("colors", set()))
        owned_bottom = any(pattern.search(request.prompt) for pattern in OWNED_BOTTOM_PATTERNS)
        needs = [Category.top, Category.shoe] if owned_bottom else [Category.top, Category.bottom, Category.shoe]
        # Whether the prompt itself asks for a bag/accessory, so auto-mode can allow one.
        wants_bag = bool(re.search(r"\b(bag|tote|backpack|weekender|pouch|holdall|carryall)\b", prompt))
        if self._should_add_accessory(prompt, style_signals, owned_bottom, request.accessories, wants_bag):
            needs.append(Category.accessory)
        if "shirt" in prompt or "t-shirt" in prompt or "tee" in prompt:
            needs = [category for category in needs if category != Category.top]
            needs.insert(0, Category.top)
        max_price = request.max_price or self._extract_budget(prompt)
        gender = self._extract_gender(request.prompt, request.gender)
        # In auto accessory mode, steer away from bags unless the prompt asked.
        avoid_bags = request.accessories == AccessoryMode.auto and not wants_bag
        return Intent(
            colors=colors,
            occasions=occasions,
            style_signals=style_signals,
            query_terms=query_terms,
            owned_bottom=owned_bottom,
            needs=needs,
            max_price=max_price,
            gender=gender,
            avoid_bags=avoid_bags,
        )

    def _extract_gender(self, prompt: str, override: StylingFor) -> Gender:
        # An explicit UI/API choice always wins over prompt inference.
        if override == StylingFor.men:
            return Gender.men
        if override == StylingFor.women:
            return Gender.women
        has_women = bool(WOMEN_INTENT.search(prompt))
        has_men = bool(MEN_INTENT.search(prompt))
        if has_women and not has_men:
            return Gender.women
        if has_men and not has_women:
            return Gender.men
        # No explicit signal at all: default to the catalog's dominant menswear brief.
        return Gender.men

    def _gender_filter(self, gender: Gender) -> set[Gender]:
        # Always allow unisex pieces alongside the requested gender.
        if gender == Gender.women:
            return {Gender.women, Gender.unisex}
        if gender == Gender.men:
            return {Gender.men, Gender.unisex}
        return {Gender.men, Gender.women, Gender.unisex}

    def _extract_style_signals(self, prompt: str) -> set[str]:
        signals: set[str] = set()
        if re.search(r"\btech\s+bro\b", prompt):
            signals.add("tech bro")
            signals.add("tech")
        for signal in STYLE_SIGNALS:
            if signal == "tech bro":
                continue
            if re.search(rf"\b{re.escape(signal)}\b", prompt):
                signals.add(signal)
        return signals

    def _style_query_terms(self, style_signals: set[str]) -> set[str]:
        terms: set[str] = set()
        for signal in style_signals:
            terms.update(STYLE_SIGNALS.get(signal, {}).get("terms", set()))
        return terms

    def _should_add_accessory(
        self, prompt: str, style_signals: set[str], owned_bottom: bool, mode: AccessoryMode, wants_bag: bool
    ) -> bool:
        if mode == AccessoryMode.off:
            return False
        if mode == AccessoryMode.on:
            return True
        # auto: only when the prompt implies a finished look or names an accessory/bag.
        if wants_bag:
            return True
        if any(term in prompt for term in ["accessory", "accessories", "finish", "complete outfit", "full look"]):
            return True
        return False

    def _is_bag(self, item: CatalogItem) -> bool:
        text = f"{item.name} {' '.join(item.tags)}".lower()
        return bool(re.search(r"\b(bag|tote|backpack|weekender|holdall|carryall|satchel|purse|clutch)\b", text))

    def _extract_budget(self, prompt: str) -> float | None:
        match = re.search(r"(?:under|below|less than|max|budget)\s*\$?(\d{2,5})", prompt)
        return float(match.group(1)) if match else None

    def _query_for_category(self, prompt: str, category: Category, intent: Intent) -> str:
        category_terms = {
            Category.top: "premium breathable top shirt tee polo knit",
            Category.bottom: "tailored bottom chino trouser short",
            Category.shoe: "luxury shoe loafer sneaker sandal",
            Category.accessory: "accessory belt bag tote cap backpack beanie scarf",
        }
        extra = " ".join(sorted(intent.colors | intent.occasions | intent.style_signals | intent.query_terms))
        return f"{prompt} {category_terms[category]} {extra}".strip()

    def _rerank(self, candidates: list[SearchResult], intent: Intent) -> list[SearchResult]:
        reranked = []
        for result in candidates:
            score = result.score
            text = result.item.searchable_text.lower()
            for occasion in intent.occasions:
                if occasion in text:
                    score += 0.16
            for color in self._preferred_palette(intent.colors):
                if result.item.color.lower() == color:
                    score += 0.12
            if "summer" in intent.occasions and any(term in text for term in ["linen", "cotton", "lightweight"]):
                score += 0.18
            if "yacht" in intent.occasions and any(term in text for term in ["linen", "navy", "white", "loafer", "resort"]):
                score += 0.2
            for term in intent.query_terms:
                if term in text:
                    score += 0.1
            score += self._category_style_bonus(result.item, intent)
            reranked.append(SearchResult(item=result.item, score=score))
        return sorted(reranked, key=lambda result: result.score, reverse=True)

    def _category_style_bonus(self, item: CatalogItem, intent: Intent) -> float:
        text = item.searchable_text.lower()
        color = item.color.lower()
        bonus = 0.0
        if {"tech", "tech bro", "nerdy"} & intent.style_signals:
            if item.category == Category.top and any(term in text for term in ["crew", "tee", "oxford", "shirt", "standard-fit"]):
                bonus += 0.22
            if item.category == Category.bottom and any(term in text for term in ["chino", "trouser", "pant", "jean"]):
                bonus += 0.18
            if item.category == Category.shoe and any(term in text for term in ["sneaker", "loafer", "white", "black"]):
                bonus += 0.2
            if item.category == Category.accessory and any(term in text for term in ["backpack", "tote", "beanie", "cap", "belt"]):
                bonus += 0.24
        if {"suave", "pro"} & intent.style_signals:
            if any(term in text for term in ["shirt", "oxford", "silk", "linen", "trouser", "loafer", "leather", "suede"]):
                bonus += 0.18
        if "cool" in intent.style_signals:
            if color in {"black", "navy", "blue", "white", "charcoal"}:
                bonus += 0.12
            if any(term in text for term in ["sneaker", "logo", "crew", "black", "denim"]):
                bonus += 0.12
        return bonus

    def _preferred_palette(self, colors: set[str]) -> set[str]:
        palette = set(colors)
        if "navy" in colors or "blue" in colors:
            palette.update({"white", "cream", "ecru", "tan", "brown", "sand"})
        if "black" in colors:
            palette.update({"white", "grey", "charcoal", "olive"})
        if "khaki" in colors or "tan" in colors:
            palette.update({"white", "navy", "olive", "brown"})
        return palette

    async def _select_outfit(
        self,
        prompt: str,
        candidate_map: dict[Category, list[SearchResult]],
        intent: Intent,
        trace: list[AgentTraceStep],
    ) -> list[CatalogItem]:
        """Let the LLM choose one coherent item per category from the retrieved shortlist.

        Retrieval and reranking stay deterministic (cheap, auditable). Only a compact
        shortlist of facts is sent to the model, which applies fashion-pairing judgment
        the heuristics cannot. Falls back to deterministic selection on any failure.
        """

        if self.llm_provider.lower() not in {"groq", "openai"} or not self.llm_api_key:
            return self._select_items(candidate_map, intent)

        shortlist: dict[str, list[dict]] = {}
        id_lookup: dict[str, CatalogItem] = {}
        for category, results in candidate_map.items():
            options = []
            for result in results[:6]:
                item = result.item
                id_lookup[item.id] = item
                options.append(
                    {
                        "id": item.id,
                        "name": item.name,
                        "color": item.color,
                        "material": item.material,
                        "price": item.price,
                        "gender": item.gender.value,
                    }
                )
            if options:
                shortlist[category.value] = options

        if not shortlist:
            return self._select_items(candidate_map, intent)

        instruction = (
            "You are a luxury menswear/womenswear stylist building ONE coherent outfit. "
            "Choose exactly one item id from each provided category. Apply fashion rules: "
            "harmonize colors, respect the requested palette and budget, keep formality consistent "
            "with the occasion, and avoid clashing the owned pieces the client mentioned. "
            'Return STRICT JSON: {"picks": {"<category>": "<id>"}, "rationale": "<one short sentence>"}.'
        )
        context = {
            "prompt": prompt,
            "intent": {
                "gender": intent.gender.value,
                "occasions": sorted(intent.occasions),
                "colors": sorted(intent.colors),
                "style_signals": sorted(intent.style_signals),
                "max_price": intent.max_price,
                "owned_bottom": intent.owned_bottom,
            },
            "candidates": shortlist,
        }
        payload = {
            "model": self.llm_model,
            "messages": [
                {"role": "system", "content": instruction},
                {"role": "user", "content": json.dumps(context)},
            ],
            "temperature": 0.2,
            "max_tokens": 220,
            "response_format": {"type": "json_object"},
        }
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    f"{self.llm_base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.llm_api_key}"},
                    json=payload,
                )
                response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            picks = json.loads(content).get("picks", {})
            selected: list[CatalogItem] = []
            chosen_ids: set[str] = set()
            for category in intent.needs:
                pick_id = picks.get(category.value)
                if pick_id and pick_id in id_lookup and pick_id not in chosen_ids:
                    selected.append(id_lookup[pick_id])
                    chosen_ids.add(pick_id)
            # Backfill any category the model skipped with the deterministic top pick.
            if len(selected) < len(shortlist):
                fallback = self._select_items(candidate_map, intent)
                for item in fallback:
                    if item.id not in chosen_ids and item.category in {c for c in intent.needs}:
                        if not any(s.category == item.category for s in selected):
                            selected.append(item)
                            chosen_ids.add(item.id)
            if selected:
                trace.append(
                    AgentTraceStep(
                        step="llm_select",
                        detail=f"{self.llm_provider}:{self.llm_model} chose {len(selected)} items from shortlist",
                    )
                )
                return self._order_by_needs(selected, intent)
        except Exception as exc:  # pragma: no cover - external provider fallback
            logger.warning("LLM selection failed, using deterministic selection: %s", exc)
            trace.append(AgentTraceStep(step="llm_select_fallback", detail="LLM selection failed; used deterministic selection"))
        return self._select_items(candidate_map, intent)

    def _order_by_needs(self, selected: list[CatalogItem], intent: Intent) -> list[CatalogItem]:
        order = {category: index for index, category in enumerate(intent.needs)}
        return sorted(selected, key=lambda item: order.get(item.category, 99))

    def _select_items(self, candidate_map: dict[Category, list[SearchResult]], intent: Intent) -> list[CatalogItem]:
        selected: list[CatalogItem] = []
        used_colors: set[str] = set()
        for category in intent.needs:
            candidates = candidate_map.get(category, [])
            if not candidates:
                continue
            pick = candidates[0].item
            shoe_colors = self._preferred_shoe_colors(intent)
            for candidate in candidates:
                if category == Category.shoe and candidate.item.color.lower() in shoe_colors:
                    pick = candidate.item
                    break
                if candidate.item.color.lower() not in used_colors:
                    pick = candidate.item
                    break
            selected.append(pick)
            used_colors.add(pick.color.lower())
        return selected

    def _preferred_shoe_colors(self, intent: Intent) -> set[str]:
        if {"tech", "tech bro", "nerdy", "cool"} & intent.style_signals:
            return {"white", "black", "grey", "ivory", "navy", "blue"}
        return {"brown", "tan", "white", "sand", "ivory", "black"}

    def _to_recommendation(self, item: CatalogItem, intent: Intent) -> RecommendedItem:
        reason = self._reason_for_item(item, intent)
        return RecommendedItem(
            id=item.id,
            brand=item.brand,
            name=item.name,
            category=item.category,
            price=item.price,
            currency=item.currency,
            image_url=item.image_url,
            product_url=item.product_url,
            color=item.color,
            gender=item.gender,
            reason=reason,
        )

    def _reason_for_item(self, item: CatalogItem, intent: Intent) -> str:
        fabric = "breathable " if item.material.lower() in {"linen", "cotton", "cotton linen"} else ""
        occasion = next(iter(sorted(intent.occasions)), "setting")
        profile = self._style_profile(intent)
        return f"The {item.color} {fabric}{item.category.value} supports the {profile} brief while staying composed for a {occasion} look."

    def _style_profile(self, intent: Intent) -> str:
        labels = [
            str(STYLE_SIGNALS[signal]["label"])
            for signal in sorted(intent.style_signals)
            if signal in STYLE_SIGNALS
        ]
        if labels:
            return ", ".join(dict.fromkeys(labels))
        if intent.occasions:
            return ", ".join(sorted(intent.occasions))
        return "client"

    async def _stylist_note(
        self,
        prompt: str,
        selected: list[CatalogItem],
        trace: list[AgentTraceStep],
        intent: Intent,
    ) -> str:
        if self.llm_provider.lower() not in {"groq", "openai"} or not self.llm_api_key:
            return self._local_stylist_note(selected, intent)
        compact_items = [
            {
                "name": item.name,
                "brand": item.brand,
                "category": item.category.value,
                "color": item.color,
                "material": item.material,
                "price": item.price,
            }
            for item in selected
        ]
        style_payload = {
            "style_profile": self._style_profile(intent),
            "style_signals": sorted(intent.style_signals),
            "occasions": sorted(intent.occasions),
            "colors": sorted(intent.colors),
            "query_terms": sorted(intent.query_terms),
        }
        payload = {
            "model": self.llm_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a concise luxury menswear stylist. Return one elegant note under 70 words. "
                        "Do not mention unavailable products."
                    ),
                },
                {"role": "user", "content": json.dumps({"prompt": prompt, "intent": style_payload, "items": compact_items})},
            ],
            "temperature": 0.35,
            "max_tokens": 120,
        }
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    f"{self.llm_base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.llm_api_key}"},
                    json=payload,
                )
                response.raise_for_status()
            trace.append(AgentTraceStep(step="llm", detail=f"generated stylist note with {self.llm_provider}:{self.llm_model}"))
            return response.json()["choices"][0]["message"]["content"].strip()
        except Exception as exc:  # pragma: no cover - external provider fallback
            logger.warning("LLM provider failed, falling back to local note: %s", exc)
            trace.append(AgentTraceStep(step="llm_fallback", detail="external LLM failed; used local deterministic stylist"))
            return self._local_stylist_note(selected, intent)

    def _local_stylist_note(self, selected: list[CatalogItem], intent: Intent) -> str:
        colors = ", ".join(dict.fromkeys(item.color for item in selected))
        fabrics = ", ".join(dict.fromkeys(item.material for item in selected if item.material != "unknown"))
        names = [item.name for item in selected]
        profile = self._style_profile(intent)
        if len(names) > 3:
            pairing = f"{names[0]} with {names[1]}, ground it with {names[2]}, and finish with {names[3]}"
        elif len(names) > 2:
            pairing = f"{names[0]} with {names[1]} and finish with {names[2]}"
        elif len(names) > 1:
            pairing = f"{names[0]} with {names[1]}"
        else:
            pairing = names[0] if names else "the selected pieces"
        return (
            f"For a {profile} brief, the {colors} palette gives the outfit quiet polish while "
            f"{fabrics or 'premium textures'} keep it intentional. Pair {pairing} for a look that reads specific, not generic."
        )
