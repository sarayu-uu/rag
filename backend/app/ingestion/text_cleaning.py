"""
File purpose:
- Text cleaning utilities for ingestion.
- Removes common noisy formatting, normalizes whitespace,
  and preserves page/section metadata when cleaning structured input.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any


_ZERO_WIDTH_PATTERN = re.compile(r"[\u200B-\u200D\uFEFF]")
_DECORATIVE_LINE_PATTERN = re.compile(r"^[\s\-\_=*`~.]{4,}$")
_LONG_SEPARATOR_PATTERN = re.compile(r"[\-=*_~#]{4,}")
_BULLET_PREFIX_PATTERN = re.compile(r"^\s*(?:[-*•▪◦]+|\d+[.)])\s+")
_MULTI_SPACE_PATTERN = re.compile(r"[ \t]+")
_MULTI_NEWLINE_PATTERN = re.compile(r"\n{3,}")
_NON_TEXT_SYMBOL_PATTERN = re.compile(r"[^\w\s.,:;!?()/'\"%-]")

_REPLACEMENTS = {
    "\u00A0": " ",
    "â†’": " ",
    "→": " ",
    "â€“": "-",
    "â€”": "-",
    "–": "-",
    "—": "-",
    "•": " ",
    "▪": " ",
    "◦": " ",
}


def remove_noisy_formatting(text: str) -> str:
    """
    Remove common formatting noise while keeping readable content intact.
    """
    if not text:
        return ""

    cleaned = unicodedata.normalize("NFKC", text)
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    for old, new in _REPLACEMENTS.items():
        cleaned = cleaned.replace(old, new)
    cleaned = _ZERO_WIDTH_PATTERN.sub("", cleaned)
    cleaned = _LONG_SEPARATOR_PATTERN.sub("\n", cleaned)

    filtered_lines: list[str] = []
    for raw_line in cleaned.split("\n"):
        line = _BULLET_PREFIX_PATTERN.sub("", raw_line).strip()
        if _DECORATIVE_LINE_PATTERN.match(line):
            continue
        line = _NON_TEXT_SYMBOL_PATTERN.sub(" ", line)
        line = _MULTI_SPACE_PATTERN.sub(" ", line).strip()
        if not line:
            continue
        filtered_lines.append(line)

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

