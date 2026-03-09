"""
main.py
-------
Entry point for the Techizo PWA news reader.
Sets up FastAPI with Jinja2 templating, mounts static files,
includes API routes, and manages the background scheduler lifecycle.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import config
from api.routes import router as api_router
from fetcher.scheduler import start_scheduler, stop_scheduler

# ── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown) ────────────────────────────────────
@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Start the scheduler on boot; stop it on shutdown."""
    logger.info("Techizo starting up …")
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    start_scheduler()
    yield
    stop_scheduler()
    logger.info("Techizo shut down.")


# ── App ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Techizo",
    description="AI / Tech / Robotics news reader PWA",
    version="1.0.0",
    lifespan=lifespan,
)

# Mount static files at /static
app.mount("/static", StaticFiles(directory=config.BASE_DIR / "static"), name="static")

# Jinja2 templates
templates = Jinja2Templates(directory=str(config.BASE_DIR / "templates"))

# Include API routes
app.include_router(api_router)


# ── Pages ────────────────────────────────────────────────────────────
@app.get("/sw.js")
async def service_worker():
    """
    Serve the service worker from the root path.

    Service workers can only control pages at or below their own URL path.
    Serving from /static/sw.js would limit scope to /static/.
    This route serves the file from / so it can control the entire app.
    """
    return FileResponse(
        config.BASE_DIR / "static" / "sw.js",
        media_type="application/javascript",
        headers={
            "Service-Worker-Allowed": "/",
            "Cache-Control": "no-cache, no-store, must-revalidate",
        },
    )


@app.get("/health")
async def health_check():
    """Render.com load balancer health check."""
    return {"status": "ok"}


@app.get("/")
async def index(request: Request):
    """Serve the PWA shell — the main index page."""
    return templates.TemplateResponse("index.html", {"request": request})


# ── Run ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=config.PORT,
        reload=True,
    )
