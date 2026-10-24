#!/usr/bin/env python3
"""Ratchet gate for files that were split once and keep regrowing (#5830).

CLAUDE.md asks for modules under 300 lines, and several god-files were split to
get there (#4245, #4249, #4250, #5463) and closed. Each was then lengthened a
few lines at a time by unrelated fixes — the coordinator gets the new code
rather than a sibling — until one sat at exactly 300 and another passed the
waiver ceiling written in its own docstring. Nothing re-measured them after the
close, so the documented numbers were unenforced.

``loc-ceilings.json`` lists those files with the line count each may not exceed.
A listed file that grows fails the gate; one that shrinks is reported so the
ceiling can be lowered. The ceilings only go down: a split target that needs
more room should be split again, not given a higher number.

New entries are ALWAYS written at the file's current size (#6268), never the
blanket 299: a ratchet must hold each file where it closed, or a 58-line file
can quadruple before the gate notices. When a split creates a new target, run
``--update`` (or add the entry at its measured size) in the same commit. The
one documented exception shape: a not-yet-split offender (e.g. hybrid_processor
before #6272) may hold an above-300 ceiling at its exact current size until
its own split lands.

Usage:
    python scripts/check_loc_ratchet.py             # verify
    python scripts/check_loc_ratchet.py --update    # lower ceilings to current size
    python scripts/check_loc_ratchet.py --list      # print current sizes

Exit codes: 0 = no listed file above its ceiling, 1 = a file grew (or the
ceilings file could not be read).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CEILINGS_PATH = REPO_ROOT / "loc-ceilings.json"


def count_lines(path: Path) -> int:
    """Physical line count, as ``wc -l`` reports it (trailing newline included)."""
    with path.open("rb") as handle:
        return sum(1 for _ in handle)


def load_ceilings(path: Path = CEILINGS_PATH) -> dict[str, int]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))["ceilings"]
        return {str(name): int(limit) for name, limit in raw.items()}
    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError) as err:
        print(f"x Could not read {path.name}: {err}", file=sys.stderr)
        sys.exit(1)


def measure(ceilings: dict[str, int], root: Path = REPO_ROOT) -> dict[str, int | None]:
    """Current size of each listed file; ``None`` if it no longer exists."""
    sizes: dict[str, int | None] = {}
    for name in ceilings:
        target = root / name
        sizes[name] = count_lines(target) if target.is_file() else None
    return sizes


def write_ceilings(ceilings: dict[str, int], path: Path = CEILINGS_PATH) -> None:
    payload = {
        "_comment": (
            "Closed split targets and the line count each may not exceed (#5830). "
            "The ceilings only go down: split the file again instead of raising one. "
            "Lower them with: python scripts/check_loc_ratchet.py --update"
        ),
        "ceilings": dict(sorted(ceilings.items())),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true", help="lower ceilings to current sizes")
    parser.add_argument("--list", action="store_true", help="print current sizes")
    args = parser.parse_args()

    ceilings = load_ceilings()
    sizes = measure(ceilings)

    if args.list:
        for name, size in sorted(sizes.items()):
            print(f"{size if size is not None else 'MISSING':>7}  (ceiling {ceilings[name]})  {name}")
        return 0

    if args.update:
        lowered = {
            name: min(limit, sizes[name]) if sizes[name] is not None else limit
            for name, limit in ceilings.items()
        }
        write_ceilings(lowered)
        print(f"Ceilings rewritten: {CEILINGS_PATH.name}")
        return 0

    over = {n: (s, ceilings[n]) for n, s in sizes.items() if s is not None and s > ceilings[n]}
    missing = sorted(n for n, s in sizes.items() if s is None)
    slack = {n: (s, ceilings[n]) for n, s in sizes.items() if s is not None and s < ceilings[n]}

    print(f"LOC ratchet: {len(sizes)} file(s) listed, {len(over)} over their ceiling.")
    if missing:
        print(f"\n! {len(missing)} listed file(s) no longer exist — remove them from {CEILINGS_PATH.name}:")
        for name in missing:
            print(f"    {name}")
    if slack:
        print(f"\n+ {len(slack)} file(s) shrank; lower the ceiling: python scripts/check_loc_ratchet.py --update")
        for name, (size, limit) in sorted(slack.items()):
            print(f"    {name}: {size} < {limit}")
    if over:
        print(f"\nx {len(over)} file(s) grew past their ceiling:")
        for name, (size, limit) in sorted(over.items()):
            print(f"    {name}: {size} > {limit}")
        print("\n  Move the new code into a sibling module. The ceiling does not go up.")
        return 1

    print("OK: no split target regrew.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
