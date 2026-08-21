"""
Continuous Space Processing Mode
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Processing mode using continuous parameter space instead of discrete presets.
Generates optimal parameters from audio fingerprints.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

This file owns one job: turning audio into ``ProcessingParameters``, either from
a fingerprint and the reference cloud or from a fixed-targets dict. What is then
done with those parameters lives alongside it (#4254) --
``continuous_stages.py`` holds the guarded stage sequence,
``continuous_dsp_ops.py`` the DSP primitives it drives, ``continuous_guards.py``
the guard knees, and ``fixed_target_params.py`` the fixed-targets conversion.
"""

from collections.abc import Sequence
from typing import Any

import numpy as np

from auralis.core.analysis import ContentAnalyzer

from ...utils.logging import debug
from .album_target import AlbumTarget, derive_album_target
from .continuous_space import (
    PreferenceVector,
    ProcessingParameters,
    ProcessingSpaceMapper,
)
from .continuous_stages import ContinuousStagesMixin
from .fixed_target_params import convert_targets_to_parameters
from .parameter_generator import ContinuousParameterGenerator


class ContinuousMode(ContinuousStagesMixin):
    """
    Continuous space processing mode - intelligent mastering using fingerprints.

    Instead of discrete presets, this mode maps the audio's 25D fingerprint
    to a continuous 3D processing space and generates optimal parameters
    for that specific position.
    """

    def __init__(
        self,
        config: Any,
        content_analyzer: Any,
        fingerprint_analyzer: Any,
        fingerprint_repository: Any | None = None,
    ) -> None:
        """
        Initialize continuous space processor.

        Args:
            config: UnifiedConfig instance
            content_analyzer: ContentAnalyzer for audio analysis
            fingerprint_analyzer: AudioFingerprintAnalyzer for 25D fingerprints
            fingerprint_repository: Optional FingerprintRepository used to fetch
                the reference cloud (is_reference=True fingerprints). When
                provided AND the cloud is non-empty, the EQ stage uses the
                continuous delta-from-target derivation (Phase 4). Otherwise
                falls back to the legacy deficit-based curve.
        """
        self.config = config
        self.content_analyzer: ContentAnalyzer = content_analyzer
        self.fingerprint_analyzer = fingerprint_analyzer
        self.fingerprint_repository = fingerprint_repository

        # Reference-cloud caches (lazy-loaded on first process() call so we
        # don't hit the DB during construction). Invalidate by setting to None.
        self._reference_cloud: list[Any] | None = None
        self._distance_stats: Any | None = None

        # Album-consistency override (#3481). When set, every process() call
        # uses this one target instead of deriving its own, so tracks played as
        # an album converge on a shared tonality. None = per-track mode.
        self._album_target: dict[str, float] | None = None

        # Initialize continuous space components
        self.space_mapper = ProcessingSpaceMapper()
        self.param_generator = ContinuousParameterGenerator()

        # Store last fingerprint and parameters for debugging/learning
        self.last_fingerprint = None
        self.last_coordinates: Any | None = None  # ProcessingCoordinates
        self.last_parameters: ProcessingParameters | None = None

        # Cross-dimensional analysis (populated after each process() call)
        self.last_journal = None
        self.last_side_effects = []
        self.last_quality_comparison = None
        self.last_mastering_measurements = None

        # Quality-gate sampling counter (#3460): only run the gate on selected
        # process() calls per config.quality_gate_interval.
        self._quality_gate_call_count = 0

    def _derive_target_spectrum(self, fingerprint: dict[str, Any]) -> dict[str, float] | None:
        """Lazy-load the reference cloud and derive a continuous target.

        Returns None when no repository is wired or the cloud is empty —
        the parameter generator then falls back to legacy deficit-based math.
        Cached across process() calls so we only hit the DB once per session.
        """
        # Album mode short-circuits the per-track k-NN entirely (#3481): the
        # shared target IS the answer, and re-deriving one here would be the
        # per-track drift album mode exists to remove.
        if self._album_target is not None:
            return self._album_target

        context = self._reference_context()
        if context is None:
            return None
        references, stats = context

        from .target_derivation import derive_target
        result = derive_target(fingerprint, references, stats)
        if result is None:
            return None
        debug(
            f"[Mastering] Target derived from {result.n_matched} references "
            f"(top: {result.top_ref_ids[:3]})"
        )
        return result.target

    def _reference_context(self) -> tuple[list[Any], Any] | None:
        """Lazy-load the reference cloud and its z-score stats.

        Cached across process() calls so we only hit the DB once per session.
        Returns None when no repository is wired or the cloud is empty — every
        caller then falls back to legacy deficit-based math.
        """
        if self.fingerprint_repository is None:
            return None

        # Lazy load on first call (and only once)
        if self._reference_cloud is None:
            try:
                self._reference_cloud = self.fingerprint_repository.get_reference_cloud()
            except Exception as e:
                debug(f"[Mastering] Failed to load reference cloud: {e}")
                self._reference_cloud = []

        if not self._reference_cloud:
            return None

        # Fit z-score stats once per cached cloud
        if self._distance_stats is None:
            from .target_derivation import DistanceStats
            self._distance_stats = DistanceStats.from_references(self._reference_cloud)

        return self._reference_cloud, self._distance_stats

    def set_album_target(self, target: dict[str, float] | None) -> None:
        """Pin every subsequent process() call to one shared target (#3481).

        Pass None to return to per-track derivation. Only the target spectrum is
        shared: each track still gets its own coordinates, dynamics, loudness and
        stereo width, and its own EQ curve — the curve is a symmetric delta from
        that track's source to this target, which is how tracks starting from
        different places converge rather than staying different.
        """
        self._album_target = target

    def derive_album_target(
        self, album_audio: Sequence[np.ndarray]
    ) -> AlbumTarget | None:
        """Fingerprint every track of an album and derive one shared target.

        Returns None when the reference cloud is unavailable or no track yielded
        a target; the caller should then simply not enter album mode.
        """
        context = self._reference_context()
        if context is None:
            return None
        references, stats = context

        fingerprints = [
            self.fingerprint_analyzer.analyze(audio, self.config.internal_sample_rate)
            for audio in album_audio
        ]
        return derive_album_target(
            [fp for fp in fingerprints if fp], references, stats
        )

    def process_album(
        self, album_audio: Sequence[np.ndarray], eq_processor: Any
    ) -> list[np.ndarray]:
        """Process a whole album against one shared target (#3481).

        Falls back to plain per-track processing when no shared target can be
        derived, so this is always safe to call. The override is cleared in a
        ``finally`` — a track that raises mid-album must not leave the processor
        pinned to an album target for whatever plays next.
        """
        album = list(album_audio)
        album_target = self.derive_album_target(album)
        if album_target is None:
            debug("[Album] No shared target available — processing per track")
            return [self.process(audio, eq_processor) for audio in album]

        debug(
            f"[Album] Processing {len(album)} tracks against a shared target "
            f"({album_target.n_tracks} contributed, {album_target.n_skipped} skipped)"
        )
        self.set_album_target(album_target.target)
        try:
            return [self.process(audio, eq_processor) for audio in album]
        finally:
            self.set_album_target(None)

    def process(self, target_audio: np.ndarray, eq_processor: Any,
                fixed_params: dict[str, Any] | None = None) -> np.ndarray:
        """Process audio using continuous parameter space.

        Dispatches to parameter resolution then DSP application.
        ``fixed_params`` selects the fast path (no fingerprint extraction).
        """
        debug("Applying continuous space processing")
        processed_audio = target_audio.copy()
        params = self._resolve_parameters(processed_audio, fixed_params)
        if params is None:
            return processed_audio
        return self._apply_dsp_stages(target_audio, processed_audio, eq_processor, params)

    def _resolve_parameters(
        self,
        processed_audio: np.ndarray,
        fixed_params: dict[str, Any] | None,
    ) -> Any:
        """Resolve processing parameters from fixed params or fingerprint.

        Fast path: convert ``fixed_params`` dict directly (8× faster, no fingerprint).
        Fingerprint path: extract 25D fingerprint → map coordinates → generate params.

        Returns the resolved ``ProcessingParameters``, or ``None`` when fingerprint
        extraction returns empty (caller should skip processing and return the copy).
        """
        if fixed_params is not None:
            debug("⚡ Using fixed parameters from .25d file (fast path)")
            params = convert_targets_to_parameters(fixed_params)
            self.last_parameters = params
            # last_fingerprint and last_coordinates remain from the first extraction
            return params

        # Step 1: Extract 25D fingerprint
        fingerprint = self.fingerprint_analyzer.analyze(
            processed_audio,
            self.config.internal_sample_rate
        )
        self.last_fingerprint = fingerprint

        if not fingerprint:
            debug("Fingerprint extraction returned empty — skipping continuous processing")
            return None

        debug(f"[Continuous Space] Fingerprint extracted: Bass: {fingerprint['bass_pct']:.1f}%, Crest: {fingerprint['crest_db']:.1f} dB, LUFS: {fingerprint['lufs']:.1f}")

        # Step 2: Map to 3D processing space
        coords = self.space_mapper.map_fingerprint_to_space(fingerprint)
        self.last_coordinates = coords
        debug(f"[Continuous Space] Coordinates: {coords}")

        # Step 3: Get user preference (from preset if using legacy mode)
        preset_name = self.config.mastering_profile or 'adaptive'
        preference = PreferenceVector.from_preset_name(preset_name)
        debug(f"[Continuous Space] Preference: {preference}")

        # Step 4: Derive a continuous target spectrum from the reference
        # cloud (Phase 4). If no cloud is available (no repository, or
        # nothing flagged is_reference yet), target_spectrum is None and
        # generate_parameters falls back to the legacy deficit-based curve.
        target_spectrum = self._derive_target_spectrum(fingerprint)

        # Step 5: Generate processing parameters
        params = self.param_generator.generate_parameters(
            coords, preference, target_spectrum=target_spectrum,
        )
        self.last_parameters = params
        debug(f"[Continuous Space] Parameters: {params}")
        return params
