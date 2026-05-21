#!/usr/bin/env bash
set -Eeuo pipefail
exec "$(git rev-parse --show-toplevel)/scripts/agy/audit_spell_primitives.sh"
