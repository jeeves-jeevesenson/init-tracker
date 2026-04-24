# Scripts

This directory contains the supported checkout installer, launch helpers, build utilities, data/migration tools, audits, and validation scripts.

## Current Checkout Installer

### `quick-install.sh`
Fresh-checkout installer for the current repository:
- Locates the repository root from the script path
- Discovers a usable Python interpreter, or uses `PYTHON=/path/to/python`
- Verifies Python 3.9+ and `venv` support
- Creates or reuses a local `.venv`
- Upgrades pip inside the venv
- Installs `requirements.txt`
- Prints exact desktop and headless launch commands

Usage:
```bash
bash scripts/quick-install.sh
bash scripts/quick-install.sh --dry-run
PYTHON=/opt/python3.12/bin/python3 bash scripts/quick-install.sh
```

## Launchers

### `launch-windows.bat`
Quick launcher for running the tracker directly from a Windows checkout without installation.

Usage:
```cmd
scripts\launch-windows.bat
```

### `launchers/launcher.py`
Python launcher wrapper used by the optional PyInstaller build helper.

Usage:
```bash
python scripts/launchers/launcher.py
```

## Validation

### `validation/check-lan-script.mjs`
Extracts inline `<script>` blocks from `assets/web/lan/index.html` and validates their syntax with Node's `--check` flag. CI runs this workflow.

Usage:
```bash
node scripts/validation/check-lan-script.mjs
```

### `validation/lan-smoke-playwright.py`
Launches a local HTTP server, opens `/lan` in Playwright, and runs deterministic LAN spell-manager smoke coverage.

Usage:
```bash
python -m playwright install --with-deps chromium
python scripts/validation/lan-smoke-playwright.py
```

## Build

### `build/create_icon.py`
Creates `assets/icon.ico` from PNG images in `assets/`.

Usage:
```bash
python scripts/build/create_icon.py
```

### `build/build_exe.py`
Builds a standalone Windows `.exe` launcher from `scripts/launchers/launcher.py` using PyInstaller and the generated icon.

Usage:
```bash
python scripts/build/build_exe.py
```

## Migration / Data Utilities

These scripts can write repository data. Review options and use dry-run modes where available before running them.

### `migration/aidedd_image_archive.py`
Downloads monster images from AideDD by slug or XML list.

### `migration/backfill_monster_sections.py`
Backfills monster section text from AideDD 2024 with 5eTools JSON fallback.

### `migration/build_shop_catalog.py`
Builds or refreshes the shop catalog from item definition directories.

Usage:
```bash
python scripts/migration/build_shop_catalog.py
```

### `migration/import_srd_items.py`
Bulk-imports open SRD item data into local YAML item definitions.

Usage:
```bash
python scripts/migration/import_srd_items.py
```

### `migration/import_tiled_ship_blueprints.py`
Imports Tiled-authored ship JSON into normalized composite ship blueprints.

Usage:
```bash
python scripts/migration/import_tiled_ship_blueprints.py
```

## Audit

### `audit/spell_automation_audit.py`
Generates a spell automation audit report for level 0-6 spells.

Usage:
```bash
python scripts/audit/spell_automation_audit.py
```

## Notes

- `quick-install.sh` is the supported installer and intentionally remains at `scripts/quick-install.sh`.
- Legacy install/update/uninstall scripts were retired.
- `launch-windows.bat` remains top-level because it is a direct launcher, not an installer or validation utility.
