# Repo Shape: init-tracker Planning Tool Knowledge

This document provides a high-level overview of the repository's structure and domains to assist the **Planning Tool** in its research.

## Application Overview

`init-tracker` is a D&D initiative tracker and combat engine migrating from a Tkinter desktop app to a headless, browser-first system.

- **Primary Language**: Python 3.10+
- **Frontend**: Vanilla HTML/JS/CSS (Browser-based DM and LAN surfaces)
- **Web Framework**: Custom implementation using `http.server` and WebSockets in `dnd_initative_tracker.py`.
- **Runtime Host**: `serve_headless.py`

## Core Surfaces

1. **DM Dashboard** (`/dm`): The primary operator surface for the Dungeon Master.
2. **DM Control** (`/dmcontrol`): Mobile-friendly, high-latency-safe control surface for monsters and encounter management.
3. **LAN Player** (`/lan`): Player-facing view for combat tracking, character management, and spellcasting.
4. **Tactical Map** (`/dm/map`): Tactical grid for movement and AoE resolution.

## Common Planning Domains

- **Spell Engine**: `spell_engine_primitives.py`, `Spells/` directory, and the `SpellCastResult` contract.
- **Combat Logic**: `combat_service.py`, `combatant_name_service.py`, and the monolithic `dnd_initative_tracker.py`.
- **Player Commands**: `player_command_contracts.py`, `player_command_service.py`.
- **Monster Capabilities**: `monster_capability_service.py`, `monster_capabilities/` directory.
- **Data Schemas**: YAML-based data for Monsters, Spells, Items, and Players.

## Repo Path Map

- `docs/`: Documentation and living plans.
- `tests/`: Extensive unit and integration tests.
- `assets/web/`: Frontend source code.
- `scripts/`: Maintenance, validation, and developer tools.

## Key Planning Concepts

### Official vs. Community vs. Inference
- **Official**: Rules directly from D&D 2014 or 2024 SRD/PHB.
- **Community**: Common house rules or VTT-standard implementations (e.g., how to handle "the help action").
- **Inference**: Logic the Planning Tool derives from existing code patterns in the repo. **Inference MUST be confirmed by code evidence.**

### D&D 2014 vs. 2024
The project is currently in a transition phase. Some features follow 2014 rules, others are moving toward 2024. Always check `majorTODO.md` and `GEMINI.md` for the current transition status before recommending a rules-based change.

### Experimental Quarantine
New features or major migrations are often "quarantined" behind environment flags (e.g., `INIT_TRACKER_ENABLE_TACTICAL_MAP`). Research passes should identify if a new feature belongs in quarantine first.
