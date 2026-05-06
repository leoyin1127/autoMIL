"""Section-replacement overlay merger tests (MRT-01 / D-89).

Includes a documented known-limitation test for code-block false-split.
"""
from __future__ import annotations

from pathlib import Path

from automil.agent_assets._overlay import merge_skill, _parse_sections


# --- _parse_sections unit tests ---

def test_parse_sections_basic(tmp_path: Path) -> None:
    text = "# Title\n\nIntro text.\n\n## Section A\n\nBody A.\n\n## Section B\n\nBody B.\n"
    preamble, sections = _parse_sections(text)
    assert "Title" in preamble
    assert "## Section A" in sections
    assert "## Section B" in sections
    assert "Body A." in sections["## Section A"]
    assert "Body B." in sections["## Section B"]


def test_parse_sections_no_h2(tmp_path: Path) -> None:
    text = "# Title\n\nNo sections here.\n"
    preamble, sections = _parse_sections(text)
    assert sections == {}
    assert "No sections here." in preamble


# --- merge_skill: no overlay ---

def test_merge_skill_no_overlay_returns_shared(tmp_path: Path) -> None:
    """When overlay_path is None, return shared_text unchanged."""
    shared = tmp_path / "SKILL.md"
    shared.write_text("# Skill\n\n## How to use\n\nUniversal content.\n")
    result = merge_skill("test_runtime", shared, None)
    assert result == shared.read_text()


def test_merge_skill_nonexistent_overlay_returns_shared(tmp_path: Path) -> None:
    """When overlay_path does not exist, return shared_text unchanged."""
    shared = tmp_path / "SKILL.md"
    shared.write_text("# Skill\n\n## How to use\n\nUniversal content.\n")
    overlay = tmp_path / "nonexistent.md"
    result = merge_skill("test_runtime", shared, overlay)
    assert result == shared.read_text()


# --- merge_skill: section replacement ---

def test_overlay_replaces_matching_section(tmp_path: Path) -> None:
    """Overlay section with matching H2 header replaces shared section."""
    shared = tmp_path / "shared.md"
    shared.write_text(
        "# Skill\n\n"
        "## How to use\n\nShared content.\n\n"
        "## Constraints\n\nUniversal constraints.\n"
    )
    overlay = tmp_path / "overlay.md"
    overlay.write_text(
        "## How to use\n\nRuntime-specific content.\n"
    )
    result = merge_skill("claude", shared, overlay)
    assert "Runtime-specific content." in result
    assert "Shared content." not in result           # replaced
    assert "Universal constraints." in result        # preserved


def test_shared_sections_without_override_pass_through(tmp_path: Path) -> None:
    """Shared sections with no matching overlay section are preserved."""
    shared = tmp_path / "shared.md"
    shared.write_text(
        "# Skill\n\n"
        "## Section A\n\nContent A.\n\n"
        "## Section B\n\nContent B.\n"
    )
    overlay = tmp_path / "overlay.md"
    overlay.write_text("## Section A\n\nReplaced A.\n")
    result = merge_skill("opencode", shared, overlay)
    assert "Content B." in result        # Section B preserved
    assert "Replaced A." in result       # Section A replaced
    assert "Content A." not in result


def test_overlay_appends_new_sections(tmp_path: Path) -> None:
    """Overlay sections with no shared match are appended at the end."""
    shared = tmp_path / "shared.md"
    shared.write_text("# Skill\n\n## Setup\n\nCommon setup.\n")
    overlay = tmp_path / "overlay.md"
    overlay.write_text(
        "## Runtime Specifics\n\nOpencode-specific instructions.\n"
    )
    result = merge_skill("opencode", shared, overlay)
    assert "Common setup." in result             # shared preserved
    assert "Opencode-specific instructions." in result
    assert "## Runtime Specifics" in result
    # New section comes after shared sections
    assert result.index("## Setup") < result.index("## Runtime Specifics")


def test_h1_always_from_shared(tmp_path: Path) -> None:
    """H1 title is always taken from _shared; overlay H1 is ignored (it ends up in overlay preamble which is discarded)."""
    shared = tmp_path / "shared.md"
    shared.write_text("# AutoMIL Skill\n\n## Section A\n\nContent.\n")
    overlay = tmp_path / "overlay.md"
    overlay.write_text("## Section A\n\nOverridden.\n")
    result = merge_skill("claude", shared, overlay)
    assert result.startswith("# AutoMIL Skill")


def test_case_sensitive_header_matching(tmp_path: Path) -> None:
    """Section matching is case-sensitive — different case = no match (D-89)."""
    shared = tmp_path / "shared.md"
    shared.write_text("# Skill\n\n## How to Use\n\nOriginal content.\n")
    overlay = tmp_path / "overlay.md"
    overlay.write_text("## how to use\n\nThis has different case.\n")  # different case
    result = merge_skill("claude", shared, overlay)
    # Original preserved (no match), new section appended
    assert "Original content." in result
    assert "This has different case." in result


def test_overlay_empty_h2_sections_returns_shared(tmp_path: Path) -> None:
    """Overlay with no H2 sections (empty or preamble-only) returns shared unchanged."""
    shared = tmp_path / "shared.md"
    shared.write_text("# Skill\n\n## Setup\n\nCommon setup.\n")
    overlay = tmp_path / "overlay.md"
    overlay.write_text("Some preamble text with no H2 sections.\n")
    result = merge_skill("claude", shared, overlay)
    assert result == shared.read_text()


# --- Known limitation: code-block false-split ---

def test_known_limitation_code_block_false_split(tmp_path: Path) -> None:
    """KNOWN LIMITATION: `## ` at line start inside a fenced code block is treated as H2.

    This test documents the known false-split behaviour of the regex-based H2 splitter.
    Skill authors MUST NOT use `## ` at line start inside fenced code blocks.
    See _overlay.py module docstring for full explanation.
    """
    shared = tmp_path / "shared.md"
    # A SKILL.md where a bash comment `## usage` is at line start inside a code block
    shared.write_text(
        "# Skill\n\n"
        "## Setup\n\n"
        "```bash\n"
        "## This line SHOULD be inside code block but WILL be treated as H2\n"
        "echo hello\n"
        "```\n"
        "\n"
        "## Constraints\n\nConstraints content.\n"
    )
    _, sections = _parse_sections(shared.read_text())
    # The false-split: `## This line...` is incorrectly treated as an H2 section boundary
    # This test CONFIRMS the known limitation exists (documents, not fixes it)
    has_false_section = any("This line" in k for k in sections)
    # We ASSERT the false-split happens (so future changes that accidentally "fix" it
    # without a proper AST-based solution are caught — the fix must be deliberate)
    assert has_false_section, (
        "False-split of code-block H2 no longer occurs — if this was intentionally fixed "
        "with an AST-based parser, update this test to reflect the new behaviour."
    )
