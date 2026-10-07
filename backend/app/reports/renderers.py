import html
import unicodedata

from fpdf import FPDF

from app.reports.schemas import ReportData


def render_html(report: ReportData) -> bytes:
    sections = []
    for section in report.sections:
        values = "".join(
            "<li><strong>" + html.escape(value.label) + ":</strong> " + html.escape(value.value)
            + " <small>[" + html.escape(", ".join(value.source_ids) or "No linked source") + "]</small></li>"
            for value in section.values
        )
        sections.append(
            "<section><h2>" + html.escape(section.title) + "</h2><ul>" + values + "</ul></section>"
        )

    sources = "".join(
        "<li><strong>" + html.escape(source.source_id) + "</strong> "
        + html.escape(source.source_label) + " — "
        + html.escape(source.timestamp.isoformat()) + " ("
        + html.escape(source.provenance.value) + ")</li>"
        for source in report.sources
    )
    data_gaps = "".join("<li>" + html.escape(gap) + "</li>" for gap in report.data_gaps)
    ai_section = ""
    if report.ai_interpretation is not None:
        ai = report.ai_interpretation
        observations = "".join(
            "<li>" + html.escape(item.observation) + " <small>[" + html.escape(", ".join(item.source_ids)) + "]</small></li>"
            for item in ai.key_observations
        )
        recommendations = "".join(
            "<li>" + html.escape(item.recommendation) + " <small>[" + html.escape(", ".join(item.source_ids)) + "]</small></li>"
            for item in ai.recommendations
        )
        ai_section = (
            "<section><h2>AI-assisted interpretation</h2><p>" + html.escape(ai.summary)
            + " <small>[" + html.escape(", ".join(ai.summary_source_ids)) + "]</small></p>"
            "<h3>Observations</h3><ul>" + observations + "</ul>"
            "<h3>Recommendations for review</h3><ul>" + recommendations + "</ul></section>"
        )
    longitudinal = "".join(
        "<li>" + html.escape(item.statement) + " <small>["
        + html.escape(", ".join(item.source_ids)) + "]</small></li>"
        for item in report.longitudinal_insights
    )
    limitations = "".join("<li>" + html.escape(item) + "</li>" for item in report.limitations)

    document = (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>" + html.escape(report.title) + "</title><style>"
        "body{font:16px/1.55 system-ui,sans-serif;color:#182230;background:#f5f8fc;margin:0;padding:2rem}"
        "main{max-width:900px;margin:auto;background:#fff;padding:2rem;border-radius:16px}"
        "h1,h2{color:#153d70}section{border-top:1px solid #dbe4ee;padding:1rem 0}"
        "li{margin:.45rem 0}small{color:#53677f} .notice{background:#fff8df;padding:1rem;border-radius:8px}"
        "</style></head><body><main><h1>" + html.escape(report.title) + "</h1>"
        "<p>Generated " + html.escape(report.generated_at.isoformat()) + "</p>"
        "<p class=\"notice\">Completeness: " + html.escape(report.data_completeness.value)
        + ". This report summarizes recorded data and is not a diagnosis or medical clearance.</p>"
        "<p>" + html.escape(report.factual_summary) + "</p>"
        + "".join(sections) + ai_section
        + "<section><h2>Longitudinal comparisons</h2><ul>" + longitudinal + "</ul></section>"
        + "<section><h2>Data gaps</h2><ul>" + data_gaps + "</ul></section>"
        + "<section><h2>Limitations</h2><ul>" + limitations + "</ul></section>"
        + "<section><h2>Sources</h2><ul>" + sources + "</ul></section>"
        + "</main></body></html>"
    )
    return document.encode("utf-8")


def render_pdf(report: ReportData) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    _pdf_line(pdf, report.title, 11)
    pdf.set_font("Helvetica", size=10)
    _pdf_line(pdf, f"Generated {report.generated_at.isoformat()}")
    _pdf_line(pdf, f"Completeness: {report.data_completeness.value}")
    _pdf_line(pdf, "This report summarizes recorded data and is not a diagnosis or medical clearance.")
    pdf.ln(3)
    pdf.set_font("Helvetica", size=11)
    _pdf_line(pdf, report.factual_summary, 7)

    for section in report.sections:
        _pdf_heading(pdf, section.title)
        if not section.values:
            _pdf_line(pdf, "No recorded values for this category.")
        for value in section.values:
            _pdf_line(pdf, f"{value.label}: {value.value} [{', '.join(value.source_ids) or 'No linked source'}]")

    if report.ai_interpretation is not None:
        _pdf_heading(pdf, "AI-assisted interpretation")
        _pdf_line(
            pdf,
            f"{report.ai_interpretation.summary} [{', '.join(report.ai_interpretation.summary_source_ids)}]",
        )
        for item in report.ai_interpretation.key_observations:
            _pdf_line(pdf, f"Observation: {item.observation} [{', '.join(item.source_ids)}]")
        for item in report.ai_interpretation.recommendations:
            _pdf_line(pdf, f"Review: {item.recommendation} [{', '.join(item.source_ids)}]")

    _pdf_heading(pdf, "Longitudinal comparisons")
    for insight in report.longitudinal_insights:
        _pdf_line(pdf, f"{insight.statement} [{', '.join(insight.source_ids)}]")
    if not report.longitudinal_insights:
        _pdf_line(pdf, "No comparisons met the minimum-data requirement.")

    _pdf_heading(pdf, "Data gaps")
    for gap in report.data_gaps or ["No known data gaps were detected."]:
        _pdf_line(pdf, f"- {gap}")
    _pdf_heading(pdf, "Limitations")
    for limitation in report.limitations:
        _pdf_line(pdf, f"- {limitation}")
    _pdf_heading(pdf, "Sources")
    for source in report.sources:
        _pdf_line(
            pdf,
            f"{source.source_id}: {source.source_label}, {source.timestamp.isoformat()}, {source.provenance.value}",
        )
    return bytes(pdf.output())


def _pdf_heading(pdf: FPDF, text: str) -> None:
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(21, 61, 112)
    _pdf_line(pdf, text, 8)
    pdf.set_text_color(24, 34, 48)
    pdf.set_font("Helvetica", size=11)


def _pdf_text(value: str) -> str:
    return unicodedata.normalize("NFKD", value).encode("latin-1", "replace").decode("latin-1")


def _pdf_line(pdf: FPDF, text: str, height: float = 6) -> None:
    pdf.multi_cell(0, height, _pdf_text(text), new_x="LMARGIN", new_y="NEXT")
