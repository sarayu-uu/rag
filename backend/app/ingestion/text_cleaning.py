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

# Removes noisy formatting artifacts from extracted text
# (extra symbols, repeated separators, broken spacing patterns)
# so the content is cleaner before chunking/retrieval.
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

    # Build a clean list of meaningful lines from the normalized text.
    filtered_lines: list[str] = []
    for raw_line in cleaned.split("\n"):
        # Remove leading bullet markers and trim whitespace.
        line = _BULLET_PREFIX_PATTERN.sub("", raw_line).strip()
        # Skip lines that are only decorative separators/noise.
        if _DECORATIVE_LINE_PATTERN.match(line):
            continue
        # Replace non-text symbols, then collapse repeated spaces.
        line = _NON_TEXT_SYMBOL_PATTERN.sub(" ", line)
        line = _MULTI_SPACE_PATTERN.sub(" ", line).strip()
        # Ignore empty lines after cleanup.
        if not line:
            continue
        filtered_lines.append(line)

    # Reassemble cleaned lines into final text for downstream chunking.
    return "\n".join(filtered_lines)


# Cleans whitespace in extracted text by removing extra spaces/blank lines
# and normalizing line breaks, so the text is consistent before chunking.
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


# Main text-cleaning pipeline for extracted content.
# Runs whitespace normalization + noisy-format cleanup,
# and returns cleaner text ready for validation and chunking.
def clean_text(text: str) -> str:
    """
    Full text-cleaning pipeline for extracted raw text.
    """
    return normalize_whitespace(remove_noisy_formatting(text))


# Cleans a list of text sections (for example page-wise content),
# applies text cleanup to each section, and keeps section metadata intact
# so downstream chunking/citation logic still knows source boundaries.
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

