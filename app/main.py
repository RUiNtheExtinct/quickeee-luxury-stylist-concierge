from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.dependencies import container
from app.models import CatalogItem, HealthResponse, StyleRequest, StyleResponse

settings = get_settings()
logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
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
        llm_provider=settings.llm_provider,
    )


@app.head("/health", include_in_schema=False)
async def health_head() -> Response:
    return Response(status_code=200)


@app.post("/api/v1/style-me", response_model=StyleResponse)
async def style_me(request: StyleRequest) -> StyleResponse:
    return await container.agent.recommend(request)


@app.get("/api/v1/catalog", response_model=list[CatalogItem])
async def catalog(limit: int = 24) -> list[CatalogItem]:
    return container.catalog.load()[: max(1, min(limit, 100))]
