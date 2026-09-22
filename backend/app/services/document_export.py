"""Branded document export: cover, TOC, headers/footers, styled tables (D60).

No company logo/name in v1 — neutral CrewLane shell. Markdown content from
documents.py is wrapped at export/preview time.
"""

from __future__ import annotations

import html
import io
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.agents.deliverables import PACK_BY_KEY
from app.agents.templates import get_template
from app.models.project import Project
from app.models.snapshot import Snapshot

_BOLD = re.compile(r"\*\*(.+?)\*\*")
_NAVY = (0.12, 0.23, 0.37)
_GREY_HEADER = (0.91, 0.93, 0.95)
_COVER_PAGES = 1
_TOC_PAGES = 1

_DOC_TYPE_BY_PACK: dict[str, str] = {
    "requirements_summary": "REQUIREMENTS SUMMARY",
    "business_requirements": "BUSINESS REQUIREMENTS SPECIFICATION",
    "functional_requirements": "FUNCTIONAL REQUIREMENTS SPECIFICATION",
    "non_functional_requirements": "NON-FUNCTIONAL REQUIREMENTS",
    "epics_features_stories": "EPICS / FEATURES / USER STORIES",
    "data_requirements": "DATA REQUIREMENTS",
    "integration_requirements": "INTEGRATION REQUIREMENTS",
    "traceability_matrix": "REQUIREMENTS TRACEABILITY MATRIX",
    "user_journey": "USER JOURNEY",
    "quality_gap_report": "REQUIREMENTS QUALITY & GAP REPORT",
}

_NUMBER_PREFIX: dict[str, str] = {
    "planning": "CHR",
    "requirements_summary": "REQ-SUM",
    "business_requirements": "REQ-BRS",
    "functional_requirements": "REQ-FRS",
    "non_functional_requirements": "REQ-NFR",
    "epics_features_stories": "REQ-EFS",
    "data_requirements": "REQ-DAT",
    "integration_requirements": "REQ-INT",
    "traceability_matrix": "REQ-RTM",
    "user_journey": "REQ-UJD",
    "quality_gap_report": "REQ-QGR",
}


@dataclass(frozen=True)
class ExportMeta:
    title: str
    document_type: str
    document_number: str
    version: int
    effective_date: datetime
    project_name: str

    @property
    def version_label(self) -> str:
        return f"{self.version}.0"

    @property
    def effective_date_label(self) -> str:
        return self.effective_date.strftime("%m/%d/%Y")


@dataclass(frozen=True)
class TocEntry:
    title: str
    level: int
    page: int


@dataclass(frozen=True)
class TableBlock:
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class TextBlock:
    kind: Literal["h1", "h2", "h3", "h4", "p", "bullet"]
    text: str


Block = TextBlock | TableBlock


def build_publish_meta(
    project: Project,
    *,
    phase: str,
    version: int,
    pack_key: str | None = None,
    effective_date: datetime | None = None,
) -> ExportMeta:
    """Export meta for publish paths (OneDrive) without a frozen snapshot row."""
    from datetime import UTC

    template = get_template(phase)
    eff = effective_date or datetime.now(UTC)
    if pack_key and pack_key in PACK_BY_KEY:
        pack = PACK_BY_KEY[pack_key]
        title = pack.title
        doc_type = _DOC_TYPE_BY_PACK.get(pack_key, pack.title.upper())
        prefix = _NUMBER_PREFIX.get(pack_key, "REQ")
    else:
        title = template.document
        doc_type = "PROJECT CHARTER" if phase == "planning" else template.document.upper()
        prefix = _NUMBER_PREFIX.get(phase, "DOC")
    number = f"{prefix}-{int(version):03d}"
    return ExportMeta(
        title=title,
        document_type=doc_type,
        document_number=number,
        version=int(version),
        effective_date=eff,
        project_name=project.name,
    )


def build_export_meta(
    project: Project,
    snapshot: Snapshot,
    *,
    pack_key: str | None = None,
) -> ExportMeta:
    if pack_key and pack_key in PACK_BY_KEY:
        version = int(project.requirements_doc_version or 1)
    else:
        version = int(
            project.planning_doc_version
            if snapshot.phase == "planning"
            else project.requirements_doc_version
        ) or 1
    return build_publish_meta(
        project,
        phase=snapshot.phase,
        version=version,
        pack_key=pack_key,
        effective_date=snapshot.created_at,
    )


def parse_document_blocks(markdown: str) -> list[Block]:
    lines = markdown.splitlines()
    blocks: list[Block] = []
    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.strip()
        if not line or line == "---":
            i += 1
            continue
        if line.startswith("|") and i + 1 < len(lines) and _is_table_sep(lines[i + 1]):
            table_lines = [line]
            i += 1
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].strip())
                i += 1
            blocks.append(_parse_table(table_lines))
            continue
        if line.startswith("#### "):
            blocks.append(TextBlock("h4", _plain(line[5:])))
        elif line.startswith("### "):
            blocks.append(TextBlock("h3", _plain(line[4:])))
        elif line.startswith("## "):
            blocks.append(TextBlock("h2", _plain(line[3:])))
        elif line.startswith("# "):
            blocks.append(TextBlock("h1", _plain(line[2:])))
        elif line.startswith(("- ", "* ")):
            blocks.append(TextBlock("bullet", _plain(line[2:])))
        else:
            blocks.append(TextBlock("p", _plain(line)))
        i += 1
    return blocks


def toc_entries_for(blocks: list[Block], section_pages: dict[str, int]) -> list[TocEntry]:
    entries: list[TocEntry] = []
    section_no = 0
    for block in blocks:
        if not isinstance(block, TextBlock):
            continue
        if block.kind == "h1":
            entries.append(TocEntry(block.text, 1, section_pages.get(block.text, _CONTENT_START)))
        elif block.kind == "h2":
            section_no += 1
            numbered = f"{section_no}. {block.text}"
            entries.append(TocEntry(numbered, 1, section_pages.get(block.text, _CONTENT_START)))
        elif block.kind == "h3":
            entries.append(TocEntry(block.text, 2, section_pages.get(block.text, _CONTENT_START)))
    if not entries:
        entries.append(TocEntry("Document", 1, _CONTENT_START))
    vd_page = section_pages.get("Version Details", _CONTENT_START)
    entries.append(TocEntry("Version Details", 1, vd_page))
    return entries


_CONTENT_START = _COVER_PAGES + _TOC_PAGES + 1


def layout_section_pages(markdown: str) -> tuple[int, dict[str, int]]:
    """Count body PDF pages and map section titles to page numbers."""
    chunks = _split_by_sections(markdown)
    pages: dict[str, int] = {}
    body_page = 0
    section_no = 0
    for title, level, chunk in chunks:
        chunk_pages = _count_body_pages(chunk)
        final_page = _CONTENT_START + body_page
        pages[title] = final_page
        if level == "h2":
            section_no += 1
            pages[f"{section_no}. {title}"] = final_page
        body_page += chunk_pages
    version_pages = max(_count_body_pages(_version_details_html_placeholder()), 1)
    pages["Version Details"] = _CONTENT_START + body_page
    total_pages = _COVER_PAGES + _TOC_PAGES + body_page + version_pages
    return total_pages, pages


def _version_details_html_placeholder() -> str:
    return "<h1>Version Details</h1><table><tr><th>x</th><td>y</td></tr></table>"


def export_branded_docx(markdown: str, meta: ExportMeta) -> bytes:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT, WD_TAB_LEADER
    from docx.shared import Inches, Pt, RGBColor

    blocks = parse_document_blocks(markdown)
    total_pages, section_pages = layout_section_pages(markdown)
    toc = toc_entries_for(blocks, section_pages)

    doc = Document()
    _set_doc_defaults(doc)

    _docx_cover(doc, meta)
    doc.add_page_break()

    toc_section = doc.add_section()
    _docx_running_header(toc_section, meta, add_footer=True, total_pages=total_pages)
    h = doc.add_heading("Table of Contents", level=1)
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in h.runs:
        run.font.color.rgb = RGBColor(30, 58, 95)
    for entry in toc:
        p = doc.add_paragraph()
        indent = Inches(0.25 * (entry.level - 1))
        p.paragraph_format.left_indent = indent
        p.paragraph_format.tab_stops.add_tab_stop(
            Inches(6.2), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS
        )
        label = entry.title if entry.level > 1 else entry.title
        run = p.add_run(label)
        run.font.size = Pt(11)
        run.add_tab()
        run2 = p.add_run(str(entry.page))
        run2.font.size = Pt(11)
    doc.add_page_break()

    body_section = doc.add_section()
    _docx_running_header(body_section, meta, add_footer=True, total_pages=total_pages)
    _docx_body(doc, blocks, section_pages)
    _docx_version_details(doc, meta)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def export_branded_pdf(markdown: str, meta: ExportMeta) -> bytes:
    import pymupdf

    blocks = parse_document_blocks(markdown)
    body_only = _pdf_story_bytes(_blocks_to_html(blocks, numbered_h2=True))
    version_only = _pdf_story_bytes(_version_details_html(meta))
    body_page_count = max(pymupdf.open(stream=body_only).page_count, 1)
    version_page_count = max(pymupdf.open(stream=version_only).page_count, 1)
    total_pages = _COVER_PAGES + _TOC_PAGES + body_page_count + version_page_count

    _, section_pages = layout_section_pages(markdown)
    section_pages["Version Details"] = _CONTENT_START + body_page_count
    toc = toc_entries_for(blocks, section_pages)

    merged = pymupdf.open()
    for part in (
        _pdf_single_html_page(_cover_html(meta)),
        _pdf_single_html_page(_toc_html(toc)),
        body_only,
        version_only,
    ):
        src = pymupdf.open(stream=part)
        merged.insert_pdf(src)
        src.close()

    for idx in range(merged.page_count):
        page = merged[idx]
        _pdf_draw_running_header(page, meta, page_num=idx + 1, total_pages=total_pages)
        _pdf_draw_running_footer(page, meta, page_num=idx + 1, total_pages=total_pages)

    out = merged.tobytes()
    merged.close()
    return out


# --- shared helpers ---------------------------------------------------------


def _plain(text: str) -> str:
    return _BOLD.sub(r"\1", text).strip()


def _is_table_sep(line: str) -> bool:
    s = line.strip()
    return bool(s) and set(s.replace("|", "").replace(":", "").replace("-", "").strip()) <= {" "}


def _parse_table(lines: list[str]) -> TableBlock:
    rows: list[tuple[str, ...]] = []
    for i, line in enumerate(lines):
        if i == 1 and _is_table_sep(line):
            continue
        cells = tuple(_plain(c) for c in line.strip("|").split("|"))
        rows.append(cells)
    if not rows:
        return TableBlock((), ())
    return TableBlock(rows[0], tuple(rows[1:]))


def _split_by_sections(markdown: str) -> list[tuple[str, str, str]]:
    """Return (title, level, chunk_markdown) for each major heading block."""
    blocks = parse_document_blocks(markdown)
    chunks: list[tuple[str, str, str]] = []
    current_title = "Document"
    current_level = "h1"
    current_lines: list[str] = []
    for block in blocks:
        if isinstance(block, TextBlock) and block.kind in {"h1", "h2", "h3"}:
            if current_lines:
                chunks.append((current_title, current_level, "\n".join(current_lines)))
            current_title = block.text
            current_level = block.kind
            current_lines = [f"{'#' * int(block.kind[1])} {block.text}"]
        else:
            current_lines.append(_block_to_md(block))
    if current_lines:
        chunks.append((current_title, current_level, "\n".join(current_lines)))
    if not chunks:
        chunks.append(("Document", "h1", markdown))
    return chunks


def _block_to_md(block: Block) -> str:
    if isinstance(block, TableBlock):
        lines = ["| " + " | ".join(block.headers) + " |"]
        lines.append("| " + " | ".join("---" for _ in block.headers) + " |")
        for row in block.rows:
            lines.append("| " + " | ".join(row) + " |")
        return "\n".join(lines)
    prefix = {"h1": "# ", "h2": "## ", "h3": "### ", "h4": "#### ", "bullet": "- ", "p": ""}
    return f"{prefix[block.kind]}{block.text}"


def _body_html(chunk: str) -> str:
    blocks = parse_document_blocks(chunk)
    return _blocks_to_html(blocks, numbered_h2=False)


def _count_body_pages(chunk: str) -> int:
    import pymupdf

    html_body = _body_html(chunk)
    story = pymupdf.Story(html=_html_shell(html_body))
    tmp = io.BytesIO()
    writer = pymupdf.DocumentWriter(tmp)
    mediabox = pymupdf.paper_rect("a4")
    where = mediabox + (54, 72, -54, -80)
    while True:
        device = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(device)
        writer.end_page()
        if not more:
            break
    writer.close()
    return max(pymupdf.open(stream=tmp.getvalue()).page_count, 1)


def _html_shell(body: str) -> str:
    css = (
        "body { font-family: Arial, Helvetica, sans-serif; font-size: 11pt; "
        "color: #222; line-height: 1.45; }"
        "h1 { color: rgb(30,58,95); font-size: 16pt; margin-top: 14pt; }"
        "h2 { color: rgb(30,58,95); font-size: 13pt; margin-top: 12pt; }"
        "h3 { color: rgb(30,58,95); font-size: 12pt; margin-top: 10pt; }"
        "table { border-collapse: collapse; width: 100%; margin: 8pt 0; }"
        "th { background: #e8ecf1; font-weight: bold; text-align: left; }"
        "td, th { border: 1px solid #bbb; padding: 5pt 6pt; }"
        "ul { margin: 4pt 0 4pt 16pt; }"
    )
    return f"<!DOCTYPE html><html><head><style>{css}</style></head><body>{body}</body></html>"


def _blocks_to_html(blocks: list[Block], *, numbered_h2: bool) -> str:
    parts: list[str] = []
    section_no = 0
    for block in blocks:
        if isinstance(block, TableBlock):
            parts.append("<table><thead><tr>")
            for h in block.headers:
                parts.append(f"<th>{html.escape(h)}</th>")
            parts.append("</tr></thead><tbody>")
            for row in block.rows:
                parts.append("<tr>")
                for cell in row:
                    parts.append(f"<td>{html.escape(cell)}</td>")
                parts.append("</tr>")
            parts.append("</tbody></table>")
            continue
        text = html.escape(block.text)
        if block.kind == "h1":
            parts.append(f"<h1>{text}</h1>")
        elif block.kind == "h2":
            section_no += 1
            label = f"{section_no}. {text}" if numbered_h2 else text
            parts.append(f"<h2>{html.escape(label)}</h2>")
        elif block.kind == "h3":
            parts.append(f"<h3>{text}</h3>")
        elif block.kind == "h4":
            parts.append(f"<h4>{text}</h4>")
        elif block.kind == "bullet":
            parts.append(f"<ul><li>{text}</li></ul>")
        else:
            parts.append(f"<p>{text}</p>")
    return "\n".join(parts)


# --- DOCX building blocks ----------------------------------------------------


def _set_doc_defaults(doc) -> None:
    from docx.shared import Pt

    style = doc.styles["Normal"]
    style.font.name = "Arial"
    style.font.size = Pt(11)


def _docx_cover(doc, meta: ExportMeta) -> None:
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt, RGBColor

    for _ in range(4):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(meta.project_name)
    run.bold = True
    run.font.size = Pt(14)
    run.font.color.rgb = RGBColor(80, 80, 80)

    doc.add_paragraph()
    for label, value in (
        ("Document Type", meta.document_type),
        ("Document Number", meta.document_number),
    ):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r1 = p.add_run(f"{label}: ")
        r1.font.size = Pt(11)
        r2 = p.add_run(value)
        r2.bold = True
        r2.underline = True
        r2.font.size = Pt(11)

    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(meta.title)
    run.bold = True
    run.font.size = Pt(22)
    run.font.color.rgb = RGBColor(30, 30, 30)

    doc.add_paragraph()
    for label, value in (
        ("Version", meta.version_label),
        ("Effective Date", meta.effective_date_label),
    ):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(f"{label}: {value}")
        r.font.size = Pt(11)


def _docx_running_header(
    section, meta: ExportMeta, *, add_footer: bool, total_pages: int = 0
) -> None:
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
    from docx.shared import Inches, Pt

    header = section.header
    hp = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
    hp.clear()
    hp.paragraph_format.tab_stops.add_tab_stop(Inches(6.5), WD_TAB_ALIGNMENT.RIGHT)
    left = hp.add_run(f"Version: {meta.version_label}")
    left.font.size = Pt(9)
    hp.add_run("\t")
    right = hp.add_run(f"Effective Date: {meta.effective_date_label}")
    right.font.size = Pt(9)

    if not add_footer:
        return
    footer = section.footer
    fp = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    fp.clear()
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _add_footer_fields(fp, total_pages)


def _add_footer_fields(paragraph, total_pages: int) -> None:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt

    def _page_field() -> None:
        run = paragraph.add_run()
        run.font.size = Pt(8)
        r = run._r
        for tag, fld_type, text in (
            ("w:fldChar", "begin", None),
            ("w:instrText", None, "PAGE"),
            ("w:fldChar", "separate", None),
            ("w:fldChar", "end", None),
        ):
            el = OxmlElement(tag)
            if tag == "w:instrText":
                el.set(qn("xml:space"), "preserve")
                el.text = text or ""
            else:
                el.set(qn("w:fldCharType"), fld_type or "")
            r.append(el)

    left = paragraph.add_run("Internal use only  |  Generated by CrewLane  |  Page ")
    left.font.size = Pt(8)
    _page_field()
    right = paragraph.add_run(f" of {total_pages}")
    right.font.size = Pt(8)


def _docx_body(doc, blocks: list[Block], section_pages: dict[str, int]) -> None:
    from docx.shared import RGBColor

    section_no = 0
    skip_first_h1 = True
    for block in blocks:
        if isinstance(block, TableBlock):
            rows = [block.headers, *block.rows]
            table = doc.add_table(rows=len(rows), cols=len(block.headers))
            table.style = "Table Grid"
            for r_idx, row in enumerate(rows):
                for c_idx, cell_text in enumerate(row):
                    cell = table.rows[r_idx].cells[c_idx]
                    cell.text = cell_text
                    if r_idx == 0:
                        for p in cell.paragraphs:
                            for run in p.runs:
                                run.bold = True
            doc.add_paragraph()
            continue
        if block.kind == "h1" and skip_first_h1:
            skip_first_h1 = False
            continue
        if block.kind == "h2":
            section_no += 1
            h = doc.add_heading(f"{section_no}. {block.text}", level=1)
        elif block.kind == "h1":
            h = doc.add_heading(block.text, level=0)
        elif block.kind == "h3":
            h = doc.add_heading(block.text, level=2)
        elif block.kind == "h4":
            h = doc.add_heading(block.text, level=3)
        elif block.kind == "bullet":
            doc.add_paragraph(block.text, style="List Bullet")
            continue
        else:
            doc.add_paragraph(block.text)
            continue
        for run in h.runs:
            run.font.color.rgb = RGBColor(30, 58, 95)


def _docx_version_details(doc, meta: ExportMeta) -> None:
    from docx.shared import RGBColor

    doc.add_page_break()
    h = doc.add_heading("Version Details", level=1)
    for run in h.runs:
        run.font.color.rgb = RGBColor(30, 58, 95)
    table = doc.add_table(rows=4, cols=2)
    table.style = "Table Grid"
    for row_idx, (k, v) in enumerate(
        (
            ("Document", meta.title),
            ("Document Number", meta.document_number),
            ("Version", meta.version_label),
            ("Effective Date", meta.effective_date_label),
        )
    ):
        table.rows[row_idx].cells[0].text = k
        table.rows[row_idx].cells[1].text = v
        for p in table.rows[row_idx].cells[0].paragraphs:
            for run in p.runs:
                run.bold = True


# --- PDF building blocks -----------------------------------------------------


def _cover_html(meta: ExportMeta) -> str:
    dt = html.escape(meta.document_type)
    dn = html.escape(meta.document_number)
    title = html.escape(meta.title)
    proj = html.escape(meta.project_name)
    ver = html.escape(meta.version_label)
    eff = html.escape(meta.effective_date_label)
    return f"""
    <div style="font-family:Arial;text-align:center;padding-top:120pt;">
      <p style="font-size:12pt;color:#555;">{proj}</p>
      <p style="margin-top:36pt;font-size:11pt;">Document Type: <b><u>{dt}</u></b></p>
      <p style="font-size:11pt;">Document Number: <b><u>{dn}</u></b></p>
      <p style="margin-top:48pt;font-size:22pt;font-weight:bold;">{title}</p>
      <p style="margin-top:36pt;font-size:11pt;">Version: {ver}</p>
      <p style="font-size:11pt;">Effective Date: {eff}</p>
    </div>"""


def _toc_html(toc: list[TocEntry]) -> str:
    rows = []
    for e in toc:
        pad = "&nbsp;" * (4 * (e.level - 1))
        rows.append(
            f'<tr><td style="padding:4pt 0;">{pad}{html.escape(e.title)}</td>'
            f'<td style="text-align:right;padding:4pt 0;">{e.page}</td></tr>'
        )
    body_rows = "".join(rows)
    return f"""
    <div style="font-family:Arial;font-size:11pt;padding-top:24pt;">
      <p style="text-align:center;color:rgb(30,58,95);font-size:14pt;font-weight:bold;">
        Table of Contents
      </p>
      <table style="width:100%;border-collapse:collapse;margin-top:18pt;">
        {body_rows}
      </table>
    </div>"""


def _version_details_html(meta: ExportMeta) -> str:
    return f"""
    <h1>Version Details</h1>
    <table>
      <tr><th>Document</th><td>{html.escape(meta.title)}</td></tr>
      <tr><th>Document Number</th><td>{html.escape(meta.document_number)}</td></tr>
      <tr><th>Version</th><td>{html.escape(meta.version_label)}</td></tr>
      <tr><th>Effective Date</th><td>{html.escape(meta.effective_date_label)}</td></tr>
    </table>"""


def _pdf_single_html_page(inner_html: str) -> bytes:
    import pymupdf

    doc = pymupdf.open()
    mediabox = pymupdf.paper_rect("a4")
    page = doc.new_page(width=mediabox.width, height=mediabox.height)
    page.insert_htmlbox(mediabox + (54, 72, -54, -72), inner_html)
    data = doc.tobytes()
    doc.close()
    return data


def _pdf_story_bytes(inner_html: str) -> bytes:
    import pymupdf

    story = pymupdf.Story(html=_html_shell(inner_html))
    buf = io.BytesIO()
    writer = pymupdf.DocumentWriter(buf)
    mediabox = pymupdf.paper_rect("a4")
    where = mediabox + (54, 72, -54, -80)
    while True:
        device = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(device)
        writer.end_page()
        if not more:
            break
    writer.close()
    return buf.getvalue()


def _pdf_draw_running_header(page, meta: ExportMeta, *, page_num: int, total_pages: int) -> None:
    import pymupdf

    rect = page.rect
    y = 42
    page.draw_line((54, 52), (rect.width - 54, 52), color=_NAVY, width=0.6)
    page.insert_text((54, y), f"Version: {meta.version_label}", fontsize=9, fontname="helv")
    date_text = f"Effective Date: {meta.effective_date_label}"
    tw = pymupdf.get_text_length(date_text, fontname="helv", fontsize=9)
    page.insert_text((rect.width - 54 - tw, y), date_text, fontsize=9, fontname="helv")


def _pdf_draw_running_footer(page, meta: ExportMeta, *, page_num: int, total_pages: int) -> None:
    import pymupdf

    rect = page.rect
    y = rect.height - 36
    page.draw_line((54, y - 8), (rect.width - 54, y - 8), color=_NAVY, width=0.6)
    center = f"Internal use only  |  Generated by CrewLane  |  Page {page_num} of {total_pages}"
    tw = pymupdf.get_text_length(center, fontname="helv", fontsize=8)
    page.insert_text(((rect.width - tw) / 2, y), center, fontsize=8, fontname="helv")
