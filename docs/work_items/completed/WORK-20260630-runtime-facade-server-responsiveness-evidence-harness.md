# WORK-20260630-runtime-facade-server-responsiveness-evidence-harness

Status: Completed

## Goal

Add a developer-run responsiveness evidence harness that can be pointed at an already-running init-tracker server to measure whether HTTP handling remains responsive while heavier DM read-model work is occurring.

This was a harness/docs slice only. No app/runtime behavior, routes, cache behavior, snapshot builders, response schemas, queue behavior, LAN controller behavior, Tk behavior, WebSockets, gameplay, launcher behavior, production topology, deploy files, server starts, browser smoke, commits, or pushes were changed or run.

## Files Changed

- `scripts/server_responsiveness_harness.py`
- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-server-responsiveness-evidence-harness.md`

No active work item copy was left after completion.

## Source Inspected

- `docs/work_items/current_work.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-post-smoke-latency-read-model-checkpoint.md`
- `docs/planning/living_docs/server_runtime_post_smoke_latency_read_model_checkpoint_20260630.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-dm-console-read-model-cache-refinement-minimal-implementation.md`
- `docs/work_items/completed/WORK-20260630-runtime-facade-latency-read-model-followup-decision.md`
- `docs/planning/living_docs/server_runtime_latency_read_model_followup_decision_20260630.md`
- `init_tracker_server/app.py`: health/readiness route names only.
- `dnd_initative_tracker.py`: `GET /api/dm/combat` route path/query shape only.
- `scripts/` directory listing only.

## Harness Behavior

The new script targets an already-running server and does not start, stop, restart, deploy, or mutate server state.

Default target:

```bash
.venv/bin/python scripts/server_responsiveness_harness.py
```

Default connection settings:

- Host: `127.0.0.1`
- Port: `8787`
- Duration: `30` seconds
- Interval: `1` second between concurrent polling rounds
- Per-request timeout: `2` seconds

Polled endpoints:

- `/health`
- `/api/health`
- `/ready`
- `/api/ready`
- `/api/dm/combat`
- `/api/dm/combat?workspace=dmcontrol`

Each round issues one GET to every endpoint concurrently. The two DM combat probes are intentionally included in the same round as health/readiness probes so slow DM-console/tactical read-model work can overlap with lighter HTTP checks.

The script uses only the Python standard library.

## Evidence Output

By default, the script writes JSONL under `logs/smoke/` with this work item ID and a timestamp in the filename:

```text
logs/smoke/WORK-20260630-runtime-facade-server-responsiveness-evidence-harness_<timestamp>.jsonl
```

The output contains a `run_start` record, one `sample` record per endpoint request, and a `run_end` record. Sample records include endpoint, URL, HTTP status when present, latency in milliseconds, bytes read, timeout setting, success/failure flag, and any connection/timeout/HTTP error classification.

Connection failures, refused connections, timeouts, HTTP 4xx/5xx statuses, and readiness 503s are recorded as evidence lines rather than uncaught crashes.

Stdout remains compact and prints only the output path plus per-endpoint count, failure count, p50, p95, max latency, and status distribution.

## Command Examples

Default local run against the standard headless server port:

```bash
.venv/bin/python scripts/server_responsiveness_harness.py
```

Longer developer evidence run while heavier DM read-model activity is occurring:

```bash
.venv/bin/python scripts/server_responsiveness_harness.py --host 127.0.0.1 --port 8787 --duration-seconds 60 --interval-seconds 0.5 --timeout-seconds 2
```

Explicit evidence file:

```bash
.venv/bin/python scripts/server_responsiveness_harness.py --output logs/smoke/WORK-20260630-runtime-facade-server-responsiveness-evidence-harness_manual.jsonl
```

Help path, which does not require a running server:

```bash
.venv/bin/python scripts/server_responsiveness_harness.py --help
```

## What This Measures

The harness measures route-level client-observed latency and status for health, readiness, and DM combat reads while those requests are made concurrently.

It is intended to answer whether lightweight health/readiness HTTP handling remains responsive while `GET /api/dm/combat` and `GET /api/dm/combat?workspace=dmcontrol` are exercising the current DM-console/tactical read-model path.

## What This Does Not Prove

The harness does not prove root cause by itself. It does not identify whether latency is from ASGI event-loop blocking, worker/thread starvation, tracker/Tk-owned state access, cache misses, tactical/LAN snapshot construction, queue waits, browser behavior, network effects, auth configuration, or server process startup/shutdown.

It does not replace developer browser smoke, debug-trace analysis, route instrumentation, production monitoring, cache/offload design, or thread-safety review. It also does not make route-side offload, facade-owned caching, TTL changes, static hydration changes, further route adoption, or topology changes safe by itself.

## Required Developer Follow-up

Run the harness against an already-running headless server while known heavier DM read-model activity is occurring:

```bash
.venv/bin/python scripts/server_responsiveness_harness.py --host 127.0.0.1 --port 8787 --duration-seconds 60 --interval-seconds 0.5 --timeout-seconds 2
```

Then inspect/record the JSONL evidence under `logs/smoke/` and commit the evidence plus this completed harness/doc change if acceptable.

## Ledger Update

`docs/work_items/current_work.md` was returned to Idle.

Allowed next action is to run developer smoke/evidence with the new harness against an already-running headless server, then record and commit the evidence if acceptable.

Do not proceed to cache escalation, route-side offload, route migration, app-host changes, launcher changes, direct gameplay-route migration, player-command routes, combat mutation routes, rules-aware move, AoE create, structures, ships, boarding links, static hydration changes, queue behavior changes, WebSocket behavior changes, deploys, pushes, or production commands without a new active work item.

## Validation

Required validation commands:

- `.venv/bin/python -m py_compile scripts/server_responsiveness_harness.py`
- `.venv/bin/python scripts/server_responsiveness_harness.py --help`
- `timeout 10s git diff --check`
- `git status --short`

Results:

- `.venv/bin/python -m py_compile scripts/server_responsiveness_harness.py` passed with no output.
- `.venv/bin/python scripts/server_responsiveness_harness.py --help` passed and printed usage without requiring a running server.
- `timeout 10s git diff --check` passed with no output.
- `git status --short` showed the expected modified/new harness files plus known unrelated baseline untracked dirt under `docs/bug_reports/inbox/BUG-20260626-dmcontrol-terrain-not-visible.md` and `logs/context/`.

## Developer evidence follow-up — 2026-06-30

Evidence status: captured and usable.

Notes:
- An earlier harness run was invalid because the server had already been stopped; it produced connection-refused samples and should not be used for responsiveness conclusions.
- The valid run used an already-running headless server.

Evidence files:
- Harness JSONL: `logs/smoke/WORK-20260630-runtime-facade-server-responsiveness-evidence-harness_20260630-204930.jsonl`
- Smoke server log: `logs/smoke/WORK-20260630-runtime-facade-server-responsiveness-evidence-harness_smoke-server_20260630-204822.log`
- Debug trace: `logs/debug-trace-20260630-204822.jsonl`

Valid harness summary:
- `/health`: 120 samples, 0 failures, HTTP 200 for all samples, p50 12.324 ms, p95 898.975 ms, max 976.759 ms.
- `/api/health`: 120 samples, 0 failures, HTTP 200 for all samples, p50 14.345 ms, p95 897.679 ms, max 976.826 ms.
- `/ready`: 120 samples, 0 failures, HTTP 200 for all samples, p50 16.512 ms, p95 896.786 ms, max 977.464 ms.
- `/api/ready`: 120 samples, 0 failures, HTTP 200 for all samples, p50 13.757 ms, p95 897.209 ms, max 976.381 ms.
- `/api/dm/combat`: 120 samples, 0 failures, HTTP 200 for all samples, p50 13.184 ms, p95 898.410 ms, max 977.185 ms.
- `/api/dm/combat?workspace=dmcontrol`: 120 samples, 0 failures, HTTP 200 for all samples, p50 12.698 ms, p95 890.811 ms, max 976.909 ms.

Conclusion:
- The harness itself is usable and should be committed.
- HTTP stayed alive with no request failures during the valid run.
- The shared p95/max spikes across health, readiness, and combat endpoints indicate a server responsiveness concern that should be evaluated before any route-read offload implementation.
- Next recommended work item: `WORK-20260630-runtime-facade-route-read-offload-decision`.
