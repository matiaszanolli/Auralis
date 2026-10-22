#!/usr/bin/env bash
# Run the path-reference gate when a commit deletes or renames files (#5818).
#
# A "delete the dead X" refactor greps the code for X but rarely .claude/ or
# docs/, and the path-reference gate (.github/workflows/path-references.yml)
# only ran after the push — so #5526 (queue history) and #5642 (index.css,
# ShuffleModeSelector) each turned master red until a follow-up doc commit.
# Commits that only add or modify files skip this entirely.
set -euo pipefail
cd "$(dirname "$0")/.."

if git diff --cached --diff-filter=DR --quiet; then
    exit 0
fi

echo "Commit deletes or renames files: checking path references (.claude/commands/_audit-validate.sh)"
exec .claude/commands/_audit-validate.sh
