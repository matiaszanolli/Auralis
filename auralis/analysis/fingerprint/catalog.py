"""SQLite catalog for standalone audio fingerprint collection."""

from __future__ import annotations

import math
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Self

from auralis.__version__ import FINGERPRINT_ALGORITHM_VERSION
from auralis.analysis.fingerprint.schema import DIMENSION_SCHEMA
from auralis.io.formats import AUDIO_EXTENSIONS
from auralis.version import __version__

CATALOG_SCHEMA_VERSION = 1
SAMPLING_STRATEGY = "body-50pct-90s+probes-25pct-75pct-30s"
DIMENSION_NAMES = tuple(DIMENSION_SCHEMA)


def discover_audio_files(source: Path, *, recursive: bool = True) -> list[Path]:
    """Return supported audio files below ``source`` in stable path order."""
    source = source.expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    if source.is_file():
        if source.suffix.lower() not in AUDIO_EXTENSIONS:
            raise ValueError(f"unsupported audio format: {source.suffix or '(none)'}")
        return [source]
    if not source.is_dir():
        raise ValueError(f"not a regular file or directory: {source}")

    candidates = source.rglob("*") if recursive else source.iterdir()
    return sorted(
        (
            path.resolve()
            for path in candidates
            if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
        ),
        key=lambda path: str(path).casefold(),
    )


class FingerprintCatalog:
    """Persist versioned 25D measurements without writing audio sidecars."""

    def __init__(self, database_path: Path) -> None:
        self.path = database_path.expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self._initialize()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self.connection.close()

    def _initialize(self) -> None:
        columns = ",\n".join(f'"{name}" REAL NOT NULL' for name in DIMENSION_NAMES)
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute(
            f"""
            CREATE TABLE IF NOT EXISTS fingerprints (
                source_path TEXT PRIMARY KEY,
                source_size INTEGER NOT NULL,
                source_mtime_ns INTEGER NOT NULL,
                fingerprint_version INTEGER NOT NULL,
                auralis_version TEXT NOT NULL,
                sampling_strategy TEXT NOT NULL,
                analyzed_at TEXT NOT NULL,
                {columns}
            )
            """
        )
        self.connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_fingerprints_analyzed_at
            ON fingerprints(analyzed_at)
            """
        )
        self.connection.execute(f"PRAGMA user_version = {CATALOG_SCHEMA_VERSION}")
        self.connection.commit()

    def is_current(self, audio_path: Path) -> bool:
        """Whether the catalog has this unchanged file using this algorithm."""
        resolved = audio_path.expanduser().resolve()
        stat = resolved.stat()
        row = self.connection.execute(
            """
            SELECT 1
            FROM fingerprints
            WHERE source_path = ?
              AND source_size = ?
              AND source_mtime_ns = ?
              AND fingerprint_version = ?
              AND sampling_strategy = ?
            """,
            (
                str(resolved),
                stat.st_size,
                stat.st_mtime_ns,
                FINGERPRINT_ALGORITHM_VERSION,
                SAMPLING_STRATEGY,
            ),
        ).fetchone()
        return row is not None

    def store(self, audio_path: Path, fingerprint: dict[str, Any]) -> None:
        """Atomically insert or replace one complete fingerprint."""
        actual = set(fingerprint)
        expected = set(DIMENSION_NAMES)
        if actual != expected:
            missing = sorted(expected - actual)
            extra = sorted(actual - expected)
            raise ValueError(
                f"fingerprint schema mismatch; missing={missing}, extra={extra}"
            )

        values: list[float] = []
        for name in DIMENSION_NAMES:
            value = float(fingerprint[name])
            if not math.isfinite(value):
                raise ValueError(f"non-finite fingerprint dimension: {name}")
            values.append(value)

        resolved = audio_path.expanduser().resolve()
        stat = resolved.stat()
        metadata_columns = (
            "source_path",
            "source_size",
            "source_mtime_ns",
            "fingerprint_version",
            "auralis_version",
            "sampling_strategy",
            "analyzed_at",
        )
        all_columns = metadata_columns + DIMENSION_NAMES
        quoted_columns = ", ".join(f'"{column}"' for column in all_columns)
        placeholders = ", ".join("?" for _ in all_columns)
        updates = ", ".join(
            f'"{column}" = excluded."{column}"'
            for column in all_columns
            if column != "source_path"
        )
        row = (
            str(resolved),
            stat.st_size,
            stat.st_mtime_ns,
            FINGERPRINT_ALGORITHM_VERSION,
            __version__,
            SAMPLING_STRATEGY,
            datetime.now(UTC).isoformat(),
            *values,
        )

        with self.connection:
            self.connection.execute(
                f"""
                INSERT INTO fingerprints ({quoted_columns})
                VALUES ({placeholders})
                ON CONFLICT(source_path) DO UPDATE SET {updates}
                """,
                row,
            )

    def count(self) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) AS count FROM fingerprints"
        ).fetchone()
        return int(row["count"])
