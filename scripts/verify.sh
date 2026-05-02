#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_DIR="$ROOT_DIR/skills/personal-health-agent"

export PYTHONDONTWRITEBYTECODE=1

python3 "$SKILL_DIR/tests/test_handler.py"
python3 "$SKILL_DIR/handler.py" '{"action":"help"}' >/dev/null

if [ -f "$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py" ]; then
  python3 "$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py" "$SKILL_DIR"
fi

python3 -m json.tool "$SKILL_DIR/skill.json" >/dev/null
python3 -m json.tool "$SKILL_DIR/.claw/identity.json" >/dev/null
python3 -m json.tool "$ROOT_DIR/.codex-plugin/plugin.json" >/dev/null

printf 'Verification passed for personal-health-agent\n'
