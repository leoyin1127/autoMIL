"""Error types raised by registry validators (REG-03 / D-32).

Hard-fail semantics: every ValidationError carries enough context for the
operator to fix the problem in one edit (path + line + reason +
fix_suggestion). No soft-warn substitute (D-32).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ValidationError(Exception):
    """Raised by interface / purity / identity validators on hard-fail.

    Plan 01-07 (submit hook) catches these and re-raises as
    click.ClickException with a "Refusing to submit: ..." message including
    all four fields below.
    """
    validator_name: str       # "interface" | "purity" | "identity"
    path: Path                # variant module path
    reason: str               # one-line description of the violation
    fix_suggestion: str       # operator-friendly fix hint
    line: Optional[int] = None    # AST line number of the violation; None if module-level
    column: Optional[int] = None  # AST col_offset; None if not available

    def __post_init__(self) -> None:
        # dataclass-Exception interplay: ensure args is set so str(self) works
        # even if the caller catches as a plain Exception.
        super().__init__(self.__str__())

    def __str__(self) -> str:
        loc = f"{self.path}:{self.line}" if self.line else str(self.path)
        col = f":{self.column}" if self.column is not None else ""
        return (
            f"[{self.validator_name}] {loc}{col}: {self.reason} "
            f"Fix: {self.fix_suggestion}"
        )
