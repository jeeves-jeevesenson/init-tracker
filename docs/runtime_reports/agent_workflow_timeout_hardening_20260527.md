# Agent Workflow Timeout Hardening - 2026-05-27

## Failure mode observed

A Gate 1 task completed its required validation, then launched an extra broad `DmTacticalMapHotfixTests` class run and hung at the known websocket test `test_ws_dm_endpoint_dmcontrol_workspace_query_param`.

This wasted developer time and agent quota without adding trustworthy release evidence.

## Rule added

- All gate unittest validation must be timeout-bounded.
- Required gate validation is sufficient for the agent final report.
- Agents must not run broad extra unittest classes after required validation passes.
- Extra tests must be targeted to a specific failure, timeout-bounded, and named in the final report.
- Known websocket tests must never be run without timeout.
- Browser smoke remains developer-owned and cannot be replaced by additional Python tests.

## Validation to run

```bash
git diff --check
bash -n scripts/agent_gate_validate.sh
AGENT_TEST_TIMEOUT_S=20 scripts/agent_gate_validate.sh gate1-map
```

## Remaining risk

This hardening prevents unbounded validator/test runs, but agents can still attempt unrelated shell commands unless the task and root instructions remain strict.
