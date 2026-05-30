import time
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import OperationalError

from app.db.session import init_db, engine
from app.api.scrape import router as scrape_router
from app.api.companies import router as companies_router

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def _wait_for_db(retries: int = 10, delay: int = 5):
    """Block startup until MySQL is ready (common in Docker environments)."""
    for attempt in range(1, retries + 1):
        try:
            with engine.connect():
                log.info("Database connection established.")
                return
        except OperationalError as e:
            log.warning(f"DB not ready (attempt {attempt}/{retries}): {e}")
            time.sleep(delay)
    raise RuntimeError("Could not connect to the database after multiple retries.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _wait_for_db()
    init_db()
    log.info("Tables created / verified.")
    yield


app = FastAPI(
    title="APII Scraper API",
    description=(
        "REST API to trigger APII Industrial scraping, "
        "LinkedIn URL discovery, and LinkedIn profile enrichment. "
        "Results are stored in MySQL and queryable via /companies."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scrape_router,    prefix="/api")
app.include_router(companies_router, prefix="/api")


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "message": "APII Scraper API is running"}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy"}