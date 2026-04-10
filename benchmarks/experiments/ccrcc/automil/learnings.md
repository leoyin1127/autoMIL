# Learnings

## Trusted Baseline

- **node_0002** — CLAM_MB + uni_v2, default hyperparameters
  (lr=1e-4, wd=1e-5, dropout=0.25, bag_weight=0.7)
  - val_auc 0.7876, val_bacc 0.6856
  - test_auc 0.7902, test_bacc 0.6984
  - composite **0.7443**

## Invalidated Round 1 (do NOT trust)

Nodes 3–13 were run BEFORE the worktree isolation bug was fixed. The
editable `pip install -e .` of `autobench` silently shadowed every
worktree overlay under `benchmarks/src/autobench/` and `benchmarks/lib/`,
so every "modified" experiment actually ran the same baseline code.
Symptoms: node_0007 and node_0008 produced byte-identical training logs
and identical composite 0.7458 despite different code edits.

Archived under `automil/orchestrator/archive_invalidated/` for forensics.

**Lesson:** whenever results look suspiciously similar across different
code edits, stop and verify `autobench.__file__` / `autobench.LIB_ROOT`
point to the worktree, not the main repo.

## Isolation Fix (2026-04-10)

- `orchestrator._launch()` now sets `AUTOBENCH_ROOT=<worktree>/benchmarks`
  and prepends `<worktree>/benchmarks/src` to `PYTHONPATH` per experiment.
- `autobench/__init__.py` honors `AUTOBENCH_ROOT` so `LIB_ROOT` routes
  CLAM/SMMILe/nnMIL imports through the worktree's `lib/`.
- `run_experiment.py` now prints `autobench.__file__` and `LIB_ROOT` on
  startup as a per-run diagnostic — check `run.log` to confirm overlay
  activation before trusting any result.

## Round 1 Results (with verified isolation)

- **node_0003 — Cosine annealing LR**: composite 0.7458 (+0.0015)
  - val_auc 0.7885, val_bacc 0.6976, test_auc 0.7908, test_bacc 0.7009
  - Tiny improvement; probably within noise. LR decay alone isn't the lever.

- **node_0005 — Class-weighted CE (inv-freq, mild 0.85/1.21)**: composite 0.7458 (+0.0015)
  - Essentially identical to cosine annealing. Weak weights → weak effect.
  - Lesson: the 58/42 class imbalance isn't severe enough for inverse-frequency
    weighting to matter. If we want to push BACC via weighting, we'd need a
    much more aggressive multiplier (e.g., [0.5, 2.0]) — and that risks
    over-biasing toward the minority class.

- **node_0006 — Focal loss γ=2**: composite **0.7273 (−0.0170)** ❌
  - test_auc 0.7776, test_bacc 0.6771 — **both metrics regressed**
  - Focal loss's hard-example focus *hurt* in this MIL setup. Plausible
    explanation: CLAM's attention mechanism already identifies hard
    instances per-slide. Focal loss's per-bag re-weighting then amplifies
    ambiguous / noisy bags that the attention correctly down-weighted.
    **Don't stack focal loss with CLAM.**

- **node_0004 — Label smoothing 0.1**: composite **0.7673 (+0.0230)** 🏆
  - val_auc 0.7984, val_bacc 0.7043, test_auc 0.8084, test_bacc 0.7262
  - **Both metrics improved meaningfully**. BACC +0.028 is 4 % relative.
  - Strong Pareto dominance over baseline — clean keep.
  - Validates the "calibration is the bottleneck" hypothesis.

- **node_0007 — Label smoothing 0.15**: composite **0.7727 (+0.0284)** 🏆🏆
  - val_auc 0.8094, val_bacc 0.7301, test_auc 0.8138, test_bacc 0.7317
  - Better than 0.1 on every metric. BACC now +0.033 over baseline.

- **node_0008 — Label smoothing 0.2**: composite 0.7580 (+0.0137)
  - val_auc 0.8113 (highest!), val_bacc 0.7431 (highest!), but
  - test_auc 0.7965 (drops), test_bacc 0.7195 (drops)
  - **Over-regularizes**: val scores peak but test scores regress. The
    model can no longer discriminate confidently on held-out data.

**Label smoothing sweep:**
  `LS 0.0  → 0.7443`
  `LS 0.1  → 0.7673 (+0.023)`
  `LS 0.15 → 0.7727 (+0.028)  ← peak`
  `LS 0.2  → 0.7580 (+0.014)`
  Peak is at 0.15; further smoothing over-regularizes.

**Cosine annealing is a no-op:**
  `LS 0.0 + cosine → 0.7458 (+0.0015 vs baseline — noise)`
  `LS 0.1 + cosine → 0.7674 (vs 0.7673 LS 0.1 alone — zero delta)`
  Early stopping fires (epoch 20–50) before LR decay over 200 epochs
  has time to matter. **Don't waste cycles on cosine anymore.**

## Seed Variance — Noise Floor (nodes 0031 & 0033, 2026-04-10)

**CRITICAL:** the `seed` arg controls both model init AND 5-fold split
creation, so different seeds = different test sets. This makes seed
variance very large.

Paired measurements:

  `Seed  42: baseline 0.7443 | LS 0.15 0.7727 | Δ = +0.0284`
  `Seed 123: baseline 0.7630 | LS 0.15 0.7516 | Δ = −0.0114`

**The LS-vs-baseline delta flips sign across seeds.** The "+0.028" I
was celebrating was a lucky split. The average effect is probably tiny
(roughly +0.009 across 2 seeds) and within the noise band itself.

Baseline variance alone: ±0.019
LS 0.15 variance alone: ±0.021

**Revised trustable conclusions** (only effects > 0.03):
- CLAM_SB hurts vs CLAM_MB: −0.024 (borderline)
- hoptimus1 encoder hurts vs uni_v2: −0.031 (real)
- Longer training (patience 30 / stop_epoch 80) hurts: −0.019 (probably real — big BACC drop 0.70 vs 0.73)
- Focal loss hurts: −0.017 (probably real — very different mechanism)

**Everything else — including the "LS 0.15 winner" — is within or near
the seed-variance band**. Single-seed comparisons for deltas < 0.03 are
not informative in this setup.

**Lesson:** in high-variance regimes, don't search with single-seed runs.
Either (a) use ≥3 seeds per config and paired comparisons, or (b) reduce
variance first (e.g. fix folds across runs, or use larger dataset).

## 4-Seed Paired Comparison — LS 0.15 vs Baseline (nodes 0033–0038, 2026-04-10)

| Seed | Baseline | LS 0.15 | Δ      |
|------|----------|---------|--------|
|  42  | 0.7443   | 0.7727  | +0.0284|
| 123  | 0.7630   | 0.7516  | −0.0114|
|   7  | 0.7476   | 0.7569  | +0.0093|
| 2024 | 0.7600   | 0.7718  | +0.0118|
| mean | 0.7537   | 0.7633  | +0.0095|
|  std |  0.0091  |  0.0101 |  0.0163|

**Paired t-test:** t = 1.17, df = 3, p ≈ 0.32.
**95 % CI for mean Δ:** [−0.016, +0.036].

The mean LS effect is **+0.010 composite**, but the CI straddles zero.
Four seeds are not enough to confirm the effect at p < 0.05, though
the point estimate is stable and positive.

**Honest conclusion:**
- LS 0.15 probably helps by about +0.01 composite (≈1 % relative).
- The *single-seed* 0.7727 "winner" was a lucky initialization; the
  multi-seed mean at LS 0.15 is 0.7633.
- The task (CCRCC high_grade, n_train=204, n_test=68) is intrinsically
  high-variance; single-seed hyperparameter search here is unreliable
  for deltas < 0.03.

## Splits are Globally Cached (major methodology bug, node_0040, 2026-04-10)

`benchmarks/src/autobench/pipeline/prepare.py:117` only creates splits
if `splits_0.csv` is absent. Once created, the splits are cached at
`benchmark/splits/standard/high_grade/` and **reused forever,
regardless of what `seed` is passed to `prepare_all`.** Every
experiment in this session — including the "different seeds" for the
noise study — used the same train/val/test partition.

**Proof:** node_0040 (LS 0.15, split_seed=42 forced, train_seed=7) and
node_0034 (LS 0.15, seed=7 for both) produced byte-identical metrics:
val_auc 0.7744, val_bacc 0.6598, test_auc 0.8024, test_bacc 0.7114,
composite 0.7569. Changing the "split seed" had no effect.

**Revised variance interpretation:**
- The ±0.020 composite variance I attributed to "data splits" is
  actually entirely from **model initialization / training
  non-determinism on the same fixed test set**.
- Hyperparameter comparisons *were* valid (same test set throughout),
  but the signal is dominated by the ±0.020 init noise.
- CLAM already averages across 5 folds, yet still exhibits this ±0.020
  init-level noise. That suggests fold-to-fold independence is fragile
  with n_train=204.

**Actionable next direction:** multi-init ensembling. Train the same
config with ≥3 different random inits on the same splits and average
the per-slide prediction logits. With model-init noise ±0.020, a
3-model ensemble should reduce noise to ~0.012, a 5-model ensemble
to ~0.009. This is the highest-leverage remaining lever for a real
gain — probably more than any single hyperparameter.

**Insight:** label smoothing did ~15× more work than cosine annealing for
the same code-edit cost. The prior invalidated "0.7458" result for label
smoothing was clearly baseline code executing — real label smoothing
produces a much larger delta.

## Open Questions

- Does **label smoothing + cosine annealing** stack additively?
- Does **higher label smoothing (0.15 / 0.2)** help further, or does it
  flatten the decision boundary too much?
- Does **class-weighted loss** add more BACC on top of label smoothing?
- Does **focal loss** compete with label smoothing, or is it redundant?

## Bottleneck

- BACC (0.6984) lags AUC (0.7902) by ~9 points. Techniques that improve
  calibration / decision-boundary placement are the most promising.
- **Class imbalance confirmed** via node_0005 diagnostic: train split is
  120 neg / 84 pos (58.8 % / 41.2 %). Modest imbalance, but non-trivial.

## Isolation Fix Verified (2026-04-10)

node_0005 run.log shows:
`Init loss function... class_counts=[120, 84] class_weights=[0.85, 1.214]`

This print exists only in the worktree-overlay copy of
`benchmarks/lib/CLAM/utils/core_utils.py` and would not appear if the
editable-installed main-repo version shadowed it. End-of-story proof
that the PYTHONPATH + AUTOBENCH_ROOT fix routes imports through the
worktree for real experiments.
