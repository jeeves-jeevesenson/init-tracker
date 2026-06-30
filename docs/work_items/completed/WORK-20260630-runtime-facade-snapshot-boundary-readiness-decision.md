# WORK-20260630-runtime-facade-snapshot-boundary-readiness-decision: Runtime facade snapshot-boundary readiness decision

## Status

Completed.

## Type

Bounded planning/decision pass only.

## Goal

Create the durable readiness decision for a future `ServerRuntimeFacade.read_snapshot()` implementation before any runtime/app/source/test behavior changes.

## Initial Repository State

Initial `git status --short`:

```text
?? docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md
?? logs/context/
```

Local `HEAD` was verified as `ef62236`.

The current-work ledger was `Idle` and explicitly allowed opening `WORK-20260630-runtime-facade-snapshot-boundary-readiness-decision` as the next bounded planning/decision pass.

## Files Inspected

- `docs/work_items/current_work.md`
- `docs/planning/living_docs/server_runtime_snapshot_boundary_checkpoint_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-snapshot-boundary-checkpoint.md`
- `docs/planning/living_docs/server_runtime_package_boundary_plan_20260630.md`
- `docs/architecture/server_runtime_facade_command_inventory_20260630.md`
- `docs/architecture/server_runtime_extraction_decision_20260628.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-package-import-realignment.md`
- `AGENTS.md`
- `docs/agent_tasks/templates/task-packet.md`
- `server_runtime.py`, targeted ranges only
- `dnd_initative_tracker.py`, targeted ranges only
- `combat_service.py`, targeted ranges only
- `tests/test_server_runtime.py`, targeted ranges only

## Targeted Source/Test Ranges Inspected

- `server_runtime.py` lines 1-240: runtime command/snapshot contracts, status constants, command constants, facade readiness, and queue adapter setup.
- `server_runtime.py` lines 240-380: representative queue-backed command dispatch/result handling.
- `server_runtime.py` lines 700-790: spell-color direct facade path and fail-closed `read_snapshot(...)`.
- `dnd_initative_tracker.py` lines 140-200: `_current_request_wants_tactical_map()`.
- `dnd_initative_tracker.py` lines 1490-1545: adjacent cached/prebuild helper context.
- `dnd_initative_tracker.py` lines 8388-8565: `_dm_console_snapshot()` and `_dm_console_snapshot_payload()`.
- `dnd_initative_tracker.py` lines 46745-46870: `_dm_tactical_snapshot_from_lan_snapshot()` and `_dm_tactical_snapshot()`.
- `combat_service.py` lines 190-530: `CombatService.combat_snapshot()` and immediate post-mutation snapshot pattern.
- `tests/test_server_runtime.py` lines 1-1700 plus final tail: package re-export, command contract, fail-closed command, queue timeout/error, route mapping, and migrated command tests.

## Files Changed

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-snapshot-boundary-readiness-decision.md`
- `docs/planning/living_docs/server_runtime_snapshot_boundary_readiness_decision_20260630.md`
- `docs/agent_tasks/WORK-20260630-runtime-facade-snapshot-boundary-readiness-decision.md`

During the pass, `docs/work_items/active/WORK-20260630-runtime-facade-snapshot-boundary-readiness-decision.md` was created and then removed before completion so no active work item remains.

## Decision

The future `read_snapshot()` implementation should be a narrow facade wrapper over existing legacy read helpers, not a route migration, not cache relocation, and not a new snapshot builder.

Chosen snapshot modes:

- `combat`: combat-only DM read model from `CombatService.combat_snapshot()`, with no tactical payload.
- `tactical`: tactical/map read model from `_dm_tactical_snapshot()`, with static hydration out of scope.
- `dm_console`: route-compatible DM console composite from `_dm_console_snapshot(include_tactical=<resolved bool>)`, including pending prompts and optionally `tactical_map`.

Caller workspace/tactical preference should be explicit through `RuntimeSnapshotRequest.params`, not hidden request-path globals.

## Result Semantics

Future snapshot results should preserve the existing `success` and `data` shape and may add only defaulted metadata/error fields if the implementation task explicitly touches the dataclass.

Allowed read statuses are:

- `completed`
- `failed`
- `timed_out` only if a later timeout/offload task explicitly introduces read timeout behavior

Read results should not use `accepted`, `queued`, or `dispatching`.

Failures should return no partial payload and should expose a safe structured error shape if the dataclass is extended.

## Fail Behavior Decision

The current `read_snapshot()` remains fail-closed and unimplemented.

The future implementation must fail closed before readiness, when `lan_controller`/legacy app/service references are missing, when snapshot types or params are unsupported, and when legacy builders fail.

No new fail-open cache fallback is allowed.

## Cache / Prebuild Ownership Decision

The first implementation must preserve existing cached DM snapshot reuse by delegating `dm_console` mode to `_dm_console_snapshot(...)`.

The facade must not own cache state, relocate `_cached_dm_snapshot`, change TTL/one-shot behavior, add invalidation hooks, or introduce static-hydration cache behavior in the first slice.

## Deferred Scope

- Direct-route migration.
- Route offload.
- Route instrumentation.
- AoE create.
- Rules-aware move.
- Structures.
- Ships.
- Boarding links.
- Gameplay mutation semantics.
- Static map hydration.
- Snapshot cache relocation.
- WebSocket/event publication boundary changes.
- Browser smoke.

## Recommended Next Task

Recommended exact next task:

`WORK-20260630-runtime-facade-read-snapshot-minimal-implementation`

Reason: the readiness decision now defines enough request/result, mode, failure, cache, boundary, and validation semantics to proceed directly to a minimal implementation slice with focused contract tests included. A separate tests-only pass would either leave red tests or duplicate the implementation scope.

## Validation

Required validation for this docs-only pass:

- `git status --short`
- `timeout 10s git diff --check`

No Python tests were run because this pass did not edit runtime/app/source/test behavior.

## Ledger Update

`docs/work_items/current_work.md` was returned to Idle after completion and now recommends opening `WORK-20260630-runtime-facade-read-snapshot-minimal-implementation` as the exact next task.

## Untouched Pre-existing Untracked Paths

The expected pre-existing untracked paths remained outside this pass:

- `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md`
- `logs/context/`

