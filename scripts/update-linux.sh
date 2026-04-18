#!/bin/bash
# Update script for D&D Initiative Tracker (Linux/macOS)
# This script updates the application to the latest version from GitHub

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$(dirname "$SCRIPT_DIR")"
APPDIR="${APPDIR:-$HOME/.local/share/dnd-initiative-tracker}"
DESKTOP_FILE="$HOME/.local/share/applications/inittracker.desktop"
WRAPPER="${APPDIR}/launch-inittracker.sh"
ICON_NAME="inittracker"
TEMP_DIR="/tmp/dnd-tracker-update-$$"
YAML_DIRS=("players")
YAML_BACKUP_DIR="$TEMP_DIR/yaml_backup"
LOG_DIR="$INSTALL_DIR/logs"
LOG_FILE="$LOG_DIR/update.log"
EXPECTED_REPO_SLUG="jeeves-jeevesenson/init-tracker"

normalize_repo_slug() {
    local remote_url="${1:-}"
    if [ -z "$remote_url" ]; then
        return 1
    fi
    # Normalize common GitHub remote forms to owner/repo:
    # - strip protocol
    # - strip optional git@ prefix
    # - strip github.com host + separators
    # - strip optional .git suffix
    local normalized
    normalized="$(printf '%s' "$remote_url" | sed -E 's#^[^:]+://##; s#^git@##; s#github.com[:/]##; s#\.git$##')"
    normalized="${normalized#/}"
    printf '%s' "$normalized" | tr '[:upper:]' '[:lower:]'
}

mkdir -p "$LOG_DIR"
{
    echo "=========================================="
    echo "Update started: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo "=========================================="
} >> "$LOG_FILE"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=========================================="
echo "D&D Initiative Tracker - Update"
echo "=========================================="
echo ""

# Function to cleanup temp files
cleanup() {
    local exit_code=$?
    if [ -d "$TEMP_DIR" ]; then
        echo "Cleaning up temporary files..."
        rm -rf "$TEMP_DIR"
        echo "✓ Cleanup complete"
    fi
    if [ "$exit_code" -eq 0 ]; then
        echo "✓ Update finished successfully."
    else
        echo "✗ Update failed with exit code $exit_code."
    fi
}

# Register cleanup on exit
trap cleanup EXIT

# Check if we're in the right directory
if [ ! -f "$INSTALL_DIR/dnd_initative_tracker.py" ]; then
    echo "Error: Could not find D&D Initiative Tracker installation"
    echo "Expected location: $INSTALL_DIR"
    exit 1
fi

echo "Installation directory: $INSTALL_DIR"
echo ""

# Check if git is available
if ! command -v git &> /dev/null; then
    echo "Error: git is not installed. Please install git first."
    exit 1
fi

# Check if this is a git repository
if [ ! -d "$INSTALL_DIR/.git" ]; then
    echo "Error: This installation was not installed via git."
    echo "Please re-install using the quick-install script to enable updates."
    exit 1
fi

echo "Checking for updates..."
cd "$INSTALL_DIR"

# Fetch latest changes from the supported repo only
if ! git remote get-url origin >/dev/null 2>&1; then
    echo "Error: No 'origin' remote found."
    exit 1
fi

ORIGIN_URL="$(git remote get-url origin 2>/dev/null || true)"
ORIGIN_SLUG="$(normalize_repo_slug "$ORIGIN_URL" || true)"
if [ -z "$ORIGIN_SLUG" ] || [ "$ORIGIN_SLUG" != "$EXPECTED_REPO_SLUG" ]; then
    echo "Error: This install is not connected to the supported update repository."
    echo "  Found origin: ${ORIGIN_URL:-<missing>}"
    echo "  Expected: https://github.com/${EXPECTED_REPO_SLUG}.git"
    echo "Refusing to run automatic update to avoid pulling the wrong project."
    echo "Use a manual/source update flow for this checkout."
    exit 1
fi

git fetch origin --prune --tags

# Check if there are updates
LOCAL_COMMIT=$(git rev-parse HEAD)
REMOTE_BRANCH="origin/main"
if ! git rev-parse --verify "${REMOTE_BRANCH}" >/dev/null 2>&1; then
    echo "Error: Could not resolve update branch ${REMOTE_BRANCH}."
    echo "Run 'git fetch origin --prune --tags' and verify origin/main exists."
    exit 1
fi
REMOTE_COMMIT=$(git rev-parse "$REMOTE_BRANCH")

if [ "$LOCAL_COMMIT" = "$REMOTE_COMMIT" ]; then
    echo ""
    echo "✓ You are already up to date!"
    exit 0
fi

echo "✓ Updates available"
echo ""

# Show what will be updated
echo "Changes to be applied:"
git log --oneline --decorate -n 5 "HEAD..${REMOTE_BRANCH}"
echo ""

# Ask for confirmation
read -p "Do you want to update? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Update cancelled"
    exit 0
fi

echo ""
echo "Updating application..."

# Check for running tracker process and stop before updating
tracker_was_running=false
tracker_pids=()
if command -v pgrep >/dev/null 2>&1; then
    while IFS= read -r pid; do
        tracker_pids+=("$pid")
    done < <(pgrep -f "dnd_initative_tracker.py" || true)

    if [ -x "$WRAPPER" ]; then
        while IFS= read -r pid; do
            tracker_pids+=("$pid")
        done < <(pgrep -f "$WRAPPER" || true)
    else
        while IFS= read -r pid; do
            tracker_pids+=("$pid")
        done < <(pgrep -f "launch-inittracker.sh" || true)
    fi

    if [ "${#tracker_pids[@]}" -gt 0 ]; then
        tracker_pids=($(printf "%s\n" "${tracker_pids[@]}" | sort -u))
        tracker_was_running=true
        echo "Running tracker process detected (PIDs: ${tracker_pids[*]})."
        read -p "Stop the tracker before updating? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Update cancelled. Please close the app and re-run the updater."
            exit 0
        fi

        echo "Stopping tracker..."
        kill -TERM "${tracker_pids[@]}" 2>/dev/null || true

        for _ in {1..10}; do
            still_running=false
            for pid in "${tracker_pids[@]}"; do
                if kill -0 "$pid" 2>/dev/null; then
                    still_running=true
                    break
                fi
            done
            if [ "$still_running" = "false" ]; then
                break
            fi
            sleep 1
        done

        still_running=false
        for pid in "${tracker_pids[@]}"; do
            if kill -0 "$pid" 2>/dev/null; then
                still_running=true
                break
            fi
        done

        if [ "$still_running" = "true" ]; then
            echo "Tracker did not exit in time; sending SIGKILL..."
            kill -KILL "${tracker_pids[@]}" 2>/dev/null || true
        fi

        echo "✓ Tracker stopped"
    fi
else
    echo "Warning: pgrep not available; unable to detect running tracker."
fi

# Backup YAML files to preserve local customizations
echo "Backing up YAML files..."
mkdir -p "$YAML_BACKUP_DIR"
for yaml_dir in "${YAML_DIRS[@]}"; do
    if [ -d "$INSTALL_DIR/$yaml_dir" ]; then
        while IFS= read -r -d '' file; do
            rel_path="${file#$INSTALL_DIR/}"
            mkdir -p "$YAML_BACKUP_DIR/$(dirname "$rel_path")"
            cp "$file" "$YAML_BACKUP_DIR/$rel_path"
            git checkout -- "$rel_path" 2>/dev/null || true
        done < <(find "$INSTALL_DIR/$yaml_dir" -type f \( -name "*.yaml" -o -name "*.yml" \) -print0)
    fi
done

# Pull latest changes
git pull --ff-only origin main
git clean -fd -e "logs/" -e "launch-inittracker.sh"

# Update dependencies
if [ -f "$INSTALL_DIR/.venv/bin/activate" ]; then
    echo ""
    echo "Updating dependencies..."
    source "$INSTALL_DIR/.venv/bin/activate"
    pip install --upgrade pip --quiet
    pip install -r requirements.txt --quiet
    echo "✓ Dependencies updated"
fi

# Restore YAML files to keep local customizations
if [ -d "$YAML_BACKUP_DIR" ]; then
    echo ""
    echo "Restoring local YAML files..."
    while IFS= read -r -d '' file; do
        rel_path="${file#$YAML_BACKUP_DIR/}"
        mkdir -p "$INSTALL_DIR/$(dirname "$rel_path")"
        cp "$file" "$INSTALL_DIR/$rel_path"
    done < <(find "$YAML_BACKUP_DIR" -type f -print0)
    echo "✓ Local YAML files restored"
fi

desktop_install_detected=false
if [ -x "$WRAPPER" ] || [ -f "$DESKTOP_FILE" ]; then
    desktop_install_detected=true
fi

if [ "$desktop_install_detected" = "true" ]; then
    echo ""
    echo "Refreshing launcher and desktop entry..."
    APPDIR="$APPDIR" INSTALL_DESKTOP_ENTRY=1 INSTALL_PIP_DEPS=0 bash "$INSTALL_DIR/scripts/install-linux.sh"
fi

echo ""
echo "=========================================="
echo "✓ Update complete!"
echo "=========================================="
echo ""
echo "You can now restart the D&D Initiative Tracker to use the updated version."
echo ""

if [ "$tracker_was_running" = "true" ] && [ -x "$WRAPPER" ]; then
    read -p "Relaunch the tracker now? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Relaunching tracker..."
        "$WRAPPER" >/dev/null 2>&1 &
        disown || true
    fi
fi
