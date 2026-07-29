#!/usr/bin/env python3
"""Fingerprint one audio file or a folder into a standalone SQLite catalog."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from auralis.analysis.fingerprint.audio_fingerprint_analyzer import (
    AudioFingerprintAnalyzer,
)
from auralis.analysis.fingerprint.catalog import (
    FingerprintCatalog,
    discover_audio_files,
)
from auralis.analysis.fingerprint.windowed_compute import (
    compute_windowed_fingerprint,
)

DEFAULT_DATABASE = Path.home() / ".auralis" / "fingerprints.sqlite3"


@dataclass
class RunSummary:
    discovered: int = 0
    fingerprinted: int = 0
    skipped: int = 0
    failed: int = 0


def fingerprint_source(
    source: Path,
    database: Path,
    *,
    recursive: bool = True,
    force: bool = False,
) -> RunSummary:
    """Fingerprint supported files and store each successful result."""
    files = discover_audio_files(source, recursive=recursive)
    summary = RunSummary(discovered=len(files))
    analyzer = AudioFingerprintAnalyzer()

    with FingerprintCatalog(database) as catalog:
        for position, audio_path in enumerate(files, start=1):
            prefix = f"[{position}/{len(files)}]"
            if not force and catalog.is_current(audio_path):
                summary.skipped += 1
                print(f"{prefix} skip {audio_path}")
                continue

            print(f"{prefix} fingerprint {audio_path}", flush=True)
            fingerprint = compute_windowed_fingerprint(analyzer, audio_path)
            if fingerprint is None:
                summary.failed += 1
                print(f"{prefix} failed {audio_path}", file=sys.stderr)
                continue

            try:
                catalog.store(audio_path, fingerprint)
            except (OSError, TypeError, ValueError) as exc:
                summary.failed += 1
                print(f"{prefix} failed {audio_path}: {exc}", file=sys.stderr)
                continue
            summary.fingerprinted += 1

    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compute representative 25D fingerprints for one audio file or "
            "a folder and store them in SQLite."
        ),
        epilog=(
            "Examples:\n"
            "  python -m scripts.fingerprint album/\n"
            "  python -m scripts.fingerprint track.flac --database study.sqlite3\n"
            "  python -m scripts.fingerprint library/ --force"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("source", type=Path, help="audio file or folder")
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE,
        help=f"SQLite output (default: {DEFAULT_DATABASE})",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="for a folder, fingerprint only audio files directly inside it",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="recompute rows even when file revision and algorithm are unchanged",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        summary = fingerprint_source(
            args.source,
            args.database,
            recursive=not args.no_recursive,
            force=args.force,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nInterrupted; completed rows are safely committed.", file=sys.stderr)
        return 130

    print(
        "Done: "
        f"{summary.discovered} discovered, "
        f"{summary.fingerprinted} fingerprinted, "
        f"{summary.skipped} unchanged, "
        f"{summary.failed} failed. "
        f"Database: {args.database.expanduser().resolve()}"
    )
    return 1 if summary.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
