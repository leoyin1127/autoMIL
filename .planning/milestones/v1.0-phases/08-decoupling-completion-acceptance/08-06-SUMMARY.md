---
phase: 08-decoupling-completion-acceptance
plan: 06
subsystem: examples
tags: [decoupling, consumer, sklearn, iris, DEC-02, D-203]
dependency_graph:
  requires: [08-01]
  provides: [examples/sklearn-iris consumer files]
  affects: []
tech_stack:
  added: ["scikit-learn>=1.4 ([examples-iris] optional extra)"]
  patterns: ["inline SIGTERM handler (single-shot, no-fold pattern per OQ-4)", "consumer-decoupled result.json (zero automil.* imports)"]
key_files:
  created:
    - examples/sklearn-iris/train.py
    - examples/sklearn-iris/automil/config.yaml
    - examples/sklearn-iris/automil/program.md
    - examples/sklearn-iris/automil/variants/classifier_v0/__init__.py
    - examples/sklearn-iris/automil/variants/classifier_v0/logistic_v0.py
    - examples/sklearn-iris/README.md
  modified:
    - pyproject.toml
decisions:
  - "Inline SIGTERM handler chosen over register_sigterm_flush: sklearn-iris is single-shot (no folds); register_sigterm_flush aggregates fold_<i>_result.json which does not exist here (OQ-4)"
  - "scikit-learn>=1.4 pinned in [examples-iris] extra, not top-level dependency; already in [ml] at >=1.3"
  - "pyyaml>=6.0 included in [examples-iris] extra because train.py reads config.yaml; pyyaml is already a top-level dep but explicit pin in extra for consumers who install only examples-iris"
metrics:
  duration: "8 minutes"
  completed: "2026-05-08T03:30:06Z"
  tasks_completed: 3
  files_created: 6
  files_modified: 1
---

# Phase 08 Plan 06: sklearn-iris Second Consumer Summary

Shipped 6 new files under `examples/sklearn-iris/` implementing the DEC-02 second consumer: a 80-line sklearn LogisticRegression script that plugs into autoMIL via the documented contract with zero framework imports.

## Smoke Test Result

`python train.py` (CWD = examples/sklearn-iris) writes `result.json` with:
- `composite = 1.0` (iris with LogisticRegression, seed=42, 30% split)
- `f1 = 1.0`
- `status = "completed"`
- Schema validation against `src/automil/schemas/result.schema.json` passes (Draft202012Validator)

Expected range in README is 0.93-0.98; actual result slightly above due to perfect separation on this split. Composite well above the 0.90 acceptance gate threshold.

## Line Count

`train.py`: exactly 80 lines (at the D-203 cap). Docstring condensed to reach cap; implementation is complete and uncompromised.

## Framework Purity

Zero `automil.*` imports in any file under `examples/sklearn-iris/`. Consumer is fully decoupled. The `logistic_v0.py` variant is plain sklearn with no registry decoration (decoration happens at runtime via `automil refresh-registry`; shipped file is the pre-registration baseline).

## File Summary

| File | Lines | Role |
|------|-------|------|
| `train.py` | 80 | Minimal training script (DEC-02 contract demo) |
| `automil/config.yaml` | 44 | Consumer config: env.required=[], env.passthrough=[], scoring.formula=accuracy |
| `automil/program.md` | 22 | Search space narrative for agent |
| `automil/variants/classifier_v0/__init__.py` | 7 | Package docstring (no registry imports) |
| `automil/variants/classifier_v0/logistic_v0.py` | 13 | make_classifier(seed=42) starter variant |
| `README.md` | 47 | Quickstart + file table |

## pyproject.toml Change

Added `[examples-iris]` optional extra: `["scikit-learn>=1.4", "pyyaml>=6.0"]`. Not a top-level dependency. Existing `[ml]` extra already pins `scikit-learn>=1.3`.

## Deviations from Plan

None. Plan executed exactly as written.

## Commits

| Hash | Message |
|------|---------|
| 7d8f719 | feat(08-06): add sklearn-iris train.py (DEC-02 minimal consumer script) |
| 48eb2d3 | feat(08-06): add sklearn-iris automil/ scaffold (config, program.md, logistic_v0) |
| 414c0ff | feat(08-06): add sklearn-iris README with quickstart and file table |
| 70185e6 | feat(08-06): add [examples-iris] optional extra (scikit-learn>=1.4, pyyaml>=6.0) |

## Self-Check: PASSED

Files verified:
- examples/sklearn-iris/train.py: EXISTS, 80 lines, parses ok
- examples/sklearn-iris/automil/config.yaml: EXISTS, cfg shape ok
- examples/sklearn-iris/automil/program.md: EXISTS
- examples/sklearn-iris/automil/variants/classifier_v0/__init__.py: EXISTS
- examples/sklearn-iris/automil/variants/classifier_v0/logistic_v0.py: EXISTS, parses ok
- examples/sklearn-iris/README.md: EXISTS
- pyproject.toml: examples-iris extra present

Commits verified: 7d8f719, 48eb2d3, 414c0ff, 70185e6 in git log.
