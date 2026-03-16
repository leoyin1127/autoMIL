#!/bin/bash
# autoMIL stop hook -- prevents the agent from stopping while the loop is active.
#
# Activation:   touch .autoresearch_active
# Deactivation: rm    .autoresearch_active
#
# When active, any attempt by the agent to stop will be intercepted with a
# state-aware continuation prompt.
#
# SETUP: Update EXPERIMENT_DIR to point to your experiment directory.

EXPERIMENT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
FLAG_FILE="${EXPERIMENT_DIR}/.autoresearch_active"
STATE_FILE="${EXPERIMENT_DIR}/state.json"

if [ ! -f "$FLAG_FILE" ]; then
    exit 0  # No output = allow stop
fi

cat <<'EOF'
DO NOT STOP. The autoresearch loop is active.

Resume protocol:
1. Read state.json (where you left off)
2. Read learnings.md (consolidated insights, "What Works" / "What Doesn't Work")
3. Read strategies.json (pick next strategy)
4. Read config.yaml (project settings)
5. Continue the experiment loop (program.md)

EOF

if [ -f "$STATE_FILE" ]; then
    echo "--- Current state ---"
    cat "$STATE_FILE"
    echo ""
fi

echo "To deactivate this loop, the human must run: rm .autoresearch_active"
exit 1
