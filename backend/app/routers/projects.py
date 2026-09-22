from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response, StreamingResponse

from app.agents.inference import get_inference
from app.agents.templates import get_template
from app.core.config import get_settings
from app.dependencies import CurrentAccountId, SessionDep
from app.schemas.api import (
    CardOut,
    CardUpdateIn,
    ChatStateOut,
    ConflictResolveIn,
    FeasibilityIn,
    GateActionIn,
    LinkIn,
    MessageCreate,
    MessageOut,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
    SnapshotOut,
    TranscribeOut,
    UploadOut,
)
from app.services import audit as audit_service
from app.services import belief as belief_service
from app.services import cards as cards_service
from app.services import chat as chat_service
from app.services import chat_state as chat_state_service
from app.services import conflict_advice as conflict_advice_service
from app.services import documents as documents_service
from app.services import feasibility as feasibility_service
from app.services import ingestion as ingestion_service
from app.services import projects as project_service
from app.services import rag_traces
from app.services import stream as stream_service
from app.services.parsers import is_audio
from app.services.transcription import MAX_TRANSCRIBE_BYTES, transcribe_audio

router = APIRouter(prefix="/projects", tags=["projects"])


def _owned_project(session: SessionDep, account_id: CurrentAccountId, project_id: UUID):
    project = project_service.get_project(session, account_id, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "project not found")
    return project


def _account(session: SessionDep, account_id: CurrentAccountId):
    account = project_service.get_account(session, account_id)
    if account is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown account")
    return account


@router.get("", response_model=list[ProjectOut])
def list_projects(session: SessionDep, account_id: CurrentAccountId) -> list[ProjectOut]:
    return [
        ProjectOut.model_validate(p) for p in project_service.list_projects(session, account_id)
    ]


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    body: ProjectCreate, session: SessionDep, account_id: CurrentAccountId
) -> ProjectOut:
    if project_service.get_account(session, account_id) is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "unknown account")
    project = project_service.create_project(session, account_id, body.brief, name=body.name)
    audit_service.record(
        session,
        project_id=project.id,
        account_id=account_id,
        kind="project_created",
        detail={"name": project.name},
    )
    return ProjectOut.model_validate(project)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: UUID, session: SessionDep, account_id: CurrentAccountId) -> ProjectOut:
    return ProjectOut.model_validate(_owned_project(session, account_id, project_id))


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    session: SessionDep,
    account_id: CurrentAccountId,
) -> ProjectOut:
    project = _owned_project(session, account_id, project_id)
    previous = project.name
    project = project_service.rename_project(session, project, body.name)
    if previous != project.name:
        audit_service.record(
            session,
            project_id=project.id,
            account_id=account_id,
            kind="project_renamed",
            detail={"from": previous, "to": project.name},
        )
    return ProjectOut.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: UUID, session: SessionDep, account_id: CurrentAccountId
) -> None:
    project = _owned_project(session, account_id, project_id)
    project_service.delete_project(session, project)


@router.get("/{project_id}/messages", response_model=list[MessageOut])
def list_messages(
    project_id: UUID,
    session: SessionDep,
    account_id: CurrentAccountId,
    phase: str | None = None,
) -> list[MessageOut]:
    project = _owned_project(session, account_id, project_id)
    account = _account(session, account_id)
    if phase is not None and phase not in ("planning", "requirements"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid phase")
    try:
        rows = chat_service.list_messages(session, project, account, phase=phase)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return [MessageOut.model_validate(m) for m in rows]


@router.get("/{project_id}/chat-state", response_model=ChatStateOut)
def get_chat_state(
    project_id: UUID,
    session: SessionDep,
    account_id: CurrentAccountId,
    tab: str = "planning",
) -> ChatStateOut:
    project = _owned_project(session, account_id, project_id)
    account = _account(session, account_id)
    try:
        state = chat_state_service.get_chat_state(session, project, account, tab=tab)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return ChatStateOut.model_validate(state)


@router.post("/{project_id}/messages", response_model=list[MessageOut])
def post_message(
    project_id: UUID,
    body: MessageCreate,
    session: SessionDep,
    account_id: CurrentAccountId,
) -> list[MessageOut]:
    if not body.skipped and not body.content:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "message cannot be blank")
    project = _owned_project(session, account_id, project_id)
    account = _account(session, account_id)
    try:
        messages = chat_service.post_user_message(
            session,
            project,
            account,
            content=body.content,
            skipped=body.skipped,
            bound_to_question=body.bound_to_question,
            tab=body.tab,
            skip_redirect_check=body.skip_redirect_check,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return [MessageOut.model_validate(m) for m in messages]


@router.post("/{project_id}/messages/stream")
def post_message_stream(
    project_id: UUID,
    body: MessageCreate,
    session: SessionDep,
    account_id: CurrentAccountId,
) -> StreamingResponse:
    if not body.skipped and not body.content:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "message cannot be blank")
    project = _owned_project(session, account_id, project_id)
    account = _account(session, account_id)

    def generate():
        yield from stream_service.stream_user_message_events(
            session,
            project,
            account,
            content=body.content,
            skipped=body.skipped,
            bound_to_question=body.bound_to_question,
            tab=body.tab,
            skip_redirect_check=body.skip_redirect_check,
        )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{project_id}/cards", response_model=list[CardOut])
def list_cards(
    project_id: UUID, session: SessionDep, account_id: CurrentAccountId
) -> list[CardOut]:
    project = _owned_project(session, account_id, project_id)
    sources = cards_service.card_sources(session, project)
    out = []
    for card in cards_service.list_cards(session, project):
        row = CardOut.model_validate(card)
        row.sources = sources.get(card.id, [])
        out.append(row)
    return out


@router.patch("/{project_id}/cards/{card_id}", response_model=CardOut)
def update_card(
    project_id: UUID,
    card_id: UUID,
    body: CardUpdateIn,
    session: SessionDep,
    account_id: CurrentAccountId,
) -> CardOut:
    project = _owned_project(session, account_id, project_id)
    try:
        card = cards_service.update_card(session, project, card_id, body.body)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    audit_service.record(
        session,
        project_id=project.id,
        account_id=account_id,
        kind="card_edited",
        detail={"card_id": str(card_id), "new_body": body.body[:300]},
    )
    return CardOut.model_validate(card)


@router.post("/{project_id}/cards/{card_id}/retire", status_code=status.HTTP_204_NO_CONTENT)
def retire_card(
    project_id: UUID,
    card_id: UUID,
    session: SessionDep,
    account_id: CurrentAccountId,
) -> None:
    project = _owned_project(session, account_id, project_id)
    try:
        cards_service.retire_card(session, project, card_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    audit_service.record(
        session,
        project_id=project.id,
        account_id=account_id,
        kind="card_struck",
        detail={"card_id": str(card_id)},
    )


@router.get("/{project_id}/snapshots", response_model=list[SnapshotOut])
def list_snapshots(
    project_id: UUID, session: SessionDep, account_id: CurrentAccountId
) -> list[SnapshotOut]:
    project = _owned_project(session, account_id, project_id)
    out: list[SnapshotOut] = []
    for snap in cards_service.list_snapshots(session, project):
        template = get_template(snap.phase)
        out.append(
            SnapshotOut(
                id=snap.id,
                phase=snap.phase,
                document=template.document,
                body=cards_service.render_snapshot(session, snap),
                narrative=snap.narrative,
                narratives=snap.narratives,
                accepted_by_account_id=snap.accepted_by_account_id,
                created_at=snap.created_at,
            )
        )
    return out


@router.get("/{project_id}/snapshots/{snapshot_id}/export")
def export_snapshot(
    project_id: UUID,
    snapshot_id: UUID,
    session: SessionDep,
    account_id: CurrentAccountId,
    format: str = "md",
    pack: str | None = None,
) -> Response:
    project = _owned_project(session, account_id, project_id)
    snapshot = next(
        (s for s in cards_service.list_snapshots(session, project) if s.id == snapshot_id),
        None,
    )
    if snapshot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "snapshot not found")
    exporter = documents_service.EXPORTERS.get(format)
    if exporter is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "format must be md, docx, or pdf")
    render, media_type, ext = exporter
    meta = documents_service.build_export_meta(project, snapshot, pack_key=pack)
    markdown = documents_service.snapshot_markdown(session, snapshot, pack=pack)
    template = get_template(snapshot.phase)
    label = pack or template.document.replace(" ", "-").lower()
    filename = f"{label}-{str(snapshot.id)[:8]}.{ext}"
    return Response(
        content=render(markdown, meta),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{project_id}/links", response_model=UploadOut, status_code=status.HTTP_201_CREATED)
def ingest_link(
    project_id: UUID,
    body: LinkIn,
    session: SessionDep,
    account_id: CurrentAccountId,
) -> UploadOut:
    project = _owned_project(session, account_id, project_id)
    try:
        upload = ingestion_service.ingest_link(
            session, project=project, account_id=account_id, url=body.url.strip()
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    audit_service.record(
        session,
        project_id=project.id,
        account_id=account_id,
        kind="link_ingested",
        detail={"url": body.url.strip()[:300]},
    )
    return UploadOut.model_validate(upload)


@router.post("/{project_id}/transcribe", response_model=TranscribeOut)
async def transcribe_dictation(
    project_id: UUID,
    session: SessionDep,
    account_id: CurrentAccountId,
    file: Annotated[UploadFile, File()],
) -> TranscribeOut:
    """Speech-to-text for the chat composer mic — no ingest, no evidence chunks."""
    _owned_project(session, account_id, project_id)
    body = await file.read()
    filename = file.filename or "dictation.webm"
    if not is_audio(filename):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "audio file required")
    if len(body) > MAX_TRANSCRIBE_BYTES:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "recording too large")
    text = transcribe_audio(get_settings(), filename, body)
    return TranscribeOut(text=text)


@router.post("/{project_id}/uploads", response_model=UploadOut, status_code=status.HTTP_201_CREATED)
async def upload_file(
    project_id: UUID,
    session: SessionDep,
    account_id: CurrentAccountId,
    file: Annotated[UploadFile, File()],
    speaker_name: Annotated[str | None, Form()] = None,
) -> UploadOut:
    project = _owned_project(session, account_id, project_id)
    body = await file.read()
    filename = file.filename or "upload.bin"
    try:
        upload = ingestion_service.enqueue_upload(
            session,
            project=project,
            account_id=account_id,
            filename=filename,
            content_type=file.content_type or "application/octet-stream",
            body=body,
            speaker_name=speaker_name.strip() if speaker_name else None,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    audit_service.record(
        session,
        project_id=project.id,
        account_id=account_id,
        kind="evidence_uploaded",
        detail={"filename": filename},
    )
    return UploadOut.model_validate(upload)


@router.get("/{project_id}/uploads", response_model=list[UploadOut])
def list_uploads(
    project_id: UUID, session: SessionDep, account_id: CurrentAccountId
) -> list[UploadOut]:
    project = _owned_project(session, account_id, project_id)
    return [UploadOut.model_validate(u) for u in ingestion_service.list_uploads(session, project)]


@router.post("/{project_id}/uploads/{upload_id}/keep", response_model=UploadOut)
def keep_flagged_upload(
    project_id: UUID,
    upload_id: UUID,
    session: SessionDep,
    account_id: CurrentAccountId,
) -> UploadOut:
    """Human override: ingest a flagged (judged off-topic) upload anyway."""
    project = _owned_project(session, account_id, project_id)
    upload = ingestion_service.get_upload(session, project, upload_id)
    if upload is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "upload not found")
    try:
        ingestion_service.keep_flagged_upload(session, project, upload)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    audit_service.record(
        session,
        project_id=project.id,
        account_id=account_id,
        kind="upload_kept_despite_flag",
        detail={"filename": upload.filename},
    )
    return UploadOut.model_validate(upload)


@router.post("/{project_id}/uploads/{upload_id}/discard", response_model=UploadOut)
def discard_flagged_upload(
    project_id: UUID,
    upload_id: UUID,
    session: SessionDep,
    account_id: CurrentAccountId,
) -> UploadOut:
    """Human override: confirm a flagged upload should stay excluded."""
    project = _owned_project(session, account_id, project_id)
    upload = ingestion_service.get_upload(session, project, upload_id)
    if upload is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "upload not found")
    try:
        ingestion_service.discard_flagged_upload(session, project, upload)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    audit_service.record(
        session,
        project_id=project.id,
        account_id=account_id,
        kind="upload_discarded",
        detail={"filename": upload.filename},
    )
    return UploadOut.model_validate(upload)


@router.get("/{project_id}/uploads/{upload_id}/content")
def get_upload_content(
    project_id: UUID,
    upload_id: UUID,
    session: SessionDep,
    account_id: CurrentAccountId,
) -> Response:
    """Stream the original uploaded file for Evidence preview (D82)."""
    project = _owned_project(session, account_id, project_id)
    upload = ingestion_service.get_upload(session, project, upload_id)
    if upload is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "upload not found")
    try:
        body = ingestion_service.read_upload_bytes(upload)
    except FileNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "file not found") from exc
    filename = upload.filename or "upload.bin"
    disposition = (
        f"inline; filename=\"{filename}\"; filename*=UTF-8''{quote(filename)}"
    )
    return Response(
        content=body,
        media_type=upload.content_type or "application/octet-stream",
        headers={
            "Content-Disposition": disposition,
            "Cache-Control": "private, max-age=60",
        },
    )


@router.get("/{project_id}/audit")
def list_audit(project_id: UUID, session: SessionDep, account_id: CurrentAccountId) -> list[dict]:
    project = _owned_project(session, account_id, project_id)
    return audit_service.list_events(session, project.id)


@router.get("/{project_id}/retrieval-traces")
def list_retrieval_traces(
    project_id: UUID, session: SessionDep, account_id: CurrentAccountId
) -> list[dict]:
    project = _owned_project(session, account_id, project_id)
    return rag_traces.list_traces(session, project.id)


@router.get("/{project_id}/conflicts")
def list_conflicts(
    project_id: UUID, session: SessionDep, account_id: CurrentAccountId
) -> dict:
    project = _owned_project(session, account_id, project_id)
    return belief_service.conflict_progress(session, project)


@router.get("/{project_id}/conflicts/{conflict_id}/advice")
def conflict_advice(
    project_id: UUID,
    conflict_id: UUID,
    session: SessionDep,
    account_id: CurrentAccountId,
) -> dict:
    project = _owned_project(session, account_id, project_id)
    row = next(
        (c for c in belief_service.list_conflicts(session, project) if c["id"] == str(conflict_id)),
        None,
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "conflict not found")
    settings = get_settings()
    advice = conflict_advice_service.advise_single_conflict(
        get_inference(settings),
        model=settings.groq_model,
        row=row,
    )
    return advice


@router.post(
    "/{project_id}/conflicts/{conflict_id}/resolve",
    status_code=status.HTTP_204_NO_CONTENT,
)
def resolve_conflict(
    project_id: UUID,
    conflict_id: UUID,
    body: ConflictResolveIn,
    session: SessionDep,
    account_id: CurrentAccountId,
) -> None:
    project = _owned_project(session, account_id, project_id)
    try:
        cleared = belief_service.resolve_conflict(
            session, project, conflict_id, body.winner_card_id
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    audit_service.record(
        session,
        project_id=project.id,
        account_id=account_id,
        kind="conflict_resolved",
        detail={
            "conflict_id": str(conflict_id),
            "winner_card_id": str(body.winner_card_id),
            "cleared_count": cleared,
        },
    )


@router.post("/{project_id}/feasibility", response_model=MessageOut)
def post_feasibility(
    project_id: UUID,
    body: FeasibilityIn,
    session: SessionDep,
    account_id: CurrentAccountId,
) -> MessageOut:
    project = _owned_project(session, account_id, project_id)
    try:
        message = feasibility_service.run_feasibility(session, project, body.query.strip())
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return MessageOut.model_validate(message)


@router.post("/{project_id}/gate", response_model=list[MessageOut])
def post_gate_action(
    project_id: UUID,
    body: GateActionIn,
    session: SessionDep,
    account_id: CurrentAccountId,
) -> list[MessageOut]:
    project = _owned_project(session, account_id, project_id)
    account = _account(session, account_id)
    phase_at_gate = project.phase
    try:
        messages = chat_service.post_gate_action(
            session,
            project,
            account,
            action=body.action,
            content=body.content,
            area=body.area,
            pack_ids=body.pack_ids,
            pack_mode=body.pack_mode,
            tab=body.tab,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    audit_service.record(
        session,
        project_id=project.id,
        account_id=account_id,
        kind="gate_accepted" if body.action == "accept" else "gate_revised",
        detail={"phase": phase_at_gate, "area": body.area, "note": body.content[:300]},
    )
    return [MessageOut.model_validate(m) for m in messages]
