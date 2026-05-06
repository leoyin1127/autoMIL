"""BCK-04 / D-65: pytest enforcement gate for backend isolation lint.

This test is the always-on enforcement gate.  The pre-commit hook is optional
convenience; this test is what CI runs every time (D-65).

Wraps ``scripts/check_backend_isolation.py`` via subprocess so the lint runs in
the same Python environment as the test suite.  Exit 0 = pass; exit 1 = fail
with file:line diagnostics in the assertion message.

D-148 (Phase 5): the gate/ package is explicitly included in the BCK-04 scan;
``test_gate_clean_per_bck04_allowlist`` asserts it is part of the src_root
passed to the script.  Dedicated AST-level gate/ checks live in
``tests/gate/test_framework_purity.py::test_gate_no_process_control_refs``.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Resolve REPO_ROOT relative to this test file's location so the test works
# regardless of the current working directory at pytest invocation.
REPO_ROOT = Path(__file__).resolve().parent.parent


def test_no_process_control_outside_allowlist() -> None:
    """scripts/check_backend_isolation.py must exit 0 on src/automil/.

    Validates BCK-04: os.kill, os.killpg, os.getpid, Popen, and .pid
    attribute references are forbidden outside the allowlist:
      - backends/local.py
      - backends/_orchestrator_daemon.py
      - viz/server.py

    If this test fails, a new file outside the allowlist has introduced
    process-control code.  Either fix the violation or extend the allowlist
    with a rationale comment in check_backend_isolation.py.
    """
    script = REPO_ROOT / "scripts" / "check_backend_isolation.py"
    src_root = REPO_ROOT / "src" / "automil"

    result = subprocess.run(
        [sys.executable, str(script), str(src_root)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"BCK-04 lint FAILED — process-control references found outside allowlist:\n"
        f"stderr: {result.stderr}\n"
        f"stdout: {result.stdout}"
    )


def test_gate_clean_per_bck04_allowlist() -> None:
    """D-148 / Phase 5: gate/ package is scanned by BCK-04 and stays clean.

    The main test above passes src/automil/ which includes gate/ as a subdirectory.
    This explicit test asserts that gate/ has zero files on the BCK-04 allowlist
    (i.e., gate/ does not require process-control permissions) and that the
    check_backend_isolation.py script succeeds when pointed specifically at gate/.

    Rationale: gate/ is a pure-logic package (manifest, nominate, evaluate, promote,
    stats) — it must NEVER spawn processes or reference PIDs directly.  The only
    subprocess calls in gate/ are git operations (manifest.py) which use
    subprocess.run() with a command list — this pattern is explicitly ALLOWED by
    the BCK-04 script because it does not match the FORBIDDEN_NAMES (Popen) nor
    FORBIDDEN_OS_ATTRS (kill, killpg, getpid).
    """
    script = REPO_ROOT / "scripts" / "check_backend_isolation.py"
    gate_dir = REPO_ROOT / "src" / "automil" / "gate"

    assert gate_dir.exists(), f"gate/ dir not found at {gate_dir}"

    result = subprocess.run(
        [sys.executable, str(script), str(gate_dir)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"BCK-04 gate/ extension FAILED — process-control references found in gate/:\n"
        f"stderr: {result.stderr}\n"
        f"stdout: {result.stdout}\n"
        f"(D-148: gate/ must be process-control free; no os.kill/Popen/.pid)"
    )
