"""Lifecycle commands for variant management (CLI-01/02/05/06/08/09).

Phase 0 shipped `cli/lifecycle.py` as a stub. Plan 01-08 converts it to a
package so each command lives in its own file — wave-safety enabler for
Plans 01-09/10/11/12, each of which modifies exactly one sub-module.

Importing this package runs each sub-module's @main.command decorator,
registering all six commands on the Click main group.

Wave-safety invariant (CRITICAL):
  Plans 01-09/10/11/12 MUST NOT modify this __init__.py.
  They modify their per-command file ONLY.
  - Plan 01-09 owns: apply.py, refresh_registry.py
  - Plan 01-10 owns: revert_baseline.py
  - Plan 01-11 owns: port_variant.py, promote_variant.py
  - Plan 01-12 owns: verify_repro.py
  Cross-plan conflicts on this file are prevented because the import list
  is locked in by THIS plan (01-08).
"""
from __future__ import annotations

# Alphabetic order; Click registration is idempotent.
from automil.cli.lifecycle import apply              # noqa: F401
from automil.cli.lifecycle import port_variant       # noqa: F401
from automil.cli.lifecycle import promote_variant    # noqa: F401
from automil.cli.lifecycle import refresh_registry   # noqa: F401
from automil.cli.lifecycle import revert_baseline    # noqa: F401
from automil.cli.lifecycle import verify_repro       # noqa: F401
