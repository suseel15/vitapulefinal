from io import BytesIO

import pytest
from fpdf import FPDF
from fastapi import HTTPException
from PIL import Image

from app.core.config import Settings
from app.schemas.medical_report import OCRQuality, OCRResult, PageText
from app.services.report_extraction import extract_structured_report
from app.services.report_ocr import process_report_ocr, validate_report_file


def png_bytes() -> bytes:
    image = Image.new("RGB", (8, 8), "white")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_report_upload_checks_image_signature_and_mime() -> None:
    content = png_bytes()

    assert validate_report_file(content, "lab.png", "image/png", 25) == "image/png"

    with pytest.raises(HTTPException) as error:
        validate_report_file(content, "lab.png", "application/pdf", 25)
    assert error.value.status_code == 415


def test_report_upload_rejects_invalid_pdf_and_oversized_files() -> None:
    with pytest.raises(HTTPException) as invalid_pdf:
        validate_report_file(b"%PDF-1.7 not a pdf", "lab.pdf", "application/pdf", 25)
    assert invalid_pdf.value.status_code == 400

    with pytest.raises(HTTPException) as oversized:
        validate_report_file(b"x" * 11, "lab.pdf", "application/pdf", 0)
    assert oversized.value.status_code == 413


def test_report_upload_rejects_extension_mismatch() -> None:
    with pytest.raises(HTTPException) as error:
        validate_report_file(png_bytes(), "lab.pdf", "image/png", 25)
    assert error.value.status_code == 415


@pytest.mark.asyncio
async def test_embedded_pdf_text_is_extracted_without_running_ocr() -> None:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(text="Hemoglobin 13.5 g/dL")
    content = bytes(pdf.output())

    result = await process_report_ocr(
        content,
        "application/pdf",
        Settings(ocr_enabled=False),
    )

    assert result.ocr_engine == "pypdf"
    assert result.quality == OCRQuality.TEXT_LAYER
    assert result.ocr_confidence is None
    assert "Hemoglobin 13.5 g/dL" in result.pages[0].text


def test_biomarker_extraction_preserves_source_and_does_not_invent_confidence_or_codes() -> None:
    page_text = "Hemoglobin 13.5 g/dL (12.0 - 16.0)\nGlucose 104 mg/dL HIGH"
    result = OCRResult(
        pages=[PageText(page_number=2, text=page_text)],
        ocr_engine="test",
        ocr_version="1",
        pages_processed=1,
        text_length=len(page_text),
        ocr_confidence=None,
        quality=OCRQuality.GOOD,
    )

    extracted = extract_structured_report(result)

    assert [item.canonical_name for item in extracted.biomarkers] == ["hemoglobin", "glucose"]
    assert extracted.biomarkers[0].value_numeric == 13.5
    assert extracted.biomarkers[0].unit == "g/dL"
    assert extracted.biomarkers[0].reference_low == 12.0
    assert extracted.biomarkers[0].reference_high == 16.0
    assert extracted.biomarkers[1].abnormal_flag == "HIGH"
    assert all(item.standard_code is None for item in extracted.biomarkers)
    assert all(item.confidence is None for item in extracted.biomarkers)
    assert all(item.source_page == 2 for item in extracted.biomarkers)
    assert extracted.biomarkers[0].source_text == "Hemoglobin 13.5 g/dL (12.0 - 16.0)"


def test_biomarker_extraction_ignores_unknown_and_non_numeric_lines() -> None:
    result = OCRResult(
        pages=[PageText(page_number=1, text="Patient number 12834\nHemoglobin pending")],
        ocr_engine="test",
        ocr_version="1",
        pages_processed=1,
        text_length=39,
        ocr_confidence=None,
        quality=OCRQuality.GOOD,
    )

    assert extract_structured_report(result).biomarkers == []
