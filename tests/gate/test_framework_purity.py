"""Framework-purity guards for src/automil/gate/ (D-148 / Phase 5 analog of cells/).

Mirrors tests/test_registry_validator_purity.py and the inline purity checks in
individual gate test files. Asserts:
  - zero autobench/AUTOBENCH_/benchmarks/ refs (framework purity — D-148)
  - zero process-control code refs (BCK-04 lint extension — D-148)
  - zero `git checkout` for rollback (Leo memory feedback_never_blind_checkout)

All checks are file-wide — they guard against future regressions.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Discovery: all .py files under src/automil/gate/
# ---------------------------------------------------------------------------

# Use __file__ to resolve relative to this test file (always works regardless of cwd)
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GATE_DIR = _REPO_ROOT / "src" / "automil" / "gate"
GATE_FILES = list(GATE_DIR.rglob("*.py"))


def test_gate_dir_has_files():
    """Smoke test: gate/ must be non-empty (guards against path misconfiguration)."""
    assert GATE_FILES, f"No .py files found under {GATE_DIR}; check GATE_DIR path"


# ---------------------------------------------------------------------------
# Test 1: framework purity — zero autobench/AUTOBENCH_/benchmarks/ refs
# ---------------------------------------------------------------------------

def test_gate_no_autobench_refs():
    """D-148: gate/ must be autobench-free (framework purity).

    autoMIL is a generic framework; autobench is one consumer. Framework code
    must never hardcode consumer-specific names.
    """
    offenders: list[tuple[Path, str]] = []
    for path in GATE_FILES:
        content = path.read_text()
        for token in ("autobench", "AUTOBENCH_", "benchmarks/"):
            if token in content:
                offenders.append((path.relative_to(_REPO_ROOT), token))

    assert not offenders, (
        f"Framework purity (D-148): {offenders} — "
        "gate/ must be autobench-free. "
        "autoMIL is generic; autobench is one consumer."
    )


# ---------------------------------------------------------------------------
# Test 2: BCK-04 extension — zero process-control code in gate/
# ---------------------------------------------------------------------------

# AST-based visitor mirrors scripts/check_backend_isolation.py for gate/ scope.
# Docstring mentions of forbidden patterns (e.g. "BCK-04 clean: no os.kill")
# are NOT flagged because we parse AST attribute/call nodes, not raw strings.

_FORBIDDEN_OS_ATTRS: frozenset[str] = frozenset({"kill", "killpg", "getpid"})
_FORBIDDEN_NAMES: frozenset[str] = frozenset({"Popen"})
_FORBIDDEN_ATTR: str = "pid"


class _GatePurityVisitor(ast.NodeVisitor):
    """Walk module AST and collect BCK-04 violations in gate/ files."""

    def __init__(self, source_lines: list[str]) -> None:
        self.violations: list[tuple[int, str]] = []
        self._source_lines = source_lines

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # os.kill / os.killpg / os.getpid
        if (
            isinstance(node.value, ast.Name)
            and node.value.id == "os"
            and node.attr in _FORBIDDEN_OS_ATTRS
        ):
            self.violations.append(
                (node.lineno, f"os.{node.attr}")
            )
        # .pid attribute access (process.pid, proc.pid, etc.)
        if node.attr == _FORBIDDEN_ATTR:
            self.violations.append(
                (node.lineno, f".{_FORBIDDEN_ATTR}")
            )
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        # Bare Popen name reference
        if node.id in _FORBIDDEN_NAMES:
            self.violations.append((node.lineno, node.id))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        # `from subprocess import Popen` / `from os import kill`
        if node.module == "subprocess":
            for alias in node.names:
                if alias.name in _FORBIDDEN_NAMES or alias.name == "*":
                    self.violations.append(
                        (node.lineno, f"from subprocess import {alias.name}")
                    )
        if node.module == "os":
            for alias in node.names:
                if alias.name in _FORBIDDEN_OS_ATTRS or alias.name == "*":
                    self.violations.append(
                        (node.lineno, f"from os import {alias.name}")
                    )
        self.generic_visit(node)


def test_gate_no_process_control_refs():
    """BCK-04 lint extension: gate/ must not contain process-control code.

    Uses AST-level detection (mirrors scripts/check_backend_isolation.py) so
    docstring mentions of forbidden patterns are NOT flagged as violations.
    """
    all_offenders: list[tuple[str, int, str]] = []
    for path in GATE_FILES:
        content = path.read_text()
        try:
            tree = ast.parse(content, filename=str(path))
        except SyntaxError as exc:
            pytest.fail(f"Syntax error in {path}: {exc}")
            return
        visitor = _GatePurityVisitor(content.splitlines())
        visitor.visit(tree)
        for lineno, pattern in visitor.violations:
            all_offenders.append(
                (str(path.relative_to(_REPO_ROOT)), lineno, pattern)
            )

    assert not all_offenders, (
        f"BCK-04 lint extension: gate/ must not invoke process control "
        f"(os.kill/os.killpg/os.getpid/Popen/.pid). "
        f"Offenders (file, line, pattern): {all_offenders}"
    )


# ---------------------------------------------------------------------------
# Test 3: no blind checkout — Leo memory feedback_never_blind_checkout
# ---------------------------------------------------------------------------

# Match call-site patterns only: `subprocess.run([..., "checkout", ...])` or
# `["git", "checkout", "--"]` as a list literal.  The manifest.py file uses
# `path.unlink()` for rollback (correct); this test enforces that future
# changes don't add `git checkout` for file restoration.

_BLIND_CHECKOUT_RE = re.compile(
    # Match `["git", "checkout"`, `'git', 'checkout'`, or `"git checkout --"`
    r"""(?x)
    (
        ["\']git["\']\s*,\s*["\']checkout["\'] |  # list: "git", "checkout"
        "git\s+checkout\s+--"                   |  # inline: "git checkout --"
        'git\s+checkout\s+--'                      # single-quoted variant
    )
    """,
    re.VERBOSE,
)


def test_gate_no_blind_checkout():
    """Leo memory feedback_never_blind_checkout: no `git checkout` for rollback in gate/.

    gate/manifest.py correctly uses path.unlink() for rollback (never git checkout).
    This test ensures that guarantee holds for future changes.
    """
    offenders: list[tuple[str, int, str]] = []
    for path in GATE_FILES:
        content = path.read_text()
        for line_no, line in enumerate(content.splitlines(), 1):
            # Skip comment lines
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if _BLIND_CHECKOUT_RE.search(line):
                offenders.append(
                    (str(path.relative_to(_REPO_ROOT)), line_no, line.strip())
                )

    assert not offenders, (
        "Leo memory feedback_never_blind_checkout: rollback must use "
        "path.unlink() NEVER `git checkout` — checkout silently destroys "
        f"uncommitted work. Offenders: {offenders}"
    )
