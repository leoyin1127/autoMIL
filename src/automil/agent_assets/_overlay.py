"""Section-replacement overlay merger for agent_assets (MRT-01, MRT-02 / D-89).

Algorithm: merge _shared/<asset>.md with <runtime>/<asset>.md by H2 section-replacement.
- H1 title is always taken from _shared (preamble before first H2).
- Overlay H2 sections replace matching _shared H2 sections (case-sensitive, exact match).
- Overlay sections with no shared match are appended at the end.
- Shared sections with no override pass through unchanged.

WARNING: The `^## ` H2 split treats ANY line beginning with `## ` as a section header,
INCLUDING lines inside fenced code blocks (e.g., bash comments like `## usage`).
Skill authors MUST NOT use `## ` at the start of a line inside a fenced code block.
Violation causes a false section split. This known limitation is documented in
tests/agent_assets/test_overlay.py::test_known_limitation_code_block_false_split.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

_H2_SPLIT = re.compile(r"^(## .+)$", re.MULTILINE)


def _parse_sections(text: str) -> tuple[str, dict[str, str]]:
    """Split markdown text into (preamble, {h2_header: body}).

    Preamble: H1 title + any content before the first H2.
    Sections: ordered dict keyed by exact H2 header text (case-sensitive).
    """
    parts = _H2_SPLIT.split(text)
    preamble = parts[0]
    sections: dict[str, str] = {}
    for i in range(1, len(parts), 2):
        header = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ""
        sections[header] = body
    return preamble, sections


def merge_skill(
    runtime: str,
    shared_path: Path,
    overlay_path: Path | None,
) -> str:
    """Merge _shared/<asset>.md with <runtime>/<asset>.md via H2 section-replacement.

    Args:
        runtime: Runtime identifier (e.g., "claude", "opencode") — used for logging only.
        shared_path: Path to the _shared/<asset>.md file (canonical content).
        overlay_path: Path to <runtime>/<asset>.md, or None if no overlay exists.

    Returns:
        Merged markdown text as a string. No writes — purely functional.

    Section matching is case-sensitive and whitespace-exact (D-89).
    H1 title is always taken from _shared. Overlay MUST NOT contain H1.
    """
    shared_text = shared_path.read_text(encoding="utf-8")
    preamble, shared_sections = _parse_sections(shared_text)

    if overlay_path is None or not overlay_path.exists():
        logger.debug(
            "No overlay for runtime %r at %s; returning shared content",
            runtime,
            overlay_path,
        )
        return shared_text

    overlay_text = overlay_path.read_text(encoding="utf-8")
    _, overlay_sections = _parse_sections(overlay_text)

    if not overlay_sections:
        logger.debug(
            "Overlay for runtime %r has no H2 sections; returning shared content",
            runtime,
        )
        return shared_text

    # Section-replacement: overlay wins, shared is default
    merged: dict[str, str] = dict(shared_sections)
    for header, body in overlay_sections.items():
        merged[header] = body  # replaces matching or will be appended below

    # Reconstruct: shared sections in shared's original order
    result = preamble
    for header in shared_sections:
        result += header + merged[header]
    # Append new sections from overlay that have no shared counterpart
    for header in overlay_sections:
        if header not in shared_sections:
            result += header + overlay_sections[header]

    return result
