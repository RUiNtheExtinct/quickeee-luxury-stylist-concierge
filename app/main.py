from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import Deque

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.dependencies import container
from app.models import CatalogItem, HealthResponse, StyleRequest, StyleResponse

settings = get_settings()
logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)
rate_limit_window: dict[str, Deque[float]] = defaultdict(deque)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await container.startup()
    logger.info("Quickeee stylist ready with %s items", len(container.catalog.load()))
    yield


app = FastAPI(
    title="Quickeee Luxury Stylist Concierge",
    version="0.1.0",
    description="Agentic RAG pipeline for real-time fashion styling recommendations.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    # Public, credential-free JSON API: wildcard origins are fine, but
    # allow_credentials must stay False — the two are invalid together per the
    # CORS spec, and browsers refuse credentialed wildcard requests anyway.
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "HEAD", "OPTIONS"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", include_in_schema=False)
async def console() -> FileResponse:
    return FileResponse("app/static/index.html")


@app.head("/", include_in_schema=False)
async def console_head() -> Response:
    return Response(status_code=200)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        catalog_items=len(container.catalog.load()),
        vector_backend=container.vector_store.backend_name,
        embedding_provider=settings.embedding_provider,
        embedding_model=settings.embedding_model,
        llm_provider=settings.llm_provider,
    )


@app.head("/health", include_in_schema=False)
async def health_head() -> Response:
    return Response(status_code=200)


@app.post("/api/v1/style-me", response_model=StyleResponse)
async def style_me(request: StyleRequest, http_request: Request) -> StyleResponse:
    enforce_rate_limit(http_request)
    return await container.agent.recommend(request)


@app.get("/api/v1/catalog", response_model=list[CatalogItem])
async def catalog(limit: int = 24, offset: int = 0) -> list[CatalogItem]:
    items = container.catalog.load()
    safe_limit = max(1, min(limit, 100))
    safe_offset = max(0, offset)
    return items[safe_offset : safe_offset + safe_limit]


def enforce_rate_limit(request: Request) -> None:
    if settings.rate_limit_per_minute <= 0:
        return
    forwarded_for = request.headers.get("x-forwarded-for", "")
    client_ip = forwarded_for.split(",")[0].strip() if forwarded_for else ""
    if not client_ip and request.client:
        client_ip = request.client.host
    key = client_ip or "anonymous"
    now = time.time()
    hits = rate_limit_window[key]
    while hits and now - hits[0] > 60:
        hits.popleft()
    if len(hits) >= settings.rate_limit_per_minute:
        raise HTTPException(
            status_code=429,
            detail="Stylist is pacing requests to protect the free demo. Please try again in a minute.",
        )
    hits.append(now)
