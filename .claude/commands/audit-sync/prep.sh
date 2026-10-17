#!/usr/bin/env bash
# .claude/commands/audit-sync/prep.sh
#
# Deterministic half of /audit-sync: everything the fan-out agents need, computed
# once so eight agents don't each re-derive it.
#
#   .claude/commands/audit-sync/prep.sh <scratch-dir> [--base <rev>]
#
# Writes into <scratch-dir>:
#   BRIEF.md                     brief.tmpl rendered with base/head/scratch
#   open.txt                     every OPEN issue number (snapshot)
#   cited.txt                    every #NNNN cited by a command, shared file or agent
#   closed_since.tsv             number<TAB>title, closed since the base commit date
#   cited_closed_recent_map.txt  `#N: file …` for cited issues closed since base
#   weights.tsv                  group<TAB>changed-files-under-its-prefixes<TAB>cited-closed-since
#   proposals.md                 empty collector for out-of-scope agent proposals
# and checks that groups.txt covers every non-underscore .claude/commands/*.md exactly once.

set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

here=.claude/commands/audit-sync
scratch="${1:?usage: prep.sh <scratch-dir> [--base <rev>]}"
shift
base="$(awk '{print $1; exit}' "$here/BASELINE")"
if [[ "${1:-}" == "--base" ]]; then base="${2:?--base needs a rev}"; fi
git rev-parse --verify -q "$base^{commit}" >/dev/null || { echo "bad base: $base" >&2; exit 1; }

mkdir -p "$scratch"
head="$(git rev-parse --short HEAD)"
base_date="$(git log -1 --format=%cs "$base")"
ncommits="$(git rev-list --count "$base..HEAD")"
cmds=( $(ls .claude/commands/*.md | sed -E 's#.*/([^/]+)\.md#\1#' | grep -v '^_') )

# groups.txt data lines: `group: cmd cmd | prefix prefix`
group_lines() { grep -vE '^\s*(#|$)' "$here/groups.txt"; }

# --- groups.txt coverage -----------------------------------------------------
grouped="$(group_lines | cut -d: -f2- | cut -d'|' -f1 | tr ' ' '\n' | grep -v '^$' | sort)"
dups="$(uniq -d <<<"$grouped")"
missing="$(comm -23 <(printf '%s\n' "${cmds[@]}" | sort) <(sort -u <<<"$grouped"))"
unknown="$(comm -13 <(printf '%s\n' "${cmds[@]}" | sort) <(sort -u <<<"$grouped"))"
[[ -z "$dups$missing$unknown" ]] || {
    echo "groups.txt mismatch — duplicated: ${dups:-none}; ungrouped: ${missing:-none}; unknown: ${unknown:-none}" >&2
    exit 1
}

# --- issue state -------------------------------------------------------------
cited_files=( .claude/commands/*.md .claude/agents/*.md )
grep -ohE '#[0-9]{3,5}\b' "${cited_files[@]}" | tr -d '#' | sort -u > "$scratch/cited.txt"
gh issue list --state open --limit 5000 --json number --jq '.[].number' | sort -u > "$scratch/open.txt"
gh issue list --state closed --search "closed:>=$base_date" --limit 2000 \
    --json number,title --jq '.[] | "\(.number)\t\(.title)"' > "$scratch/closed_since.tsv"
: > "$scratch/cited_closed_recent_map.txt"
for n in $(comm -12 "$scratch/cited.txt" <(cut -f1 "$scratch/closed_since.tsv" | sort -u)); do
    where="$(grep -lE "#$n\b" "${cited_files[@]}" | sed -E 's#\.claude/commands/##; s#\.claude/##; s#\.md$##' | tr '\n' ' ')"
    echo "#$n: $where" >> "$scratch/cited_closed_recent_map.txt"
done

# --- per-group weight --------------------------------------------------------
# Changed files under a group's path prefixes (a file may count toward several
# groups). Two groups are inflated by churn, not code: `regression` (every
# tests/ edit) and `debt` (every docs/ edit) — discount those before splitting.
git diff --name-only "$base..HEAD" > "$scratch/changed.txt"
{
    printf 'group\tchanged_files\tcited_closed_since\n'
    while IFS= read -r line; do
        g="${line%%:*}"; rest="${line#*:}"
        members="${rest%%|*}"; prefixes="${rest#*|}"
        rf="$(awk -v pre="$prefixes" '
            BEGIN { n = split(pre, P, " ") }
            { for (i = 1; i <= n; i++) if ($0 == P[i] || index($0, P[i] "/") == 1) { c++; break } }
            END { print c + 0 }' "$scratch/changed.txt")"
        cc=0
        for s in $members; do
            cc=$((cc + $(grep -cE "(^|[: ])$s( |$)" "$scratch/cited_closed_recent_map.txt" || true)))
        done
        printf '%s\t%s\t%s\n' "$g" "$rf" "$cc"
    done < <(group_lines)
} > "$scratch/weights.tsv"

# --- brief -------------------------------------------------------------------
sed -e "s#{{BASE}}#$base#g" -e "s#{{BASE_DATE}}#$base_date#g" -e "s#{{HEAD}}#$head#g" \
    -e "s#{{NCOMMITS}}#$ncommits#g" -e "s#{{SCRATCH}}#$scratch#g" "$here/brief.tmpl" > "$scratch/BRIEF.md"
[[ -f "$scratch/proposals.md" ]] || : > "$scratch/proposals.md"

echo "base $base ($base_date) → HEAD $head: $ncommits commits"
echo "cited issues: $(wc -l < "$scratch/cited.txt"); cited & closed since base: $(wc -l < "$scratch/cited_closed_recent_map.txt")"
echo
echo "group weights (changed files / cited-closed):"
while IFS=$'\t' read -r g rf cc; do
    [[ "$g" == group ]] && continue
    members="$(group_lines | awk -F: -v g="$g" '$1==g {sub(/\|.*/, "", $2); print $2}')"
    printf '  %-12s %5d / %-4d %s\n' "$g" "$rf" "$cc" "$members"
done < "$scratch/weights.tsv"
echo
echo "brief: $scratch/BRIEF.md"
