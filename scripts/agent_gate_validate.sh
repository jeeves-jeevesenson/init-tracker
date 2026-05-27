#!/usr/bin/env bash
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

usage() {
  cat <<'USAGE'
Usage: scripts/agent_gate_validate.sh <gate-id>

Supported gate ids:
  gate1-map
  gate2-spells
  gate3-latency
  gate4-resources
  gate5-quarantine

This script validates local recovery gate work only. It does not start
production, deploy, commit, push, SSH, or restart services.
USAGE
}

if [ "${1:-}" = "" ] || [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

gate="$1"

# Prefer repo virtualenv python if it exists
PYTHON_BIN="python3"
if [ -x "./.venv/bin/python3" ]; then
  PYTHON_BIN="./.venv/bin/python3"
fi

echo "== recovery gate validation =="
echo "gate: ${gate}"
echo "repo: $(pwd)"
echo "python: $PYTHON_BIN"
echo "note: no production start, deploy, commit, push, SSH, or restart is performed"

echo
echo "== git status --short =="
git status --short

echo
echo "== git diff --check =="
git diff --check

echo
echo "== py_compile core files =="
core_files=(
  dnd_initative_tracker.py
  combat_service.py
  player_command_service.py
  player_command_contracts.py
  monster_capability_service.py
  runtime_config.py
  spell_engine_primitives.py
  map_state.py
  serve_headless.py
  scripts/trace_latency_summary.py
)
existing_core_files=()
for file in "${core_files[@]}"; do
  if [ -f "$file" ]; then
    existing_core_files+=("$file")
  fi
done
$PYTHON_BIN -m py_compile "${existing_core_files[@]}"

run_unittest() {
  local module="$1"
  echo
  echo "== unittest ${module} =="
  $PYTHON_BIN -m unittest "$module"
}

case "$gate" in
  gate1-map)
    run_unittest tests.test_dm_tactical_map_routes
    echo
    echo "Smoke required by recovery doc: move monster in /dmcontrol; verify grid tokens in /dm/map."
    ;;
  gate2-spells)
    run_unittest tests.test_lan_spellbook_contract_ui
    run_unittest tests.test_lan_snapshot_cache
    echo
    echo "Smoke required by recovery doc: add spell in Manage Spells; verify it persists after HP damage update."
    ;;
  gate3-latency)
    run_unittest tests.test_trace_latency_summary
    echo
    echo "Trace evidence required by recovery doc: scripts/trace_latency_summary.py shows zero static_plus_dynamic builds in the hot path."
    echo "Smoke required by recovery doc: rapid Move -> Attack -> End Turn."
    ;;
  gate4-resources)
    run_unittest tests.test_resource_pool_accounting
    run_unittest tests.test_pact_magic_spell_slots
    echo
    echo "Smoke required by recovery doc: perform Long Rest; verify HP, slots, and pools reset."
    ;;
  gate5-quarantine)
    run_unittest tests.test_lan_snapshot_static
    echo
    echo "Pass criterion from recovery doc: zero _dm_tactical_snapshot calls when flags are false."
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac

echo
echo "== changed browser assets requiring inline JS syntax check =="
changed_browser_assets=()
while IFS= read -r path; do
  case "$path" in
    assets/web/dm/index.html|assets/web/lan/index.html|assets/web/dmcontrol/index.html)
      if [ -f "$path" ]; then
        changed_browser_assets+=("$path")
      fi
      ;;
  esac
done < <(
  {
    git diff --name-only
    git diff --cached --name-only
    git ls-files --others --exclude-standard
  } | sort -u
)

if [ "${#changed_browser_assets[@]}" -eq 0 ]; then
  echo "No changed browser HTML assets among dm, lan, dmcontrol."
else
  printf '%s\n' "${changed_browser_assets[@]}"
  echo
  echo "== inline JS syntax check via node --check =="
  $PYTHON_BIN - "${changed_browser_assets[@]}" <<'PY'
from html.parser import HTMLParser
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile


class ScriptExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_script = False
        self.scripts = []
        self._buf = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "script":
            return
        attrs = dict(attrs)
        if attrs.get("src"):
            return
        self.in_script = True
        self._buf = []

    def handle_endtag(self, tag):
        if tag.lower() == "script" and self.in_script:
            self.in_script = False
            self.scripts.append("".join(self._buf))
            self._buf = []

    def handle_data(self, data):
        if self.in_script:
            self._buf.append(data)


node = shutil.which("node")
if not node:
    print("ERROR: node is not available; cannot run browser JS syntax check.", file=sys.stderr)
    sys.exit(1)

for raw_path in sys.argv[1:]:
    path = Path(raw_path)
    parser = ScriptExtractor()
    parser.feed(path.read_text(encoding="utf-8"))
    combined = "\n;\n".join(parser.scripts)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile("w", suffix=f".{path.stem}.js", delete=False, encoding="utf-8") as tmp:
            tmp.write(combined)
            tmp_path = tmp.name
        result = subprocess.run([node, "--check", tmp_path], text=True, capture_output=True)
        if result.returncode != 0:
            print(f"JS syntax check failed for {path}", file=sys.stderr)
            if result.stdout:
                print(result.stdout, file=sys.stderr)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            sys.exit(result.returncode)
        print(f"JS syntax check passed for {path}")
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
PY
fi

echo
echo "== validation complete =="
echo "gate: ${gate}"
