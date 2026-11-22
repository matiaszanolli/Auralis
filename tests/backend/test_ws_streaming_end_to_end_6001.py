"""The real /ws streaming path, end to end, on a real track (#6001).

Handler-level specs stream real files through stream_normal_audio with the socket mocked; nothing drove
the live endpoint itself: the repository lookup in the (isolated) library, path validation, the real
ChunkedAudioProcessor for the enhanced path, the start / meta+binary chunk / end protocol and the socket
framing together. These tests do, on a 20 s stereo WAV whose samples are their own frame index, so the
payload that arrives can be compared with the file sample for sample.

:copyright: (C) 2026 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import json

import numpy as np
import pytest
import soundfile as sf

SAMPLE_RATE = 8000
SECONDS = 20  # more than one 15 s chunk, so the chunk boundary is crossed
INDEX_SCALE = 2**21  # a power of two: exact in float32 and below 1.0 for this length


@pytest.fixture
def indexed_track(client, tmp_path):
    """A real library track whose sample value is its own frame index / INDEX_SCALE."""
    from main import globals_dict

    frames = SAMPLE_RATE * SECONDS
    ramp = (np.arange(frames, dtype=np.float64) / INDEX_SCALE).astype(np.float32)
    path = tmp_path / "indexed.wav"
    sf.write(str(path), np.column_stack([ramp, ramp]), SAMPLE_RATE, subtype="FLOAT")

    tracks = globals_dict["library_database"].tracks
    track = tracks.add({
        "title": "Indexed Track", "filepath": str(path), "artists": ["E2E"], "album": "E2E",
        "format": "WAV", "sample_rate": SAMPLE_RATE, "channels": 2, "duration": float(SECONDS),
    })
    assert track is not None
    yield track, frames
    tracks.delete(track.id)


def _stream(client, command: str, data: dict, terminal: set[str], max_frames: int = 400):
    """Send ``command`` and collect (messages, concatenated float32 payload) until a terminal message."""
    messages: list[dict] = []
    payload = bytearray()
    with client.websocket_connect("/ws") as ws:
        ws.send_text(json.dumps({"type": command, "data": data}))
        for _ in range(max_frames):
            frame = ws.receive()
            if frame.get("bytes") is not None:
                payload.extend(frame["bytes"])
                continue
            message = json.loads(frame["text"])
            messages.append(message)
            if message["type"] in terminal:
                break
        else:
            raise AssertionError(f"no {terminal} within {max_frames} frames; saw {[m['type'] for m in messages]}")
    return messages, np.frombuffer(bytes(payload), dtype="<f4")


def _types(messages):
    return [m["type"] for m in messages]


def test_normal_stream_delivers_every_sample_of_the_file_in_order(client, indexed_track):
    track, frames = indexed_track

    messages, pcm = _stream(
        client, "play_normal", {"track_id": track.id}, {"audio_stream_end", "audio_stream_error", "error"}
    )

    assert "audio_stream_error" not in _types(messages), messages
    types = _types(messages)
    assert "audio_stream_start" in types
    assert types.index("audio_stream_start") < types.index("audio_chunk_meta"), "audio before the start message"
    assert _types(messages)[-1] == "audio_stream_end"
    assert messages[-1]["data"].get("reason") in (None, "completed"), messages[-1]

    stereo = pcm.reshape(-1, 2)
    assert len(stereo) == frames
    indices = np.rint(stereo[:, 0].astype(np.float64) * INDEX_SCALE).astype(np.int64)
    assert np.array_equal(indices, np.arange(frames)), "a sample was dropped, duplicated or reordered"
    assert np.array_equal(stereo[:, 0], stereo[:, 1]), "channels were misaligned"


def test_chunk_metadata_precedes_its_binary_frames_with_consistent_counts(client, indexed_track):
    track, frames = indexed_track

    messages, pcm = _stream(
        client, "play_normal", {"track_id": track.id}, {"audio_stream_end", "audio_stream_error", "error"}
    )

    metas = [m["data"] for m in messages if m["type"] == "audio_chunk_meta"]
    assert metas, "no audio_chunk_meta frames"
    assert sum(meta["sample_count"] for meta in metas) == pcm.size == frames * 2
    assert [meta["seq"] for meta in metas] == list(range(len(metas))), "frame sequence is not monotonic"
    assert {meta["track_id"] for meta in metas} == {track.id}


def test_an_unknown_track_gets_an_error_not_a_hang(client):
    messages, pcm = _stream(
        client, "play_normal", {"track_id": 987654}, {"audio_stream_error", "error", "audio_stream_end"}
    )

    assert _types(messages)[-1] in {"audio_stream_error", "error"}
    assert pcm.size == 0


def test_enhanced_stream_delivers_the_whole_track_through_the_real_processor(client, indexed_track):
    """Real ChunkedAudioProcessor and DSP over /ws: the delivered sample count equals the source's."""
    track, frames = indexed_track

    messages, pcm = _stream(
        client,
        "play_enhanced",
        {"track_id": track.id, "preset": "adaptive", "intensity": 1.0, "force": True},
        {"audio_stream_end", "audio_stream_error", "error"},
        max_frames=2000,
    )

    assert "audio_stream_error" not in _types(messages), messages
    assert _types(messages)[-1] == "audio_stream_end"
    assert messages[-1]["data"].get("reason") in (None, "completed"), messages[-1]
    assert pcm.size == frames * 2, f"delivered {pcm.size // 2} frames of {frames}"
    assert np.all(np.isfinite(pcm))
    assert float(np.max(np.abs(pcm))) <= 1.0 + 1e-6


@pytest.fixture
def mono_track(client, tmp_path):
    """A real one-channel library track (REC-03): a 440 Hz tone, mono on disk."""
    from main import globals_dict

    frames = SAMPLE_RATE * SECONDS
    tone = (0.25 * np.sin(2 * np.pi * 440 * np.arange(frames) / SAMPLE_RATE)).astype(np.float32)
    path = tmp_path / "mono.wav"
    sf.write(str(path), tone, SAMPLE_RATE, subtype="FLOAT")

    tracks = globals_dict["library_database"].tracks
    track = tracks.add({
        "title": "Mono Track", "filepath": str(path), "artists": ["E2E"], "album": "E2E",
        "format": "WAV", "sample_rate": SAMPLE_RATE, "channels": 1, "duration": float(SECONDS),
    })
    assert track is not None
    yield track, frames
    tracks.delete(track.id)


@pytest.mark.parametrize(
    "command, extra",
    [
        ("play_normal", {}),
        ("play_enhanced", {"preset": "adaptive", "intensity": 1.0, "force": True}),
    ],
)
def test_mono_track_plays_whole_and_finite_in_both_modes(client, mono_track, command, extra):
    """REC-03: a mono file streams in normal and enhanced mode with every frame and finite PCM."""
    track, frames = mono_track

    messages, pcm = _stream(
        client, command, {"track_id": track.id, **extra},
        {"audio_stream_end", "audio_stream_error", "error"}, max_frames=2000,
    )

    assert "audio_stream_error" not in _types(messages), messages
    assert _types(messages)[-1] == "audio_stream_end"
    assert pcm.size == frames, f"delivered {pcm.size} mono samples of {frames}"
    assert np.all(np.isfinite(pcm))
    assert float(np.max(np.abs(pcm))) <= 1.0 + 1e-6
