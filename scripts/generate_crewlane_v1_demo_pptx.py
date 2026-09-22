#!/usr/bin/env python3
"""Generate docs/CrewLane-v1-Demo.pptx — one-off deck builder."""

from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "CrewLane-v1-Demo.pptx"

NAVY = RGBColor(0x1E, 0x3A, 0x5F)
INK = RGBColor(0x1A, 0x1A, 0x1F)
MUTED = RGBColor(0x5C, 0x5C, 0x6A)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
ACCENT_BG = RGBColor(0xF0, 0xF4, 0xF8)


def _box(slide, left, top, width, height, fill=None):
    shape = slide.shapes.add_shape(1, left, top, width, height)  # MSO_SHAPE.RECTANGLE
    shape.line.fill.background()
    if fill:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill
    return shape


def _text(
    slide,
    left,
    top,
    width,
    height,
    lines: list[tuple[str, int, bool, RGBColor | None]],
    *,
    align=PP_ALIGN.LEFT,
):
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.TOP
    for i, (text, size, bold, color) in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = text
        p.font.size = Pt(size)
        p.font.bold = bold
        p.font.color.rgb = color or INK
        p.alignment = align
        p.space_after = Pt(6 if size >= 14 else 4)
    return tb


def _title_slide(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _box(slide, Inches(0), Inches(0), prs.slide_width, Inches(1.1), NAVY)
    _text(
        slide,
        Inches(0.6),
        Inches(0.28),
        Inches(9),
        Inches(0.7),
        [("CrewLane v1 Demo", 32, True, WHITE)],
    )
    _text(
        slide,
        Inches(0.6),
        Inches(1.5),
        Inches(9),
        Inches(1.2),
        [
            (
                "AI-assisted Planning & Requirements with human gates at every step",
                20,
                False,
                NAVY,
            ),
        ],
    )
    _text(
        slide,
        Inches(0.6),
        Inches(2.4),
        Inches(9),
        Inches(0.8),
        [("Evidence in → structured facts → interview → documents out", 14, False, MUTED)],
    )
    _box(slide, Inches(0.6), Inches(3.5), Inches(8.8), Inches(1.4), ACCENT_BG)
    _text(
        slide,
        Inches(0.8),
        Inches(3.65),
        Inches(8.4),
        Inches(1.2),
        [
            (
                '"Agents draft; humans accept. Documents are views of a card model with provenance."',
                13,
                True,
                NAVY,
            ),
        ],
        align=PP_ALIGN.CENTER,
    )


def _what_slide(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _text(
        slide,
        Inches(0.5),
        Inches(0.35),
        Inches(9),
        Inches(0.5),
        [("What is CrewLane?", 28, True, NAVY)],
    )
    bullets = [
        "AI workspace for early SDLC: Planning + Requirements (v1 scope only).",
        "Upload evidence (docs, notes, transcripts) and answer guided interview questions.",
        "Answers become typed facts (cards) with provenance — not hand-maintained files.",
        "LangGraph agent interviews across a coverage checklist until draft-ready.",
        "Accept or Revise at each gate; named human decision required to proceed.",
        "Outputs: Project Charter (Planning) and selectable Requirements deliverable packs.",
    ]
    y = 1.0
    for b in bullets:
        _text(slide, Inches(0.65), Inches(y), Inches(8.8), Inches(0.45), [(f"• {b}", 13, False, INK)])
        y += 0.52


def _flow_slide(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _text(
        slide,
        Inches(0.5),
        Inches(0.3),
        Inches(9),
        Inches(0.45),
        [("System flow & tech stack", 26, True, NAVY)],
    )
    flow = (
        "User  →  Upload / paste  →  Parse & chunk  →  Extract facts  →  Belief layer\n"
        "         ↓ merge / conflict review\n"
        "Cards + vectors (Postgres / pgvector)  ↔  LangGraph interview  →  Gate  →  Compose docs\n"
        "         ↓ RAG retrieval during chat\n"
        "Export DOCX / PDF  +  OneDrive PDF sync"
    )
    _box(slide, Inches(0.5), Inches(0.85), Inches(9), Inches(1.55), ACCENT_BG)
    _text(
        slide,
        Inches(0.65),
        Inches(0.95),
        Inches(8.7),
        Inches(1.4),
        [(flow, 11, False, INK)],
    )
    stack = [
        ("UI", "Next.js, React, SSE streaming"),
        ("API", "FastAPI, session auth (JWT cookie)"),
        ("Agent", "LangGraph, Groq LLM (+ scripted fallback)"),
        ("Data", "PostgreSQL, MinIO (S3), pgvector (HNSW)"),
        ("Embeddings", "Local EmbeddingGemma-300M"),
        ("Parsing", "Docling (pdf, docx, pptx, xlsx, csv, md, vtt…)"),
        ("Jobs", "In-process worker (ingest + OneDrive sync)"),
        ("Integrations", "Microsoft Graph (personal OneDrive, optional)"),
    ]
    y = 2.55
    _text(
        slide,
        Inches(0.5),
        Inches(y),
        Inches(4),
        Inches(0.3),
        [("Tech stack", 14, True, NAVY)],
    )
    y += 0.35
    for label, val in stack:
        _text(
            slide,
            Inches(0.55),
            Inches(y),
            Inches(9),
            Inches(0.28),
            [(f"{label}:  {val}", 10, False, INK)],
        )
        y += 0.28


def _built_slide(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _text(
        slide,
        Inches(0.5),
        Inches(0.3),
        Inches(9),
        Inches(0.45),
        [("In scope — built in v1", 26, True, NAVY)],
    )
    sections = [
        (
            "Planning",
            [
                "Guided interview: business need, scope, stakeholders, risks",
                "Coverage checklist + readiness gate before draft",
                "Accept / Revise → frozen snapshot → Project Charter",
            ],
        ),
        (
            "Requirements",
            [
                "Nine coverage areas seeded from Planning",
                "Selectable deliverable packs → Generate → Accept",
                "Post-accept chat + Redraft requirements (version bump)",
            ],
        ),
        (
            "Evidence & trust",
            [
                "Multi-format upload → chunk → embed → fact extraction",
                "Belief layer: merge duplicates, conflict queue blocks interview",
                "RAG during interview; human edit/retire cards; audit trail",
            ],
        ),
        (
            "Documents & publish",
            [
                "Branded DOCX/PDF: cover, TOC, headers, styled tables",
                "In-app branded preview; OneDrive branded PDF sync",
            ],
        ),
    ]
    col_w = Inches(4.35)
    positions = [(0.5, 0.85), (5.0, 0.85), (0.5, 3.35), (5.0, 3.35)]
    for (title, items), (x, y) in zip(sections, positions, strict=True):
        _box(slide, Inches(x), Inches(y), col_w, Inches(2.35), ACCENT_BG)
        _text(
            slide,
            Inches(x + 0.12),
            Inches(y + 0.1),
            col_w - Inches(0.2),
            Inches(0.35),
            [(title, 12, True, NAVY)],
        )
        iy = y + 0.42
        for item in items:
            _text(
                slide,
                Inches(x + 0.15),
                Inches(iy),
                col_w - Inches(0.25),
                Inches(0.5),
                [(f"• {item}", 9, False, INK)],
            )
            iy += 0.38


def _future_slide(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _text(
        slide,
        Inches(0.5),
        Inches(0.3),
        Inches(9),
        Inches(0.45),
        [("Out of scope / future", 26, True, NAVY)],
    )
    items = [
        "Multi-user / team collaboration (single operator today)",
        "Microsoft Teams and email ingestion connectors",
        "Separate tabs for Planning chat vs Requirements chat",
        "Click checklist item → focused Q&A or redraft for that area only",
        "Deeper, area-by-area interview before draft",
        "Later SDLC phases (Design, Build, Test, Deploy…)",
        "Enterprise SSO; company logo / white-label on exports",
        "Jira and other ALM integrations",
    ]
    y = 0.95
    for item in items:
        _text(slide, Inches(0.65), Inches(y), Inches(8.8), Inches(0.4), [(f"• {item}", 12, False, INK)])
        y += 0.48


def _demo_slide(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _text(
        slide,
        Inches(0.5),
        Inches(0.3),
        Inches(9),
        Inches(0.45),
        [("Live demo agenda (~6 min)", 26, True, NAVY)],
    )
    steps = [
        "Sign in → create project (one-line brief)",
        "Upload evidence → wait for ingest (Artifacts tab)",
        "Resolve conflicts if any (interview blocked until done)",
        "Interview — read-back, questions, chips, evidence Q&A",
        "Planning gate → Accept → Project Charter",
        "Requirements — coverage → pick packs → Generate → Accept",
        "Documents — branded preview; download PDF/DOCX",
        "Optional: OneDrive connected → show PDF in folder tree",
    ]
    y = 0.95
    for i, step in enumerate(steps, 1):
        _text(
            slide,
            Inches(0.65),
            Inches(y),
            Inches(8.8),
            Inches(0.38),
            [(f"{i}. {step}", 12, False, INK)],
        )
        y += 0.42


def _qa_slide(prs: Presentation) -> None:
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    _box(slide, Inches(0), Inches(0), prs.slide_width, prs.slide_height, ACCENT_BG)
    _text(
        slide,
        Inches(0.5),
        Inches(2.8),
        Inches(9),
        Inches(1),
        [("Questions?", 36, True, NAVY)],
        align=PP_ALIGN.CENTER,
    )
    _text(
        slide,
        Inches(0.5),
        Inches(3.6),
        Inches(9),
        Inches(0.5),
        [("CrewLane v1 Demo", 16, False, MUTED)],
        align=PP_ALIGN.CENTER,
    )


def main() -> None:
    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(5.625)  # 16:9
    _title_slide(prs)
    _what_slide(prs)
    _flow_slide(prs)
    _built_slide(prs)
    _future_slide(prs)
    _demo_slide(prs)
    _qa_slide(prs)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUT)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
