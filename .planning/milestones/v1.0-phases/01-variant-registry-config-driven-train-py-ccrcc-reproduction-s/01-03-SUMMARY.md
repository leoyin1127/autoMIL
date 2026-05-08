---
phase: "01"
plan: "01-03"
subsystem: "registry/config"
tags: ["registry", "config-schema", "init-scaffold", "REG-04", "REG-06", "REG-07"]
dependency_graph:
  requires: []
  provides:
    - "automil.registry.config.RegistryConfig"
    - "automil.registry.config.load_registry_config"
    - "automil.registry.config.Mode"
    - "automil/variants/<_losses|_policies|_candidates>/ skeleton via automil init"
  affects:
    - "src/automil/templates/config.yaml.j2"
    - "src/automil/cli/init.py"
tech_stack:
  added:
    - "src/automil/registry/ package (new)"
    - "RegistryConfig frozen dataclass"
    - "yaml.safe_load + .get() chains (no Pydantic, per PATTERNS.md §5)"
  patterns:
    - "Frozen dataclass for typed config view (per orchestrator.py GPUInfo analog)"
    - "Hard-fail with operator-named key on type/value errors"
    - "Idempotent mkdir parents=True exist_ok=True for directory scaffolding"
key_files:
  created:
    - "src/automil/registry/__init__.py (8 lines)"
    - "src/automil/registry/config.py (118 lines)"
    - "tests/test_registry_config.py (106 lines)"
    - "tests/test_init_registry_scaffold.py (160 lines)"
  modified:
    - "src/automil/templates/config.yaml.j2 (70→104 lines, +34 registry+variant sections)"
    - "src/automil/cli/init.py (128→150 lines, +_scaffold_variants_skeleton helper + call)"
decisions:
  - "RegistryConfig.protected is a tuple (not list) — frozen dataclass semantics, immutable after construction"
  - "load_registry_config raises TypeError/ValueError with key-named messages — no silent coercion"
  - "config.yaml.j2 registry section appended at end, preserving all existing keys"
  - "_scaffold_variants_skeleton is a module-level helper (not inline) to enable direct unit test (test_scaffold_helper_idempotent)"
  - "Per-parent <parent>/ directories NOT created at init time (D-25 — port-variant owns that on first use)"
metrics:
  duration: "~8 minutes"
  completed: "2026-05-02"
  tasks_completed: 3
  files_modified: 6
  net_new_tests: 22
---

# Phase 01 Plan 03: Config Schema + automil init Scaffolding Summary

**One-liner:** `RegistryConfig` frozen dataclass + `load_registry_config()` reader with operator-friendly type validation, `config.yaml.j2` extended with `registry:`/`model:`/`loss:`/`policy:` sections, and `automil init` now scaffolds `variants/_losses|_policies|_candidates/.gitkeep` skeleton.

## What Was Built

### `src/automil/registry/config.py` (118 lines)

New module providing:

- `Mode = Literal["free", "architecture-preserving"]` — type alias consumed by Plans 01-05 and 01-07.
- `RegistryConfig` — frozen dataclass with four fields:
  - `protected: tuple[str, ...]` — glob patterns; default `()` (D-33: no framework defaults, D-49: framework is generic).
  - `mode: Mode` — default `"free"` (D-31).
  - `repro_tolerance: float` — default `0.005` (D-39: CCRCC ±0.005 as framework default; consumer can override).
  - `identity_constraints: tuple[str, ...]` — default `()` (D-31: per-project structural rules for Plan 01-05).
- `_coerce_str_tuple(raw, key)` — validates YAML list fields; raises `TypeError(f"...{key!r}...")` on wrong type.
- `load_registry_config(automil_dir: Path) -> RegistryConfig` — reads `automil/config.yaml`, returns defaults if file/section absent, raises `TypeError`/`ValueError` with operator-named keys on invalid values.

**Backwards-compat invariant:** old `config.yaml` (without `registry:` section) returns `RegistryConfig()` with all defaults — no crash.

### `src/automil/templates/config.yaml.j2` (extended, 104 lines)

Appended at end of existing template (all existing keys preserved):

```yaml
# --- Registry (Phase 1, REG-04 / REG-06 / REG-07) ---
registry:
  protected: []
  mode: "free"
  repro_tolerance: 0.005
  identity_constraints: []

# --- Variant selection (D-35, REG-07) ---
model:
  variant: null    # e.g. "clam_mb_v0176"
  parent: null     # e.g. "clam_mb"
loss:
  variant: null    # e.g. "ce_smooth008"
policy:
  variant: null    # e.g. "sam_lookahead"
```

### `src/automil/cli/init.py` (extended, 150 lines)

Added `_scaffold_variants_skeleton(automil_dir: Path)` helper (module-level, 20 lines) and call site after orchestrator-dirs mkdir loop:

```python
def _scaffold_variants_skeleton(automil_dir: Path) -> None:
    variants_root = automil_dir / "variants"
    variants_root.mkdir(parents=True, exist_ok=True)
    (variants_root / ".gitkeep").touch()
    for sub in ("_losses", "_policies", "_candidates"):
        sub_dir = variants_root / sub
        sub_dir.mkdir(parents=True, exist_ok=True)
        (sub_dir / ".gitkeep").touch()
```

Call site (inside `init()`, after orchestrator dirs, before template rendering):
```python
# Scaffold the registry variants/ skeleton (D-25, REG-04).
_scaffold_variants_skeleton(automil_dir)
```

**Idempotence preserved:** the existing guard `if automil_dir.exists() and (automil_dir / "config.yaml").exists(): raise click.ClickException(...)` still fires on re-init, preventing double-init from clobbering user variant files. `_scaffold_variants_skeleton` is idempotent internally (`mkdir exist_ok=True`, `.touch()` is safe to repeat) so future callers can call it independently.

## Test Coverage (22 new tests)

### `tests/test_registry_config.py` (11 tests)

| Test | Assertion |
|------|-----------|
| `test_empty_config_returns_defaults` | Empty config.yaml → `RegistryConfig(protected=(), mode="free", repro_tolerance≈0.005, identity_constraints=())` |
| `test_empty_registry_section_returns_defaults` | `registry: {}` → same defaults |
| `test_protected_list_returns_tuple` | `protected: ["a/**", "b/foo.py"]` → `("a/**", "b/foo.py")` tuple |
| `test_mode_architecture_preserving_accepted` | `mode: architecture-preserving` accepted |
| `test_mode_free_explicitly` | `mode: free` accepted |
| `test_mode_unknown_value_rejected` | `mode: evil` → `ValueError` matching `registry.mode\|free\|architecture-preserving` |
| `test_repro_tolerance_custom_value` | `repro_tolerance: 0.01` → `0.01` |
| `test_protected_wrong_type_rejected` | `protected: 42` → `TypeError` matching `registry.protected` |
| `test_config_yaml_missing_returns_defaults` | No config.yaml → all defaults (fresh init flow) |
| `test_registry_config_is_frozen` | `cfg.mode = "..."` → `FrozenInstanceError` |
| `test_no_autobench_defaults_d49` | `RegistryConfig().protected` contains no `benchmarks`/`AUTOBENCH`/`ccrcc` |

### `tests/test_init_registry_scaffold.py` (11 tests)

| Test | Assertion |
|------|-----------|
| `test_variants_losses_gitkeep_created` | `automil/variants/_losses/.gitkeep` exists after init |
| `test_variants_policies_gitkeep_created` | `automil/variants/_policies/.gitkeep` exists |
| `test_variants_candidates_gitkeep_created` | `automil/variants/_candidates/.gitkeep` exists (Phase 5 GTE hook) |
| `test_variants_root_gitkeep_created` | `automil/variants/.gitkeep` exists (empty dir commits cleanly) |
| `test_no_parent_dir_at_init_time` | No non-`_`-prefixed subdirs in `variants/` (D-25: port-variant creates them) |
| `test_config_yaml_has_registry_section` | rendered config.yaml contains `registry:`, `protected: []`, `mode: "free"`, `repro_tolerance: 0.005` |
| `test_config_yaml_has_variant_selection` | rendered config contains `model:`, `loss:`, `policy:` sections with `variant: null` |
| `test_init_idempotence_preserves_user_files` | Re-init fails "already initialized"; user's `_losses/my_loss.py` untouched |
| `test_scaffold_helper_idempotent` | `_scaffold_variants_skeleton()` called twice = no error, files still present |
| `test_init_with_custom_path_argument` | `automil init myautomil` → `myautomil/variants/_losses/.gitkeep` |
| `test_rendered_config_is_parseable` | Rendered `config.yaml` round-trips through `yaml.safe_load()` → dict with `registry` key |

## Deviations from Plan

None — plan executed exactly as written.

## Threat Model Compliance

All four STRIDE mitigations implemented and verified:

| Threat ID | Mitigation | Verification |
|-----------|------------|--------------|
| T-01-10 | Mode literal enforced via `_VALID_MODES` tuple + `ValueError` | `test_mode_unknown_value_rejected` |
| T-01-11 | `_coerce_str_tuple` raises `TypeError` on non-list `protected` | `test_protected_wrong_type_rejected` |
| T-01-12 | Existing re-init guard at `cli/init.py:53-54` raises before file writes | `test_init_idempotence_preserves_user_files` |
| T-01-13 | `RegistryConfig().protected == ()` — zero consumer-specific defaults | `test_no_autobench_defaults_d49` |

## Operational Notes

**Partial init recovery:** If `automil init` crashes mid-scaffold (e.g., disk full while writing `.gitkeep`), `git status` shows the partial directory tree. The existing idempotence guard blocks re-run (config.yaml may not exist yet in a partial crash, allowing re-run — `_scaffold_variants_skeleton` is idempotent). Operator fix: `rm -rf automil/` and re-run init. Plan 01-12 (verify-repro) and future Phase 7 (auto-setup skill) own the broader recovery story.

## Commits

| Hash | Message |
|------|---------|
| `7ea1960` | `test(01-03): add failing tests for RegistryConfig reader (REG-04, REG-06, D-31, D-33, D-39)` |
| `4f42eba` | `test(01-03): add failing tests for automil init variants/ scaffolding (REG-04, D-25)` |
| `ae83f37` | `feat(registry): add config schema + variants/ scaffolding to automil init (REG-04, REG-06, REG-07)` |

## Self-Check: PASSED

- `src/automil/registry/__init__.py`: FOUND
- `src/automil/registry/config.py`: FOUND
- `tests/test_registry_config.py`: FOUND (11 tests)
- `tests/test_init_registry_scaffold.py`: FOUND (11 tests)
- `src/automil/templates/config.yaml.j2` contains `registry:`: FOUND
- `src/automil/cli/init.py` contains `_scaffold_variants_skeleton`: FOUND
- Commit `ae83f37`: FOUND
- 135 tests pass (113 baseline + 22 new)
- D-49 grep-guard: `src/automil/registry/config.py` contains no `benchmarks`/`AUTOBENCH`/`ccrcc` in non-comment lines
