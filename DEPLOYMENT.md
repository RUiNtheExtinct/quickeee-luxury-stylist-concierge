# Deployment

## Recommended Free Path

Use Render for the public web service and keep `VECTOR_BACKEND=local_json`. This deploys as one Docker web service, which is the simplest free setup for a reviewer to open.

```bash
git init
git add .
git commit -m "Build Quickeee luxury stylist concierge"
gh repo create quickeee-luxury-stylist --public --source=. --push
```

Then connect the GitHub repo to Render. The included `render.yaml` configures the service.

## Production-Style Vector DB

Use Qdrant Cloud free tier when you want a managed vector database:

```env
VECTOR_BACKEND=qdrant
QDRANT_URL=https://your-qdrant-cluster-url
QDRANT_API_KEY=your-qdrant-api-key
QDRANT_COLLECTION=quickeee_catalog
```

## Optional Hosted LLM

The project works without an LLM key. To show a hosted model in the demo, set:

```env
LLM_PROVIDER=groq
LLM_API_KEY=your-key
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.3-70b-versatile
```

## Accounts Needed

To provision the hosted services, use:

- GitHub: public repository
- Render: free web service
- Qdrant Cloud: optional free vector cluster
- Groq or OpenAI-compatible provider: optional hosted stylist note

No paid database is required. The hosted demo also keeps `RATE_LIMIT_PER_MINUTE=30` by default so the free service is harder to exhaust during review.
