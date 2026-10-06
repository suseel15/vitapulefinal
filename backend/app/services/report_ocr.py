import asyncio
import importlib.metadata
import io
import re
import shutil
import sys
import tempfile
from pathlib import Path

from fastapi import HTTPException, status
from PIL import Image
from pypdf import PdfReader

from app.core.config import Settings
from app.schemas.medical_report import OCRQuality, OCRResult, PageText

MAX_REPORT_PAGES = 200
MAX_IMAGE_PIXELS = 30_000_000
LANGUAGE_PATTERN = re.compile(r"^[a-zA-Z0-9_+-]{2,64}$")


class OCRUnavailableError(RuntimeError):
    pass


class OCRExecutionError(RuntimeError):
    pass


def validate_report_file(content: bytes, filename: str, mime_type: str, max_size_mb: int) -> str:
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The selected report is empty.")
    if len(content) > max_size_mb * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"Reports must be no larger than {max_size_mb} MB.",
        )

    detected_mime = None
    if content.startswith(b"%PDF-"):
        detected_mime = "application/pdf"
        try:
            reader = PdfReader(io.BytesIO(content), strict=True)
            if reader.is_encrypted:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Password-protected reports cannot be processed.",
                )
            if not reader.pages:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The PDF contains no pages.")
            if len(reader.pages) > MAX_REPORT_PAGES:
                raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="The PDF has too many pages.")
        except HTTPException:
            raise
        except Exception as error:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The selected PDF is invalid.") from error
    elif content.startswith(b"\xff\xd8\xff"):
        detected_mime = "image/jpeg"
    elif content.startswith(b"\x89PNG\r\n\x1a\n"):
        detected_mime = "image/png"

    if detected_mime is None or mime_type.lower() != detected_mime:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Upload a valid PDF, JPEG, or PNG report.",
        )

    extension = Path(filename.replace("\\", "/")).suffix.lower()
    valid_extensions = {
        "application/pdf": {".pdf"},
        "image/jpeg": {".jpg", ".jpeg"},
        "image/png": {".png"},
    }
    if extension and extension not in valid_extensions[detected_mime]:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="The file extension does not match the report file type.",
        )
    if detected_mime != "application/pdf":
        try:
            with Image.open(io.BytesIO(content)) as image:
                image.verify()
            with Image.open(io.BytesIO(content)) as image:
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail="The report image dimensions are too large.",
                    )
        except HTTPException:
            raise
        except Exception as error:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The selected image is invalid.") from error
    return detected_mime


def _image_as_pdf(content: bytes) -> bytes:
    with Image.open(io.BytesIO(content)) as source:
        image = source.convert("RGB")
        output = io.BytesIO()
        image.save(output, format="PDF", resolution=150)
        return output.getvalue()


def _page_texts(pdf_content: bytes) -> list[str]:
    reader = PdfReader(io.BytesIO(pdf_content), strict=True)
    if reader.is_encrypted:
        raise OCRExecutionError("The PDF is encrypted.")
    if len(reader.pages) > MAX_REPORT_PAGES:
        raise OCRExecutionError("The PDF contains too many pages.")
    return [(page.extract_text() or "").strip() for page in reader.pages]


def _quality(texts: list[str]) -> OCRQuality:
    if not any(text.strip() for text in texts):
        return OCRQuality.LOW_QUALITY
    if sum(len(text.strip()) for text in texts) < 20:
        return OCRQuality.LOW_QUALITY
    return OCRQuality.GOOD


def _resolve_executable(name: str) -> str | None:
    located = shutil.which(name)
    if located:
        return located
    suffix = ".exe" if sys.platform == "win32" else ""
    candidate = Path(sys.executable).resolve().parent / f"{name}{suffix}"
    return str(candidate) if candidate.is_file() else None


async def process_report_ocr(content: bytes, mime_type: str, settings: Settings) -> OCRResult:
    input_pdf = content if mime_type == "application/pdf" else _image_as_pdf(content)
    try:
        source_pages = _page_texts(input_pdf)
    except Exception as error:
        raise OCRExecutionError("The uploaded report could not be read.") from error

    if source_pages and all(len(text.strip()) >= 8 for text in source_pages):
        return OCRResult(
            pages=[PageText(page_number=index + 1, text=text) for index, text in enumerate(source_pages)],
            ocr_engine="pypdf",
            ocr_version=importlib.metadata.version("pypdf"),
            pages_processed=len(source_pages),
            text_length=sum(len(text) for text in source_pages),
            ocr_confidence=None,
            quality=OCRQuality.TEXT_LAYER,
        )

    executable = _resolve_executable(settings.ocr_executable)
    if not executable:
        raise OCRUnavailableError("OCRmyPDF is not installed or is not available on PATH.")
    if not settings.ocr_enabled or not settings.ocrmy_pdf_enabled:
        raise OCRUnavailableError("OCR is not enabled.")
    if not LANGUAGE_PATTERN.fullmatch(settings.ocr_languages):
        raise OCRUnavailableError("The configured OCR language value is invalid.")
    ghostscript_names = ("gswin64c", "gswin32c", "gs") if sys.platform == "win32" else ("gs",)
    if not _resolve_executable("tesseract") or not any(_resolve_executable(name) for name in ghostscript_names):
        raise OCRUnavailableError("Tesseract and Ghostscript must be installed for scanned reports.")

    with tempfile.TemporaryDirectory(prefix="vitapulse-ocr-") as temp_directory:
        input_path = Path(temp_directory) / "source.pdf"
        output_path = Path(temp_directory) / "searchable.pdf"
        input_path.write_bytes(input_pdf)
        command = [
            executable,
            "--skip-text",
            "--deskew",
            "--rotate-pages",
            "--jobs",
            "1",
            "--language",
            settings.ocr_languages,
            str(input_path),
            str(output_path),
        ]
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except OSError as error:
            raise OCRUnavailableError("OCRmyPDF could not be started.") from error
        try:
            await asyncio.wait_for(process.wait(), timeout=settings.ocr_timeout_seconds)
        except TimeoutError as error:
            process.kill()
            await process.wait()
            raise OCRExecutionError("OCR processing timed out.") from error
        if process.returncode != 0 or not output_path.is_file():
            raise OCRExecutionError("OCRmyPDF could not process the report.")
        try:
            texts = _page_texts(output_path.read_bytes())
        except Exception as error:
            raise OCRExecutionError("The OCR output could not be read.") from error
        try:
            version_process = await asyncio.create_subprocess_exec(
                executable,
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            version_output, _ = await asyncio.wait_for(version_process.communicate(), timeout=5)
            version = version_output.decode("utf-8", errors="replace").strip()[:100] or "unknown"
        except (OSError, TimeoutError):
            version = "unknown"

    return OCRResult(
        pages=[PageText(page_number=index + 1, text=text) for index, text in enumerate(texts)],
        ocr_engine="ocrmypdf",
        ocr_version=version,
        pages_processed=len(texts),
        text_length=sum(len(text) for text in texts),
        ocr_confidence=None,
        quality=_quality(texts),
    )
