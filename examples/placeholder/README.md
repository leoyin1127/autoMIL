# Placeholder Example

Minimal template showing what `automil init` creates. Copy and edit
`automil/config.yaml` for your project.

## Quick start from this template

```bash
cp -r examples/placeholder/automil /path/to/your/project/
cd /path/to/your/project

# Edit automil/config.yaml: at minimum, set
#   run.script
#   files.editable / files.readonly
#   env.required + env.passthrough
#   scoring.formula
#   cap.budget_seconds + cap.safety_buffer_seconds
#   baseline.composite

automil check                       # validates protected files, env.required, backend
automil orchestrator start
```

Ensure your training script honors the
[training-script contract](../../docs/training-script-contract.md): write
`result.json` matching `automil/schemas/result.schema.json`, exit cleanly
on SIGTERM with a partial result, declare env vars under `env.required`.

For a worked minimal reference (~80 LOC, no `automil.*` imports), see
[`examples/sklearn-iris/`](../sklearn-iris/).
