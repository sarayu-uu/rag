"""
File purpose:
- Text cleaning utilities for ingestion.
- Removes common noisy formatting, normalizes whitespace,
  and preserves page/section metadata when cleaning structured input.
"""

from __future__ import annotations

import re
from typing import Any


_ZERO_WIDTH_PATTERN = re.compile(r"[\u200B-\u200D\uFEFF]")
_DECORATIVE_LINE_PATTERN = re.compile(r"^[\s\-\_=*`~.]{4,}$")
_MULTI_SPACE_PATTERN = re.compile(r"[ \t]+")
_MULTI_NEWLINE_PATTERN = re.compile(r"\n{3,}")


def remove_noisy_formatting(text: str) -> str:
    """
    Remove common formatting noise while keeping readable content intact.
    """
    if not text:
        return ""

    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = cleaned.replace("\u00A0", " ")
    cleaned = _ZERO_WIDTH_PATTERN.sub("", cleaned)

    filtered_lines: list[str] = []
    for raw_line in cleaned.split("\n"):
        line = raw_line.strip()
        if _DECORATIVE_LINE_PATTERN.match(line):
            continue
        filtered_lines.append(raw_line)

    return "\n".join(filtered_lines)


def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace while preserving paragraph boundaries.
    """
    if not text:
        return ""

    lines = text.split("\n")
    normalized_lines = []
    for line in lines:
        line = _MULTI_SPACE_PATTERN.sub(" ", line).strip()
        normalized_lines.append(line)

    normalized = "\n".join(normalized_lines)
    normalized = _MULTI_NEWLINE_PATTERN.sub("\n\n", normalized)
    return normalized.strip()


def clean_text(text: str) -> str:
    """
    Full text-cleaning pipeline for extracted raw text.
    """
    return normalize_whitespace(remove_noisy_formatting(text))


def clean_sections(
    sections: list[dict[str, Any]],
    *,
    text_key: str = "text",
) -> list[dict[str, Any]]:
    """
    Clean section/page text without modifying section metadata.
    """
    cleaned_sections: list[dict[str, Any]] = []

    for section in sections:
        section_copy = dict(section)
        value = section_copy.get(text_key, "")

        if isinstance(value, str):
            section_copy[text_key] = clean_text(value)

        cleaned_sections.append(section_copy)

    return cleaned_sections

