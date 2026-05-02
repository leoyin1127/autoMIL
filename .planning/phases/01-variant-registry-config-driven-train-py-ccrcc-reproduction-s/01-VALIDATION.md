---
phase: 01
slug: variant-registry-config-driven-train-py-ccrcc-reproduction-s
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-05-02
tests_total: 387
tests_added: 0
gaps_resolved: 0
gaps_manual_only: 0
---

# Phase 1 — Validation Strategy

> Nyquist audit completed 2026-05-02. State B reconstruction from 01-CONTEXT.md (D-21..D-50), 01-VERIFICATION.md (8/8 success criteria, 15/15 REQ-IDs satisfied, 387 tests passing), and 01-SECURITY.md (55/55 threats closed). No gap-filler tests generated — coverage was already complete. See "Audit Findings" section for edge-case verification evidence.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `uv run pytest tests/ -q` |
| **Full suite command** | `uv run pytest tests/ -v` |
| **Estimated runtime** | ~25 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -q`
- **After every plan wave:** Run `uv run pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|------|--------|
| 01-01 | 01-01 | 1 | REG-01 | T-01-01, T-01-02, T-01-03 | VariantSpec frozen — FrozenInstanceError on mutation; Kind exhaustiveness guard | unit | `uv run pytest tests/test_registry_variants_abc.py tests/test_registry_spec.py -q` | test_registry_variants_abc.py + test_registry_spec.py | green |
| 01-02 | 01-02 | 1 | REG-02 | T-01-05, T-01-06, T-01-08, T-01-09 | Duplicate (kind, name) hard-fails; ABC subclass required; registry isolated per test; fork-safe re-population | unit | `uv run pytest tests/test_registry_singleton.py -q` | test_registry_singleton.py | green |
| 01-03 | 01-03 | 1 | REG-04, REG-06, REG-07 | T-01-10, T-01-11, T-01-12, T-01-13 | Mode literal validation; no framework-baked protected list; consumer config schema; init idempotence | unit | `uv run pytest tests/test_registry_config.py tests/test_init_registry_scaffold.py -q` | test_registry_config.py + test_init_registry_scaffold.py | green |
| 01-04 | 01-04 | 2 | REG-03 | T-01-14, T-01-15, T-01-17 | InterfaceValidator rejects missing abstractmethods + signature mismatches; ValidationError raised (no soft-warn) | unit | `uv run pytest tests/test_registry_validator_interface.py -q` | test_registry_validator_interface.py | green |
| 01-05 | 01-05 | 2 | REG-03, REG-06 | T-01-19, T-01-20, T-01-22 | PurityValidator rejects top-level I/O; IdentityValidator mode-aware (free vs architecture-preserving); atomic failure JSON write | unit | `uv run pytest tests/test_registry_validator_purity.py tests/test_registry_validator_identity.py -q` | test_registry_validator_purity.py + test_registry_validator_identity.py | green |
| 01-06 | 01-06 | 2 | REG-02, REG-08 | T-01-23, T-01-24, T-01-25, T-01-27 | Scanner idempotent byte-identical body; manifest read/write atomic; import-error isolated per module | unit | `uv run pytest tests/test_registry_scanner.py tests/test_registry_manifest.py -q` | test_registry_scanner.py + test_registry_manifest.py | green |
| 01-07 | 01-07 | 2 | REG-03, REG-04, REG-05 | T-01-28, T-01-29, T-01-30, T-01-31 | Submit protected-glob hard-fail (exit 2); purity runs before interface (ordering invariant); no --force flag; check fails on dirty protected path | integration | `uv run pytest tests/test_submit_protected_files.py tests/test_submit_validator_chain.py tests/test_check_registry_extension.py -q` | test_submit_protected_files.py + test_submit_validator_chain.py + test_check_registry_extension.py | green |
| 01-08 | 01-08 | 3 | CLI-01, CLI-08 | T-01-33, T-01-34 | Six commands registered; each --help >100 chars with workflow keyword; stub list empty | integration | `uv run pytest tests/test_lifecycle_skeleton.py -q` | test_lifecycle_skeleton.py | green |
| 01-09 | 01-09 | 3 | CLI-01, CLI-08 | T-01-36, T-01-37, T-01-38, T-01-39 | apply edits config.yaml only; atomic write + rolling .bak; refresh-registry idempotent | integration | `uv run pytest tests/test_lifecycle_apply.py tests/test_lifecycle_refresh_registry.py -q` | test_lifecycle_apply.py + test_lifecycle_refresh_registry.py | green |
| 01-10 | 01-10 | 3 | CLI-02 | T-01-40, T-01-41, T-01-42, T-01-43, T-01-44 | Mandatory pre-stash before git checkout; stash name surfaced in stdout; untracked files included | integration | `uv run pytest tests/test_lifecycle_revert_baseline.py -q` | test_lifecycle_revert_baseline.py | green |
| 01-11 | 01-11 | 3 | CLI-05, CLI-06 | T-01-45, T-01-46, T-01-47, T-01-48, T-01-49, T-01-50a | port-variant auto-name + auto-kind + idempotent; mismatched node_id same-name hard-fails; promote-variant stages but does NOT auto-commit | integration | `uv run pytest tests/test_lifecycle_port_variant.py tests/test_lifecycle_promote_variant.py -q` | test_lifecycle_port_variant.py + test_lifecycle_promote_variant.py | green |
| 01-12 | 01-12 | 4 | REG-08, REG-09, CLI-09 | T-01-51, T-01-52, T-01-54 | Full register→port-variant→refresh-registry→apply→verify-repro chain with no mocks; negative tolerance case asserts fail manifest + non-zero exit; env whitelist (no AUTOBENCH_* leakage) | integration | `uv run pytest tests/test_verify_repro.py tests/test_synthetic_consumer_roundtrip.py -q` | test_verify_repro.py + test_synthetic_consumer_roundtrip.py | green |

*Status: ⬜ pending · green · red · flaky*

---

## Nyquist Audit Findings (2026-05-02)

Adversarial stance applied: starting hypothesis was "implementation does not meet requirement." Three edge cases were explicitly probed before marking coverage complete.

### Edge Case 1: --help quality for all 6 lifecycle commands

**Requirement:** Each lifecycle command has >100-char help with a workflow-explaining keyword.

**Tests:** `test_lifecycle_skeleton.py::test_each_command_has_help[*]` (6 parametrized cases) + `test_each_command_helpdoc_mentions_workflow[*]` (6 parametrized cases). Commands covered: apply, revert-baseline, refresh-registry, port-variant, promote-variant, verify-repro.

**Result:** 13/13 pass. Coverage: complete for all 6 final commands.

### Edge Case 2: Synthetic-consumer negative case

**Requirement:** `verify-repro` exits non-zero and writes a fail manifest when actual composite exceeds tolerance.

**Test:** `test_synthetic_consumer_roundtrip.py::test_full_roundtrip_fail_exceeds_tolerance`

**Result:** PASS. The test asserts the manifest `status == "fail"` and CLI exit code is non-zero.

### Edge Case 3: Hard-fail invariants (D-32, D-34) — no soft-warn, no --force

**Requirement:** submit hard-fails on protected file match with no --force escape hatch.

**Tests:** `test_submit_protected_files.py::test_no_force_flag_d34` (Click rejects `--force` as unknown option) + `test_submit_protected_files.py::test_submit_help_does_not_mention_force` (help text does not advertise --force).

**Result:** Both PASS. D-34 enforced.

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. No Wave 0 stub files were needed — Phase 1 was implemented before this Nyquist audit was written (State B reconstruction).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| CCRCC `node_0176` reproduces within ±0.005 on real GPU | REG-09 (D-50 deferred demonstration) | 4h GPU training — untenable in CI; explicitly deferred to consumer follow-up per D-49/D-50 | `cd benchmarks/experiments/ccrcc && automil port-variant node_0176 && automil verify-repro node_0176`; inspect `automil/repro_manifest.yaml` for `status: pass` and `actual_composite` within 0.005 of 0.8074 |

---

## Validation Sign-Off

- [x] All tasks have automated verify command
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0: not applicable (State B reconstruction — implementation preceded audit)
- [x] No watch-mode flags
- [x] Feedback latency < 30s (full suite ~25s; incremental per-file <3s)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-05-02

---

## Test File Inventory

Phase 1 net-new test files (274 tests, 18 files):

| File | Tests | REQ-IDs |
|------|-------|---------|
| `tests/test_registry_spec.py` | 10 | REG-01 |
| `tests/test_registry_variants_abc.py` | 12 | REG-01 |
| `tests/test_registry_singleton.py` | 18 | REG-02 |
| `tests/test_registry_config.py` | 11 | REG-04, REG-06, REG-07 |
| `tests/test_registry_manifest.py` | 12 | REG-08 |
| `tests/test_registry_scanner.py` | 14 | REG-02, REG-08 |
| `tests/test_registry_validator_interface.py` | 14 | REG-03 |
| `tests/test_registry_validator_purity.py` | 18 | REG-03 |
| `tests/test_registry_validator_identity.py` | 15 | REG-03, REG-06 |
| `tests/test_submit_protected_files.py` | 9 | REG-04, REG-05 |
| `tests/test_submit_validator_chain.py` | 10 | REG-03, REG-04 |
| `tests/test_check_registry_extension.py` | 12 | REG-05, CLI-09 |
| `tests/test_init_registry_scaffold.py` | 11 | REG-04 |
| `tests/test_lifecycle_skeleton.py` | 24 | CLI-01, CLI-02, CLI-05, CLI-06, CLI-08, CLI-09 |
| `tests/test_lifecycle_apply.py` | 14 | CLI-01 |
| `tests/test_lifecycle_revert_baseline.py` | 15 | CLI-02 |
| `tests/test_lifecycle_refresh_registry.py` | 13 | CLI-08 |
| `tests/test_lifecycle_port_variant.py` | 20 | CLI-05, REG-08 |
| `tests/test_lifecycle_promote_variant.py` | 10 | CLI-06 |
| `tests/test_verify_repro.py` | 9 | REG-09, CLI-09 |
| `tests/test_synthetic_consumer_roundtrip.py` | 3 | REG-08, REG-09 (Phase 1 acceptance gate) |

Phase 0 baseline (113 tests, preserved):
`test_graph.py` (30) · `test_runner.py` (8) · `test_cli.py` (21) · `test_integration.py` (8) · `test_compat.py` (4) · `test_recompute_best.py` (12) · `test_orchestrator_*.py` (30 across 4 files)

**Total: 387 tests passing** (`uv run pytest tests/ -q` — 25.47s)
