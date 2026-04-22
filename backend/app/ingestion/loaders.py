"""
File purpose:
- Contains all ingestion loaders for supported input types.
- Each loader converts its input source into plain text for downstream RAG processing.
"""

from pathlib import Path
import subprocess
import tempfile
from typing import Union

# PDF
import fitz  # PyMuPDF

# DOCX
from docx import Document

# PPTX
from pptx import Presentation

# Image OCR
from PIL import Image
import pytesseract

# CSV
import pandas as pd

# Web
import requests
from bs4 import BeautifulSoup

# JSON
import json
import xml.etree.ElementTree as ET


def _run_powershell_office_conversion(
    script: str,
    source_path: Path,
    output_path: Path,
) -> None:
    try:
        subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                script,
                str(source_path),
                str(output_path),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=120,
        )
    except FileNotFoundError as exc:
        raise ValueError("PowerShell is not available for legacy Office file conversion.") from exc
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Legacy Office file conversion timed out.") from exc
    except subprocess.CalledProcessError as exc:
        details = exc.stderr.strip() or exc.stdout.strip() or "Unknown conversion error."
        raise ValueError(f"Legacy Office file conversion failed: {details}") from exc


def load_pdf(file_path: Union[str, Path]) -> str:
    sections = load_pdf_sections(file_path)
    return "\n".join(section["text"] for section in sections)


def load_pdf_sections(file_path: Union[str, Path]) -> list[dict[str, Union[int, str]]]:
    doc = fitz.open(file_path)
    sections: list[dict[str, Union[int, str]]] = []
    for page_index, page in enumerate(doc, start=1):
        sections.append(
            {
                "page_number": page_index,
                "text": page.get_text(),
            }
        )
    doc.close()
    return sections


def load_doc(file_path: Union[str, Path]) -> str:
    source_path = Path(file_path)
    with tempfile.TemporaryDirectory() as temp_dir:
        converted_path = Path(temp_dir) / f"{source_path.stem}.docx"
        script = (
            "$ErrorActionPreference='Stop';"
            "$sourcePath=$args[0];"
            "$outputPath=$args[1];"
            "$word=$null;"
            "$document=$null;"
            "try {"
            "  $word=New-Object -ComObject Word.Application;"
            "  $word.Visible=$false;"
            "  $document=$word.Documents.Open($sourcePath);"
            "  $document.SaveAs([ref]$outputPath,[ref]16);"
            "} finally {"
            "  if ($document -ne $null) { $document.Close() }"
            "  if ($word -ne $null) { $word.Quit() }"
            "}"
        )
        _run_powershell_office_conversion(script, source_path, converted_path)
        return load_docx(converted_path)


def load_docx(file_path: Union[str, Path]) -> str:
    doc = Document(file_path)
    text = ""
    for para in doc.paragraphs:
        text += para.text + "\n"
    return text


def load_ppt(file_path: Union[str, Path]) -> str:
    source_path = Path(file_path)
    with tempfile.TemporaryDirectory() as temp_dir:
        converted_path = Path(temp_dir) / f"{source_path.stem}.pptx"
        script = (
            "$ErrorActionPreference='Stop';"
            "$sourcePath=$args[0];"
            "$outputPath=$args[1];"
            "$powerpoint=$null;"
            "$presentation=$null;"
            "try {"
            "  $powerpoint=New-Object -ComObject PowerPoint.Application;"
            "  $presentation=$powerpoint.Presentations.Open($sourcePath,$false,$false,$false);"
            "  $presentation.SaveAs($outputPath,24);"
            "} finally {"
            "  if ($presentation -ne $null) { $presentation.Close() }"
            "  if ($powerpoint -ne $null) { $powerpoint.Quit() }"
            "}"
        )
        _run_powershell_office_conversion(script, source_path, converted_path)
        return load_pptx(converted_path)


def load_pptx(file_path: Union[str, Path]) -> str:
    prs = Presentation(file_path)
    text = ""
    for slide in prs.slides:
        for shape in slide.shapes:
            if hasattr(shape, "text"):
                text += shape.text + "\n"
    return text


def load_image(file_path: Union[str, Path]) -> str:
    img = Image.open(file_path)
    text = pytesseract.image_to_string(img)
    return text


def load_csv(file_path: Union[str, Path]) -> str:
    df = pd.read_csv(file_path)
    text = ""
    for _, row in df.iterrows():
        row_text = ", ".join([f"{col}: {row[col]}" for col in df.columns])
        text += row_text + "\n"
    return text


def load_txt(file_path: Union[str, Path]) -> str:
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def load_web(url: str) -> str:
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    for script in soup(["script", "style"]):
        script.decompose()

    return soup.get_text(separator="\n")


def load_json(file_path: Union[str, Path]) -> str:
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return json.dumps(data, indent=2)


def load_xml(file_path: Union[str, Path]) -> str:
    tree = ET.parse(file_path)
    root = tree.getroot()

    parts: list[str] = []

    def walk(element: ET.Element, path: str) -> None:
        current_path = f"{path}/{element.tag}" if path else element.tag

        text = (element.text or "").strip()
        if text:
            parts.append(f"{current_path}: {text}")

        for key, value in element.attrib.items():
            parts.append(f"{current_path}[@{key}]: {value}")

        for child in list(element):
            walk(child, current_path)

    walk(root, "")
    return "\n".join(parts)
