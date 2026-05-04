#!/usr/bin/env bash
# Hook: trajectory recording + prevent agent from stopping while autoMIL loop is active.
# Claude Code delivers hook payload on stdin — HOOK_EVENT=$(cat) (NOT an env var).
# Exit 1 = prevent stop. Exit 0 = allow stop.
# Trajectory recording fires automil trajectory record (TRJ-04 / D-96).

# Read hook event from stdin (Claude Code hook delivery mechanism — D-95/D-96 CORRECTED)
HOOK_EVENT="$(cat)"

# Find project root by walking up
DIR="$PWD"
while [ "$DIR" != "/" ]; do
    if [ -f "$DIR/.automil_active" ]; then
        echo "autoMIL loop is active. Run 'automil stop-loop' to allow stopping."
        echo ""
        echo "Resume instructions:"
        echo "  1. Read config.yaml, graph.json, learnings.md, program.md"
        echo "  2. Run: automil reconcile"
        echo "  3. Continue the experiment loop"
        exit 1
    fi
    DIR="$(dirname "$DIR")"
done

# Trajectory recording — only fires if AUTOMIL_NODE_ID and AUTOMIL_RUNTIME are both set.
# These are set by the orchestrator before starting the agent session (not by Claude Code).
if [[ -n "${AUTOMIL_NODE_ID:-}" && -n "${AUTOMIL_RUNTIME:-}" && -n "$HOOK_EVENT" ]]; then
    automil trajectory record "$HOOK_EVENT" \
        2>>"${AUTOMIL_DIR:-/tmp}/trajectory.err.log" || true
fi

exit 0
