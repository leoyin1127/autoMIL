---
phase: "01"
plan: "01-04"
subsystem: registry.validators
requirements: [REG-03]
tags: [validators, static-analysis, AST, interface-check, purity-check, hard-fail]

dependency_graph:
  requires: [01-01, 01-02]
  provides: [ValidationError, InterfaceValidator, PurityValidator]
  affects: [01-07, 01-09]

tech_stack:
  added:
    - "ast (stdlib) — pure AST walk for PurityValidator; no external deps"
    - "importlib.util — spec_from_file_location / module_from_spec for InterfaceValidator dynamic import"
    - "inspect — inspect.signature for method signature compatibility check"
  patterns:
    - "Dataclass-Exception hybrid (ValidationError) — dataclass fields for structured access, Exception for raise/catch"
    - "Two-phase validation: AST-first (cheap) then dynamic-import (reflection only after AST passes)"
    - "ast.walk over RHS of Assign nodes to catch chained calls like open(...).read()"
    - "Permissive signature check: only truly-new required positional params rejected; default-tightening allowed"

key_files:
  created:
    - path: "src/automil/registry/errors.py"
      lines: 40
      role: "ValidationError dataclass exception with path/line/validator_name/reason/fix_suggestion"
    - path: "src/automil/registry/validators/__init__.py"
      lines: 17
      role: "Subpackage exporter: InterfaceValidator + PurityValidator"
    - path: "src/automil/registry/validators/interface.py"
      lines: 370
      role: "InterfaceValidator: AST scan + dynamic import + ABC subclass + method signature check"
    - path: "src/automil/registry/validators/purity.py"
      lines: 309
      role: "PurityValidator: pure AST walk; never imports; rejects top-level I/O + mutable globals"
    - path: "tests/test_registry_validator_interface.py"
      lines: 334
      role: "14 tests: happy paths (model/loss/policy), all rejection classes, error-str format"
    - path: "tests/test_registry_validator_purity.py"
      lines: 302
      role: "18 tests: clean module, all banned top-level calls, mutable globals, __main__ block, AST-only invariant"
  modified:
    - path: "src/automil/registry/__init__.py"
      role: "Added re-exports: ValidationError, InterfaceValidator, PurityValidator"

decisions:
  - "Signature compatibility is permissive on default-tightening: variant may make an optional ABC param required (coords=None -> coords) without rejection. Only truly new required positional params (not present in ABC at all) are rejected."
  - "RegistrationError raised during interface validator import is translated into a ValidationError that names the ABC base class from AST, not just the runtime error string — giving operators a clearer message."
  - "ast.walk over Assign-RHS catches chained calls (open(...).read()) rather than only the outermost Call node."
  - "PurityValidator: top-level Expr calls that aren't string constants are rejected unconditionally (bare top-level function calls are always side effects). The @register decorator lives on ClassDef, not Expr, so this rule never fires on valid variant modules."
  - "InterfaceValidator uses a unique module name (_automil_validator_<stem>_<id(path)>) to avoid sys.modules collision on repeated calls."
  - "Plan 01-07 MUST run PurityValidator before InterfaceValidator (T-01-14 mitigation: purity blocks malicious import-time calls before interface ever imports the module)."

metrics:
  duration: "~15 minutes"
  completed: "2026-05-02"
  tasks_completed: 3
  files_created: 6
  tests_added: 32
  tests_baseline: 175
  tests_total: 207
---

# Phase 01 Plan 04: Static Validators (Interface + Purity, REG-03) Summary

**One-liner:** AST-based submit-time validators — InterfaceValidator (import + reflection for ABC subclass + method signature) and PurityValidator (pure AST walk for top-level I/O, network calls, mutable globals) — both hard-fail with file:line + fix suggestion (D-32).

## Files Created

| File | Lines | Role |
|------|-------|------|
| `src/automil/registry/errors.py` | 40 | `ValidationError` dataclass exception |
| `src/automil/registry/validators/__init__.py` | 17 | Subpackage exporter |
| `src/automil/registry/validators/interface.py` | 370 | `InterfaceValidator` |
| `src/automil/registry/validators/purity.py` | 309 | `PurityValidator` |
| `tests/test_registry_validator_interface.py` | 334 | 14 interface tests |
| `tests/test_registry_validator_purity.py` | 302 | 18 purity tests |

## Public API

```python
# errors.py
@dataclass
class ValidationError(Exception):
    validator_name: str       # "interface" | "purity" | "identity"
    path: Path
    reason: str
    fix_suggestion: str
    line: Optional[int] = None
    column: Optional[int] = None

# validators/interface.py
class InterfaceValidator:
    def check(self, module_path: Path) -> None: ...

# validators/purity.py
class PurityValidator:
    def check(self, module_path: Path) -> None: ...

# Re-exported from automil.registry:
from automil.registry import ValidationError, InterfaceValidator, PurityValidator
```

## Test Coverage

### InterfaceValidator (14 tests)

| Test | Assertion |
|------|-----------|
| `test_happy_path_model_variant` | No exception for valid ModelVariant |
| `test_happy_path_loss_variant` | No exception for valid LossVariant |
| `test_happy_path_policy_variant` | No exception for valid PolicyVariant |
| `test_missing_forward_method_rejected` | ValidationError; reason has "forward"; fix_suggestion has ABC name |
| `test_wrong_signature_extra_positional_arg_rejected` | ValidationError; reason mentions forward/signature/param |
| `test_tighter_default_is_permissive` | No exception (coords without default is valid narrowing) |
| `test_kind_abc_mismatch_rejected` | ValidationError; reason has "model" + "LossVariant"/"loss" |
| `test_multiple_register_classes_rejected` | ValidationError matching "single|one|D-26|multiple" |
| `test_no_register_decorator_rejected` | ValidationError; reason has "register" |
| `test_syntax_error_rejected` | ValidationError; line >= 1 |
| `test_file_does_not_exist` | ValidationError matching "not found|missing|exist" |
| `test_validation_error_str_includes_path_and_line` | str(e) has path + "interface" + "forward" |
| `test_runtime_safe_module_path_resolution` | Deep nested path accepted |
| `test_validator_short_circuits_on_first_failure` | Single ValidationError (not chained) |

### PurityValidator (18 tests)

| Test | Assertion |
|------|-----------|
| `test_clean_module_passes` | No exception for imports + constants + class with internal I/O |
| `test_immutable_constants_at_module_level_ok` | str/float/tuple/None constants all pass |
| `test_function_body_io_ok` | open() inside method body is allowed |
| `test_open_at_module_level_rejected` | ValidationError; "open" in reason; line == 3 |
| `test_path_write_at_module_level_rejected` | Matches "write|filesystem|I/O" |
| `test_requests_at_module_level_rejected` | Matches "requests|network" |
| `test_urllib_at_module_level_rejected` | Matches "urllib|network" |
| `test_socket_at_module_level_rejected` | Matches "socket|network" |
| `test_subprocess_at_module_level_rejected` | Matches "subprocess|process" |
| `test_print_at_module_level_rejected` | Matches "print" |
| `test_os_system_at_module_level_rejected` | Matches "os.|system" |
| `test_os_environ_set_at_module_level_rejected` | Matches "os.environ|environ|env" |
| `test_mutable_list_global_rejected` | Matches "mutable|list" |
| `test_mutable_dict_global_rejected` | Matches "mutable|dict" |
| `test_if_main_block_rejected` | Matches "__main__|library|script" |
| `test_unimportable_package_does_not_crash_purity` | No exception — AST-only invariant |
| `test_validation_error_format` | str(e) has "purity" + path + "open" |
| `test_line_number_reported_on_failure` | ValidationError.line >= 1 |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed chained call detection for open().read() pattern**
- **Found during:** Task 3 GREEN — `test_open_at_module_level_rejected` failed
- **Issue:** `data = open("/etc/passwd").read()` — the outer Call's func is `Attribute(.attr='read')`. The original `_reject_call` only checked the outermost func, missing the inner `open()`.
- **Fix:** Changed Assign-value inspection to use `ast.walk(value)` over all sub-nodes, catching inner `open()` in chained method calls.
- **Files modified:** `src/automil/registry/validators/purity.py`
- **Commit:** bdd2063

**2. [Rule 1 - Bug] Fixed signature compatibility check to be permissive on default-tightening**
- **Found during:** Task 3 GREEN — `test_tighter_default_is_permissive` failed
- **Issue:** `_signature_compatible` compared required-param counts; variant with `forward(self, features, coords)` (2 required) rejected vs ABC with `forward(self, features, coords=None)` (1 required). This was overly strict — variants may tighten defaults.
- **Fix:** Redesigned to compare name-sets: reject only truly-new required positional params whose names don't appear in the ABC at all. A variant narrowing an optional to required is allowed.
- **Files modified:** `src/automil/registry/validators/interface.py`
- **Commit:** bdd2063

**3. [Rule 2 - Missing] Added RegistrationError translation in InterfaceValidator import exception handler**
- **Found during:** Task 3 GREEN — `test_kind_abc_mismatch_rejected` failed
- **Issue:** KIND_MISMATCH module (`LossVariant` base with `kind="model"`) raises `RegistrationError` during import. The generic import-failed handler produced "import failed: RegistrationError: ...not a subclass of ModelVariant." — no mention of `LossVariant`.
- **Fix:** Added special case in import exception handler to detect `RegistrationError` and re-raise as a `ValidationError` that includes the base class names from AST analysis in the reason.
- **Files modified:** `src/automil/registry/validators/interface.py`
- **Commit:** bdd2063

## Critical Note for Plan 01-07 (Submit Hook)

**PURITY BEFORE INTERFACE — T-01-14 MITIGATION:**

Plan 01-07's submit hook MUST run validators in this order:
1. `PurityValidator().check(path)` — pure AST, no import
2. `InterfaceValidator().check(path)` — imports the module for reflection

If purity runs first, malicious top-level calls (os.system, subprocess.run, network requests) are caught before the module is ever imported. If interface runs first, a crafted module could execute arbitrary code during the import step. This ordering invariant must be enforced and tested in Plan 01-07.

## Commits

| Hash | Type | Description |
|------|------|-------------|
| d587f56 | test | Add failing tests for InterfaceValidator (RED) — 14 tests |
| 9c2c953 | test | Add failing tests for PurityValidator (RED) — 18 tests |
| bdd2063 | feat | Implement errors.py + validators/{interface, purity, __init__}.py (GREEN) |

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| `src/automil/registry/errors.py` exists | FOUND |
| `src/automil/registry/validators/__init__.py` exists | FOUND |
| `src/automil/registry/validators/interface.py` exists | FOUND |
| `src/automil/registry/validators/purity.py` exists | FOUND |
| `tests/test_registry_validator_interface.py` exists | FOUND |
| `tests/test_registry_validator_purity.py` exists | FOUND |
| commit d587f56 (RED interface tests) | FOUND |
| commit 9c2c953 (RED purity tests) | FOUND |
| commit bdd2063 (GREEN implementation) | FOUND |
| Full suite: 207 tests | PASSED |
