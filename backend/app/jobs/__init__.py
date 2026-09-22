"""In-process job worker (D32). Processes ingestion jobs when enabled."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.core.db import get_session_factory
from app.models.job import Job
from app.services import onedrive as onedrive_service
from app.services.ingestion import INGEST_KIND, process_ingest_job

log = logging.getLogger(__name__)


def _process_job(session, job: Job) -> None:
    if job.kind == INGEST_KIND:
        process_ingest_job(session, job)
        return
    if job.kind == onedrive_service.ONEDRIVE_SYNC_KIND:
        onedrive_service.process_onedrive_job(session, job)
        return
    job.status = "failed"
    job.last_error = f"unknown job kind: {job.kind}"
    session.commit()


async def run_worker(stop: asyncio.Event) -> None:
    factory = get_session_factory()
    while not stop.is_set():
        session = factory()
        try:
            job = session.scalar(select(Job).where(Job.status == "queued").limit(1))
            if job is None:
                await asyncio.sleep(2)
                continue
            job.attempts += 1
            session.commit()
            job_id = job.id
            try:
                # Blocking work (LLM calls, ffmpeg, storage) off the event
                # loop - running it inline froze every API request for the
                # duration of an ingest (E2E finding).
                await asyncio.to_thread(_process_job, session, job)
            except Exception as exc:
                session.rollback()
                job = session.get(Job, job_id)
                if job is not None:
                    job.status = "failed" if job.attempts >= 3 else "queued"
                    job.last_error = str(exc)[:2000]
                    upload_id = job.payload.get("upload_id")
                    if upload_id:
                        from uuid import UUID

                        from app.models.upload import Upload

                        upload = session.get(Upload, UUID(str(upload_id)))
                        if upload is not None:
                            upload.status = "failed"
                            upload.last_error = job.last_error
                    session.commit()
                log.exception("job %s failed", job.id if job else "?")
        except Exception:
            session.rollback()
            log.exception("job worker tick failed")
            await asyncio.sleep(2)
        finally:
            session.close()
