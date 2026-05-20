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

- The public Render deployment uses the frugal `local_json` vector backend so it can stay on a free web service without a paid vector database.
- The same code supports Qdrant via Docker Compose or Qdrant Cloud by changing environment variables.
- The app intentionally works without an LLM key. If a Groq/OpenAI-compatible key is configured, only compact selected item facts are sent to the LLM after retrieval.
- `data/catalog.scraped.sample.json` is a representative live scraper output from public apparel sources.
- `data/catalog.seed.json` is the stable deploy/demo catalog used by the hosted service.

## Documentation

- Architecture: `ARCHITECTURE.md`
- System flow: `SYSTEM_FLOW.md`
- Deployment: `DEPLOYMENT.md`
- Assignment copy: `Quickeee Gen AI Assignment.md`
