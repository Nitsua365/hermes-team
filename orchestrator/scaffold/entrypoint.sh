#!/usr/bin/env bash
set -e

# Sync built-in tools and skills from the image into the profile volume.
# -n (no-clobber) preserves any files the user has already customized.
if [[ -d /opt/hermes-builtin/tools ]]; then
  mkdir -p /opt/data/tools
  cp -rn /opt/hermes-builtin/tools/. /opt/data/tools/
fi

if [[ -d /opt/hermes-builtin/skills ]]; then
  mkdir -p /opt/data/skills
  cp -rn /opt/hermes-builtin/skills/. /opt/data/skills/
fi

exec /opt/hermes/.venv/bin/hermes "$@"
