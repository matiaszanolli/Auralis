"""
Regression tests for the files router's closure-to-module-level extraction
(#4670).

create_files_router() used to be a closure -- both handlers were nested
`async def`s reachable only by constructing the whole router with its
dependency graph. Handlers are now module-level `async def` functions with
FastAPI Depends() defaults; a caller that wants to unit-test one directly
just passes the dependency explicitly as a keyword argument, bypassing
Depends() (and _FilesDeps, and the router) entirely. These tests exist to
prove that seam is real, not just that it types.
"""

import io
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, UploadFile

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web" / "backend"))

from routers.files import (  # noqa: E402
    _MAX_UPLOAD_FILES,
    get_supported_formats,
    upload_files,
)

pytestmark = pytest.mark.asyncio


def _upload(name: str, data: bytes) -> UploadFile:
    return UploadFile(filename=name, file=io.BytesIO(data))


async def test_get_supported_formats_callable_with_no_dependencies_at_all():
    """No router, no _FilesDeps, no app -- just the handler."""
    result = await get_supported_formats()

    assert ".flac" in result["input_formats"]
    assert 44100 in result["sample_rates"]
    assert result["bit_depths"] == [16, 24, 32]


async def test_upload_files_callable_with_a_bare_stub_repo_provider():
    """A stub repository provider is enough to drive a successful upload."""
    track = MagicMock()
    track.id = 7
    track.title = "song"
    track.duration = 1.5
    track.sample_rate = 44100
    repos = MagicMock()
    repos.tracks.add.return_value = track

    wav = b"RIFF" + b"\x00" * 4 + b"WAVEfmt " + b"\x00" * 32

    import routers.files as files_module

    # load_audio is the only engine call in the success path; patching it
    # keeps this a pure handler test (a 44-byte stub WAV is not decodable).
    original_load = files_module.load_audio
    files_module.load_audio = lambda path: (MagicMock(ndim=1, __len__=lambda s: 44100), 44100)
    try:
        result = await upload_files(
            files=[_upload("song.wav", wav)],
            get_repos=lambda: repos,
        )
    finally:
        files_module.load_audio = original_load

    assert len(result["results"]) == 1
    assert result["results"][0]["status"] == "success"
    assert result["results"][0]["track_id"] == 7
    repos.tracks.add.assert_called_once()


async def test_upload_files_rejects_bad_magic_without_touching_the_repos():
    """Magic-byte validation still runs before any repository access."""
    repos = MagicMock()

    result = await upload_files(
        files=[_upload("fake.wav", b"NOTAUDIO" * 4)],
        get_repos=lambda: repos,
    )

    assert result["results"][0]["status"] == "error"
    assert "does not match any known audio format" in result["results"][0]["message"]
    repos.tracks.add.assert_not_called()


async def test_upload_files_count_cap_precedes_repository_resolution():
    """413 wins over the repository provider's 503 (validation order, #4349).

    The provider is invoked from inside the handler body -- after the count
    check -- not hoisted into a Depends(), so an over-large batch never
    resolves it.
    """
    def _boom():
        raise HTTPException(status_code=503, detail="Repository factory not available")

    wav = b"RIFF" + b"\x00" * 40
    files = [_upload(f"t{i}.wav", wav) for i in range(_MAX_UPLOAD_FILES + 1)]

    with pytest.raises(HTTPException) as exc:
        await upload_files(files=files, get_repos=_boom)

    assert exc.value.status_code == 413
