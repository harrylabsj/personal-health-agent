#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="$ROOT_DIR/skills/personal-health-agent"
TARGET_DIR="${HERMES_SKILLS_DIR:-$HOME/.hermes/skills/health}/personal-health-agent"

mkdir -p "$TARGET_DIR"
cp -R "$SOURCE_DIR"/. "$TARGET_DIR"/

printf 'Installed personal-health-agent to %s\n' "$TARGET_DIR"
printf 'Start a new Hermes session for the skill loader to see it.\n'
