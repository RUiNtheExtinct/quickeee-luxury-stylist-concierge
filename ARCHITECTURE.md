# Architecture

## Goal

Build a context-aware luxury shopping assistant that can ingest apparel inventory, retrieve relevant products with RAG, and return a structured outfit recommendation through a single API endpoint.

## System Components

### Scraping Layer

`scripts/scrape_catalog.py` collects catalog data from four public apparel websites (more than the assignment's two-site minimum, for catalog breadth across tops, bottoms, shoes, and accessories):

- Everlane
- Taylor Stitch
- Koio
- Nisolo

The primary path reads Shopify product feeds because they expose clean product structure without brittle CSS selectors. The script still includes an optional Playwright DOM fallback for JavaScript-heavy collection pages. The scraper normalizes every product into:

- `id`
- `brand`
- `source`
- `name`
- `price`
- `currency`
- `image_url`
- `product_url`
- `category`
- `gender`
- `description`
- `color`
- `material`
- `tags`

**Structured extraction over free-text scanning.** Earlier the scraper guessed `color` by scanning concatenated title+description+tags for the first color word, which mislabeled products (a gold sandal became "black" because "black" appeared elsewhere in the copy). The scraper now reads Shopify's *structured* signals first and only falls back to text:

- **Color** prefers tagged values (`Primary Color: Green`, `Color:Green`, `color-greige`) and the human-readable color option (`Marigold`), then falls back to the product name/handle. Values are canonicalized onto a compact, stylable palette (e.g. `marigold`/`gold` → `yellow`, `greige` → `stone`), with a small alias map for poetic brand color names (e.g. `Heathered Oat` → `cream`).
- **Material** prefers tagged values (`Primary Material: Organic Cotton`).
- **Gender** is derived from `product_type` ("Men's Leather Slip On"), `handle` (`womens-...`), and tags (`MENS`, `women's`) — never the display name. This is what stops a women's sandal from appearing in a men's brief.

**Rate-limit handling and resilience.** The Shopify fetch (`fetch_brand_products`) uses randomized user agents, jittered delays, and **exponential backoff that honors `Retry-After` on 429/503** — a brand that throttles or returns a transient error is retried rather than crashing the run, and a brand that fails outright is skipped with a warning instead of aborting the whole scrape.

**Complex DOM fallback (real, not vestigial).** When a brand blocks its JSON feed or renders inventory behind client-side state, `scripts/scrape_catalog.py --use-playwright` drives a headless Chromium that scrolls, waits, and reads product-card text/images, then funnels those records through the same `classify`/`extract_color`/`detect_gender` helpers into `CatalogItem`s. The JSON feed is the preferred path (richer, cleaner) but the DOM path is wired in and reachable, satisfying the "handle complex DOM structures gracefully" requirement.

`data/catalog.scraped.sample.json` stores a representative scraper run, and the checked-in 420-item seed catalog (balanced 160 tops / 120 bottoms / 60 shoes / 80 accessories, with gender and clean colors) exists so the demo remains reliable even if a retailer blocks traffic during review.

### Vector Memory

The app supports two vector backends behind the same interface:

- `qdrant`: real vector DB for Docker Compose and Qdrant Cloud.
- `local_json`: deploy-anywhere fallback that persists vectors to `data/vector_store.json`.

Metadata is stored alongside every vector so retrieval can filter *before* the semantic search runs (Qdrant payload indexes back each of these):

- `category`
- `price`
- `color`
- `gender`

Gender filtering always includes `unisex` pieces alongside the requested gender, so a women's brief retrieves women's + unisex items and never men's.

The default embedding implementation uses FastEmbed with `BAAI/bge-small-en-v1.5`, a local 384-dimensional neural embedding model. This keeps retrieval model-backed without paid embedding API calls. A deterministic hashing embedder remains as an emergency fallback if a free host cannot initialize the model.

### Database Schema

Each catalog item is one Qdrant point: a 384-dim cosine vector (the embedded `searchable_text`) plus a JSON payload. The payload doubles as both the returned product record and the filter surface.

| Field | Type | Indexed | Notes |
|---|---|---|---|
| `id` | string | (point id) | stable SHA1-derived id |
| `brand` | string | no | e.g. "Everlane" |
| `source` | string | no | retailer base URL |
| `name` | string | no | product title |
| `price` | float | **yes** (range) | filterable: `price <= max` |
| `currency` | string | no | default `USD` |
| `image_url` | string | no | product image |
| `product_url` | string | no | link back to retailer |
| `category` | keyword | **yes** (match) | `top` \| `bottom` \| `shoe` \| `accessory` |
| `gender` | keyword | **yes** (match) | `men` \| `women` \| `unisex` |
| `color` | keyword | **yes** (match) | canonicalized palette |
| `material` | string | no | e.g. `linen`, `leather` |
| `tags` | string[] | no | normalized lowercase tags |

Vector params: `size=384`, `distance=Cosine`. Payload indexes on `price` (float/range), `category`/`gender`/`color` (keyword/match) are what make the "filter before semantic search" requirement true pre-filtering rather than post-hoc filtering. The same shape backs the local-JSON fallback store, where the filters run as Python predicates before cosine scoring.

### Agent Workflow

`app/agent.py` runs a compact agentic workflow:

1. Check semantic cache before any retrieval.
2. Extract intent from the prompt: gender, colors, occasion, budget, owned garments, style signals, and required categories.
3. Query vector memory once per needed category, **pre-filtered by gender and budget** so the candidate set is already coherent.
4. Rerank candidates with fashion-aware signals such as color harmony, summer fabrics, yacht/resort vocabulary, tech/pro/cool/nerdy vocabulary, and material suitability.
5. **LLM reasoning step** — in a single call, the model selects one coherent item per category from the reranked shortlist *and* writes the stylist note (see below).
6. Return a structured JSON payload.

The workflow is intentionally auditable. The response includes `trace`, so a reviewer can see the steps (`intent`, `retrieve_*`, `llm_compose`, `rank`) without exposing hidden chain-of-thought.

This is a "native routing" agent in the assignment's sense: deterministic tools (retrieval, reranking, filtering) gather and shape the context, and the LLM makes the actual judgment call over that context. It is intentionally not a multi-hop LangChain/LangGraph loop — for a fixed three-step fashion task (retrieve → reason → compose) a single well-shaped reasoning call is more reliable, far cheaper, and easier to audit than an open-ended agent loop.

### The reasoning step: deterministic retrieval, LLM judgment, one call

Retrieval and reranking stay deterministic — they are cheap, fast, and explainable. The actual *outfit decision* and the prose are where fashion judgment matters, so both are delegated to the LLM in **one combined call**: the agent sends a compact shortlist (top ~6 candidates per category, each a small fact object — id, name, brand, color, material, price, gender) plus the parsed intent, and asks the model to return strict JSON with both the chosen ids per category and the stylist note. This is what the assignment means by "the LLM must evaluate fashion rules": the model harmonizes colors, honors the requested palette/budget/gender, keeps formality consistent with the occasion, and complements owned pieces.

Collapsing what used to be two LLM calls (select, then note) into one halves both token spend and request count — friendlier to free-tier rate limits and a concrete frugal-mindset win — and removes a failure point. The call uses `temperature=0.7` for inventive, characterful styling and `reasoning_effort=low` so reasoning-capable models (Groq's `gpt-oss`) emit clean JSON instead of burning the budget on hidden chain-of-thought.

It degrades gracefully: if no LLM key is configured, or the call fails after retry/backoff, or the model returns unusable ids, the agent falls back to deterministic selection (palette preference + color diversity) and a templated note. The `token_strategy` field in the response reports exactly which path ran and the real token count spent.

### LLM Strategy

The hosted demo uses `LLM_PROVIDER=groq` with `openai/gpt-oss-120b` over Groq's OpenAI-compatible API. Setting `LLM_PROVIDER=local` (or simply leaving the key blank) runs a fully deterministic stylist with no paid key, so the project is always runnable. The HTTP call (`_chat_completion`) retries 429/5xx with exponential backoff that honors `Retry-After`, so a transient free-tier rate limit recovers instead of silently degrading.

This prompt shape is frugal:

- No full catalog is sent to the LLM — only ~6 candidate facts per needed category.
- Retrieval and reranking happen first; the LLM sees a pre-filtered shortlist.
- Selection and the note are one combined call, not two.
- Responses are capped with `max_tokens` and `reasoning_effort=low`.
- Similar prompts short-circuit on the semantic cache, skipping the LLM entirely.

### Semantic Cache

`app/cache.py` stores prompt embeddings and full responses. Cache entries are namespaced by agent version, embedding model, **and the active LLM signature** (`provider:model`, or `local`). The LLM part matters: without it, a note generated in deterministic `local` mode could be served after Groq was enabled (and vice-versa). Namespacing by the response-shaping config guarantees a cached response always matches the pipeline that would generate it fresh. Entries are also scoped by a per-request **variant key** (gender, accessory mode, budget bucket, currency), so the same prompt with different preferences never collides on a stale result. A similar prompt above the configured similarity threshold and with a matching variant returns a cached response, preventing repeated LLM calls and repeated retrieval work for common styling requests.

### API

Required endpoint:

```http
POST /api/v1/style-me
```

Request:

```json
{
  "prompt": "I have dark navy chinos, what t-shirt and shoes should I wear for a summer yacht party?",
  "max_price": 500,
  "gender": "either",
  "accessories": "auto",
  "include_trace": true
}
```

`gender` (`men` | `women` | `either`, default `either`) and `accessories` (`auto` | `on` | `off`, default `auto`) are optional. They are metadata-filter knobs surfaced as controls in the UI:

- `gender` — an explicit choice overrides prompt inference and filters retrieval to that gender plus unisex. `either` falls back to inferring from the prompt (defaulting to menswear). This is what stops women's pieces from appearing in a men's brief.
- `accessories` — `auto` adds a finishing accessory only when the prompt implies one (and steers away from bags/totes unless the prompt asks for a bag); `on` always adds one; `off` never does. This addresses unwanted auto-recommended bags.

Response:

```json
{
  "request_id": "...",
  "cache_hit": false,
  "recommended_items": [],
  "total_price": 0,
  "currency": "USD",
  "stylist_note": "...",
  "token_strategy": "...",
  "trace": []
}
```

### UI

The app serves a concierge console at `/`. It is not a mock: the form calls the live API, renders returned products, shows the total, and displays the agent trace in Engineer mode. The inventory preview is paginated with `limit` and `offset`, then lazy-loaded in the browser so larger seed catalogs do not force the page to render every product at once. The UI also ships a custom SVG brand mark plus generated PNG favicons under `app/static/icons/`.

## Deployment Choices

### Local Full Stack

`docker-compose.yml` runs FastAPI and Qdrant.

### Free Hosted Demo

`render.yaml` deploys a single Docker web service using Qdrant Cloud free tier for vector memory and Groq for hosted stylist notes. FastEmbed still runs locally in the app, so embedding generation does not require a paid embedding API.

### Zero-Key Local Fallback

For a zero-service local fallback, set:

```env
VECTOR_BACKEND=local_json
LLM_PROVIDER=local
```

For Qdrant Cloud, set:

```env
VECTOR_BACKEND=qdrant
QDRANT_URL=...
QDRANT_API_KEY=...
QDRANT_COLLECTION=quickeee_catalog
```

For hosted stylist notes, set:

```env
LLM_PROVIDER=groq
LLM_API_KEY=...
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.3-70b-versatile
```

## State Management

The service keeps state in three places:

- Catalog JSON: durable source inventory for demo/review.
- Vector store: derived index from the catalog.
- Semantic cache: derived response cache for frugal repeated use.

All three are rebuildable. The source of truth remains the catalog.

## Free-Tier Protection

`POST /api/v1/style-me` has a lightweight in-memory per-IP rate limit, configured by `RATE_LIMIT_PER_MINUTE`. The default is `30` requests per minute, which is enough for review demos while preventing accidental hammering on the free Render service. A production version would move this to Redis or an edge gateway, but adding that dependency would work against the assignment's frugal deployment goal.
