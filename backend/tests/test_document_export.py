"""Branded export shell: cover, TOC, headers, tables."""

from datetime import UTC, datetime
from uuid import uuid4

from app.models.project import Project
from app.models.snapshot import Snapshot
from app.services.document_export import (
    ExportMeta,
    build_export_meta,
    build_publish_meta,
    export_branded_docx,
    export_branded_pdf,
    parse_document_blocks,
    toc_entries_for,
)

_SAMPLE = """# Project Charter

## Purpose

Patients need online rescheduling.

## Scope

| Area | Detail |
| --- | --- |
| In scope | Rescheduling |
| Out of scope | Billing |

## Stakeholders

Clinic managers own delivery.
"""


def _meta() -> ExportMeta:
    return ExportMeta(
        title="Project Charter",
        document_type="PROJECT CHARTER",
        document_number="CHR-001",
        version=1,
        effective_date=datetime(2026, 8, 31, tzinfo=UTC),
        project_name="Clinic Booking",
    )


def test_parse_document_blocks_includes_table() -> None:
    blocks = parse_document_blocks(_SAMPLE)
    kinds = [type(b).__name__ for b in blocks]
    assert "TableBlock" in kinds
    assert any(getattr(b, "kind", None) == "h2" for b in blocks if hasattr(b, "kind"))


def test_build_export_meta_planning() -> None:
    aid = uuid4()
    project = Project(
        id=uuid4(),
        name="Clinic",
        brief="x",
        phase="planning",
        planning_doc_version=2,
        created_by_account_id=aid,
    )
    snapshot = Snapshot(
        project_id=project.id,
        phase="planning",
        card_versions=[],
        accepted_by_account_id=aid,
        created_at=datetime.now(UTC),
    )
    meta = build_export_meta(project, snapshot)
    assert meta.document_number == "CHR-002"
    assert meta.document_type == "PROJECT CHARTER"


def test_build_publish_meta_without_snapshot() -> None:
    aid = uuid4()
    project = Project(
        id=uuid4(),
        name="Clinic",
        brief="x",
        phase="requirements",
        requirements_doc_version=3,
        created_by_account_id=aid,
    )
    meta = build_publish_meta(
        project, phase="requirements", version=3, pack_key="requirements_summary"
    )
    assert meta.document_number == "REQ-SUM-003"
    assert meta.title == "Requirements Summary"


def test_toc_includes_version_details() -> None:
    blocks = parse_document_blocks(_SAMPLE)
    entries = toc_entries_for(blocks, {"Purpose": 3, "Version Details": 5})
    titles = [e.title for e in entries]
    assert any("Purpose" in t for t in titles)
    assert "Version Details" in titles


def test_export_branded_docx_is_zip() -> None:
    data = export_branded_docx(_SAMPLE, _meta())
    assert data[:2] == b"PK"
    assert len(data) > 5000


def test_export_branded_pdf_is_pdf() -> None:
    data = export_branded_pdf(_SAMPLE, _meta())
    assert data[:5] == b"%PDF-"
    assert len(data) > 5000
