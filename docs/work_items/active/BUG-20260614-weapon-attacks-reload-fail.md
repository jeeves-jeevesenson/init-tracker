# BUG-20260614-weapon-attacks-reload-fail

## Status

- **Status:** Active
- **Type:** Bug evidence capture / classification
- **Severity:** S1
- **Source bug report:** ../../bug_reports/triaged/BUG-20260614-weapon-attacks-reload-fail.md
- **Opened:** 2026-06-26

## Goal

Capture enough current evidence to determine whether weapon reload failure and saber attack failure are:
1. the same root cause,
2. separate bugs,
3. stale/non-reproducible behavior, or
4. missing player data/equipment configuration.

Do not implement a broad weapon/action fix from the initial report alone.

## Known report

Developer notes from the triaged bug:

- "reloading doesnt really work. you can select it and my weapon shows loaded but no way for me to reload"
- "scratch that a saber attack failed too"

## Missing evidence

- Character name.
- Weapon name.
- Whether the weapon is equipped.
- Whether a reload action appears and what it does.
- Whether weapon load state changes server-side.
- Saber actor/target/action details.
- Browser-visible error, console error, backend traceback, or debug trace event.
- Whether reload failure and saber failure share a code path.

## Initial evidence commands

```bash
scripts/chatgpt_context_refresher.sh
cat /tmp/init-tracker-context-refresher.txt
LOG="$(ls -t logs/live-debug-console*.log 2>/dev/null | head -1)"; echo "$LOG"; tail -200 "$LOG"
TRACE="$(ls -t logs/debug-trace-*.jsonl 2>/dev/null | head -1)"; echo "$TRACE"; ./.venv/bin/python3 scripts/trace_latency_summary.py "$TRACE"
grep -Rni "reload\|loaded\|saber\|weapon" logs docs/runtime_reports 2>/dev/null | tail -120
```

## AGY posture

Use AGY only for a bounded evidence-capture/classification task.

AGY must not perform broad implementation, whole-repo review, full-suite testing, deploys, service restarts, or unrelated cleanup.

## Fix phase

Evidence capture classified the initial report as two separate defects with small implicated areas:

1. Reload failure: missing websocket routing for `reload_weapon` in `InitiativeTracker._lan_apply_action`.
2. Saber/inventory weapon failure: inventory-equipped weapons bypass full weapon normalization in `InitiativeTracker._normalize_player_profile`.

Use `docs/work_items/active/BUG-20260614-weapon-attacks-reload-fail-evidence.md` as the canonical evidence note for implementation scope.

## Fix done condition

- `reload_weapon` websocket action reaches the existing reload backend path.
- Inventory-equipped synced weapons receive the same normalization needed by normal profile weapons.
- Focused regression tests cover both fixes.
- No broad weapon/action rewrite is performed.
- Developer browser smoke remains required before closeout.

## Done condition for this phase

A repo-written evidence/classification note exists that states:

- what evidence was found,
- whether the bug is currently reproducible from available logs/traces/docs,
- the smallest likely code/data area for a follow-up fix, or
- what specific developer smoke evidence is still required.

## Closeout

Status: Complete

Functional fix commit: `7d10a14`

Developer browser smoke passed.

Validated outcomes:

- Multiattack no longer fails with `No actions left, matey.`
- Monster/enemy capability resolution no longer uses PC-style action-budget blocking.
- Single rifle attacks decrement loaded ammo after Apply.
- Multiattack rifle components decrement the correct weapon ammo after Apply.
- Preview/target selection does not decrement ammo.
- Failed/canceled apply does not decrement ammo.
- Reload fills the selected weapon after ammo is spent.
- Invalid `Current Ammo: 0 / 0` reload modal no longer appears.
- Reload is weapon-specific when enemies have multiple weapons.
- Reload remains mutually exclusive with active Multiattack.

Follow-up recommendation:

Open a separate work item for a dedicated Multiattack modal UI.
