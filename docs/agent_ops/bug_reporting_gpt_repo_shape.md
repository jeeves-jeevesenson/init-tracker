# init-tracker: Bug Reporting Tool Knowledge (Evergreen Repo Shape)

## A. Purpose and Warning
This document provides **stable app and repo-shape guidance** for the `init-tracker` Bug Reporting Tool. It describes how the application is structured and where evidence is typically found.

- **Warning**: This is NOT current repo state.
- **Current State**: Must always come from running `scripts/chatgpt_context_refresher.sh` or inspecting the latest logs.
- **No Guessing**: Do not guess the current commit, dirty state, hostnames, ports, production topology, or root cause. If information is missing, ask the developer to run the relevant evidence command.

## B. Application Overview
`init-tracker` is a D&D combat and session tracker migrating from a Tkinter desktop host toward a **headless/browser-first** backend-owned system.

### Major Surfaces
- `/dm`: The DM Cockpit. Roster visibility, encounter management, and status tracking.
- `/dm/map`: The DM Tactical Map. Grid rendering and token placement.
- `/dmcontrol`: The DM Control surface. High-resolution monster ability dashboard and tactical interaction.
- **LAN Player Page** (`/`): The player-facing surface for spells, actions, and character state.
- **Backend / Headless Server**: The Python process (`serve_headless.py`) that owns the combat authority and state.
- **Production Deployment**: A headless Linux environment running the tracker as a service.

## C. Common Bug Areas
- **Map / DM Control**: Grid rendering, token movement, coordinate mismatches, or interaction latency.
- **LAN Player Actions**: Button clicks, turn-passing, or character selection failures.
- **Spells and Manage Spells**: Spell visibility, search/filter failures, or "Manage Spells" synchronization issues.
- **Resources / Rest / Pact Slots**: Inaccurate HP/slot counts after casts or rests; Long Rest failures.
- **Inventory / Equipment**: Weapon equip state not reflecting in attack dropdowns.
- **Attacks / Damage / Auras**: Incorrect damage application, aura radius mismatches, or resolution failures.
- **Latency / Responsiveness**: Delays between action and UI update; "double-click" race conditions.
- **Deployment / Production**: Startup failures, networking/WS disconnects, or environment-specific crashes.
- **Experimental Systems**: Ship surfaces, boarding logic, and structural objects (often quarantined).

## D. Important Repo Paths
- `dnd_initative_tracker.py`: Main backend authority and monolithic state owner.
- `combat_service.py`: High-level combat mechanics (Rests, Attacks, Damage).
- `player_command_service.py`: Logic for executing player-driven actions.
- `player_command_contracts.py`: JSON schemas and allowlists for player actions.
- `runtime_config.py`: Application flags and performance settings.
- `map_state.py`: Tactical grid and token coordinate management.
- `assets/web/dm/index.html`: Source for the DM Cockpit.
- `assets/web/dmcontrol/index.html`: Source for the DM Control surface.
- `assets/web/lan/index.html`: Source for the LAN Player page.
- `tests/`: Project test suite.
- `scripts/`: Operational and diagnostic scripts.
- `docs/agent_ops/`: Instructions and workflows for project agents.
- `docs/runtime_reports/`: Logs of manual smoke tests and latency traces.
- `docs/bug_reports/`: Storage for official bug reports.
- `logs/`: Directory for console logs and debug traces.

## E. Log and Evidence Command Catalog
Run these from the repo root to gather evidence for a bug report.

### Basic Context
```bash
scripts/chatgpt_context_refresher.sh
cat /tmp/init-tracker-context-refresher.txt
git status --short
git log --oneline -5
```

### List Logs
```bash
ls -lt logs | head -40
ls -t logs/debug-trace-*.jsonl 2>/dev/null | head -5
ls -t logs/live-debug-console*.log 2>/dev/null | head -5
```

### Tail Recent Console Log
```bash
LOG="$(ls -t logs/live-debug-console*.log 2>/dev/null | head -1)"; echo "$LOG"; tail -200 "$LOG"
```

### Trace Summary
```bash
TRACE="$(ls -t logs/debug-trace-*.jsonl 2>/dev/null | head -1)"; echo "$TRACE"; ./.venv/bin/python3 scripts/trace_latency_summary.py "$TRACE"
```

### Fallback Trace Summary (If venv path issues occur)
```bash
TRACE="$(ls -t logs/debug-trace-*.jsonl 2>/dev/null | head -1)"; echo "$TRACE"; PYTHONPATH="$PWD/.venv/lib/python3.13/site-packages:${PYTHONPATH:-}" python3 scripts/trace_latency_summary.py "$TRACE"
```

### Search Logs for a Term
```bash
grep -Rni "TERM_HERE" logs docs/runtime_reports 2>/dev/null | tail -80
```

### Browser Evidence
- **Console Errors**: Ask the developer to copy and paste text from the browser console (F12).
- **Screenshots**: Request only when visual state (alignment, rendering) is the primary issue.
- **URLs**: Ask for the exact surface URL being used (e.g., `http://localhost:8000/dmcontrol`).

## F. Evidence Checklist by Bug Type

### For Map Bugs
- **Surface**: Was `/dm`, `/dm/map`, or `/dmcontrol` being used?
- **Visibility**: Is the page loading? Is the grid visible? Are tokens visible?
- **Interaction**: Does dragging a token work?
- **Browser**: Are there console errors?
- **Backend**: Latest console log and debug trace summary.
- **Scope**: Does it happen locally, on production, or both?

### For Spell / Capability Bugs
- **Character**: Name of the character involved.
- **Spell**: Name of the spell.
- **Surface**: LAN, DM, or Manage Spells?
- **Behavior**: Expected vs. Actual visibility or cast result.
- **Impact**: Did resource pools or slots update correctly?
- **Logs**: Relevant console logs/traces during the cast.

### For Latency Bugs
- **Action**: What specific action was performed (e.g., "Next Turn")?
- **Actor**: Which character/monster was active?
- **Delay**: Approximate delay felt by the user.
- **Repeatability**: Did multiple clicks make it worse?
- **Evidence**: `scripts/trace_latency_summary.py` output for the relevant session.

### For Inventory / Weapon Bugs
- **Character**: Name of the character.
- **Item**: Name of the weapon or equipment.
- **State**: Was it equipped at the time of the bug?
- **Behavior**: Expected vs. Actual attack options.
- **Logs**: Backend logs showing weapon resolution logic.

### For Resource / Rest / Pact Bugs
- **Resource**: HP, Spell Slots, or named Resource Pool?
- **Values**: What were the "Before" and "After" values?
- **Trigger**: Was it a Short Rest, Long Rest, or a specific action?
- **Behavior**: What was expected vs. what actually occurred?

### For Deployment Bugs
- **Recon**: Require current context refresher and `git status`.
- **Environment**: Are we on the production server or local?
- **Constraint**: Do not guess service names or FQDNs.

## G. Bug Report Format and Storage
- **Path**: `docs/bug_reports/inbox/BUG-YYYYMMDD-short-slug.md`
- **Triage**: Move to `triaged/` when verified, `resolved/` when fixed.
- **Granularity**: One bug per report.
- **Severity (S0-S3)**: S0 (Blocker) to S3 (Minor/Cosmetic).
- **Priority (P0-P3)**: P0 (Urgent) to P3 (Low).
- **Note**: Suspected hypotheses are NOT root causes.

## H. Orchestrator Handoff Format
Always end the bug report generation with this paste-ready message for the developer:

"I have a new official bug report saved at: `<path>`. Please read it, ask for a current context refresher if needed, classify it against the active recovery gate, and decide whether this needs evidence capture, a Gemini task, a Codex task, or a smoke test."
