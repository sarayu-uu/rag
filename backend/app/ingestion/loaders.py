"""
File purpose:
- Contains all ingestion loaders for supported input types.
- Each loader converts its input source into plain text for downstream RAG processing.
"""

from pathlib import Path
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


def load_docx(file_path: Union[str, Path]) -> str:
    doc = Document(file_path)
    text = ""
    for para in doc.paragraphs:
        text += para.text + "\n"
    return text


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
