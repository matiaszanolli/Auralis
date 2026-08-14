#!/usr/bin/env python3
"""Assert the hash-locked file agrees with the manifest it was compiled from (#4871).

`requirements.txt` declares the intended versions; `requirements-lock.txt` is
what CI and the release build actually install (`pip install --require-hashes`).
Nothing compared them, so they were free to describe different stacks — and did:
at the time #4871 was filed, `requirements.txt` pinned `fastapi==0.122.0` while
the environment every audit conclusion was drawn from ran `0.141.1`, and
`starlette` was pinned in neither.

That is the whole shape of the bug this guards: *a manifest that does not
describe the environment anything is verified against*. A pin nobody installs
is documentation, not a constraint.

Checks, in order of what they catch:

1. Every ``==`` pin in the manifest appears in the lock at the SAME version.
   Catches the drift above: editing a pin and forgetting to recompile.
2. Every manifest package appears in the lock at all.
   Catches a package added to the manifest but never locked, which would then
   be resolved freely at install time — the exact hole `--require-hashes` is
   supposed to close.
3. The lock hash-locks every entry.
   A lock line with no ``--hash`` silently downgrades `--require-hashes` for
   that package (pip rejects the *file* only if NO line has hashes).

Not checked: that the lock has no EXTRA packages. It legitimately does — it is
the full transitive closure, which is its entire purpose.

Exit code 0 on success, 1 on drift.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "requirements.txt"
LOCK = REPO_ROOT / "requirements-lock.txt"

# `name==version`, tolerating extras (`uvicorn[standard]==0.52.1`), a trailing
# line continuation, and an environment marker (`uvloop==0.22.1 ; sys_platform
# != 'win32' \`) — the lock is compiled with --universal, so markers are normal.
PIN_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)"
    r"(?:\[[^\]]*\])?"
    r"==(?P<version>[^\s;\\]+)"
)


def normalize(name: str) -> str:
    """PEP 503 normalisation, so `SQLAlchemy` and `sqlalchemy` compare equal."""
    return re.sub(r"[-_.]+", "-", name).lower()


def manifest_pins(path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        if match := PIN_RE.match(line):
            pins[normalize(match.group("name"))] = match.group("version")
    return pins


def lock_pins(path: Path) -> tuple[dict[str, str], set[str]]:
    """Return (name -> version, names whose entry carries at least one hash)."""
    pins: dict[str, str] = {}
    hashed: set[str] = set()
    current: str | None = None
    for raw in path.read_text().splitlines():
        stripped = raw.strip()
        if stripped.startswith("--hash="):
            if current:
                hashed.add(current)
            continue
        line = stripped.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        if match := PIN_RE.match(line):
            current = normalize(match.group("name"))
            pins[current] = match.group("version")
        elif not line.endswith("\\"):
            current = None
    return pins, hashed


def main() -> int:
    for path in (MANIFEST, LOCK):
        if not path.exists():
            print(f"::error::Missing manifest: {path}")
            return 1

    manifest = manifest_pins(MANIFEST)
    lock, hashed = lock_pins(LOCK)
    failures: list[str] = []

    for name, want in sorted(manifest.items()):
        got = lock.get(name)
        if got is None:
            failures.append(
                f"{name}: pinned =={want} in requirements.txt but ABSENT from "
                f"requirements-lock.txt — it would be resolved freely at install time"
            )
        elif got != want:
            failures.append(
                f"{name}: requirements.txt pins =={want} but the lock installs =={got}"
            )
        elif name not in hashed:
            failures.append(f"{name}: present in the lock but carries no --hash entry")

    if failures:
        print("::error::requirements-lock.txt does not match requirements.txt (#4871)")
        for line in failures:
            print(f"  {line}")
        print()
        print("The lock is what CI and the release build actually install, so a")
        print("mismatch means the manifest describes a stack nothing runs.")
        print("Regenerate it (--universal is required — see requirements.txt's header):")
        print("  uv pip compile requirements.txt --generate-hashes --universal \\")
        print("    --python-version 3.14 -o requirements-lock.txt")
        return 1

    print(
        f"OK: all {len(manifest)} manifest pins are present, version-identical "
        f"and hash-locked in requirements-lock.txt."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
