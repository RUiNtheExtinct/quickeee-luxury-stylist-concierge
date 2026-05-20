# Quickeee Luxury Stylist Concierge

An end-to-end Gen AI and data engineering assignment for a premium fashion concierge. The service scrapes apparel inventory, embeds the catalog, stores/searches it through a vector layer, and exposes a polished FastAPI + web console experience for outfit recommendations.

## What It Does

![Quickeee atelier empty state](docs/atelier-empty-screenshot.png)

![Quickeee concierge UI](docs/demo-screenshot.png)

![Quickeee engineer mode](docs/engineer-mode-screenshot.png)

- Live demo: `https://quickeee-luxury-stylist.onrender.com`
- Swagger/API docs: `https://quickeee-luxury-stylist.onrender.com/docs`
- Public repository: `https://github.com/RUiNtheExtinct/quickeee-luxury-stylist-concierge`

- Scrapes public apparel catalogs from two Shopify-backed fashion brands.
- Normalizes products into clean JSON: name, price, image URL, category, description, color, material, source.
- Indexes 410 curated products with FastEmbed/BGE vectors into Qdrant locally through Docker Compose, Qdrant Cloud, or a zero-service local vector fallback for free hosting.
- Runs an agentic styling workflow with intent extraction, style-signal enriched vector retrieval, reranking, semantic cache, rate limiting, and structured JSON output.
- Serves a luxury concierge UI at `/` with default Atelier mode, reviewer-facing Engineer mode, lazy-loaded inventory preview, and a custom SVG/PNG brand mark.

## Fast Start

```bash
cp .env.example .env
uv venv --python 3.13 .venv
source .venv/bin/activate
uv pip install -e ".[dev,scrape]"
python scripts/generate_seed_catalog.py
uvicorn app.main:app --reload
```

Open:

- Concierge UI: `http://localhost:8000`
- Swagger API demo: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

## Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

This runs:

- `api`: FastAPI app on port `8000`
- `qdrant`: local vector DB on port `6333`

## API Demo

```bash
curl -X POST http://localhost:8000/api/v1/style-me \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "I have dark navy chinos, what t-shirt and shoes should I wear for a summer yacht party?",
    "include_trace": true
  }'
```

Hosted API demo:

```bash
curl -X POST https://quickeee-luxury-stylist.onrender.com/api/v1/style-me \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "I have dark navy chinos, what t-shirt and shoes should I wear for a summer yacht party?",
    "include_trace": true
  }'
```

The response includes:

- `recommended_items`
- `total_price`
- `stylist_note`
- `token_strategy`
- `trace`
- `cache_hit`

## Scraping

```bash
python scripts/scrape_catalog.py --output data/catalog.live.json
```

The scraper targets:

- Everlane
- Taylor Stitch

It uses randomized user agents, polite jitter, normalized Shopify product feeds, HTML cleanup, category classification, color/material extraction, and an optional Playwright DOM fallback for JavaScript-heavy pages.

## Free Deployment Strategy

Default deploy path uses one Render web service with Qdrant Cloud free tier, local FastEmbed embeddings, and Groq for hosted stylist notes. The local JSON vector store and deterministic stylist remain as fallback modes for zero-key demos.

```env
EMBEDDING_PROVIDER=fastembed
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_DIMENSIONS=384
```

```env
VECTOR_BACKEND=qdrant
QDRANT_URL=https://your-cluster-url
QDRANT_API_KEY=your-key
QDRANT_COLLECTION=quickeee_catalog
QDRANT_RECREATE_ON_STARTUP=false
```

The hosted model uses Groq's OpenAI-compatible API:

```env
LLM_PROVIDER=groq
LLM_API_KEY=your-key
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.3-70b-versatile
```

## Repository Structure

```text
app/
  agent.py          # intent, retrieval, reranking, note generation
  cache.py          # semantic cache for repeated/similar prompts
  catalog.py        # catalog loading and category counts
  config.py         # environment settings
  embeddings.py     # FastEmbed BGE embeddings plus hashing fallback
  main.py           # FastAPI app and routes
  models.py         # Pydantic request/response/catalog models
  vector_store.py   # Qdrant and local JSON vector implementations
  static/           # concierge UI, logo, favicons, vendored icons
data/
  catalog.seed.json # checked-in demo catalog, 410 tops/bottoms/shoes/accessories
  catalog.scraped.sample.json # scraper output sample from public apparel sites
scripts/
  generate_seed_catalog.py
  scrape_catalog.py
tests/
```

## Submission Checklist

- Public GitHub repository
- `ARCHITECTURE.md`
- `SYSTEM_FLOW.md`
- Demo recording showing UI or Swagger, JSON response, and terminal logs
- API endpoint demo: `POST /api/v1/style-me`
