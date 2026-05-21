# Spell Engine Latency Debugging Runbook

Date: 2026-05-21 12:13 America/Chicago

## Purpose

Pass 8A adds opt-in live latency diagnostics only. Use this runbook to capture
one representative combat session before attempting performance changes.

The trace is structured JSONL. It records action types, timing spans, counts,
payload sizes when cheap, HTTP paths, query keys, websocket IDs, player/cid
correlation, action IDs, spell IDs/names where the backend already has them,
and rejection/failure reasons. It does not intentionally record secrets, full
HTTP request bodies, or full websocket payload bodies.

## Start The Server

From the repository root:

```bash
./.venv/bin/python3 serve_headless.py --host 0.0.0.0 --port 8787 --debugging true
```

The startup output prints the debug trace path. The path format is:

```text
logs/debug-trace-YYYYMMDD-HHMMSS.jsonl
```

Equivalent opt-in forms:

```bash
./.venv/bin/python3 serve_headless.py --host 0.0.0.0 --port 8787 --debugging
INIT_TRACKER_DEBUGGING=1 ./.venv/bin/python3 serve_headless.py --host 0.0.0.0 --port 8787
```

Debugging is off unless the CLI flag or environment variable enables it.

## Live Test Sequence

Capture normal table behavior first. Do not pause after every click unless the
UI visibly hangs.

1. Load the normal session and connect at least one LAN player plus the DM
   control surface.
2. Start or continue combat and advance through one full round.
3. Run player `attack` and damage flows, including one save-based spell if the
   session has one ready.
4. Run `cast_spell`, AoE placement/confirmation through `cast_aoe`, and one
   AoE that resolves targets.
5. Run one summon path if a summoning spell or summon control is available.
6. Exercise `Shield` and `Hellish Rebuke` reaction offer/response/resolve paths
   if the prepared characters support them.
7. Exercise `manual_override`, `reset_turn`, `end_turn`, and DM `long_rest`
   only if those actions fit the test session.
8. Note wall-clock timestamps and the visible symptom for any action that
   feels hung, delayed, or unexpectedly late to repaint.

## Quick Inspection

Set the path printed at startup:

```bash
TRACE=logs/debug-trace-YYYYMMDD-HHMMSS.jsonl
```

Find threshold hits:

```bash
grep -E '"event":"(slow.span|very_slow.span|hang_candidate.span)"' "$TRACE"
```

Inspect websocket dispatches and broadcasts:

```bash
grep -E '"event":"ws.action.dispatch.(start|end)"|"event":"broadcast.(start|end)"' "$TRACE"
```

Inspect spell and reaction spans:

```bash
grep -Ei '"span":"[^"]*(cast|spell|reaction|shield|rebuke|summon)' "$TRACE"
```

Inspect YAML/cache and snapshot work:

```bash
grep -Ei '"span":"[^"]*(yaml|cache|snapshot)' "$TRACE"
```

## Analyze The Trace

The analyzer tolerates partial JSONL if the server is still running or crashed
while writing a line.

```bash
python3 scripts/analyze_debug_trace.py "$TRACE"
```

The report includes session duration, action counts, slow spans and actions,
route summaries, websocket action summaries, broadcast summaries, snapshot
summaries, spell/reaction summaries, YAML/cache summaries, repeated expensive
spans, and suspected bottlenecks.

## Threshold Interpretation

- `slow.span` means a completed instrumented span exceeded 100 ms. Repeated
  occurrences on snapshots or broadcasts are a live-play warning even if one
  click still completes.
- `very_slow.span` means a completed span exceeded 500 ms. Correlate its
  `action_id`, `trace_id`, counts, and neighboring broadcast events with the
  tester symptom.
- `hang_candidate.span` means a completed span exceeded 2000 ms. Treat this as
  a primary investigation target unless the span is an intentionally slow
  operator action outside combat.

For a delayed click, follow one `action_id` from:

1. `ws.message.received` or `http.request.start`
2. dispatch span start/end
3. spell/reaction/combat mutation spans
4. snapshot build spans
5. broadcast start/end and failed sends
6. result payload send or HTTP request end

## Return Artifacts

After the live test, provide:

- the debug trace JSONL file
- the analyzer output
- server stdout/stderr around the tested session if it includes an exception
- the tested session action notes with approximate wall-clock times
- the exact server launch command used

Do not upload `.env` files, admin tokens, browser storage dumps, full session
exports, or unrelated player YAML unless a later investigation explicitly
needs them.
