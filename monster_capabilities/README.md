# Monster Capabilities

This directory contains normalized, executable monster capabilities. These files are intended to enhance the legacy `Monsters/*.yaml` data with structured mechanics that the backend can automate.

## Directory Structure
- `samples/`: Initial prototype capability YAMLs generated from external sources (Open5e, dnd5eapi).

## Purpose
The current `Monsters/*.yaml` files are primarily display-oriented. The capability YAMLs in this directory provide a structured overlay that includes:
- Executable attack bonuses and damage formulas.
- Structured save/area metadata where the source text is clear.
- Condition rider metadata for common riders.
- Normalized action types (melee, ranged, composite, etc.).
- Sparse importer warnings for conditional/manual fallbacks.
- Provenance and licensing information.

## How to use
In the future, the backend will look up capabilities by monster `slug` in this directory. If a match is found, the DM UI will render these as actionable buttons.

## Backend & UI Integration
The backend now includes a `MonsterCapabilityService` that loads these YAMLs.
A new DM API is available:
- `GET /api/dm/monster-capabilities`: Lists active monsters with capability overlays.
- `GET /api/dm/monster-capabilities/{cid}`: Returns the grouped capabilities for a specific combatant.
- `POST /api/dm/monster-capabilities/{cid}/execute`: Executes a simple attack or save capability. For composite (Multiattack) actions, returns an assisted sequence summary.
- `POST /api/dm/monster-capabilities/{cid}/resolve-targets`: Resolves a save/area capability against DM-selected target rows with explicit per-target outcomes.
- `POST /api/dm/monster-capabilities/{cid}/apply-effect`: Applies a condition rider (e.g. Prone, Grappled) to a target.
- `POST /api/dm/monster-capabilities/{cid}/remove-effect`: Removes a condition rider from a target.

The DM UI (`/dm` or `/dm/map`) now displays a "Monster Capabilities" card in the control lane when a supported monster is selected. Composite/Multiattack actions render as a sequence of executable child buttons for assisted sequential resolution. Save/area capabilities such as dragon breath, Frightful Presence, and Wing Attack support manual multi-target selection with per-target fail/success/no-effect/manual outcomes. This is deliberately DM-selected, not map-template or geometry-based auto-targeting. Condition riders (like Prone or Frightened) are displayed as chips with explicit Apply/Remove buttons for DM-controlled assistance.

Limited-use resources (Recharge, Daily Uses, Spell Slots) are tracked in-memory during the session. The DM can manually spend, roll, or restore these resources directly from the capability card.

## Generating Overlays
You can regenerate the capability files using the import script:
```bash
./.venv/bin/python3 scripts/importers/monster_capability_import.py
```

## Inventory Audit
To see a summary of available capability overlays:
```bash
./.venv/bin/python3 scripts/audit/monster_capability_inventory.py
```
The audit reports executable, save, area, resource, composite, rider, spellcasting, and warning counts so data-quality regressions are easier to spot after regeneration.

## Coverage Report
A detailed coverage report is available at `docs/reports/monster-capability-coverage.md`.

## Probing External Sources
To fetch fresh sample data from external APIs, run the probe script:
```bash
.venv/bin/python3 scripts/audit/monster_external_source_probe.py
```
A report and raw JSON samples will be saved in `docs/reports/`.
