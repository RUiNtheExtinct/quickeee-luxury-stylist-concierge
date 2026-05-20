# Quickeee Luxury Stylist Concierge

An end-to-end Gen AI and data engineering assignment for a premium fashion concierge. The service scrapes apparel inventory, embeds the catalog, stores/searches it through a vector layer, and exposes a polished FastAPI + web console experience for outfit recommendations.

## What It Does

![Quickeee concierge UI](docs/demo-screenshot.png)

- Live demo: `https://quickeee-luxury-stylist.onrender.com`
- Swagger/API docs: `https://quickeee-luxury-stylist.onrender.com/docs`
- Public repository: `https://github.com/RUiNtheExtinct/quickeee-luxury-stylist-concierge`

- Scrapes public apparel catalogs from two Shopify-backed fashion brands.
- Normalizes products into clean JSON: name, price, image URL, category, description, color, material, source.
- Indexes products into Qdrant locally through Docker Compose, or into a zero-service local vector fallback for free hosting.
- Runs an agentic styling workflow with intent extraction, vector retrieval, reranking, semantic cache, and structured JSON output.
- Serves a luxury concierge UI at `/` and the required API at `POST /api/v1/style-me`.

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

Default deploy path uses one Render web service with the local JSON vector fallback. That keeps the app deployable without paying for a hosted database. For a stronger production-style demo, point the same app at a free Qdrant Cloud cluster:

```env
VECTOR_BACKEND=qdrant
QDRANT_URL=https://your-cluster-url
QDRANT_API_KEY=your-key
QDRANT_COLLECTION=quickeee_catalog
```

The LLM layer is also frugal by default:

```env
LLM_PROVIDER=local
```

For a hosted model, use any OpenAI-compatible provider:

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
  embeddings.py     # deterministic local embeddings
  main.py           # FastAPI app and routes
  models.py         # Pydantic request/response/catalog models
  vector_store.py   # Qdrant and local JSON vector implementations
  static/           # concierge UI
data/
  catalog.seed.json # checked-in demo catalog, 55 tops + 55 bottoms + shoes
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
