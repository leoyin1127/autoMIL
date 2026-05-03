"""BCK-04 / D-65: pytest enforcement gate for backend isolation lint.

This test is the always-on enforcement gate.  The pre-commit hook is optional
convenience; this test is what CI runs every time (D-65).

Wraps ``scripts/check_backend_isolation.py`` via subprocess so the lint runs in
the same Python environment as the test suite.  Exit 0 = pass; exit 1 = fail
with file:line diagnostics in the assertion message.
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
