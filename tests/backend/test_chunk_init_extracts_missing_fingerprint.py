"""A track with no stored fingerprint is analysed once, up front (not per chunk).

Analysis is a property of the whole track; only rendering is chunked. Until now
``init_fingerprint_and_processor`` loaded tiers 1/2 only (``extract_if_missing=False``),
so a freshly scanned track rendered with NO targets: each chunk was fingerprinted on
its own, and the background queue's targets then arrived mid-playback — the same track
was mastered differently at its start and its end.

These tests pin that the missing-fingerprint case now extracts before the processor
is leased, and that a failed extraction still degrades instead of raising.
"""

from types import SimpleNamespace

from core import fingerprint_loading
from core.chunk_processor_init import init_fingerprint_and_processor
from core.mastering_target_service import MasteringTargetService

_FINGERPRINT = {"lufs": -13.0, "crest_db": 12.0, "bass_pct": 0.4}
_TARGETS = {"target_lufs": -14.0, "source_lufs": -13.0, "eq_curve_db": {}}


class _Factory:
    """Records the targets each lease is handed."""

    def __init__(self) -> None:
        self.targets_seen: list[object] = []

    def acquire(self, **kwargs):
        self.targets_seen.append(kwargs.get("mastering_targets"))
        return SimpleNamespace()


def test_init_asks_the_service_to_extract_when_nothing_is_stored():
    calls: list[dict] = []

    def load_fingerprint(**kwargs):
        calls.append(kwargs)
        return _FINGERPRINT, _TARGETS

    service = SimpleNamespace(load_fingerprint=load_fingerprint)
    factory = _Factory()

    fingerprint, targets, processor, _config = init_fingerprint_and_processor(
        service, factory, 1, "track.flac", "adaptive", 1.0, 44100
    )

    assert calls[0]["extract_if_missing"] is True
    assert fingerprint == _FINGERPRINT
    assert targets == _TARGETS
    # The lease is taken WITH the targets: the first chunk renders against the plan.
    assert factory.targets_seen == [_TARGETS]
    assert processor is not None


def test_unstored_track_gets_targets_from_extraction_before_any_chunk(monkeypatch):
    """Through the real service: no DB row (no repository), no .25d, extraction runs."""
    extracted: list[str] = []

    def fake_extract(filepath, derive_targets, save_to_file=True):
        extracted.append(filepath)
        return dict(_FINGERPRINT), derive_targets(_FINGERPRINT)

    monkeypatch.setattr(fingerprint_loading, "load_from_file", lambda *_a, **_k: None)
    monkeypatch.setattr(fingerprint_loading, "extract_from_audio", fake_extract)
    service = MasteringTargetService()  # no repository: tier 1 cannot hit
    factory = _Factory()

    _fp, targets, _processor, _config = init_fingerprint_and_processor(
        service, factory, 424242, "never-scanned.flac", "adaptive", 1.0, 44100
    )

    assert extracted == ["never-scanned.flac"]
    assert targets is not None
    assert "target_lufs" in targets
    assert factory.targets_seen == [targets]


def test_failed_extraction_degrades_to_no_targets_without_raising(monkeypatch):
    monkeypatch.setattr(fingerprint_loading, "load_from_file", lambda *_a, **_k: None)
    monkeypatch.setattr(fingerprint_loading, "extract_from_audio", lambda *_a, **_k: None)
    factory = _Factory()

    fingerprint, targets, processor, _config = init_fingerprint_and_processor(
        MasteringTargetService(), factory, 7, "corrupt.flac", "adaptive", 1.0, 44100
    )

    assert fingerprint is None
    assert targets is None
    assert processor is not None  # still leased; the renderer's fallback path stays available


def test_original_audio_never_extracts():
    """preset=None serves the untouched file: no analysis at all."""
    calls: list[dict] = []
    service = SimpleNamespace(load_fingerprint=lambda **kw: calls.append(kw))

    init_fingerprint_and_processor(service, _Factory(), 1, "t.flac", None, 1.0, 44100)

    assert calls == []
