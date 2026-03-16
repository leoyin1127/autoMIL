# autoMIL

Autonomous research loop for improving ML models via iterative experimentation.
Adapted from Karpathy's autoresearch concept, with persistent learnings and
robust session restart (inspired by Ralph and EvoScientist patterns).

## Restart protocol

On every session start or context reset, read these files in order:

1. **`state.json`** - where you left off (current strategy, last experiment, best composite)
2. **`learnings.md`** - consolidated insights ("What Works" / "What Doesn't Work" sections)
3. **`strategies.json`** - strategy catalog, pick next unfinished strategy
4. **`config.yaml`** - project-specific settings (metrics, run command, files)
5. **`train.py`** - current code state
6. **`results.tsv`** - full experiment history (reference only, learnings.md has the summary)

Then continue the experiment loop from the appropriate step.

## Context

We already have a completed benchmark: 7 pathology encoders x 9 MIL architectures
x 2 tasks (BRCA mutation, HRD status), all on 5-fold stratified CV. The baselines:

| Task | Best Encoder | Best MIL Model     | Test AUC-ROC |
| ---- | ------------ | ------------------ | ------------ |
| BRCA | hibou_l      | ilra_mil           | 0.722        |
| HRD  | hoptimus1    | clam_mb            | 0.865        |

The goal: **beat these baselines** by any means that improve evaluation metrics
without modifying the evaluation methods. This includes improving the training
recipe, feature preprocessing, data augmentation, multi-encoder fusion, custom
model architectures, fusing ideas from existing architectures, or building
entirely new models inline in `train.py`.

### HRD top-10 leaderboard (test AUC-ROC, 5-fold CV)

| Rank | Encoder      | Model          | Framework | AUC   | 95% CI        |
| ---- | ------------ | -------------- | --------- | ----- | ------------- |
| 1    | h_optimus_1  | clam_mb        | CLAM      | 0.865 | 0.823 - 0.907 |
| 2    | uni_v2       | vision_transformer | nnMIL | 0.858 | 0.765 - 0.951 |
| 3    | uni_v2       | clam_mb        | CLAM      | 0.850 | 0.805 - 0.896 |
| 4    | hibou_l      | rrt_mil        | nnMIL     | 0.846 | 0.791 - 0.901 |
| 5    | h_optimus_1  | dtfd_mil       | nnMIL     | 0.845 | 0.757 - 0.934 |
| 6    | h0_mini      | vision_transformer | nnMIL | 0.842 | 0.738 - 0.946 |
| 7    | h_optimus_1  | clam_sb        | CLAM      | 0.841 | 0.772 - 0.911 |
| 8    | h_optimus_1  | ab_mil         | nnMIL     | 0.839 | 0.783 - 0.896 |
| 9    | h0_mini      | clam_sb        | CLAM      | 0.836 | 0.797 - 0.874 |
| 10   | uni_v2       | clam_sb        | CLAM      | 0.834 | 0.782 - 0.886 |

CLAM models hold 5 of the top 10 slots. The overall best (h_optimus_1 + clam_mb,
0.865) outperforms the nnMIL best (uni_v2 + vision_transformer, 0.858) by 0.007.

## Current target

**HRD only.** BRCA is out of scope for now.

- **Task:** `hrd` (HRD status prediction, binary)
- **Encoder:** `hoptimus1` (1536d, best HRD encoder)
- **Model:** `clam_mb` (best HRD MIL model, CLAM framework)
- **Baseline Test AUC:** 0.865
- **Optimization target:** composite = (test_auc + test_bacc) / 2

Available `MODEL_TYPE` options:
- **nnMIL models:** `vision_transformer`, `ab_mil`, `trans_mil`, `ilra_mil`, etc.
  (created via `create_mil_model()` from nnMIL model_factory)
- **CLAM models:** `clam_sb`, `clam_mb`, `mil_fc`
  (created from `lib/CLAM/models/`; process one slide at a time)

Training config matching the benchmark:
```
learning_rate: 3e-4, weight_decay: 1e-4, dropout: 0.25,
hidden_dim: 512 (hardcoded by model_factory), num_epochs: 100,
warmup_epochs: 5, patience: 10, batch_size: 32, max_seq_length: 4096
```

CLAM-specific CONFIG keys (ignored for nnMIL models):
```
model_size: "small"       # "small" or "big" (CLAM hidden layer sizes)
k_sample: 8               # patches sampled for instance-level eval
bag_weight: 0.7           # weight for bag loss; (1 - bag_weight) for instance loss
instance_eval: True       # enable instance-level supervision (clam_sb/clam_mb only)
```

Note: CLAM models process slides individually in a per-sample loop, so
DataParallel provides no benefit. Use gradient accumulation instead.

Dataset: 206 slides (144 pos, 62 neg), UHN cohort, 5-fold stratified CV.

## Setup

Work with the user to:

1. **Agree on a run tag** (e.g. `hrd-mar10`). Branch: `autoMIL/<tag>`.
2. **Create the branch**: `git checkout -b autoMIL/<tag>` from main.
3. **Read the in-scope files**:
   - This file (`program.md`) for instructions.
   - `config.yaml` for project-specific settings.
   - `prepare.py` (read-only) for data loading, evaluation, constants.
   - `train.py` (editable) for training recipe, preprocessing, augmentation.
4. **Verify features exist**: Check that plan files exist:
   `ls /mnt/pool/ovariancancer/ovarian2026/benchmark_full/nnmil/uhn_baseline/`
5. **Establish baseline**: Run `train.py` unmodified to confirm the baseline reproduces AUC ~0.858.
6. **Initialize results.tsv**: Create with just the header row.
7. **Initialize state.json and learnings.md**: Create initial versions.
8. **Confirm and go**.

## What you CAN do

Modify files listed under `files.editable` in `config.yaml`. Everything is fair game:

- **CONFIG section**: learning rate, weight decay, dropout, hidden dim, batch size,
  max sequence length, number of epochs, patience, warmup.
- **`preprocess_features()`**: L2 normalization, standardization, PCA, feature
  selection, multi-encoder fusion (load from multiple H5 dirs and concatenate).
- **`augment_batch()`**: stochastic patch dropout, Gaussian noise on features,
  feature-space mixup, random patch masking.
- **`create_loss_fn()`**: focal loss, label smoothing, class-weighted CE.
- **`create_optimizer()`**: SAM, muon, different AdamW configs, separate LR per group.
- **`create_lr_schedule()`**: linear warmup/decay, step LR, no schedule.
- **The training loop** (`train_single_fold`): gradient clipping, accumulation,
  hard instance mining, test-time augmentation.

## What you CANNOT do

- Modify files listed under `files.readonly` in `config.yaml`.
- Change the 5-fold split assignments.

You CAN modify or replace the model. `create_mil_model()` from the model factory
is the starting point, but you are free to define custom architectures inline in
`train.py`, modify model hyperparameters (layers, heads, hidden dims), or swap
in a completely different model. The only constraint is that the evaluation
(splits, metrics) stays fixed.

**Architecture modifications are encouraged.** Beyond hyperparameter tuning and
loss/augmentation changes, you should actively look for deficiencies in the
original model architectures (e.g. in `lib/CLAM/models/`) and improve them.
This includes modifying attention mechanisms, adding layers, changing pooling
strategies, or building custom architectures inline in `train.py`. Architecture
improvements are preferred over pure hyperparameter tuning when possible.

## Improvement strategies

Strategies are tracked in `strategies.json` with structured fields:
- `id`, `name`, `tier` (1=high priority, 2=medium, 3=lower)
- `status`: `not_started`, `in_progress`, `tested`, `exhausted`
- `effort`, `expected_gain`, `risk`
- `description`, `reference`, `implementation_notes`
- `experiments`: list of experiment descriptions and composites from results.tsv

Read `strategies.json` before each experiment round to pick the next strategy.
Update the JSON after each experiment with results and status changes.
Exhausted strategies are listed in the `exhausted` array.

### Brainstorm step

Before starting a new round, if all current strategies are exhausted or stalled,
do a **thorough brainstorm**:
1. Review learnings.md for patterns (what worked, what failed, near-misses)
2. Review results.tsv for numerical trends
3. Research recent MIL literature for new techniques
4. Consider fusing ideas from multiple architectures
5. Add new strategies to `strategies.json` with full structured info

### Performance context

DeepHRD (JCO 2024) achieved AUC 0.74 on ovarian HRD from WSI. HRDPath (2025)
achieved AUC 0.846 with a multi-task dual-model architecture. Our current
composite of 0.850 is competitive but room for improvement likely exists
through architectural innovation and data augmentation strategies.

## Output format

The script prints a parseable summary:

```
---
val_auc_roc: 0.735000 (+/- 0.0500)
val_bacc: 0.680000 (+/- 0.0400)
val_f1: 0.700000 (+/- 0.0350)
test_auc_roc: 0.720000 (+/- 0.0600)
test_bacc: 0.670000 (+/- 0.0500)
test_f1: 0.690000 (+/- 0.0450)
baseline_delta: +0.013000
elapsed_seconds: 1200.5
peak_vram_mb: 4500.0
---
```

Extract the key metric: `grep "^test_auc_roc:" run.log`

## Logging results

Results are auto-logged by `train.py` to `results.tsv` (tab-separated):

```
commit	val_auc	val_bacc	test_auc	test_bacc	composite	delta	vram_gb	elapsed_min	status	description
```

The `status` (keep/discard) and `composite` are computed automatically by train.py.

## The experiment loop

Run on a dedicated branch (e.g. `autoMIL/hrd-mar10`).

**LOOP FOREVER:**

1. **Read `strategies.json`** to pick the next strategy (prefer tier 1, then 2, then 3).
   Set its `status` to `"in_progress"`.
2. **Read `learnings.md`** "What Works" / "What Doesn't Work" sections to avoid
   repeating failed approaches.
3. Review `train.py` for current state.
4. Modify `train.py` with the change.
5. `git commit -m "try: <description>"`
6. Run: `uv run python autoMIL/train.py > run.log 2>&1`
7. Extract results: `grep "^test_auc_roc:\|^baseline_delta:\|^peak_vram_mb:\|^elapsed_seconds:" run.log`
8. If grep output is empty, the run crashed. Read `tail -50 run.log` for the error.
9. Results are auto-logged to `results.tsv` by train.py (do NOT commit this file).
10. **Update `strategies.json`**: append to the strategy's `experiments` array
    (description + composite score). If the strategy is fully explored, set
    `status` to `"tested"` or `"exhausted"`. Update `meta.best_composite`
    and `meta.total_experiments` if needed.
11. **Update `state.json`**: set `current_strategy_id`, `last_experiment` details,
    `best_composite`, and `total_experiments`.
12. **Append to `learnings.md`**: add a timestamped entry with what was tried,
    the result (composite, delta), and the key insight or takeaway.
13. If composite improved: **keep** the commit, advance the branch.
14. If composite is worse or equal: **discard** via `git reset --hard HEAD~1`.
15. **Every 5 experiments**: review recent learnings entries and update the
    consolidated "What Works" / "What Doesn't Work" sections at the top of
    `learnings.md` with any new patterns.
16. **If all strategies have status `tested` or `exhausted`**: trigger a
    brainstorm round. Research new MIL techniques (web search, literature),
    analyze patterns in learnings.md and results.tsv, consider fusing near-miss
    ideas, and add new strategies to `strategies.json` with full structured fields.
    Then continue the loop.
17. Repeat.

**Timing**: Each 5-fold CV takes ~15-45 minutes depending on model complexity.
That is ~2-4 experiments per hour, ~16-32 per overnight run.

**GPU usage**: The `GPU` variable in `train.py` controls GPU allocation.
Two modes, choose per-experiment:

1. **Single GPU** (`GPU = 0`): Uses gradient accumulation (`micro_batch_size`
   forward passes accumulated to `batch_size`). Run 3 separate sessions on
   GPUs 0/1/2 for parallel exploration.

2. **Multi-GPU DataParallel** (`GPU = [0, 1, 2]`): Splits each micro-batch
   across GPUs. Use for large models or when you want faster per-experiment
   throughput instead of parallel exploration.

**Crashes**: If a run OOMs or errors, check if it is a simple fix (typo, shape
mismatch). If the idea is fundamentally broken, log as crash and move on.

**NEVER STOP**: Once the loop begins, do NOT pause to ask if you should continue.
Run until manually interrupted. If you run out of strategies, trigger the
brainstorm step (step 16) to research and add new ones. The strategy list
should always be growing, never empty.

**Simplicity criterion**: A small improvement with ugly complexity is not worth it.
Equal results with simpler code is a win. A 0.002 AUC improvement from deleting
code? Definitely keep. A 0.002 improvement from 50 lines of hacky augmentation?
Probably not worth it.

## Generalizing to other projects

To use this loop for a different experiment:

1. Copy the `autoMIL/` directory to a new location
2. Edit `config.yaml` with your project settings (task, files, metrics, run command)
3. Replace `train.py` and `prepare.py` with your equivalents
4. Clear `results.tsv`, `learnings.md`, `state.json`, and `strategies.json`
5. Update `program.md` context sections with your project's background
6. Everything else (hooks, skill, loop logic) works as-is
