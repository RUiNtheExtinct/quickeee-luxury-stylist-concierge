# System Flow

```mermaid
flowchart TD
    A["Public apparel websites<br/>Everlane · Taylor Stitch · Koio · Nisolo"] --> B["Scraper<br/>Shopify feed + optional Playwright DOM fallback"]
    B --> C["Clean catalog JSON<br/>name, price, image, category, gender, color, material"]
    C --> D["Embedding pipeline<br/>FastEmbed BGE-small neural vectors"]
    D --> E{"Vector backend"}
    E --> F["Qdrant<br/>payload indexes: category, color, gender, price"]
    E --> G["Local JSON vector store<br/>free deploy fallback"]
    H["User prompt"] --> I["POST /api/v1/style-me"]
    I --> U["Free-tier rate limit<br/>30 requests/min/IP by default"]
    U --> J["Semantic cache lookup<br/>namespaced by agent + embedder + LLM"]
    J -->|hit| R["Structured JSON response"]
    J -->|miss| K["Intent extraction<br/>gender, occasion, colors, budget, owned garments"]
    K --> L["Pre-filtered vector retrieval<br/>gender + price filter, style-enriched query"]
    F --> L
    G --> L
    L --> M["Fashion reranker<br/>palette, material, occasion rules"]
    M --> N{"LLM provider configured?"}
    N -->|yes| O["LLM-driven selection<br/>picks one coherent item per category<br/>over the retrieved shortlist (strict JSON)"]
    N -->|no| P["Deterministic selection<br/>palette + color-diversity rules"]
    O --> Q["Stylist note<br/>compact LLM or local deterministic"]
    P --> Q
    Q --> R
    R --> S["Concierge UI<br/>Atelier + Engineer modes"]
    S --> W["Paginated inventory preview<br/>lazy-loaded in 100-item chunks"]
    R --> V["Swagger API demo"]
    R --> T["Cache write for similar future prompts"]
```

## Demo Path

1. Start the app.
2. Open `/` for the concierge UI or `/docs` for Swagger.
3. Submit:

```text
I have dark navy chinos, what t-shirt and shoes should I wear for a summer yacht party?
```

4. Show returned items, total price, stylist note, and trace.
5. Submit the same or similar prompt again to show `cache_hit: true`.
