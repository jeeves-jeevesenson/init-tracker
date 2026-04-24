#!/usr/bin/env bash
set -euo pipefail

MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=9

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
VENV_DIR="${VENV_DIR:-${REPO_ROOT}/.venv}"
DRY_RUN=0

log() {
  printf '[install] %s\n' "$*"
}

die() {
  printf '[install] ERROR: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat <<EOF
Usage: bash scripts/quick-install.sh [--dry-run] [--venv PATH]

Set up this repository from a fresh checkout.

Options:
  --dry-run       Verify paths and Python discovery without creating a venv.
  --venv PATH     Create or reuse PATH instead of .venv.
  -h, --help      Show this help.

Environment:
  PYTHON          Explicit Python interpreter path to use.
  VENV_DIR        Virtual environment path, overridden by --venv.

Examples:
  bash scripts/quick-install.sh
  PYTHON=/opt/python3.12/bin/python3 bash scripts/quick-install.sh
  bash scripts/quick-install.sh --venv .venv
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --venv)
      [[ $# -ge 2 ]] || die "--venv requires a path."
      VENV_DIR="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown option: $1. Run with --help for usage."
      ;;
  esac
done

if [[ "${VENV_DIR}" != /* ]]; then
  VENV_DIR="${REPO_ROOT}/${VENV_DIR}"
fi

REQUIREMENTS_FILE="${REPO_ROOT}/requirements.txt"
DESKTOP_ENTRY="${REPO_ROOT}/dnd_initative_tracker.py"
HEADLESS_ENTRY="${REPO_ROOT}/serve_headless.py"

[[ -f "${REQUIREMENTS_FILE}" ]] || die "requirements.txt was not found at ${REQUIREMENTS_FILE}. Run this script from a complete checkout."
[[ -f "${DESKTOP_ENTRY}" ]] || die "Desktop entrypoint was not found at ${DESKTOP_ENTRY}."
[[ -f "${HEADLESS_ENTRY}" ]] || die "Headless entrypoint was not found at ${HEADLESS_ENTRY}."

python_version_check='
import sys
major, minor = sys.version_info[:2]
required = (3, 9)
if (major, minor) < required:
    raise SystemExit(1)
print(f"{major}.{minor}.{sys.version_info.micro}")
'

venv_check='
try:
    import venv  # noqa: F401
except Exception as exc:
    raise SystemExit(f"venv module is unavailable: {exc}")
'

SELECTED_PYTHON=()
SELECTED_VERSION=""

try_python() {
  local -a candidate=("$@")
  local version
  if ! command -v "${candidate[0]}" >/dev/null 2>&1; then
    return 1
  fi
  if ! version="$("${candidate[@]}" -c "${python_version_check}" 2>/dev/null)"; then
    return 1
  fi
  if ! "${candidate[@]}" -c "${venv_check}" >/dev/null 2>&1; then
    die "Python ${version} at $(command -v "${candidate[0]}") does not provide the venv module. Install the venv package for this Python and rerun."
  fi
  SELECTED_PYTHON=("${candidate[@]}")
  SELECTED_VERSION="${version}"
  return 0
}

discover_python() {
  if [[ -n "${PYTHON:-}" ]]; then
    [[ -x "${PYTHON}" || -n "$(command -v "${PYTHON}" 2>/dev/null || true)" ]] || die "PYTHON is set to '${PYTHON}', but it is not executable or on PATH."
    if try_python "${PYTHON}"; then
      return 0
    fi
    die "PYTHON='${PYTHON}' is not Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+ or cannot run venv."
  fi

  local candidate
  for candidate in python3.13 python3.12 python3.11 python3.10 python3.9 python3 python; do
    if try_python "${candidate}"; then
      return 0
    fi
  done

  if try_python py -3; then
    return 0
  fi

  die "No usable Python interpreter found. Install Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+ or rerun with PYTHON=/path/to/python."
}

venv_python_path() {
  if [[ -x "${VENV_DIR}/bin/python" ]]; then
    printf '%s\n' "${VENV_DIR}/bin/python"
    return 0
  fi
  if [[ -x "${VENV_DIR}/Scripts/python.exe" ]]; then
    printf '%s\n' "${VENV_DIR}/Scripts/python.exe"
    return 0
  fi
  return 1
}

planned_venv_python_path() {
  local os_name
  if venv_python_path; then
    return 0
  fi
  os_name="$(uname -s 2>/dev/null || true)"
  case "${os_name}" in
    MINGW*|MSYS*|CYGWIN*)
      printf '%s\n' "${VENV_DIR}/Scripts/python.exe"
      ;;
    *)
      printf '%s\n' "${VENV_DIR}/bin/python"
      ;;
  esac
}

print_next_commands() {
  local venv_python="$1"
  local activate_cmd
  if [[ -f "${VENV_DIR}/bin/activate" ]]; then
    activate_cmd="source ${VENV_DIR}/bin/activate"
  elif [[ -f "${VENV_DIR}/Scripts/activate" ]]; then
    activate_cmd="source ${VENV_DIR}/Scripts/activate"
  else
    activate_cmd="<activate script not found>"
  fi

  log "Next commands:"
  printf '  cd %q\n' "${REPO_ROOT}"
  printf '  %s\n' "${activate_cmd}"
  printf '  %q %q\n' "${venv_python}" "${DESKTOP_ENTRY}"
  printf '  %q %q --host 0.0.0.0 --port 8787\n' "${venv_python}" "${HEADLESS_ENTRY}"
}

log "Repository root: ${REPO_ROOT}"
log "Virtual environment: ${VENV_DIR}"
discover_python
log "Using Python ${SELECTED_VERSION}: ${SELECTED_PYTHON[*]}"

if [[ "${DRY_RUN}" == "1" ]]; then
  log "Dry run complete. requirements.txt and entrypoints were found."
  print_next_commands "$(planned_venv_python_path)"
  exit 0
fi

if [[ ! -d "${VENV_DIR}" ]]; then
  log "Creating virtual environment."
  "${SELECTED_PYTHON[@]}" -m venv "${VENV_DIR}"
else
  log "Reusing existing virtual environment."
  if ! venv_python_path >/dev/null; then
    log "Existing venv has no Python executable; refreshing it in place."
    "${SELECTED_PYTHON[@]}" -m venv "${VENV_DIR}"
  fi
fi

VENV_PYTHON="$(venv_python_path)" || die "Virtual environment was created, but no Python executable was found in ${VENV_DIR}."

log "Upgrading pip."
"${VENV_PYTHON}" -m pip install --upgrade pip

log "Installing requirements from ${REQUIREMENTS_FILE}."
"${VENV_PYTHON}" -m pip install -r "${REQUIREMENTS_FILE}"

log "Installation complete."
print_next_commands "${VENV_PYTHON}"
