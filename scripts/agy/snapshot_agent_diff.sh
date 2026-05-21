#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(git rev-parse --show-toplevel)"

name="${1:-agent-pass}"
ts="$(date +%Y%m%d-%H%M%S)"
out="/tmp/${name}-${ts}"

git status --short > "${out}.status"
git diff > "${out}.diff"
git diff --stat > "${out}.stat"

echo "Wrote:"
echo "  ${out}.status"
echo "  ${out}.diff"
echo "  ${out}.stat"
