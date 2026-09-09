"""Entrypoint dell'applicazione Campionissimo API."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import get_db, init_game_tables, SessionLocal
from .routers import game, search, challenge
from .services.search import build_index

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("campionissimo")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────────────
    logger.info(f"Avvio in modalità: {settings.APP_ENV}")

    # Crea le tabelle di gioco se non esistono
    init_game_tables()
    logger.info("Tabelle di gioco verificate/create.")

    # Costruisce l'indice di ricerca in memoria
    try:
        with SessionLocal() as db:
            build_index(db)
    except Exception as exc:  # pragma: no cover
        logger.warning(f"Impossibile costruire l'indice di ricerca all'avvio: {exc}")

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    logger.info("Shutdown completato.")


app = FastAPI(
    title="Campionissimo API",
    description="Backend per il gioco 'Indovina il calciatore dalla sua carriera'.",
    version="0.1.0",
    lifespan=lifespan,
    # Docs disabilitati in produzione — esporrebbero la struttura API
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    openapi_url="/openapi.json" if not settings.is_production else None,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

# ── Router ────────────────────────────────────────────────────────────────────
app.include_router(game.router)
app.include_router(search.router)
app.include_router(challenge.router)

# ── Asset statici (solo in sviluppo) ─────────────────────────────────────────
if not settings.is_production:
    assets_dir = Path(settings.ASSETS_LOCAL_DIR)
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
        logger.info(f"Asset serviti localmente da: {assets_dir.resolve()}")
    else:
        logger.warning(f"Directory asset non trovata: {assets_dir.resolve()}. Skippato il mount.")


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["infra"])
def health():
    return {"status": "ok", "env": settings.APP_ENV}
