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

Scraper rate-limit handling is intentionally simple and frugal: randomized user agents, jittered delays, timeouts, and deduplication. `data/catalog.scraped.sample.json` stores a representative scraper run, and the checked-in 420-item seed catalog (balanced 160 tops / 120 bottoms / 60 shoes / 80 accessories, with gender and clean colors) exists so the demo remains reliable even if a retailer blocks traffic during review.

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

### Agent Workflow

`app/agent.py` runs a compact agentic workflow:

1. Check semantic cache before any retrieval.
2. Extract intent from the prompt: gender, colors, occasion, budget, owned garments, style signals, and required categories.
3. Query vector memory once per needed category, **pre-filtered by gender and budget** so the candidate set is already coherent.
4. Rerank candidates with fashion-aware signals such as color harmony, summer fabrics, yacht/resort vocabulary, tech/pro/cool/nerdy vocabulary, and material suitability.
5. **LLM-driven selection** — the model picks one coherent item per category from the reranked shortlist (see below).
6. Generate a stylist note.
7. Return a structured JSON payload.

The workflow is intentionally auditable. The response includes `trace`, so a reviewer can see the steps (`intent`, `retrieve_*`, `llm_select`, `rank`, `llm`) without exposing hidden chain-of-thought.

### Selection: deterministic retrieval, LLM judgment

Retrieval and reranking stay deterministic — they are cheap, fast, and explainable. The actual *outfit decision* is where fashion judgment matters, so it is delegated to the LLM: the agent sends a compact shortlist (top ~6 candidates per category, each as a small fact object — id, name, color, material, price, gender) plus the parsed intent, and asks the model to return strict JSON choosing one id per category with a one-line rationale. This is what the assignment means by "the LLM must evaluate fashion rules": the model harmonizes colors, honors the requested palette/budget, keeps formality consistent with the occasion, and avoids clashing with owned pieces.

This is still frugal — the full catalog is never sent, only a handful of facts per category — and it degrades gracefully: if no LLM key is configured, or the call fails, or the model returns an unusable id, the agent falls back to deterministic selection (palette preference + color diversity). The previous bug where a brown top was chosen for a "cream and tan" brief is fixed because selection now reasons over the requested palette instead of just taking the top reranked hit.

### LLM Strategy

The default `LLM_PROVIDER=local` mode uses a deterministic local stylist note generator. That makes the project fully runnable with no paid key. If `LLM_PROVIDER=groq` or `LLM_PROVIDER=openai` and an API key are configured, the app sends only compact item facts to an OpenAI-compatible chat completion endpoint.

This prompt shape is frugal:

- No full catalog is sent to the LLM.
- Retrieval happens before note generation.
- Only selected item names, colors, materials, categories, and prices are sent.
- Responses are capped with `max_tokens`.

### Semantic Cache

`app/cache.py` stores prompt embeddings and full responses. Cache entries are namespaced by agent version, embedding model, **and the active LLM signature** (`provider:model`, or `local`). The LLM part matters: without it, a note generated in deterministic `local` mode could be served after Groq was enabled (and vice-versa). Namespacing by the response-shaping config guarantees a cached response always matches the pipeline that would generate it fresh. A similar prompt above the configured similarity threshold returns a cached response, preventing repeated LLM calls and repeated retrieval work for common styling requests.

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
