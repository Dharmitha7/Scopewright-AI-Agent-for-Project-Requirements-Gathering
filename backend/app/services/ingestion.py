"""Ingestion pipeline: upload → parse/transcribe → chunk → extract facts (D13)."""

from __future__ import annotations

import logging
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.embeddings import get_embeddings
from app.adapters.storage import get_storage
from app.agents.inference import PURPOSE_TAG, complete_json, facts_by_area, get_inference
from app.agents.templates import get_template
from app.core.config import get_settings
from app.models.evidence_chunk import EvidenceChunk
from app.models.job import Job
from app.models.message import Message, max_seq
from app.models.project import Project
from app.models.upload import Upload
from app.services import cards as cards_service
from app.services.parsers import chunk_text, chunk_upload, is_audio, is_image, is_supported
from app.services.transcription import transcribe_audio
from app.services.vision import describe_image

log = logging.getLogger(__name__)

INGEST_KIND = "ingest_upload"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
# Long recordings are chunked with ffmpeg before Groq's 25 MB cap applies.
MAX_AUDIO_BYTES = 200 * 1024 * 1024
MAX_LINK_BYTES = 5 * 1024 * 1024


BRIEF_SOURCE_REF = "brief"


def upload_source_ref(upload_id: UUID) -> str:
    return f"upload:{upload_id}"


def _phase_area_prompt(project: Project) -> tuple[str, set[str]]:
    """Area list + valid keys for the current phase ('' / empty set when done)."""
    try:
        template = get_template(project.phase)
    except KeyError:
        return "", set()
    lines = "\n".join(f"- {a.key}: {a.guidance}" for a in template.areas)
    return lines, {a.key for a in template.areas}


def _extract_system(area_lines: str, scope_digest: str = "") -> str:
    # Faithfulness over polish: an earlier "expand on what is implied" prompt
    # made the model invent numbers, vendors, and compliance requirements and
    # stamp them "from project brief" - poisoning the audit trail.
    base = (
        f"{PURPOSE_TAG} ingest_extract\n"
        "You are a senior business analyst. Extract the facts this evidence "
        "actually states, rephrased as clear third-person statements "
        "('The system shall...' / 'The project will...'). "
        "STRICT RULE: every detail must be traceable to the source. Never add "
        "numbers, metrics, vendors, standards, features, or requirements the "
        "source does not state. If the source is vague, the fact stays vague. "
        "Classify each fact into one coverage area key from:\n" + area_lines + "\n"
        'Use "general" when none fit. '
    )
    if not scope_digest:
        return (
            base
            + 'Return {"facts": [{"text": str, "area": str}]}. '
            "Use an empty list if nothing factual."
        )
    # Relevance gate (junk-upload filtering): only asked once a scope exists
    # to compare against - see _project_scope_digest's early-project bypass.
    #
    # Observed live (real model, not the scripted stand-in): a coherent,
    # well-written brief/notes for a completely different, named product
    # (an equipment-booking portal) was judged on_topic=true against a
    # "todo app" scope, because the old wording only asked "does this seem
    # unrelated" and defaulted to true on anything not obviously nonsensical
    # - a full alternate project reads as plausible, not nonsensical. Fixed
    # by forcing an explicit same-subject comparison and narrowing the
    # leniency default to genuinely subject-less content only, so it still
    # protects real-but-oddly-phrased evidence without waving through a
    # complete spec for a different product.
    return (
        base
        + "\nProject scope so far:\n"
        + scope_digest
        + "\n\nDecide on_topic by comparing SUBJECTS, not tone or document quality: "
        "what specific product/system does the scope above describe, and what specific "
        "product/system (if any) does this evidence describe or assume? "
        "true only if the evidence is about that SAME product/system, or is direct "
        "supporting context for it (a stakeholder, risk, or requirement that names no "
        "other product). false if the evidence's core subject is a different, "
        "self-contained product, system, or scenario than the scope describes - even if "
        "it is well-written, internally coherent, and uses the same kind of language "
        "(stakeholders, scope, requirements) as real project material. A complete, "
        "polished document for a different named product is NOT on-topic just because it "
        "looks like the sort of document this project would also have. "
        "Default to true only for content with no specific subject of its own (a generic "
        "risk statement, a stray scheduling note) where there is genuinely nothing to "
        "compare - not for content that clearly belongs to its own, differently-scoped "
        "product or project. "
        'Return {"on_topic": bool, "facts": [{"text": str, "area": str}]}. '
        "facts must be an empty list when on_topic is false. Use an empty list if nothing factual."
    )


def _project_scope_digest(session: Session, project: Project) -> str:
    """Short reference for the relevance gate, or "" to bypass it.

    Empty on purpose while the project has almost nothing recorded yet - the
    first uploads often ARE what defines the project (the "read everything
    before asking a question" front door), so there is nothing meaningful to
    judge them against until a brief and/or some facts exist. Threshold is a
    small handful, not zero: mine_brief() records at least one fact from the
    brief itself at project creation, so "zero facts" would flip the gate on
    before any actual evidence had a chance to shape the project's scope.
    """
    brief = (project.brief or "").strip()
    facts = cards_service.digest_lines(session, project)
    if len(brief) < 40 and len(facts) < 3:
        return ""
    lines = []
    if brief:
        lines.append(f"Project brief: {brief[:800]}")
    if facts:
        lines.append("Known facts so far:")
        lines.extend(f"- {f}" for f in facts[:40])
    return "\n".join(lines)[:3000]


def mine_brief(session: Session, project: Project) -> int:
    """Read the brief at creation so the interview opens already knowing it.

    Synchronous on purpose: one extract call, and the facts must exist before
    the first read-back/question is drafted.
    """
    settings = get_settings()
    area_lines, valid_areas = _phase_area_prompt(project)
    extracted = complete_json(
        get_inference(settings),
        model=settings.groq_model,
        system=_extract_system(area_lines),
        user=project.brief[:6000],
    )
    total = 0
    for fact_area, facts in facts_by_area(
        extracted, default_area="general", valid_areas=valid_areas
    ).items():
        cards_service.record_facts(
            session, project, area=fact_area, facts=facts, source_message_id=BRIEF_SOURCE_REF
        )
        total += len(facts)
    return total


def has_pending_intake(session: Session, project: Project) -> bool:
    """True while any upload is still queued/processing, or flagged awaiting a
    keep/discard decision. The interview must not open until the AI has read
    everything given at the front door, including resolving what to do with
    anything it flagged as off-topic."""
    return (
        session.scalar(
            select(Upload.id)
            .where(
                Upload.project_id == project.id,
                Upload.status.in_(("queued", "processing", "flagged")),
            )
            .limit(1)
        )
        is not None
    )


def list_uploads(session: Session, project: Project) -> list[Upload]:
    return list(
        session.scalars(
            select(Upload)
            .where(Upload.project_id == project.id)
            .order_by(Upload.created_at.asc())
        ).all()
    )


def get_upload(session: Session, project: Project, upload_id: UUID) -> Upload | None:
    upload = session.get(Upload, upload_id)
    if upload is None or upload.project_id != project.id:
        return None
    return upload


def read_upload_bytes(upload: Upload) -> bytes:
    """Return original uploaded bytes from object storage (D82 Evidence preview)."""
    if not upload.storage_key:
        raise FileNotFoundError("upload has no storage key")
    storage = get_storage(get_settings())
    return storage.get(upload.storage_key)


def enqueue_upload(
    session: Session,
    *,
    project: Project,
    account_id: UUID,
    filename: str,
    content_type: str,
    body: bytes,
    speaker_name: str | None,
) -> Upload:
    limit = MAX_AUDIO_BYTES if is_audio(filename) else MAX_UPLOAD_BYTES
    if len(body) > limit:
        raise ValueError(f"file exceeds {limit // (1024 * 1024)} MB limit")
    if not is_supported(filename):
        raise ValueError("unsupported file type")

    settings = get_settings()
    storage = get_storage(settings)
    upload = Upload(
        project_id=project.id,
        filename=filename,
        content_type=content_type or "application/octet-stream",
        storage_key="",
        submitted_by_account_id=account_id,
        speaker_name=speaker_name,
        status="queued",
    )
    session.add(upload)
    session.flush()

    key = f"projects/{project.id}/uploads/{upload.id}/{filename}"
    storage.put(key, body, upload.content_type)
    upload.storage_key = key
    session.add(
        Job(
            kind=INGEST_KIND,
            payload={
                "upload_id": str(upload.id),
                "project_id": str(project.id),
            },
            status="queued",
        )
    )
    session.commit()
    session.refresh(upload)
    return upload


def ingest_link(session: Session, *, project: Project, account_id: UUID, url: str) -> Upload:
    """Fetch a web page and push it through the same upload pipeline (D59)."""
    if not url.startswith(("http://", "https://")):
        raise ValueError("url must start with http:// or https://")
    try:
        response = httpx.get(
            url,
            timeout=20.0,
            follow_redirects=True,
            # Wikipedia and friends 403 the default httpx UA.
            headers={"User-Agent": "Mozilla/5.0 (compatible; CrewLane/0.1; evidence fetch)"},
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ValueError(f"could not fetch url: {exc}") from exc
    body = response.content[:MAX_LINK_BYTES]
    slug = (httpx.URL(url).host or "page").replace(".", "-")
    return enqueue_upload(
        session,
        project=project,
        account_id=account_id,
        filename=f"{slug}.html",
        content_type="text/html",
        body=body,
        speaker_name=None,
    )


def _post_assistant(session: Session, project_id: UUID, content: str, widget: dict | None = None):
    session.add(
        Message(
            project_id=project_id,
            role="assistant",
            content=content,
            widget=widget,
            seq=max_seq(session, project_id) + 1,
        )
    )
    session.flush()


def _chunk_upload_body(settings, upload: Upload, body: bytes) -> list[str]:
    if is_audio(upload.filename):
        return chunk_text(transcribe_audio(settings, upload.filename, body))
    if is_image(upload.filename):
        return chunk_text(describe_image(settings, upload.filename, body))
    # Docling is the sole parser for every format it covers (D71) - no
    # legacy fallback, no gate. A per-document failure raises straight
    # through into the existing job-worker retry path below.
    return chunk_upload(upload.filename, body)


class _ExtractionResult:
    __slots__ = ("total_facts", "kept_chunks", "off_topic_chunks")

    def __init__(self) -> None:
        self.total_facts = 0
        self.kept_chunks = 0
        self.off_topic_chunks = 0


def _extract_chunks(
    session: Session,
    project: Project,
    upload: Upload,
    chunks: list[str],
    *,
    gate_digest: str,
) -> _ExtractionResult:
    """Classify + record facts for each chunk.

    A chunk is only persisted (as an EvidenceChunk, and any facts as Cards)
    when it is on-topic - junk content never lands in the database at all,
    rather than being stored and filtered out later, so it can never leak
    back out through retrieval/chat asides. When gate_digest is empty (early
    project, nothing to compare against yet) every chunk is treated as
    on-topic, matching pre-filter behavior exactly.
    """
    settings = get_settings()
    inference = get_inference(settings)
    embedder = get_embeddings(settings)
    chunk_embeddings = embedder.embed_documents(chunks) if chunks else []
    area_lines, valid_areas = _phase_area_prompt(project)
    system = _extract_system(area_lines, gate_digest)

    result = _ExtractionResult()
    for index, chunk in enumerate(chunks):
        extracted = complete_json(
            inference,
            model=settings.groq_model,
            system=system,
            user=chunk[:6000],
        )
        if gate_digest and extracted.get("on_topic") is False:
            result.off_topic_chunks += 1
            continue
        result.kept_chunks += 1
        emb = chunk_embeddings[index] if index < len(chunk_embeddings) else []
        session.add(
            EvidenceChunk(
                project_id=project.id,
                upload_id=upload.id,
                chunk_index=index,
                body=chunk,
                embedding=emb or None,
            )
        )
        for fact_area, facts in facts_by_area(
            extracted, default_area="general", valid_areas=valid_areas
        ).items():
            cards_service.record_facts(
                session,
                project,
                area=fact_area,
                facts=facts,
                source_message_id=upload_source_ref(upload.id),
            )
            result.total_facts += len(facts)
    return result


def _provenance(upload: Upload) -> str:
    provenance = upload.filename
    if upload.speaker_name:
        provenance += f" (speaker: {upload.speaker_name})"
    return provenance


def process_ingest_job(session: Session, job: Job) -> None:
    upload_id = UUID(job.payload["upload_id"])
    project_id = UUID(job.payload["project_id"])
    upload = session.get(Upload, upload_id)
    project = session.get(Project, project_id)
    if upload is None or project is None:
        raise ValueError("upload or project missing")

    upload.status = "processing"
    session.commit()

    settings = get_settings()
    storage = get_storage(settings)
    body = storage.get(upload.storage_key)
    chunks = _chunk_upload_body(settings, upload, body)

    gate_digest = _project_scope_digest(session, project)
    result = _extract_chunks(session, project, upload, chunks, gate_digest=gate_digest)
    provenance = _provenance(upload)

    if chunks and gate_digest and result.kept_chunks == 0:
        # Every chunk judged off-topic: this usually means the wrong file was
        # dropped in entirely, not ordinary noise inside a relevant document
        # (which would still have some on-topic chunks). Nothing was
        # persisted above, so there is nothing to undo - just flag it and let
        # the human decide, matching the app's other human-decides gates
        # (conflict review, acceptance panel) instead of silently discarding.
        upload.status = "flagged"
        upload.last_error = (
            "Looks unrelated to this project - none of its content matched "
            "what has been established so far."
        )
        job.status = "done"
        _post_assistant(
            session,
            project.id,
            f"{provenance} looks unrelated to this project — none of its "
            f"{len(chunks)} chunk(s) matched the project's scope. Nothing was recorded.",
            widget={
                "type": "off_topic_upload",
                "upload_id": str(upload.id),
                "filename": upload.filename,
                "chunk_count": len(chunks),
            },
        )
        session.commit()
        log.info("flagged upload %s as off-topic chunks=%s", upload.id, len(chunks))
        return

    summary = (
        f"Ingested {provenance}: {len(chunks)} chunk(s), {result.total_facts} fact(s) recorded."
    )
    if result.off_topic_chunks:
        summary += f" ({result.off_topic_chunks} chunk(s) skipped as unrelated to this project.)"

    _post_assistant(
        session,
        project.id,
        summary,
        widget={
            "type": "fact_log",
            "area": "general",
            "facts": [f"Processed upload: {upload.filename}"],
            "source_message_id": upload_source_ref(upload.id),
        },
    )
    upload.status = "done"
    upload.last_error = None
    job.status = "done"
    session.commit()
    log.info(
        "ingested upload %s facts=%s chunks=%s off_topic=%s",
        upload.id,
        result.total_facts,
        len(chunks),
        result.off_topic_chunks,
    )


def keep_flagged_upload(session: Session, project: Project, upload: Upload) -> None:
    """Human override on a flagged upload: redo extraction with the relevance
    gate off. Safe to fully redo - a flagged upload has zero EvidenceChunk/Card
    rows from itself (every chunk was judged off-topic, so nothing was kept)."""
    if upload.status != "flagged":
        raise ValueError("upload is not flagged")
    settings = get_settings()
    storage = get_storage(settings)
    body = storage.get(upload.storage_key)
    chunks = _chunk_upload_body(settings, upload, body)
    result = _extract_chunks(session, project, upload, chunks, gate_digest="")
    provenance = _provenance(upload)
    _post_assistant(
        session,
        project.id,
        f"Kept {provenance} despite the off-topic flag: {len(chunks)} chunk(s), "
        f"{result.total_facts} fact(s) recorded.",
        widget={
            "type": "fact_log",
            "area": "general",
            "facts": [f"Processed upload: {upload.filename}"],
            "source_message_id": upload_source_ref(upload.id),
        },
    )
    upload.status = "done"
    upload.last_error = None
    session.commit()
    log.info(
        "kept flagged upload %s facts=%s chunks=%s", upload.id, result.total_facts, len(chunks)
    )


def discard_flagged_upload(session: Session, project: Project, upload: Upload) -> None:
    """Human override on a flagged upload: confirm it should stay excluded.

    Nothing to clean up - the off-topic chunks were never persisted - just
    close out the upload row so it stops prompting for a decision."""
    if upload.status != "flagged":
        raise ValueError("upload is not flagged")
    upload.status = "discarded"
    upload.last_error = None
    _post_assistant(
        session,
        project.id,
        f"Discarded {_provenance(upload)} — kept out of this project's evidence.",
    )
    session.commit()
