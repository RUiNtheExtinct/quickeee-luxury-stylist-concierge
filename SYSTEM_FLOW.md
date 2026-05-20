# System Flow

```mermaid
flowchart TD
    A["Public apparel websites<br/>Everlane + Taylor Stitch"] --> B["Scraper<br/>Shopify feed + optional Playwright DOM fallback"]
    B --> C["Clean catalog JSON<br/>name, price, image, category, description, color, material"]
    C --> D["Embedding pipeline<br/>deterministic local embeddings"]
    D --> E{"Vector backend"}
    E --> F["Qdrant<br/>Docker or Qdrant Cloud"]
    E --> G["Local JSON vector store<br/>free deploy fallback"]
    H["User prompt"] --> I["POST /api/v1/style-me"]
    I --> J["Semantic cache lookup"]
    J -->|hit| R["Structured JSON response"]
    J -->|miss| K["Intent extraction<br/>occasion, colors, budget, owned garments"]
    K --> L["Category-aware vector retrieval"]
    F --> L
    G --> L
    L --> M["Fashion reranker<br/>palette, material, occasion rules"]
    M --> N["Outfit selection"]
    N --> O{"LLM provider configured?"}
    O -->|yes| P["Compact LLM stylist note<br/>selected item facts only"]
    O -->|no| Q["Local deterministic stylist note"]
    P --> R
    Q --> R
    R --> S["Concierge UI + Swagger demo"]
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
