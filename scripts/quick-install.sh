#!/bin/bash
# Quick install script for D&D Initiative Tracker
# This script clones the repository, installs dependencies, and sets up the application

set -euo pipefail

INSTALL_DIR="$HOME/.local/share/dnd-initiative-tracker"
REPO_URL="https://github.com/jeeves-jeevesenson/init-tracker.git"
EXPECTED_REPO_SLUG="jeeves-jeevesenson/init-tracker"
OS_NAME="$(uname -s)"

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

echo "=========================================="
echo "D&D Initiative Tracker - Quick Install"
echo "=========================================="
echo ""

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed. Please install Python 3.9 or higher."
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
REQUIRED_VERSION="3.9"

if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 9) else 1)"; then
    echo "Error: Python $PYTHON_VERSION found, but Python $REQUIRED_VERSION or higher is required."
    exit 1
fi

echo "✓ Python $PYTHON_VERSION found"

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "Error: git is not installed. Please install git first."
    exit 1
fi

echo "✓ Git found"

# Create install directory if it doesn't exist
mkdir -p "$INSTALL_DIR"

# Clone or update the repository
if [ -d "$INSTALL_DIR/.git" ]; then
    echo ""
    echo "Updating existing installation..."
    cd "$INSTALL_DIR"
    ORIGIN_URL="$(git remote get-url origin 2>/dev/null || true)"
    ORIGIN_SLUG="$(normalize_repo_slug "$ORIGIN_URL" || true)"
    if [ -z "$ORIGIN_SLUG" ] || [ "$ORIGIN_SLUG" != "$EXPECTED_REPO_SLUG" ]; then
        echo "Error: Existing install is not the supported repository."
        echo "  Found origin: ${ORIGIN_URL:-<missing>}"
        echo "  Expected: https://github.com/${EXPECTED_REPO_SLUG}.git"
        echo "Refusing to update this directory automatically to avoid cross-repo corruption."
        echo "Either reinstall into a clean directory or update this checkout manually."
        exit 1
    fi
    git fetch origin --prune --tags
    git pull --ff-only origin main
else
    echo ""
    echo "Cloning repository to $INSTALL_DIR..."
    git clone --origin origin "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

if [[ "${OS_NAME}" == "Linux" ]]; then
    echo ""
    echo "Running Linux installer..."
    APPDIR="$INSTALL_DIR" INSTALL_PIP_DEPS=1 "$INSTALL_DIR/scripts/install-linux.sh"
else
    echo ""
    echo "Creating virtual environment..."
    python3 -m venv .venv

    echo "Activating virtual environment..."
    source .venv/bin/activate

    echo "Installing dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt

    echo ""
    echo "Creating launcher script..."
    LAUNCHER="$HOME/.local/bin/dnd-initiative-tracker"
    HEADLESS_LAUNCHER="$HOME/.local/bin/dnd-initiative-tracker-headless"
    mkdir -p "$HOME/.local/bin"

    cat > "$LAUNCHER" << EOF
#!/bin/bash
cd "$INSTALL_DIR"
source .venv/bin/activate
python dnd_initative_tracker.py "\$@"
EOF

    chmod +x "$LAUNCHER"

    cat > "$HEADLESS_LAUNCHER" << EOF
#!/bin/bash
cd "$INSTALL_DIR"
source .venv/bin/activate
python serve_headless.py "\$@"
EOF

    chmod +x "$HEADLESS_LAUNCHER"

    # Check if ~/.local/bin is in PATH
    if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
        echo ""
        echo "⚠️  Note: $HOME/.local/bin is not in your PATH"
        echo "   Add this line to your ~/.bashrc or ~/.zshrc:"
        echo "   export PATH=\"\$HOME/.local/bin:\$PATH\""
        echo ""
    fi
fi

echo ""
echo "=========================================="
echo "✓ Installation complete!"
echo "=========================================="
echo ""
echo "To run the D&D Initiative Tracker:"
if [[ "${OS_NAME}" == "Linux" ]]; then
    echo "  1. Run: dnd-initiative-tracker"
    echo "  2. Or: $INSTALL_DIR/launch-inittracker.sh"
    echo "  3. Or launch from your desktop menu"
else
    echo "  1. Run: dnd-initiative-tracker"
    echo "  2. Headless/browser-first: dnd-initiative-tracker-headless"
    echo "  3. Or: $LAUNCHER"
    echo "  4. Or navigate to $INSTALL_DIR and run:"
    echo "     source .venv/bin/activate && python dnd_initative_tracker.py"
fi
echo ""
