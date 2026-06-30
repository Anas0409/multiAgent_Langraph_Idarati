"""PDF export for submitted reclamations using ReportLab."""

import io
import os
import re
import time

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

PDFS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pdfs")

# ── Colour palette ──────────────────────────────────────────────
C_DARK   = colors.HexColor("#0f172a")
C_INDIGO = colors.HexColor("#4f46e5")
C_MUTED  = colors.HexColor("#64748b")
C_LIGHT  = colors.HexColor("#f1f5f9")
C_BORDER = colors.HexColor("#e2e8f0")
C_GREEN  = colors.HexColor("#10b981")
C_ORANGE = colors.HexColor("#f59e0b")
C_RED    = colors.HexColor("#ef4444")
C_WHITE  = colors.white


def _safe(text: str) -> str:
    """Escape HTML special chars for ReportLab Paragraph."""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


def _strip_md(text: str) -> str:
    """Strip lightweight Markdown for clean PDF rendering."""
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", text)
    text = re.sub(r"_{1,2}(.+?)_{1,2}", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    return text.strip()


def _quality_color(score: float) -> colors.Color:
    if score >= 0.85:
        return C_GREEN
    if score >= 0.5:
        return C_ORANGE
    return C_RED


def generate_pdf(data: dict) -> bytes:
    """Generate a PDF report and return the raw bytes."""
    sid = data.get("session_id", "unknown")
    buf = io.BytesIO()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()

    def style(name, **kw):
        return ParagraphStyle(name, parent=styles["Normal"], **kw)

    s_title    = style("T",  fontSize=22, textColor=C_DARK,   alignment=TA_CENTER, spaceAfter=4,  fontName="Helvetica-Bold")
    s_sub      = style("S",  fontSize=10, textColor=C_MUTED,  alignment=TA_CENTER, spaceAfter=14)
    s_section  = style("H",  fontSize=12, textColor=C_INDIGO, spaceBefore=16, spaceAfter=8, fontName="Helvetica-Bold")
    s_body     = style("B",  fontSize=9,  textColor=C_DARK,   leading=15, spaceAfter=5)
    s_response = style("R",  fontSize=9,  textColor=C_DARK,   leading=16, spaceAfter=4, leftIndent=8)
    s_footer   = style("F",  fontSize=7,  textColor=C_MUTED,  alignment=TA_CENTER)

    story = []

    # ── Header ──────────────────────────────────────────────────
    story.append(Paragraph("IDARATI v2", s_title))
    story.append(Paragraph("Rapport de Réclamation Administrative", s_sub))
    story.append(HRFlowable(width="100%", thickness=2, color=C_INDIGO, spaceAfter=14))

    # ── Metadata ────────────────────────────────────────────────
    created = data.get("created_at", time.strftime("%Y-%m-%d %H:%M"))
    proc_ms = data.get("processing_time_ms", 0)
    proc_s  = f"{proc_ms / 1000:.1f}s" if proc_ms else "N/A"
    qs      = data.get("quality_score", 0)

    meta = [
        ["Session ID",  _safe(sid[:20]),            "Date",         _safe(created)],
        ["Utilisateur", _safe(data.get("user_id", "N/A")), "Canal", _safe(data.get("canal_cible", "N/A"))],
        ["Priorité",    _safe(data.get("priorite", "N/A")), "Langue", _safe(data.get("langue", "fr"))],
        ["Intent",      _safe(data.get("intent", "N/A")),  "Temps",  proc_s],
    ]
    meta_tbl = Table(meta, colWidths=[3 * cm, 6.5 * cm, 3 * cm, 4.5 * cm])
    meta_tbl.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (0, -1), C_LIGHT),
        ("BACKGROUND",  (2, 0), (2, -1), C_LIGHT),
        ("TEXTCOLOR",   (0, 0), (0, -1), C_MUTED),
        ("TEXTCOLOR",   (2, 0), (2, -1), C_MUTED),
        ("FONTNAME",    (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",    (2, 0), (2, -1), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 8),
        ("GRID",        (0, 0), (-1, -1), 0.4, C_BORDER),
        ("PADDING",     (0, 0), (-1, -1), 5),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(meta_tbl)

    # ── Demande originale ────────────────────────────────────────
    story.append(Paragraph("Demande Originale", s_section))
    demande = _safe(data.get("demande_brute", ""))
    story.append(Paragraph(f'<i>"{demande}"</i>', s_body))

    # ── Analyse & Classification ─────────────────────────────────
    story.append(Paragraph("Analyse &amp; Classification", s_section))
    qc = _quality_color(qs)
    analysis = [
        ["Intent détecté",   _safe(data.get("intent", "N/A"))],
        ["Priorité",         _safe(data.get("priorite", "N/A"))],
        ["Langue détectée",  _safe(data.get("langue", "fr"))],
        ["Score qualité",    f"{qs:.0%}"],
        ["Temps traitement", proc_s],
    ]
    a_tbl = Table(analysis, colWidths=[4.5 * cm, 12.5 * cm])
    a_tbl.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (0, -1), colors.HexColor("#ede9fe")),
        ("TEXTCOLOR",   (0, 0), (0, -1), C_INDIGO),
        ("FONTNAME",    (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 8),
        ("GRID",        (0, 0), (-1, -1), 0.4, C_BORDER),
        ("PADDING",     (0, 0), (-1, -1), 5),
        # Color the quality score cell
        ("TEXTCOLOR",   (1, 3), (1, 3), qc),
        ("FONTNAME",    (1, 3), (1, 3), "Helvetica-Bold"),
    ]))
    story.append(a_tbl)

    # ── Plan de routage ──────────────────────────────────────────
    routing = data.get("routing_plan", [])
    if routing:
        story.append(Paragraph("Plan de Traitement des Agents", s_section))
        plan_str = " → ".join(_safe(a) for a in routing)
        story.append(Paragraph(f"Agents activés : <b>{plan_str}</b>", s_body))

    # ── Sources RAG ─────────────────────────────────────────────
    docs = data.get("documents_retrieved", [])
    if docs:
        story.append(Paragraph("Sources Consultées (RAG)", s_section))
        for i, src in enumerate(docs[:5], 1):
            snippet = _safe(str(src)[:220])
            story.append(Paragraph(f"<b>[{i}]</b> {snippet}…", s_body))

    # ── Réponse finale ───────────────────────────────────────────
    story.append(Paragraph("Réponse Finale", s_section))
    story.append(HRFlowable(width="100%", thickness=0.5, color=C_BORDER, spaceAfter=8))

    reponse = _strip_md(data.get("reponse_finale", ""))
    for para in reponse.split("\n\n"):
        para = para.strip()
        if para:
            story.append(Paragraph(_safe(para), s_response))

    # Quality badge
    story.append(Spacer(1, 0.4 * cm))
    q_style = style("QS", fontSize=9, textColor=qc, fontName="Helvetica-Bold")
    label = "✓ Validé" if qs >= 0.85 else "⚠ Partiel" if qs >= 0.5 else "✗ Faible"
    story.append(Paragraph(f"Score qualité : {qs:.0%}  —  {label}", q_style))

    # ── Trace d'exécution ────────────────────────────────────────
    audit_log = data.get("audit_log", [])
    if audit_log:
        story.append(Paragraph("Trace d'Exécution", s_section))
        rows = [["Nœud", "Δ Temps", "Détails"]]
        prev_ts = audit_log[0].get("ts", 0) if audit_log else 0
        for entry in audit_log:
            ts = entry.get("ts", 0)
            delta = ts - prev_ts if prev_ts else 0
            prev_ts = ts
            details = " | ".join(
                f"{k}={v}" for k, v in entry.items()
                if k not in ("node", "ts") and v is not None and str(v)
            )
            rows.append([
                _safe(entry.get("node", "")),
                f"+{delta:.2f}s",
                _safe(details[:55]),
            ])
        t_tbl = Table(rows, colWidths=[4.2 * cm, 2.3 * cm, 10.5 * cm])
        t_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), C_DARK),
            ("TEXTCOLOR",     (0, 0), (-1, 0), C_WHITE),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 7),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [C_WHITE, C_LIGHT]),
            ("GRID",          (0, 0), (-1, -1), 0.25, C_BORDER),
            ("PADDING",       (0, 0), (-1, -1), 4),
        ]))
        story.append(t_tbl)

    # ── Footer ───────────────────────────────────────────────────
    story.append(Spacer(1, 0.8 * cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=C_BORDER, spaceAfter=6))
    story.append(Paragraph(
        f"Rapport généré le {time.strftime('%d/%m/%Y à %H:%M')} "
        f"— Idarati v2 — Système Multi-Agent LangGraph",
        s_footer,
    ))

    doc.build(story)
    return buf.getvalue()
