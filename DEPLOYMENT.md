# Deployment

## Recommended Free Path

Use Render for the public web service, Qdrant Cloud free tier for vector search, local FastEmbed embeddings, and Groq for hosted stylist notes. This keeps the demo production-shaped while still staying on free or low-friction services.

```bash
git init
git add .
git commit -m "Build Quickeee luxury stylist concierge"
gh repo create quickeee-luxury-stylist --public --source=. --push
```

Then connect the GitHub repo to Render. The included `render.yaml` configures the service.

The Render path uses real local embeddings:

```env
EMBEDDING_PROVIDER=fastembed
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_DIMENSIONS=384
```

## Production-Style Vector DB

Use Qdrant Cloud free tier for the managed vector database:

```env
VECTOR_BACKEND=qdrant
QDRANT_URL=https://your-qdrant-cluster-url
QDRANT_API_KEY=your-qdrant-api-key
QDRANT_COLLECTION=quickeee_catalog
QDRANT_RECREATE_ON_STARTUP=false
```

## Hosted LLM

The hosted demo uses Groq's OpenAI-compatible endpoint:

```env
LLM_PROVIDER=groq
LLM_API_KEY=your-key
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.3-70b-versatile
```

Without `LLM_API_KEY`, the app can fall back to its deterministic local stylist note for zero-key development.

## Accounts Needed

To provision the hosted services, use:

- GitHub: public repository
- Render: free web service
- Qdrant Cloud: free vector cluster
- Groq: hosted stylist note

No paid database is required. The hosted demo also keeps `RATE_LIMIT_PER_MINUTE=30` by default so the free service is harder to exhaust during review.
