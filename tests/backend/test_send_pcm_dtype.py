"""
Regression tests for dtype handling in `_send_pcm_chunk` (#3875).

The float32 normalization used to be gated behind `if dtype != float32:` and,
on a miss, did a full `astype(np.float32)` copy. The branch was dead (every
caller passes native float32) but the gate still cost a comparison, and the
copy path allocated unnecessarily. The fix replaces it with a single
`astype(np.float32, copy=False)`:

  - native float32 in  → same buffer, zero allocation, bit-exact wire bytes;
  - float64 / big-endian in → still converted defensively to native
    little-endian float32, so a stray dtype can never emit a corrupt PCM frame.

These tests capture the binary frames `_send_pcm_chunk` pushes to
`_safe_send_bytes` and assert the on-the-wire samples are little-endian float32
matching the input, regardless of incoming dtype.
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "auralis-web/backend"))

from core.audio_stream_controller import AudioStreamController, _frame_seq_var


async def _send_and_capture(samples: np.ndarray) -> bytes:
    """Drive _send_pcm_chunk once and return the concatenated wire bytes."""
    _frame_seq_var.set(None)  # fresh per-task seq cell
    captured: list[bytes] = []

    controller = AudioStreamController()
    controller._safe_send = AsyncMock(return_value=True)  # type: ignore[assignment]

    async def fake_send_bytes(_ws, payload: bytes) -> bool:
        captured.append(payload)
        return True

    controller._safe_send_bytes = fake_send_bytes  # type: ignore[assignment]

    await controller._send_pcm_chunk(
        AsyncMock(),
        pcm_samples=samples,
        chunk_index=0,
        total_chunks=1,
        crossfade_samples=0,
    )
    return b"".join(captured)


async def _send_and_decode(samples: np.ndarray) -> np.ndarray:
    """Return the wire bytes decoded as little-endian float32."""
    return np.frombuffer(await _send_and_capture(samples), dtype="<f4")


@pytest.mark.asyncio
async def test_native_float32_is_emitted_bit_exact():
    """Native float32 input must reach the wire byte-for-byte unchanged."""
    samples = np.array([0.0, 0.25, -0.5, 0.999, -1.0, 0.1], dtype=np.float32)
    original = samples.copy()

    wire = await _send_and_capture(samples)

    assert wire == samples.tobytes(), "native float32 must be emitted unchanged"
    # Input must not be mutated in place.
    np.testing.assert_array_equal(samples, original)


@pytest.mark.asyncio
async def test_float64_is_converted_to_float32_wire():
    """A float64 source is converted defensively to float32 (values preserved)."""
    out = await _send_and_decode(np.array([0.1, -0.2, 0.3, -0.4], dtype=np.float64))

    np.testing.assert_array_equal(
        out, np.array([0.1, -0.2, 0.3, -0.4], dtype=np.float32)
    )


@pytest.mark.asyncio
async def test_big_endian_float32_is_emitted_little_endian():
    """A big-endian float32 source must be emitted as native little-endian
    float32, not a byte-swapped (corrupt) frame."""
    values = [0.5, -0.25, 0.75, -0.125]

    out = await _send_and_decode(np.array(values, dtype=">f4"))

    np.testing.assert_array_equal(out, np.array(values, dtype=np.float32))


@pytest.mark.asyncio
async def test_stereo_interleaving_preserved():
    """2D stereo arrays flatten to interleaved L/R order on the wire."""
    stereo = np.array([[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]], dtype=np.float32)

    out = await _send_and_decode(stereo)

    np.testing.assert_array_equal(out, stereo.reshape(-1))
