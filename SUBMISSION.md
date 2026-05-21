# Quickeee Assignment Submission

## Public Links

- Repository: `https://github.com/RUiNtheExtinct/quickeee-luxury-stylist-concierge`
- Live demo: `https://quickeee-luxury-stylist.onrender.com`
- Swagger/API docs: `https://quickeee-luxury-stylist.onrender.com/docs`
- Health check: `https://quickeee-luxury-stylist.onrender.com/health`

## API Endpoint Demo

```bash
curl -X POST https://quickeee-luxury-stylist.onrender.com/api/v1/style-me \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "I have dark navy chinos, what t-shirt and shoes should I wear for a summer yacht party?",
    "include_trace": true
  }'
```

## Notes For Reviewers

- The public Render deployment uses Qdrant Cloud for vector memory and Groq for hosted stylist notes.
- Retrieval uses FastEmbed with `BAAI/bge-small-en-v1.5` locally, so embeddings are model-backed without an embedding API bill.
- The same code supports Qdrant via Docker Compose or Qdrant Cloud by changing environment variables.
- The LLM does the final outfit selection: after gender/budget-filtered retrieval and fashion reranking, a compact shortlist of item facts is sent to Groq, which picks one coherent piece per category as strict JSON. The full catalog is never sent to the LLM, and a deterministic selector is the fallback when no key is configured.
- Gender, color, and material are extracted from Shopify's structured signals (tags, options, product type/handle), which fixes earlier mislabels (e.g. a women's gold sandal previously surfaced as a "black" men's item).
- `data/catalog.scraped.sample.json` is a representative live scraper output from public apparel sources.
- `data/catalog.seed.json` is the stable 420-item deploy/demo catalog (balanced across categories, with a `gender` field) used by the hosted service.
- The UI has a default Atelier mode for normal reviewers and an Engineer mode for agent trace, cache state, vector backend, embedding model, LLM provider, and raw response JSON.
- The inventory preview is lazy-loaded in 100-item chunks, and cards use fixed image/info regions for consistent sizing across breakpoints.
- The website includes a custom SVG logo, PNG favicons, and a web manifest.
- `POST /api/v1/style-me` includes a lightweight free-tier rate limit of `30` requests per minute per IP by default.

## Documentation

- Architecture: `ARCHITECTURE.md`
- System flow: `SYSTEM_FLOW.md`
- Deployment: `DEPLOYMENT.md`
- Assignment copy: `Quickeee Gen AI Assignment.md`
