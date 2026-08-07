"""Regression test for temp-directory name consolidation (#5021).

UPLOAD_TEMP_DIRNAME/CHUNK_TEMP_DIRNAME/PROCESSING_TEMP_DIRNAME used to be
re-typed as bare string literals at 5+ call sites across processing_api.py,
processing_engine.py, startup.py, and chunked_processor.py. This locks the
values so a future rename can't silently desync one site from the others
without a failing test.
"""

import sys
from pathlib import Path

_BACKEND = str(Path(__file__).resolve().parents[2] / "auralis-web" / "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from config.limits import (  # noqa: E402
    CHUNK_TEMP_DIRNAME,
    PROCESSING_TEMP_DIRNAME,
    UPLOAD_TEMP_DIRNAME,
)


def test_upload_temp_dirname_value():
    assert UPLOAD_TEMP_DIRNAME == "auralis_uploads"


def test_chunk_temp_dirname_value():
    assert CHUNK_TEMP_DIRNAME == "auralis_chunks"


def test_processing_temp_dirname_value():
    assert PROCESSING_TEMP_DIRNAME == "auralis_processing"
