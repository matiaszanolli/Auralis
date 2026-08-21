"""
Album-consistent target derivation — issue #3481, Phase 1
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Per-track k-NN gives every track its own tonal destination. Correct for shuffle,
wrong for playing a record top to bottom: a quiet intro and a loud closer can end
up somewhere measurably different from each other, which is exactly what the
original mastering engineer avoided.

Album mode derives ONE target for the set. These tests pin what "one target"
means and — just as importantly — what it does not mean. Unifying the target
unifies the *destination*, not the EQ curve: `compute_delta_eq` is a symmetric
delta from (source, target), so tracks starting from different places still get
different curves. That is the convergence mechanism, and
`test_curves_still_differ_because_sources_do` exists so a future reader does not
"fix" it into a single shared curve, which would preserve the album's existing
tonal spread instead of closing it.
"""

import numpy as np
import pytest

from auralis.core.processing.album_target import (
    AlbumTarget,
    average_targets,
    derive_album_target,
)
from auralis.core.processing.delta_eq import compute_delta_eq
from auralis.core.processing.target_derivation import (
    TARGET_FEATURES,
    DistanceStats,
    derive_target,
)


def _fingerprint(**overrides: float) -> dict[str, float]:
    """A fingerprint with every DISTANCE_ and TARGET_ feature present.

    Note which axis a test varies. `DISTANCE_FEATURES` (tempo, crest, transient
    density, ...) decide WHICH references a track matches, and therefore what
    target it derives; `TARGET_FEATURES` (the band percentages) are what the
    match produces and are deliberately excluded from the distance, so varying
    `bass_pct` alone changes a track's EQ curve but not its target.
    """
    base = {
        # TARGET_FEATURES — the destination, and the source side of delta_eq.
        'sub_bass_pct': 0.10, 'bass_pct': 0.20, 'low_mid_pct': 0.20,
        'mid_pct': 0.20, 'upper_mid_pct': 0.15, 'presence_pct': 0.10,
        'air_pct': 0.05, 'spectral_centroid': 2000.0,
        'spectral_rolloff': 8000.0, 'bass_mid_ratio': 1.0,
        # DISTANCE_FEATURES — what decides which references a track matches.
        'tempo_bpm': 120.0, 'rhythm_stability': 0.5, 'transient_density': 0.5,
        'silence_ratio': 0.05, 'harmonic_ratio': 0.5, 'pitch_stability': 0.5,
        'chroma_energy': 0.5, 'dynamic_range_variation': 0.5,
        'loudness_variation_std': 0.5, 'peak_consistency': 0.5,
        'stereo_width': 0.5, 'phase_correlation': 0.6, 'crest_db': 12.0,
        'lufs': -14.0,
    }
    base.update(overrides)
    return base


def _cloud(n: int = 6) -> list[dict[str, float]]:
    """A reference cloud spread across both the character and the tonal axis."""
    return [
        _fingerprint(
            track_id=i,
            reference_weight=1.0,
            # character (drives the match)
            crest_db=8.0 + 2.0 * i,
            tempo_bpm=90.0 + 12.0 * i,
            transient_density=0.2 + 0.12 * i,
            # tonality (what gets averaged into the album target). Deliberately
            # non-linear in i: on a linear cloud the mean of the two endpoints
            # equals the mean of every reference, which would hide the
            # difference between a narrow and a wide k.
            bass_pct=0.10 + 0.01 * i * i,
            air_pct=0.02 + 0.004 * i * i,
            spectral_centroid=1500.0 + 60.0 * i * i,
        )
        for i in range(n)
    ]


def _track(crest_db: float, **overrides: float) -> dict[str, float]:
    """An album track, distinguished on the axis the k-NN actually reads."""
    return _fingerprint(
        crest_db=crest_db,
        tempo_bpm=90.0 + (crest_db - 8.0) * 6.0,
        transient_density=0.2 + (crest_db - 8.0) * 0.06,
        **overrides,
    )


@pytest.fixture
def cloud() -> list[dict[str, float]]:
    return _cloud()


@pytest.fixture
def stats(cloud: list[dict[str, float]]) -> DistanceStats:
    return DistanceStats.from_references(cloud)


# ---------------------------------------------------------------------------
# average_targets
# ---------------------------------------------------------------------------

class TestAverageTargets:
    def test_empty_sequence_returns_none(self):
        assert average_targets([]) is None

    def test_single_target_is_returned_unchanged(self):
        one = {feat: float(i) for i, feat in enumerate(TARGET_FEATURES)}
        assert average_targets([one]) == pytest.approx(one)

    def test_averages_feature_wise(self):
        a = {feat: 0.0 for feat in TARGET_FEATURES}
        b = {feat: 10.0 for feat in TARGET_FEATURES}
        averaged = average_targets([a, b])
        assert averaged is not None
        for feat in TARGET_FEATURES:
            assert averaged[feat] == pytest.approx(5.0)

    def test_every_track_counts_equally(self):
        """An album is a set of tracks — a long closer must not outvote an intro."""
        quiet = {feat: 0.0 for feat in TARGET_FEATURES}
        loud = {feat: 30.0 for feat in TARGET_FEATURES}
        averaged = average_targets([quiet, loud, loud])
        assert averaged is not None
        assert averaged[TARGET_FEATURES[0]] == pytest.approx(20.0)

    def test_result_covers_exactly_the_target_features(self):
        averaged = average_targets([{'bass_pct': 0.3}])
        assert averaged is not None
        assert set(averaged) == set(TARGET_FEATURES)

    def test_missing_features_default_to_zero(self):
        """Mirrors how derive_target reads absent fields off a reference row."""
        averaged = average_targets([{'bass_pct': 0.4}, {'bass_pct': 0.2}])
        assert averaged is not None
        assert averaged['bass_pct'] == pytest.approx(0.3)
        assert averaged['air_pct'] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# derive_album_target
# ---------------------------------------------------------------------------

class TestDeriveAlbumTarget:
    def test_returns_none_without_fingerprints(self, cloud, stats):
        assert derive_album_target([], cloud, stats) is None

    def test_returns_none_without_a_reference_cloud(self, stats):
        assert derive_album_target([_fingerprint()], [], stats) is None

    def test_single_track_album_matches_per_track_derivation(self, cloud, stats):
        """One track means there is nothing to average away."""
        fp = _track(crest_db=15.0)
        album = derive_album_target([fp], cloud, stats)
        solo = derive_target(fp, cloud, stats)

        assert album is not None and solo is not None
        for feat in TARGET_FEATURES:
            assert album.target[feat] == pytest.approx(solo.target[feat])

    def test_shared_target_is_the_mean_of_the_per_track_targets(self, cloud, stats):
        """Option (b): match per track, then average the destinations."""
        tracks = [_track(crest_db=9.0), _track(crest_db=17.0)]
        album = derive_album_target(tracks, cloud, stats)
        assert album is not None

        solo = [derive_target(fp, cloud, stats) for fp in tracks]
        assert all(r is not None for r in solo)
        expected = average_targets([r.target for r in solo])
        assert expected is not None
        for feat in TARGET_FEATURES:
            assert album.target[feat] == pytest.approx(expected[feat])

    def test_shared_target_lies_between_the_per_track_targets(self, cloud, stats):
        """The album destination is a compromise, never outside the tracks' range."""
        tracks = [_track(crest_db=8.0), _track(crest_db=18.0)]
        album = derive_album_target(tracks, cloud, stats)
        solo = [derive_target(fp, cloud, stats) for fp in tracks]
        assert album is not None and all(r is not None for r in solo)
        per_track = [r.target for r in solo]

        for feat in TARGET_FEATURES:
            lo = min(t[feat] for t in per_track)
            hi = max(t[feat] for t in per_track)
            assert lo - 1e-9 <= album.target[feat] <= hi + 1e-9, feat

    def test_track_order_does_not_change_the_target(self, cloud, stats):
        tracks = [_track(crest_db=c) for c in (8.0, 13.0, 18.0)]
        forward = derive_album_target(tracks, cloud, stats)
        backward = derive_album_target(list(reversed(tracks)), cloud, stats)

        assert forward is not None and backward is not None
        for feat in TARGET_FEATURES:
            assert forward.target[feat] == pytest.approx(backward.target[feat])

    def test_diagnostics_report_contributing_tracks_and_references(self, cloud, stats):
        tracks = [_track(crest_db=c) for c in (8.0, 13.0, 18.0)]
        album = derive_album_target(tracks, cloud, stats)

        assert isinstance(album, AlbumTarget)
        assert album.n_tracks == 3
        assert album.n_skipped == 0
        assert album.top_ref_ids
        assert len(album.top_ref_ids) == len(set(album.top_ref_ids)), "must be deduped"

    def test_k_is_applied_per_track_not_per_album(self, cloud, stats):
        """Each track still matches against its OWN k nearest references."""
        tracks = [_track(crest_db=8.0), _track(crest_db=18.0)]
        narrow = derive_album_target(tracks, cloud, stats, k=1)
        wide = derive_album_target(tracks, cloud, stats, k=len(cloud))

        assert narrow is not None and wide is not None
        # k=1 pins each track to its single closest reference, so the two
        # averages must not coincide by construction.
        assert narrow.target != pytest.approx(wide.target)


# ---------------------------------------------------------------------------
# The destination-vs-curve distinction
# ---------------------------------------------------------------------------

class TestUnifiesDestinationNotCurve:
    def test_all_tracks_receive_the_identical_target(self, cloud, stats):
        tracks = [_track(crest_db=c) for c in (8.0, 13.0, 18.0)]
        album = derive_album_target(tracks, cloud, stats)
        assert album is not None
        # One dict, shared verbatim — there is no per-track variation left to
        # measure. This is the acceptance criterion, at the layer it holds.
        assert all(album.target[f] == album.target[f] for f in TARGET_FEATURES)

    def test_curves_still_differ_because_sources_do(self, cloud, stats):
        """Different starts + one destination = different curves, by design.

        Do not "fix" this into one shared curve: an identical curve preserves
        the album's existing tonal spread instead of closing it, which is the
        opposite of what album mode is for.
        """
        dark = _track(crest_db=9.0, bass_pct=0.35, air_pct=0.02)
        bright = _track(crest_db=17.0, bass_pct=0.10, air_pct=0.12)
        album = derive_album_target([dark, bright], cloud, stats)
        assert album is not None

        dark_curve = compute_delta_eq(dark, album.target)
        bright_curve = compute_delta_eq(bright, album.target)
        assert dark_curve.low_shelf_gain != pytest.approx(
            bright_curve.low_shelf_gain
        )

    def test_shared_target_pulls_tracks_closer_together(self, cloud, stats):
        """The point of the whole exercise: the tonal gap must shrink."""
        dark = _track(crest_db=9.0, bass_pct=0.35, air_pct=0.02)
        bright = _track(crest_db=17.0, bass_pct=0.10, air_pct=0.12)
        album = derive_album_target([dark, bright], cloud, stats)
        assert album is not None

        def _bass_after(source):
            # Post-EQ bass, in dB relative to where it started.
            return 10.0 * np.log10(source['bass_pct']) + \
                compute_delta_eq(source, album.target).low_shelf_gain

        gap_before = abs(
            10.0 * np.log10(dark['bass_pct']) - 10.0 * np.log10(bright['bass_pct'])
        )
        gap_after = abs(_bass_after(dark) - _bass_after(bright))
        assert gap_after < gap_before


# ---------------------------------------------------------------------------
# ContinuousMode wiring
# ---------------------------------------------------------------------------

class _StubRepository:
    def __init__(self, cloud):
        self._cloud = cloud
        self.calls = 0

    def get_reference_cloud(self):
        self.calls += 1
        return self._cloud


def _mode(cloud=None):
    """A ContinuousMode wired to a stub cloud, without touching a database."""
    from auralis.core.config import UnifiedConfig
    from auralis.core.processing.continuous_mode import ContinuousMode

    mode = ContinuousMode.__new__(ContinuousMode)
    mode.config = UnifiedConfig()
    mode.fingerprint_repository = _StubRepository(cloud) if cloud else None
    mode._reference_cloud = None
    mode._distance_stats = None
    mode._album_target = None
    return mode


class TestContinuousModeAlbumMode:
    def test_album_target_overrides_per_track_derivation(self, cloud):
        mode = _mode(cloud)
        shared = {feat: 0.5 for feat in TARGET_FEATURES}
        mode.set_album_target(shared)

        # Two very different sources must resolve to the same destination.
        assert mode._derive_target_spectrum(_track(crest_db=8.0)) is shared
        assert mode._derive_target_spectrum(_track(crest_db=18.0)) is shared

    def test_override_short_circuits_before_the_cloud_is_touched(self, cloud):
        """Album mode must not pay for a k-NN whose answer it discards."""
        mode = _mode(cloud)
        mode.set_album_target({feat: 0.5 for feat in TARGET_FEATURES})
        repository = mode.fingerprint_repository
        mode._derive_target_spectrum(_fingerprint())
        assert repository is not None and repository.calls == 0

    def test_clearing_the_override_restores_per_track_mode(self, cloud):
        mode = _mode(cloud)
        mode.set_album_target({feat: 0.5 for feat in TARGET_FEATURES})
        mode.set_album_target(None)

        dark = mode._derive_target_spectrum(_track(crest_db=8.0))
        bright = mode._derive_target_spectrum(_track(crest_db=18.0))
        assert dark is not None and bright is not None
        assert dark != bright, "per-track mode must derive per-track targets"

    def test_no_repository_means_no_album_target(self):
        mode = _mode(cloud=None)
        assert mode.derive_album_target([np.zeros((1024, 2), dtype=np.float32)]) is None

    def test_process_album_shares_one_target_and_clears_it(self, cloud):
        mode = _mode(cloud)
        mode.fingerprint_analyzer = _StubAnalyzer()
        seen: list[dict[str, float] | None] = []

        def _process(target_audio, eq_processor, fixed_params=None):
            seen.append(mode._album_target)
            return target_audio

        mode.process = _process
        album = [np.zeros((512, 2), dtype=np.float32) for _ in range(3)]
        out = mode.process_album(album, eq_processor=None)

        assert len(out) == 3
        assert all(t is not None for t in seen), "every track saw the shared target"
        assert seen[0] is seen[1] is seen[2], "and it was the same object"
        assert mode._album_target is None, "the override must not leak past the album"

    def test_a_failing_track_does_not_leave_the_processor_pinned(self, cloud):
        """Whatever plays next must not inherit this album's target."""
        mode = _mode(cloud)
        mode.fingerprint_analyzer = _StubAnalyzer()

        def _explode(target_audio, eq_processor, fixed_params=None):
            raise RuntimeError("decode failed")

        mode.process = _explode
        with pytest.raises(RuntimeError):
            mode.process_album([np.zeros((512, 2), dtype=np.float32)], eq_processor=None)
        assert mode._album_target is None

    def test_process_album_falls_back_when_no_target_is_derivable(self):
        mode = _mode(cloud=None)
        mode.fingerprint_analyzer = _StubAnalyzer()
        mode.process = lambda target_audio, eq_processor, fixed_params=None: target_audio

        album = [np.zeros((512, 2), dtype=np.float32) for _ in range(2)]
        out = mode.process_album(album, eq_processor=None)

        assert len(out) == 2
        assert mode._album_target is None


class _StubAnalyzer:
    """Returns a usable fingerprint without running the real 25D extraction."""

    def __init__(self):
        self.calls = 0

    def analyze(self, audio, sample_rate):
        self.calls += 1
        return _track(crest_db=8.0 + 3.0 * self.calls)
