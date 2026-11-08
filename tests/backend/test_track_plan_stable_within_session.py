"""A track's mastering plan does not change under a stream that is playing it.

When the fingerprint algorithm is bumped (v13: whole-track analysis) the queue
rewrites every library row in the background, possibly while a track is playing.
A processor that is rebuilt mid-track (render timeout, eviction) must still master
the rest of the track with the SAME plan as the part already heard, or the tonal
balance steps at a chunk boundary: the old windowed and new whole-track plans
differ by up to ~6 dB in a band on the same track.

MasteringTargetService caches its (fingerprint, targets) per track and file
signature for the session; only an explicit cache clear starts a new plan.
"""

from types import SimpleNamespace

from core.mastering_target_service import MasteringTargetService

_COLUMNS = (
    "sub_bass_pct bass_pct low_mid_pct mid_pct upper_mid_pct presence_pct air_pct "
    "lufs crest_db bass_mid_ratio tempo_bpm rhythm_stability transient_density "
    "silence_ratio spectral_centroid spectral_rolloff spectral_flatness harmonic_ratio "
    "pitch_stability chroma_energy dynamic_range_variation loudness_variation_std "
    "peak_consistency stereo_width phase_correlation"
).split()


def _row(**overrides):
    values = dict.fromkeys(_COLUMNS, 0.1) | {"lufs": -14.0, "crest_db": 12.0}
    return SimpleNamespace(**(values | overrides))


class _Repo:
    """get_by_track_id answers whatever row the test currently stores."""

    def __init__(self, row) -> None:
        self.row = row

    def get_by_track_id(self, _track_id):
        return self.row


def _load(service):
    return service.load_fingerprint(
        track_id=1, filepath="song.flac", extract_if_missing=True, file_signature="sig-1"
    )


def test_an_upgraded_row_does_not_change_the_plan_mid_session():
    old_row = _row(bass_pct=0.60, mid_pct=0.10, lufs=-12.9)
    repo = _Repo(old_row)
    service = MasteringTargetService(get_fingerprints_repository=lambda: repo)

    _fingerprint, plan_before = _load(service)
    repo.row = _row(bass_pct=0.30, mid_pct=0.35, lufs=-14.8)  # queue upgrades the row
    _fingerprint, plan_after = _load(service)  # e.g. a processor rebuilt mid-track

    assert plan_after == plan_before


def test_an_explicit_cache_clear_is_what_starts_a_new_plan():
    repo = _Repo(_row(bass_pct=0.60, mid_pct=0.10, lufs=-12.9))
    service = MasteringTargetService(get_fingerprints_repository=lambda: repo)
    _fp, before = _load(service)

    repo.row = _row(bass_pct=0.30, mid_pct=0.35, lufs=-14.8)
    service.clear_cache()
    _fp, after = _load(service)

    assert after != before
