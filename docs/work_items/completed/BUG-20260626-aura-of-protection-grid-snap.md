# BUG-20260626-aura-of-protection-grid-snap: Aura of Protection grid snap offset

## Status

Completed on 2026-06-26.

## Classification

Visual-only rendering bug.

Gameplay aura evaluation remains logically correct. The backend aura context/effect logic evaluates token positions consistently using integer grid coordinates. The bug was limited to active-aura serialization for map rendering.

## Root Cause

The active aura serialization in `dnd_initative_tracker.py` sent aura circle center coordinates as raw integer token cell coordinates.

The client renders token portraits centered in their cells, but rendered the aura circle at the serialized `cx` / `cy` values. That placed the Aura of Protection circle on a grid intersection instead of Dorian's token center.

## Fix

`dnd_initative_tracker.py` now serializes active aura render centers with a half-cell offset:

- `cx = source_col + 0.5`
- `cy = source_row + 0.5`

This centers the visual aura circle on Dorian's token portrait without changing gameplay calculation logic.

## Files Changed

- `dnd_initative_tracker.py`

## Validation

- `python3 -m py_compile dnd_initative_tracker.py` — passed.
- `python3 -m unittest tests/test_lan_auras_toggle.py` — passed.
- `timeout 10s git diff --check` — passed.
- Developer browser smoke — passed.

## Smoke Evidence

- Smoke log: `logs/smoke/BUG-20260626-aura-grid-snap_smoke-server_20260626-102316.log`
- Debug trace: `logs/debug-trace-20260626-102316.jsonl`

## Source

- Original bug report: `docs/bug_reports/triaged/BUG-20260626-aura-of-protection-grid-snap.md`
