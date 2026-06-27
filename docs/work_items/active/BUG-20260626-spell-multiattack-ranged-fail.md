# BUG-20260626-spell-multiattack-ranged-fail

## Status

- **Status:** Active
- **Type:** Bug evidence capture / classification
- **Severity:** S1
- **Source:** Developer report from 2026-06-26
- **Opened:** 2026-06-26

## Summary

Spell Multiattack and ranged attack failure.

## Known Symptoms

- Spell Multiattack has failing behavior.
- Ranged attack flow has failing behavior in this area.

## Unknowns To Preserve

- Exact reproduction steps are not yet captured in repo evidence.
- Whether the ranged failure is specific to spell Multiattack, normal ranged attacks, ammo weapons, targeting, preview/apply, spell targeting, action economy, preview/cancel, or apply flow is unknown.

## First Implementation Gate

Capture or confirm a narrow repro before code changes unless existing active docs already contain enough repo evidence.

## Scope & Non-Goals

- Do not reopen `BUG-20260614-weapon-attacks-reload-fail` unless new evidence proves regression.
- Do not start dedicated Multiattack modal UI work.
- Do not perform opportunistic combat cleanup.

## Next Allowed Action

Capture current repro evidence for the spell Multiattack / ranged attack failure and classify the smallest implementation scope before editing app code.
