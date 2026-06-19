# BUG-20260614-reactions-hold-combat

- **Title**: Reactions can hold up combat.
- **Status**: Active
- **Source bug**: [docs/bug_reports/triaged/BUG-20260614-reactions-hold-combat.md](../../bug_reports/triaged/BUG-20260614-reactions-hold-combat.md)
- **Severity**: S1
- **Priority**: P1
- **Area**: Reactions / Turn Flow
- **Active Gate**: Gate 1 — Evidence capture and bounded fix plan

## Goal

Capture enough concrete evidence to determine whether reaction prompts, reaction queue lifecycle, or turn-advancement gating can stall combat, then produce a bounded fix plan.

## User-visible impact

Combat flow can stall while the table waits for reaction prompts or resolution, forcing manual intervention or delaying turns.

## Evidence baseline

Current evidence is developer note only: reactions are buggy and can hold up combat.

## Missing evidence

- Specific reaction involved.
- Actor and triggering action.
- Whether prompt appeared, failed to appear, or could not be dismissed.
- Approximate delay/stall behavior.
- Whether repeated clicks made it worse.
- Browser console, backend log, and debug trace summary.

## Scope

### In scope

- Reaction prompt lifecycle evidence.
- Reaction queue / pending response state evidence.
- Turn advancement gating evidence.
- Related reaction triggers named by the source bug: Counterspell and Opportunity Attacks.
- Existing logs and debug trace summaries.
- Bounded fix plan after evidence.

### Out of scope

- Do not change app code in Gate 1.
- Do not change DM-side automation unless evidence identifies it as the blocker.
- Do not change monster AI.
- Do not change AoE targeting.
- Do not change mount behavior; mount lockout is already completed.
- Do not run broad/full test suites.

## Plan

### Gate 1: Evidence capture and bounded fix plan

- [x] Gather latest relevant live debug console log tail.
- [x] Gather latest debug trace latency summary.
- [x] Search only named runtime reports/logs for reaction, counterspell, and opportunity evidence.
- [x] Inspect related completed mount-lockout evidence only for turn-gate pattern comparison.
- [x] Produce a bounded fix plan with exact files likely needing edits and scoped validation commands. (See [docs/runtime_reports/BUG-20260614-reactions-hold-combat_gate1_evidence_20260619.md](../../runtime_reports/BUG-20260614-reactions-hold-combat_gate1_evidence_20260619.md))
- [x] Stop before implementation.

## Candidate commands

    scripts/chatgpt_context_refresher.sh
    cat /tmp/init-tracker-context-refresher.txt
    LOG="$(ls -t logs/live-debug-console*.log 2>/dev/null | head -1)"; echo "$LOG"; test -n "$LOG" && tail -200 "$LOG"
    TRACE="$(ls -t logs/debug-trace-*.jsonl 2>/dev/null | head -1)"; echo "$TRACE"; test -n "$TRACE" && ./.venv/bin/python3 scripts/trace_latency_summary.py "$TRACE"
    grep -Rni "reaction\|counterspell\|opportunity" logs docs/runtime_reports 2>/dev/null | tail -120

## Validation for Gate 1 docs/admin promotion

- `git status --short`
- `timeout 10s git diff --check`

## Stop condition

Stop after Gate 1 evidence and bounded fix plan are written. Do not implement until Gate 2 is explicitly authorized.
