"""FastAPI app factory.

Bigger Applications layout:
https://fastapi.tiangolo.com/tutorial/bigger-applications/
Settings via Depends:
https://fastapi.tiangolo.com/advanced/settings/
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.embeddings import get_embeddings
from app.agents.runner import init_checkpointer
from app.core.config import get_settings
from app.jobs import run_worker
from app.routers import auth, health, projects

log = logging.getLogger(__name__)


def apply_migrations() -> None:
    if get_settings().skip_migrations:
        return
    ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    command.upgrade(Config(str(ini)), "head")


def _check_embeddings_at_startup(settings) -> None:
    # D70: local model, no API key to check for absence - the failure mode
    # now is a bad/missing HF_TOKEN, an unaccepted model license, or no
    # network on first download. Do a real load-and-encode here so that
    # shows up in boot logs, not silently on the first chat turn. Still
    # best-effort/log-only: embeddings stay an enhancement, never load-bearing
    # (Postgres FTS still answers retrieval on its own either way, D66).
    if not settings.embeddings_enabled:
        return
    try:
        get_embeddings(settings).embed_query("startup check")
    except Exception as exc:
        log.warning("embedding model failed to load at startup: %s", exc)
    else:
        log.info("embedding model loaded and responding")


@asynccontextmanager
async def lifespan(app: FastAPI):
    apply_migrations()
    init_checkpointer()
    settings = get_settings()
    # Fire-and-forget, not awaited: a first-run EmbeddingGemma load is a
    # multi-GB gated download that can take minutes. Awaiting it here would
    # block the whole app from becoming ready (and fail the Docker
    # healthcheck) for that whole time - the same class of bug this
    # codebase already hit and fixed once for the ingestion worker
    # (app/jobs/__init__.py's asyncio.to_thread comment). Runs in the
    # background instead; still logs pass/fail once it finishes. Kept as a
    # named local (not a bare create_task() call) so asyncio's own
    # weak-reference doesn't let it get garbage-collected mid-flight - this
    # frame stays alive for the app's whole lifetime, paused at `yield`.
    embeddings_check_task = asyncio.create_task(
        asyncio.to_thread(_check_embeddings_at_startup, settings)
    )
    stop = asyncio.Event()
    worker_task: asyncio.Task | None = None
    if settings.job_worker_enabled:
        worker_task = asyncio.create_task(run_worker(stop))
    yield
    stop.set()
    if worker_task:
        worker_task.cancel()
    embeddings_check_task.cancel()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="CrewLane",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(projects.router)
    return app


app = create_app()
