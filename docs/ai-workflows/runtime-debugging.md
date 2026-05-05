# Runtime Debugging Workflow

This document describes the preferred workflow for debugging and performance observation of the init-tracker application using Gemini.

## Why Live Debugging?

The most effective way to debug complex WebSocket, state-machine, or performance issues in init-tracker is to observe the application in its real runtime environment. 

By having Gemini host the headless server while you connect from a real LAN browser, Gemini can correlate your visible symptoms with server-side logs and events in real-time. This produces evidence-backed diagnoses and prevents "guessing" from code alone.

## How to Start

1.  Navigate to the repository root: `cd ~/src/init-tracker`
2.  Launch Gemini in YOLO mode: `gemini --yolo`
    *   *YOLO mode is acceptable here because these workflows focus on observation, not code mutation.*
3.  Run one of the runtime-debug commands:
    *   `/init:lan-live-debug`: For short, focused reproduction of a specific bug.
    *   `/init:runtime-soak`: For longer observation of stability during normal use.
    *   `/init:perf-observe`: For identifying performance hot-paths with timing evidence.

## What to do as the User

Once the command is running:
1.  Gemini will provide a URL (usually `http://192.168.1.235:8787/`).
2.  Open this URL in your real browser (DM and/or LAN pages).
3.  Perform the actions that trigger the issue.
4.  Describe what you see in the browser to Gemini.
5.  Gemini will monitor the logs (`logs/websocket_debug.jsonl`, `logs/client_errors.log`, etc.) and server output.

## Log Files to Watch

*   `logs/websocket_debug.jsonl`: Server-side WebSocket lifecycle and error diagnostics.
*   `logs/client_errors.log`: Errors reported by the browser client.
*   `logs/lan_server.log`: General application and server logs.

## DM Webdev Debug Tool

When debugging `/dm` console issues (blank screens, JavaScript syntax errors, 400 API errors), use the `dm_webdev_debug.py` tool to capture a fact-bundle from a running server.

### Usage

1.  **Launch the server** (e.g., via `./scripts/dev/lan-live-debug.sh`).
2.  **Run the debug tool**:
    ```bash
    ./.venv/bin/python3 scripts/dev/dm_webdev_debug.py --url http://127.0.0.1:8787/dm
    ```
3.  **To get context for a specific line** (if Chrome DevTools reports an error at `dm:N`):
    ```bash
    ./.venv/bin/python3 scripts/dev/dm_webdev_debug.py --line 2531
    ```

### What it Captures

The tool saves a bundle to `logs/webdev-debug/latest/`:
- `dm.html`: The exact served HTML (useful for finding line numbers from browser errors).
- `dm_combat.json`: The state of the `/api/dm/combat` endpoint.
- `dm_monster_pilot.json`: The state of the `/api/dm/monster-pilot` endpoint.
- `summary.md`: A Markdown report summarizing auth attributes, missing functions, and API status.

## Findings and Next Steps

At the end of the session, Gemini will produce a report classifying findings as **Proven**, **Likely**, or **Unproven**. 

*   **Proven**: Directly supported by log evidence or stack traces.
*   **Likely**: Strongly correlated with observed behavior.
*   **Unproven**: Suspicions that need more instrumentation or specific reproduction.

Durable findings should be recorded in `docs/runtime-notes/live-debug-findings.md`.

## When to Fix

Do NOT ask Gemini to fix a bug during an observation pass. Once a diagnosis is reached:
1.  End the observation session.
2.  Start a new Gemini session (or use another agent) for the fix pass, using the evidence from the observation report.
3.  Verify the fix using the same live-debug workflow.
