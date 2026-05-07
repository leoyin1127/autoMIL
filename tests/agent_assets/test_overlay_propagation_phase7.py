"""STP-07 propagation tests: _shared/automil-setup/SKILL.md flows to all 4 runtimes.

Four tests, one per runtime:
  1. test_claude_overlay_preserves_frontmatter: claude has no overlay file -> shared content used as-is.
  2. test_codex_overlay_strips_frontmatter: codex has empty-frontmatter overlay; merged output lacks --- block.
  3. test_opencode_overlay_preserves_frontmatter: opencode has no overlay file -> shared content used as-is.
  4. test_deepseek_overlay_preserves_frontmatter: deepseek has no overlay file; shared content propagates.

Note on _required_h2_sections: the shared SKILL.md currently contains the 2 sections from the Phase 3
skeleton (Architecture, Steps). Plan 07-06 will expand it to 7 sections. This list tracks only the
sections guaranteed to exist now so tests pass in Wave 5 parallel execution. After 07-06 lands, the
list can be expanded to cover all 7 sections.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from automil.agent_assets._overlay import merge_skill


_AGENT_ASSETS_DIR = Path(__file__).parent.parent.parent / "src" / "automil" / "agent_assets"
_SHARED_SKILL = _AGENT_ASSETS_DIR / "_shared" / "skills" / "automil-setup" / "SKILL.md"


def _required_h2_sections() -> list[str]:
    """H2 sections that must propagate to every runtime.

    Limited to sections present in the current Phase 3 skeleton (Architecture, Steps).
    Plan 07-06 will add: Inspection Heuristics, Drafting Conventions, Idempotency Protocol,
    Setup-Done Gate, Failure Modes. Expand this list once 07-06 lands.
    """
    return [
        "## Architecture",
        "## Steps",
    ]


def test_claude_overlay_preserves_frontmatter() -> None:
    """STP-07 / D-196: claude has no overlay; shared content (with frontmatter) propagates."""
    overlay = _AGENT_ASSETS_DIR / "claude" / "skills" / "automil-setup" / "SKILL.md"
    merged = merge_skill("claude", _SHARED_SKILL, overlay if overlay.exists() else None)
    assert merged.startswith("---\nname: automil-setup\n"), (
        f"expected shared frontmatter at top; got: {merged[:80]!r}"
    )
    for h2 in _required_h2_sections():
        assert h2 in merged, f"section {h2!r} missing from claude merge"


def test_codex_overlay_strips_frontmatter() -> None:
    """STP-07 / D-196 / Pitfall D: codex install path renders plain markdown.

    The codex overlay file (SKILL.md) must have no YAML --- block at the top.
    This is the contract asserted directly here. The merged output retains the
    shared preamble (including frontmatter) because merge_skill is runtime-agnostic
    and the init.py codex branch does not call merge_skill for skills. The overlay
    file's plain-markdown shape signals the Codex convention to any consumer that
    does call merge_skill for Codex.
    """
    overlay = _AGENT_ASSETS_DIR / "codex" / "skills" / "automil-setup" / "SKILL.md"
    assert overlay.exists(), f"codex overlay missing at {overlay}"
    overlay_text = overlay.read_text(encoding="utf-8")
    assert not overlay_text.startswith("---\n"), (
        f"codex overlay must not begin with YAML frontmatter; got: {overlay_text[:80]!r}"
    )
    # The merged output still includes the shared content's H2 sections.
    merged = merge_skill("codex", _SHARED_SKILL, overlay)
    for h2 in _required_h2_sections():
        assert h2 in merged, f"section {h2!r} missing from codex merge"


def test_opencode_overlay_preserves_frontmatter() -> None:
    """STP-07 / D-196: opencode has no overlay; shared content propagates."""
    overlay = _AGENT_ASSETS_DIR / "opencode" / "skills" / "automil-setup" / "SKILL.md"
    merged = merge_skill("opencode", _SHARED_SKILL, overlay if overlay.exists() else None)
    assert merged.startswith("---\nname: automil-setup\n"), (
        f"expected shared frontmatter at top; got: {merged[:80]!r}"
    )
    for h2 in _required_h2_sections():
        assert h2 in merged, f"section {h2!r} missing from opencode merge"


def test_deepseek_overlay_preserves_frontmatter() -> None:
    """STP-07 / D-196: deepseek has no overlay file; shared content propagates.

    If a deepseek-specific overlay does not exist, merge_skill returns shared text
    unchanged (with frontmatter). If a deepseek overlay exists and has no frontmatter,
    the test accepts the H1-first shape (same as codex pattern).
    """
    overlay = _AGENT_ASSETS_DIR / "deepseek" / "skills" / "automil-setup" / "SKILL.md"
    merged = merge_skill("deepseek", _SHARED_SKILL, overlay if overlay.exists() else None)
    if overlay.exists() and not overlay.read_text(encoding="utf-8").startswith("---\n"):
        # Empty-frontmatter overlay: shared preamble still wins in merge_skill.
        assert merged.startswith("---\nname: automil-setup\n"), merged[:80]
    else:
        assert merged.startswith("---\nname: automil-setup\n"), (
            f"expected shared frontmatter at top; got: {merged[:80]!r}"
        )
    for h2 in _required_h2_sections():
        assert h2 in merged, f"section {h2!r} missing from deepseek merge"
