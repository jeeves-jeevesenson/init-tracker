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

## Generating Samples
You can regenerate the sample files using the import script:
```bash
.venv/bin/python3 scripts/import/monster_capability_import.py
```

## Auditing Legacy Data
To see the current state of the legacy monster library, run the audit script:
```bash
.venv/bin/python3 scripts/audit/monster_capability_audit.py
```
A report will be generated at `docs/reports/monster-capability-audit.md`.

## Probing External Sources
To fetch fresh sample data from external APIs, run the probe script:
```bash
.venv/bin/python3 scripts/audit/monster_external_source_probe.py
```
A report and raw JSON samples will be saved in `docs/reports/`.
