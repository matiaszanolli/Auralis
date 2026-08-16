#!/usr/bin/env bash
# .claude/commands/_audit-validate.sh
#
# Validates file/dir path references in the audit-skill files and the docs
# tree against the live repository tree.
#
# Why: "stale path" findings keep recurring after module splits and renames.
# A one-shot sed sweep is reactive; this gate catches drift on the
# commit that introduces it.
#
# ---------------------------------------------------------------------------
# TWO SCOPES (#5144)
# ---------------------------------------------------------------------------
# #4984 widened this gate to most of docs/ and it has exited 1 on every run
# since — 310 stale refs on day one. A gate that is red unconditionally cannot
# distinguish new rot from the backlog, so its failure was suppressed with
# `|| true` at the call site and it caught nothing for a week. The fix is the
# same ratchet the project already runs for both test suites:
#
#   STRICT scope  — .claude/** plus the authoritative docs (CLAUDE.md, README,
#                   WEBSOCKET_API, docs/architecture, docs/subsystems,
#                   docs/README). Clean today. ANY stale ref fails, exit 1.
#                   This half is wired into CI (.github/workflows/path-references.yml).
#
#   RATCHET scope — the rest of the current docs tree. Compared against
#                   _audit-validate-baseline.txt, which may SHRINK but never
#                   GROW. A new stale ref fails, exit 2. Entries in the
#                   baseline that are now clean are reported so the file can be
#                   regenerated (--update-baseline).
#
# A file moves from RATCHET to STRICT by being cleaned up and relisted below;
# that is the intended direction of travel and the baseline should trend to 0.
#
# What it checks:
#   - Every backticked path token ending in a known source/doc extension
#     (.py .ts .tsx .js .jsx .rs .toml .md .json .yaml .yml .sh .sql .css)
#     is resolved against the repo root. Missing paths print STALE.
#   - Brace-expanded refs like `auralis/{core,dsp}/foo.py` expand to N paths
#     and each is checked.
#   - Trailing `:NN` or `:NN-NN` line ranges are stripped before existence
#     check (line numbers may drift; the file must still exist).
#   - Markdown `[text](target)` link targets in the strict doc set.
#
# Path-reference convention: a path that no longer exists must not be
# backticked. Deleted modules are named in *italics* instead (see
# _audit-common.md:83 and docs/subsystems/dsp-engine.md's "Deleted paths"
# table), which documents the removal without asserting the file is live.
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
#   .claude/commands/_audit-validate.sh                    # validate
#   .claude/commands/_audit-validate.sh --verbose          # list every ref checked
#   .claude/commands/_audit-validate.sh --update-baseline  # rewrite the ratchet baseline
#
# Exit codes:
#   0  clean (strict clean, ratchet at or below baseline)
#   1  strict-scope stale reference — always a regression
#   2  ratchet-scope regression — a docs/ stale ref not in the baseline

set -euo pipefail

# Byte collation, not locale collation. `comm` compares with the C collation
# regardless of LC_COLLATE, so sorting under a UTF-8 locale produces an order
# it rejects ("file 1 is not in sorted order") and the baseline diff silently
# goes wrong. Pin both sides to C.
export LC_ALL=C

cd "$(git rev-parse --show-toplevel)"

BASELINE_FILE=".claude/commands/_audit-validate-baseline.txt"

VERBOSE=0
UPDATE_BASELINE=0
case "${1:-}" in
    --verbose)         VERBOSE=1 ;;
    --update-baseline) UPDATE_BASELINE=1 ;;
    "")                ;;
    *) echo "unknown option: $1" >&2; exit 64 ;;
esac

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

shopt -s nullglob globstar

# --- STRICT scope: must be clean, enforced in CI ----------------------------
strict_files=(
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
    docs/README.md
    CLAUDE.md
    README.md
    auralis-web/backend/WEBSOCKET_API.md
)

# --- RATCHET scope: compared against the checked-in baseline ---------------
# #4984: #4547 only covered 11 of 507 docs/**/*.md files (2.2%) — the gate
# reported false-clean over the other 496. This extends coverage to the
# full "current" (non-historical) subset. Deliberately NOT including
# docs/development/, docs/archive/ (which now also holds the former
# docs/guides/), docs/audits/, or docs/releases/: those are historical
# plan/audit/guide snapshots whose purpose is to record what was deleted or
# superseded, so naming a removed/renamed file there is correct, not drift.
ratchet_files=(
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

# docs/README.md is in the strict set; drop it from the ratchet glob expansion
# so it is not scanned twice.
filtered_ratchet=()
for f in "${ratchet_files[@]}"; do
    [[ "$f" == "docs/README.md" ]] && continue
    filtered_ratchet+=("$f")
done
ratchet_files=("${filtered_ratchet[@]}")

# Enumerate every tracked repo path once so partial refs like
# `repositories/track_repository.py` (shorthand for
# `auralis/library/repositories/track_repository.py`) resolve via
# path-suffix match.
all_paths_file=$(mktemp)
strict_hits=$(mktemp)
ratchet_hits=$(mktemp)
trap 'rm -f "$all_paths_file" "$strict_hits" "$ratchet_hits"' EXIT
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

checked_count=0

# scan_refs <output-file> <file>...
#
# Appends one TAB-separated `<file>\t<path>` key per stale ref. Keys carry no
# line number: line numbers drift as prose is edited, which would churn the
# baseline on every unrelated docs commit.
scan_refs() {
    local out="$1"; shift
    local skill line_num token local_path p
    for skill in "$@"; do
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
                    printf '%s\t%s\n' "$skill" "$p" >> "$out"
                elif [[ "$VERBOSE" == "1" ]]; then
                    echo "ok: $skill:$line_num — $p"
                fi
            done < <(expand_braces "$local_path")
        done < <(grep -noE '`[A-Za-z0-9_./{},-]+\.(py|ts|tsx|js|jsx|rs|toml|md|json|yaml|yml|sh|sql|css)' "$skill" || true)
    done
}

scan_refs "$strict_hits" "${strict_files[@]}"
scan_refs "$ratchet_hits" "${ratchet_files[@]}"

# --- Markdown link targets (#4258) -----------------------------------------
#
# The backticked-token pass above cannot see `[text](target)` links, so a docs
# hub could rot its whole navigation table while the gate reported PASS. That is
# exactly what happened to docs/README.md three times (#4052, #4063, #4258): the
# recurring defect there is dead LINKS, not dead backticked paths.
#
# Markdown links resolve relative to the file that contains them, not the repo
# root, so these cannot go through path_exists(). Every link file is in the
# strict set, so dead links are always a hard failure.
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
            printf '%s\tLINK %s\n' "$doc" "$target" >> "$strict_hits"
        elif [[ "$VERBOSE" == "1" ]]; then
            echo "ok: $doc:$line_num — ($target)"
        fi
    done < <(grep -noE '\]\([^)]+\)' "$doc" | sed -E 's/^([0-9]+):\]\((.*)\)$/\1:\2/' || true)
done

sort -o "$strict_hits" "$strict_hits"
sort -o "$ratchet_hits" "$ratchet_hits"

if (( UPDATE_BASELINE )); then
    cp "$ratchet_hits" "$BASELINE_FILE"
    echo "Baseline rewritten: $BASELINE_FILE ($(wc -l < "$BASELINE_FILE") entries)."
    echo "Commit it. The count may shrink in future, never grow."
    exit 0
fi

[[ -f "$BASELINE_FILE" ]] || : > "$BASELINE_FILE"

new_ratchet=$(comm -23 "$ratchet_hits" "$BASELINE_FILE" || true)
fixed_ratchet=$(comm -13 "$ratchet_hits" "$BASELINE_FILE" || true)

strict_count=$(wc -l < "$strict_hits" | tr -d ' ')
ratchet_count=$(wc -l < "$ratchet_hits" | tr -d ' ')
baseline_count=$(wc -l < "$BASELINE_FILE" | tr -d ' ')
new_count=$([[ -n "$new_ratchet" ]] && printf '%s\n' "$new_ratchet" | wc -l | tr -d ' ' || echo 0)
fixed_count=$([[ -n "$fixed_ratchet" ]] && printf '%s\n' "$fixed_ratchet" | wc -l | tr -d ' ' || echo 0)

if (( strict_count > 0 )); then
    echo "=== STRICT scope failures ==="
    while IFS=$'\t' read -r f p; do
        if [[ "$p" == LINK\ * ]]; then
            echo "DEAD LINK: $f — (${p#LINK })"
        else
            echo "STALE: $f — \`$p\`"
        fi
    done < "$strict_hits"
    echo
fi

if (( new_count > 0 )); then
    echo "=== RATCHET scope regressions (not in baseline) ==="
    printf '%s\n' "$new_ratchet" | while IFS=$'\t' read -r f p; do
        echo "NEW STALE: $f — \`$p\`"
    done
    echo
fi

echo "Checked $checked_count refs across $(( ${#strict_files[@]} + ${#ratchet_files[@]} )) files."
echo "Checked $link_count markdown links across ${#link_files[@]} doc files."
echo "Strict scope:  $strict_count stale (must be 0)."
echo "Ratchet scope: $ratchet_count stale vs baseline $baseline_count (new: $new_count, fixed: $fixed_count)."

if (( fixed_count > 0 && new_count == 0 && strict_count == 0 )); then
    echo
    echo "$fixed_count baseline entr$( ((fixed_count==1)) && echo y || echo ies) now clean."
    echo "Shrink the baseline: .claude/commands/_audit-validate.sh --update-baseline"
fi

if (( strict_count > 0 )); then
    echo
    echo "FAIL (strict): $strict_count stale reference(s) in .claude/** or the authoritative docs."
    echo "Fix: correct the ref, or de-backtick it (use *italics*) if the target was deleted."
    exit 1
fi

if (( new_count > 0 )); then
    echo
    echo "FAIL (ratchet): $new_count stale docs/ reference(s) beyond the baseline."
    echo "Fix the new ref(s). Do NOT run --update-baseline to absorb them — the"
    echo "baseline may shrink, never grow."
    exit 2
fi

echo "OK: strict scope clean, ratchet scope at or below baseline."
