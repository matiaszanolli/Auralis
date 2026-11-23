"""
Continuous Space Processing Mode
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Processing mode using continuous parameter space instead of discrete presets.
Generates optimal parameters from audio fingerprints.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)

This file owns one job: turning audio into ``ProcessingParameters``, either from
a fingerprint and the reference cloud or from a fixed-targets dict. What is then
done with those parameters lives alongside it (#4254) --
``continuous_stages.py`` holds the guarded stage sequence,
``continuous_dsp_ops.py`` the DSP primitives it drives, ``continuous_guards.py``
the guard knees, and ``fixed_target_params.py`` the fixed-targets conversion.
"""

from typing import Any

import numpy as np

from auralis.analysis.fingerprint import fingerprint_preloaded
from auralis.core.analysis import ContentAnalyzer

from ...dsp.utils.adaptive import calculate_loudness_units
from ...utils.logging import debug
from .continuous_space import ProcessingSpaceMapper
from .continuous_space_types import ProcessingParameters
from .continuous_stages import ContinuousStagesMixin
from .fixed_target_params import convert_targets_to_parameters
from .mastering_targets import generate_targets_from_fingerprint
from .reference_cloud import ReferenceCloud


class ContinuousMode(ContinuousStagesMixin):
    """
    Continuous space processing mode - intelligent mastering using fingerprints.

    Instead of discrete presets, this mode fingerprints the audio it is given
    and derives its parameters with the same targets law as the streaming fixed
    targets (``mastering_targets``), pulling the EQ toward the reference cloud's
    soft k-NN target when one exists. Fixed targets skip the fingerprint.
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

        # Reference cloud, lazy-loaded on the first process() call so the DB is
        # not touched during construction; see ReferenceCloud for the refresh rules.
        self.reference_cloud = ReferenceCloud(lambda: self.fingerprint_repository)

        # Initialize continuous space components
        self.space_mapper = ProcessingSpaceMapper()

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

    def reset_run_state(self) -> None:
        """Clear the last run's fingerprint, coordinates and parameters (#6088)."""
        self.last_fingerprint = None
        self.last_coordinates = None
        self.last_parameters = None

    def process(self, target_audio: np.ndarray, eq_processor: Any,
                fixed_params: dict[str, Any] | None = None, consume_input: bool = False) -> np.ndarray:
        """Process audio using continuous parameter space.

        Dispatches to parameter resolution then DSP application, which share one
        loudness reading of the input. ``fixed_params`` selects the fast path.

        ``consume_input`` (#6717): the caller created ``target_audio`` and reads
        nothing in it afterwards (HybridProcessor's validated input), so the
        stages may use it as their working buffer instead of a whole-track copy.
        Ignored while the quality comparison is on: it reads the original after
        the stages have run.
        """
        debug("Applying continuous space processing")
        input_lufs = calculate_loudness_units(target_audio, self.config.internal_sample_rate)
        params = self._resolve_parameters(target_audio, fixed_params)
        if params is None:
            return target_audio.copy()
        # Never bound here: a local would pin this copy through every stage (#6717).
        consume = consume_input and not self.config.quality_gate_enabled
        return self._apply_dsp_stages(target_audio, target_audio if consume else target_audio.copy(),
                                      eq_processor, params, input_lufs, overwrite_input=True)

    def _resolve_parameters(
        self,
        processed_audio: np.ndarray,
        fixed_params: dict[str, Any] | None,
    ) -> Any:
        """Resolve processing parameters from fixed params or fingerprint.

        Fast path: convert ``fixed_params`` dict directly (8× faster, no fingerprint).
        Fingerprint path: extract 25D fingerprint → k-NN band centers → targets → params.
        Returns the resolved ``ProcessingParameters``, or ``None`` when the audio is too
        short to fingerprint (skip, return the copy). An engine failure raises
        ``FingerprintUnavailable`` instead of bypassing silently as success (#6107).
        """
        if fixed_params is not None:
            debug("⚡ Using fixed parameters from .25d file (fast path)")
            params = convert_targets_to_parameters(fixed_params)
            self.last_parameters = params
            # last_fingerprint and last_coordinates remain from the first extraction
            return params

        # Step 1: Extract 25D fingerprint
        fingerprint = fingerprint_preloaded(
            self.fingerprint_analyzer, processed_audio, self.config.internal_sample_rate
        )
        self.last_fingerprint = fingerprint

        if not fingerprint:
            debug("Fingerprint extraction returned empty — skipping continuous processing")
            return None

        debug(f"[Continuous Space] Fingerprint extracted: Bass: {fingerprint['bass_pct']:.1f}%, Crest: {fingerprint['crest_db']:.1f} dB, LUFS: {fingerprint['lufs']:.1f}")

        # Step 2: Map to the processing space. The coordinates are telemetry for
        # the processing-parameters endpoint; no parameter is derived from them.
        coords = self.space_mapper.map_fingerprint_to_space(fingerprint)
        self.last_coordinates = coords
        debug(f"[Continuous Space] Coordinates: {coords}")

        # Step 3: The band centers to pull toward -- the soft k-NN target from the
        # reference cloud, or the corpus centers when there is no cloud yet.
        band_centers = self.reference_cloud.band_centers(fingerprint)

        # Step 4: The same targets law the streaming fixed targets come from, so a
        # whole-file job and a stream of the same audio are mastered alike (#6356).
        # source_lufs and target_lufs are both on the fingerprint's scale, and final
        # normalisation applies only their difference.
        targets = generate_targets_from_fingerprint(fingerprint, band_centers)
        params = convert_targets_to_parameters(targets)
        self.last_parameters = params
        debug(f"[Continuous Space] Parameters: {params}")
        return params
