#!/usr/bin/env bash
# .claude/commands/_audit-validate.sh
#
# Validates file/dir path references in `.claude/commands/audit-*.md`,
# `_audit-*.md`, and `.claude/agents/*.md` against the live repository tree.
#
# Why: "stale path" findings keep recurring after module splits and renames.
# A one-shot sed sweep is reactive; this gate catches drift on the
# commit that introduces it.
#
# What it checks:
#   - Every backticked path token ending in a known source/doc extension
#     (.py .ts .tsx .js .jsx .rs .toml .md .json .yaml .yml .sh .sql .css)
#     is resolved against the repo root. Missing paths print STALE and exit 1.
#   - Brace-expanded refs like `auralis/{core,dsp}/foo.py` expand to N paths
#     and each is checked.
#   - Trailing `:NN` or `:NN-NN` line ranges are stripped before existence
#     check (line numbers may drift; the file must still exist).
#
# What it skips (not real repo paths):
#   - /tmp/...                  — runtime audit scratch
#   - ~/.auralis/...            — runtime DB / cache
#   - ~/.claude/...             — user-global memory / config
#   - URLs (contain ://)
#   - bare basenames without `/` — shorthand inside a paragraph that
#                                  already established directory context
#
# Usage:
#   .claude/commands/_audit-validate.sh           # validate, exit 1 on stale
#   .claude/commands/_audit-validate.sh --verbose # list every ref checked

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

VERBOSE=0
[[ "${1:-}" == "--verbose" ]] && VERBOSE=1

should_skip() {
    local p="$1"
    [[ "$p" == /tmp/* ]] && return 0
    [[ "$p" == ~/* || "$p" == \~* ]] && return 0
    [[ "$p" == *"://"* ]] && return 0
    # Placeholder tokens in per-finding format templates, not real refs.
    [[ "$p" == *"<"* || "$p" == *">"* ]] && return 0

    # --- Precision guards (#4547) ---------------------------------------
    # Added when the scan widened to docs/: prose uses these shapes far more
    # than the skill files did, and each was a false STALE that would have
    # made the widened gate unusable.

    # A bare extension or suffix convention, not a path: `.styles.ts`,
    # `.html/.js/.css`, `.test.tsx`. No path segment precedes the dot.
    [[ "$p" == .* ]] && return 0

    # A method call mis-parsed as a path: `LibraryManager.shutdown()` yields
    # the token `LibraryManager.sh`. Real refs to shell scripts have a path
    # separator or a lowercase/underscore basename; a CapWordsClass.sh does
    # not exist in this repo.
    [[ "$p" == *.sh && "$p" != */* && "$p" =~ ^[A-Z] ]] && return 0

    # Runtime-served asset URLs (`/audio-worklet-processor.js`): rooted at the
    # web server, not the repo. Resolve against the frontend public/ dir.
    if [[ "$p" == /* ]]; then
        [[ -e "auralis-web/frontend/public${p}" ]] && return 0
    fi

    return 1
}

# Expand `prefix{a,b,c}suffix` into prefix-a-suffix, prefix-b-suffix, prefix-c-suffix.
# Supports one brace pair only (which covers every observed audit-skill case).
expand_braces() {
    local path="$1"
    if [[ "$path" == *"{"*"}"* ]]; then
        local prefix="${path%%\{*}"
        local rest="${path#*\{}"
        local inner="${rest%%\}*}"
        local suffix="${rest#*\}}"
        local IFS=','
        for part in $inner; do
            printf '%s\n' "${prefix}${part}${suffix}"
        done
    else
        printf '%s\n' "$path"
    fi
}

stale_count=0
checked_count=0
shopt -s nullglob globstar
skill_files=(
    .claude/commands/audit-*.md
    .claude/commands/_audit-*.md
    .claude/commands/fix-issue.md
    .claude/commands/sync-contracts.md
    .claude/commands/trace-flow.md
    .claude/commands/verify-*.md
    .claude/commands/gen-test.md
    .claude/agents/*.md
    # #4547: the authoritative docs tree, which rotted unchecked while the
    # gate reported PASS over the skill files alone.
    docs/architecture/*.md
    docs/subsystems/*.md
    CLAUDE.md
    README.md
    auralis-web/backend/WEBSOCKET_API.md
    # #4984: #4547 only covered 11 of 507 docs/**/*.md files (2.2%) — the gate
    # reported false-clean over the other 496. This extends coverage to the
    # full "current" (non-historical) subset, ~108 files. Deliberately NOT
    # including docs/development/, docs/archive/ (which now also holds the
    # former docs/guides/), docs/audits/, or docs/releases/: those are
    # historical plan/audit/guide snapshots whose purpose is to record what
    # was deleted or superseded, so naming a removed/renamed file there is
    # correct, not drift.
    docs/*.md
    docs/deployment/*.md
    docs/features/**/*.md
    docs/frontend/**/*.md
    docs/getting-started/*.md
    docs/optimization/*.md
    docs/security/*.md
    docs/testing/*.md
    docs/troubleshooting/*.md
    docs/ui_audit/*.md
    docs/versions/*.md
)
shopt -u nullglob globstar

# Enumerate every tracked repo path once so partial refs like
# `repositories/track_repository.py` (shorthand for
# `auralis/library/repositories/track_repository.py`) resolve via
# path-suffix match.
all_paths_file=$(mktemp)
trap 'rm -f "$all_paths_file"' EXIT
git ls-files > "$all_paths_file"

# True iff `p` matches any tracked path or path-suffix.
#
# Bare basenames (`chunked_processor.py`) are checked too — they are shorthand
# for a file the surrounding paragraph already located, and they go stale
# exactly like full paths do. Historically they were skipped, which is how
# `wav_streaming.py` and `self_tuner.py` survived long after deletion.
path_exists() {
    local p="$1"
    [[ -e "$p" ]] && return 0
    # Path-suffix match: any tracked path ending with `/$p`.
    grep -qE "(^|/)${p//./\\.}\$" "$all_paths_file"
}

for skill in "${skill_files[@]}"; do
    [[ -f "$skill" ]] || continue
    # Extract backticked tokens that look like file paths. The trailing
    # extension must be in the known source/doc set to keep noise low.
    while IFS=: read -r line_num token; do
        # Strip leading backtick from grep match.
        token="${token#\`}"
        # Strip trailing `:NN` or `:NN-NN` line range.
        local_path="${token%:[0-9]*}"
        while read -r p; do
            should_skip "$p" && continue
            checked_count=$((checked_count + 1))
            if ! path_exists "$p"; then
                echo "STALE: $skill:$line_num — \`$p\`"
                stale_count=$((stale_count + 1))
            elif [[ "$VERBOSE" == "1" ]]; then
                echo "ok: $skill:$line_num — $p"
            fi
        done < <(expand_braces "$local_path")
    done < <(grep -noE '`[A-Za-z0-9_./{},-]+\.(py|ts|tsx|js|jsx|rs|toml|md|json|yaml|yml|sh|sql|css)' "$skill" || true)
done

# --- Markdown link targets (#4258) -----------------------------------------
#
# The backticked-token pass above cannot see `[text](target)` links, so a docs
# hub could rot its whole navigation table while the gate reported PASS. That is
# exactly what happened to docs/README.md three times (#4052, #4063, #4258): the
# recurring defect there is dead LINKS, not dead backticked paths.
#
# Markdown links resolve relative to the file that contains them, not the repo
# root, so these cannot go through path_exists().
shopt -s nullglob
link_files=(
    docs/README.md
    docs/architecture/*.md
    docs/subsystems/*.md
    README.md
    CLAUDE.md
    auralis-web/backend/WEBSOCKET_API.md
)
shopt -u nullglob

link_count=0
for doc in "${link_files[@]}"; do
    [[ -f "$doc" ]] || continue
    doc_dir="$(dirname "$doc")"
    while IFS=: read -r line_num target; do
        # External and pure-anchor links are not ours to resolve.
        [[ "$target" == *"://"* || "$target" == mailto:* || "$target" == \#* ]] && continue
        # Drop any #fragment; the file must exist, the anchor is not checked.
        target="${target%%#*}"
        [[ -z "$target" ]] && continue
        link_count=$((link_count + 1))
        if [[ ! -e "$doc_dir/$target" ]]; then
            echo "DEAD LINK: $doc:$line_num — ($target)"
            stale_count=$((stale_count + 1))
        elif [[ "$VERBOSE" == "1" ]]; then
            echo "ok: $doc:$line_num — ($target)"
        fi
    done < <(grep -noE '\]\([^)]+\)' "$doc" | sed -E 's/^([0-9]+):\]\((.*)\)$/\1:\2/' || true)
done

echo
echo "Checked $checked_count refs across ${#skill_files[@]} skill files."
echo "Checked $link_count markdown links across ${#link_files[@]} doc files."
if (( stale_count > 0 )); then
    echo "FAIL: $stale_count stale path reference(s)."
    echo "Fix: update the audit skill files, OR delete the stale ref if the target moved."
    exit 1
fi
echo "OK: all path references valid."
