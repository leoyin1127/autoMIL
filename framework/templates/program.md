# autoMIL

Autonomous LLM-agent experiment loop for optimizing ML models.
The agent iteratively modifies a training script, runs experiments,
keeps improvements, discards regressions, and accumulates knowledge.

## Restart Protocol

On every session start or context reset, read these files in order:

1. **`state.json`** -- where you left off (current strategy, last experiment, best composite)
2. **`learnings.md`** -- consolidated insights ("What Works" / "What Doesn't Work")
3. **`strategies.json`** -- strategy catalog, pick next unfinished strategy
4. **`config.yaml`** -- project-specific settings (metrics, run command, files)
5. Editable files listed in `config.yaml` -- current code state
6. **`results.tsv`** -- full experiment history (reference only, learnings.md has the summary)

Then continue the experiment loop from the appropriate step.

## Project Context

Read `config.yaml` for project-specific details: task, dataset, baseline,
metrics, available models, and domain context. Everything project-specific
lives there so this file stays generic.

## What You CAN Do

Modify files listed under `files.editable` in `config.yaml`. Everything is fair game:
hyperparameters, preprocessing, augmentation, loss functions, optimizers,
learning rate schedules, model architecture, training loop logic.

## What You CANNOT Do

- Modify files listed under `files.readonly` in `config.yaml`.
- Change the cross-validation split assignments.
- Modify the evaluation metrics or their computation.

Architecture modifications are encouraged. Beyond hyperparameter tuning,
actively look for architectural improvements: attention mechanisms, pooling
strategies, regularization, custom models defined inline.

## Improvement Strategies

Strategies are tracked in `strategies.json` with structured fields:
- `id`, `name`, `tier` (1=high priority, 2=medium, 3=lower)
- `status`: `not_started`, `in_progress`, `tested`, `exhausted`
- `effort`, `expected_gain`, `risk`
- `description`, `reference`, `implementation_notes`
- `experiments`: list of experiment descriptions and results

Read `strategies.json` before each experiment to pick the next strategy.
Update it after each experiment with results and status changes.

### Brainstorm Step

When all strategies are exhausted or stalled, do a thorough brainstorm:
1. Review learnings.md for patterns (what worked, what failed, near-misses)
2. Review results.tsv for numerical trends
3. Research recent literature for new techniques (web search if available)
4. Consider combining ideas from near-miss experiments
5. Add new strategies to `strategies.json` with full structured fields

## Results Logging

The training script auto-logs to `results.tsv` (tab-separated).
The `status` (keep/discard) and optimization metric are computed automatically.
Do NOT commit results.tsv.

## The Experiment Loop

Run on a dedicated branch (e.g. `autoMIL/<run-tag>`).

**LOOP FOREVER:**

1. **Read `strategies.json`** to pick the next strategy (prefer tier 1, then 2, then 3).
   Set its `status` to `"in_progress"`.
2. **Read `learnings.md`** "What Works" / "What Doesn't Work" sections to avoid
   repeating failed approaches.
3. Review editable files for current state.
4. Modify the editable file(s) with the change.
5. `git commit -m "try: <description>"`
6. Run the experiment using the command from `config.yaml`.
7. Extract results using the extract command from `config.yaml`.
8. If extraction is empty, the run crashed. Read `tail -50 run.log` for the error.
9. Results are auto-logged to `results.tsv` by the training script.
10. **Update `strategies.json`**: append to the strategy's `experiments` array.
    If the strategy is fully explored, set status to `"tested"` or `"exhausted"`.
    Update `meta.best_composite` and `meta.total_experiments`.
11. **Update `state.json`**: set `current_strategy_id`, `last_experiment` details,
    `best_composite`, and `total_experiments`.
12. **Append to `learnings.md`**: timestamped entry with what was tried,
    the result (metric value, delta), and the key insight or takeaway.
13. If metric improved: **keep** the commit.
14. If metric is worse or equal: **discard** via `git reset --hard HEAD~1`.
15. **Every 5 experiments**: update the consolidated "What Works" / "What Doesn't Work"
    sections at the top of `learnings.md` with new patterns.
16. **If all strategies exhausted**: trigger the brainstorm step to research and add
    new strategies. The strategy list should always be growing, never empty.
17. Repeat.

**NEVER STOP**: Once the loop begins, do NOT pause to ask if you should continue.
Run until manually interrupted. If you run out of strategies, brainstorm new ones.

**Simplicity criterion**: A small improvement with ugly complexity is not worth it.
Equal results with simpler code is a win. A 0.002 improvement from deleting
code? Definitely keep. A 0.002 improvement from 50 lines of hacky code?
Probably not worth it.

## Generalizing to Other Projects

To use this loop for a different task:

1. Copy this directory to a new location
2. Edit `config.yaml` with your project settings
3. Replace `train.py` and `prepare.py` with your equivalents
4. Clear `results.tsv`, `learnings.md`, `state.json`, and `strategies.json`
5. Update `strategies.json` with initial strategies for your domain
6. Everything else (program.md, hooks, skill) works as-is
