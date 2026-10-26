#!/usr/bin/env python3
"""Assert the release build's tooling is hash-locked (#6151).

``requirements-lock.txt`` hash-locks what the app imports, but the tools that
BUILD the shipped installers -- pip, setuptools, wheel, maturin (builds the
bundled PyO3 wheel) and PyInstaller (freezes the backend and embeds its
bootloader) -- were installed unpinned on every tag build. A hijacked PyPI
release of any of them (or of pefile, altgraph, pyinstaller-hooks-contrib) would
be baked into all three installers, and SHA256SUMS is generated from the
already-built output, so it could not notice.

Checks:

1. ``requirements-build.txt`` hash-locks every package it lists and ``==`` pins
   each tool named in ``requirements-build.in``.
2. Every ``pip install`` in ``build-release.yml`` is ``--require-hashes`` or
   ``--no-deps`` (the locally built wheel); none upgrades or floats a package.

Exit code 0 on success, 1 on drift.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_IN = REPO_ROOT / "requirements-build.in"
BUILD_LOCK = REPO_ROOT / "requirements-build.txt"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "build-release.yml"

PIN_RE = re.compile(r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?==(?P<version>[^\s;\\]+)")


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def tools(path: Path) -> list[str]:
    """Names listed in requirements-build.in."""
    names = []
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip()
        if line and not line.startswith("-"):
            names.append(normalize(re.split(r"[<>=!~\[ ;]", line, maxsplit=1)[0]))
    return names


def lock_entries(path: Path) -> tuple[dict[str, str], set[str]]:
    """(name -> pinned version, names carrying at least one --hash)."""
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


def unlocked_pip_installs(workflow: Path) -> list[str]:
    """``pip install`` command lines that are neither hash-checked nor dependency-free."""
    offenders = []
    for number, raw in enumerate(workflow.read_text().splitlines(), start=1):
        line = raw.strip()
        if line.startswith("#") or not re.match(r"^(?:python -m )?pip install\b", line):
            continue
        if "--require-hashes" in line or "--no-deps" in line:
            if "--upgrade" in line or "-U " in line:
                offenders.append(f"{number}: {line}")
            continue
        offenders.append(f"{number}: {line}")
    return offenders


def problems() -> list[str]:
    found: list[str] = []
    for path in (BUILD_IN, BUILD_LOCK, WORKFLOW):
        if not path.exists():
            return [f"missing file: {path.relative_to(REPO_ROOT)}"]

    pins, hashed = lock_entries(BUILD_LOCK)
    for name in tools(BUILD_IN):
        if name not in pins:
            found.append(f"{name}: listed in requirements-build.in but not ==pinned in requirements-build.txt")
    for name in sorted(set(pins) - hashed):
        found.append(f"{name}: in requirements-build.txt without a --hash entry")
    found.extend(
        f"build-release.yml:{entry} -- install from a --require-hashes file" for entry in unlocked_pip_installs(WORKFLOW)
    )
    return found


def main() -> int:
    found = problems()
    if found:
        print("::error::release build tooling is not hash-locked (#6151)")
        for line in found:
            print(f"  {line}")
        print()
        print("Regenerate the lock (shared packages are held at the runtime lock's versions):")
        print("  uv pip compile requirements-build.in --generate-hashes --universal \\")
        print("    --python-version 3.14 -c requirements-lock.txt -o requirements-build.txt")
        return 1
    print("OK: build tools are hash-locked and every build-release.yml pip install is hash-checked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
