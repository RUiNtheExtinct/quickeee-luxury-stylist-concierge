# Architecture

## Goal

Build a context-aware luxury shopping assistant that can ingest apparel inventory, retrieve relevant products with RAG, and return a structured outfit recommendation through a single API endpoint.

## System Components

### Scraping Layer

`scripts/scrape_catalog.py` collects catalog data from at least two public apparel websites:

- Everlane
- Taylor Stitch

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
- `description`
- `color`
- `material`
- `tags`

Scraper rate-limit handling is intentionally simple and frugal: randomized user agents, jittered delays, timeouts, and deduplication. `data/catalog.scraped.sample.json` stores a representative scraper run, and the checked-in 362-item seed catalog exists so the demo remains reliable even if a retailer blocks traffic during review.

### Vector Memory

The app supports two vector backends behind the same interface:

- `qdrant`: real vector DB for Docker Compose and Qdrant Cloud.
- `local_json`: deploy-anywhere fallback that persists vectors to `data/vector_store.json`.

Metadata is stored alongside every vector so retrieval can filter by:

- `category`
- `price`
- `color`

The embedding implementation uses deterministic local hashing embeddings. This is deliberate for the assignment: it removes paid embedding calls, avoids rate-limit failures during demos, and keeps deployment free. The interface can be swapped for hosted embeddings later without changing the API contract.

### Agent Workflow

`app/agent.py` runs a compact agentic workflow:

1. Check semantic cache before any retrieval.
2. Extract intent from the prompt: colors, occasion, budget, owned garments, and required categories.
3. Query vector memory once per needed category.
4. Rerank candidates with fashion-aware signals such as color harmony, summer fabrics, yacht/resort vocabulary, and material suitability.
5. Select a coherent outfit.
6. Generate a stylist note.
7. Return a structured JSON payload.

The workflow is intentionally auditable. The response includes `trace`, so a reviewer can see the steps without exposing hidden chain-of-thought.

### LLM Strategy

The default `LLM_PROVIDER=local` mode uses a deterministic local stylist note generator. That makes the project fully runnable with no paid key. If `LLM_PROVIDER=groq` or `LLM_PROVIDER=openai` and an API key are configured, the app sends only compact item facts to an OpenAI-compatible chat completion endpoint.

This prompt shape is frugal:

- No full catalog is sent to the LLM.
- Retrieval happens before note generation.
- Only selected item names, colors, materials, categories, and prices are sent.
- Responses are capped with `max_tokens`.

### Semantic Cache

`app/cache.py` stores prompt embeddings and full responses. A similar prompt above the configured similarity threshold returns a cached response. This prevents repeated LLM calls and repeated retrieval work for common styling requests.

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
  "include_trace": true
}
```

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

`render.yaml` deploys a single Docker web service using `VECTOR_BACKEND=local_json`. That avoids paying for a hosted vector DB and keeps the public demo simple.

### Free Production-Style Upgrade

For a more realistic hosted vector DB, use Qdrant Cloud free tier and set:

```env
VECTOR_BACKEND=qdrant
QDRANT_URL=...
QDRANT_API_KEY=...
```

## State Management

The service keeps state in three places:

- Catalog JSON: durable source inventory for demo/review.
- Vector store: derived index from the catalog.
- Semantic cache: derived response cache for frugal repeated use.

All three are rebuildable. The source of truth remains the catalog.

## Free-Tier Protection

`POST /api/v1/style-me` has a lightweight in-memory per-IP rate limit, configured by `RATE_LIMIT_PER_MINUTE`. The default is `30` requests per minute, which is enough for review demos while preventing accidental hammering on the free Render service. A production version would move this to Redis or an edge gateway, but adding that dependency would work against the assignment's frugal deployment goal.
