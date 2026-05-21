#!/usr/bin/env bash
set -Eeuo pipefail
exec "$(git rev-parse --show-toplevel)/scripts/agy/validate_spell_pass.sh"
