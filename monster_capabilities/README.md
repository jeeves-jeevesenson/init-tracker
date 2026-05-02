# Monster Capabilities

This directory contains normalized, executable monster capabilities. These files are intended to enhance the legacy `Monsters/*.yaml` data with structured mechanics that the backend can automate.

## Directory Structure
- `samples/`: Initial prototype capability YAMLs generated from external sources (Open5e, dnd5eapi).

## Purpose
The current `Monsters/*.yaml` files are primarily display-oriented. The capability YAMLs in this directory provide a structured overlay that includes:
- Executable attack bonuses and damage formulas.
- Normalized action types (melee, ranged, composite, etc.).
- Provenance and licensing information.

## How to use
In the future, the backend will look up capabilities by monster `slug` in this directory. If a match is found, the DM UI will render these as actionable buttons.

## Backend & UI Integration
The backend now includes a `MonsterCapabilityService` that loads these YAMLs.
A new DM API is available:
- `GET /api/dm/monster-capabilities`: Lists active monsters with capability overlays.
- `GET /api/dm/monster-capabilities/{cid}`: Returns the grouped capabilities for a specific combatant.
- `POST /api/dm/monster-capabilities/{cid}/execute`: Executes a simple attack capability.

The DM UI (`/dm` or `/dm/map`) now displays a "Monster Capabilities" card in the control lane when a supported monster is selected.

## Generating Overlays
You can regenerate the capability files using the import script:
```bash
./.venv/bin/python3 scripts/import/monster_capability_import.py
```

## Inventory Audit
To see a summary of available capability overlays:
```bash
./.venv/bin/python3 scripts/audit/monster_capability_inventory.py
```

## Coverage Report
A detailed coverage report is available at `docs/reports/monster-capability-coverage.md`.

## Probing External Sources
To fetch fresh sample data from external APIs, run the probe script:
```bash
.venv/bin/python3 scripts/audit/monster_external_source_probe.py
```
A report and raw JSON samples will be saved in `docs/reports/`.
