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

import dataclasses
from typing import Any

import numpy as np

from auralis.analysis.fingerprint import fingerprint_preloaded
from auralis.core.analysis import ContentAnalyzer

from ...dsp.utils.adaptive import calculate_loudness_units, proxy_to_k_offset_db
from ...utils.logging import debug
from ..utils.fingerprint_unpacker import FingerprintUnpacker
from .continuous_space import ProcessingSpaceMapper
from .continuous_space_types import ProcessingParameters
from .continuous_stages import ContinuousStagesMixin
from .fixed_target_params import convert_targets_to_parameters
from .parameter_generator import ContinuousParameterGenerator
from .reference_cloud import ReferenceCloud


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

        # Reference cloud, lazy-loaded on the first process() call so the DB is
        # not touched during construction; see ReferenceCloud for the refresh rules.
        self.reference_cloud = ReferenceCloud(lambda: self.fingerprint_repository)

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

    def reset_run_state(self) -> None:
        """Clear the last run's fingerprint, coordinates and parameters (#6088)."""
        self.last_fingerprint = None
        self.last_coordinates = None
        self.last_parameters = None

    def process(self, target_audio: np.ndarray, eq_processor: Any,
                fixed_params: dict[str, Any] | None = None) -> np.ndarray:
        """Process audio using continuous parameter space.

        Dispatches to parameter resolution then DSP application, which share one
        loudness reading of the input. ``fixed_params`` selects the fast path.
        """
        debug("Applying continuous space processing")
        input_lufs = calculate_loudness_units(target_audio, self.config.internal_sample_rate)
        params = self._resolve_parameters(target_audio, fixed_params, input_lufs)
        if params is None:
            return target_audio.copy()
        # Never bound here: a local would pin this copy through every stage (#6717).
        return self._apply_dsp_stages(target_audio, target_audio.copy(), eq_processor, params, input_lufs)

    def _resolve_parameters(
        self,
        processed_audio: np.ndarray,
        fixed_params: dict[str, Any] | None, input_lufs: float | None = None,
    ) -> Any:
        """Resolve processing parameters from fixed params or fingerprint.

        Fast path: convert ``fixed_params`` dict directly (8× faster, no fingerprint).
        Fingerprint path: extract 25D fingerprint → map coordinates → generate params.
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

        # Step 2: Map to 3D processing space
        coords = self.space_mapper.map_fingerprint_to_space(fingerprint)
        self.last_coordinates = coords
        debug(f"[Continuous Space] Coordinates: {coords}")

        # Step 3: Derive a continuous target spectrum from the reference
        # cloud (Phase 4). If no cloud is available (no repository, or
        # nothing flagged is_reference yet), target_spectrum is None and
        # generate_parameters falls back to the legacy deficit-based curve.
        target_spectrum = self.reference_cloud.target_spectrum(fingerprint)

        # Step 4: Generate processing parameters
        params = self.param_generator.generate_parameters(coords, target_spectrum=target_spectrum)

        # #5700: target_lufs was built on the fingerprint's RMS-proxy scale but the
        # final normalisation chases it with the K-weighted meter, which reads ~3-4 dB
        # higher, so the realised gain was `lift - offset` and loud masters were
        # attenuated. Express the target on the meter's scale with the offset measured
        # on THIS chunk (the fixed-target path keeps both on the proxy scale).
        k_offset = proxy_to_k_offset_db(
            processed_audio,
            FingerprintUnpacker.from_dict(fingerprint).lufs,
            self.config.internal_sample_rate, measured_lufs=input_lufs,
        )
        params = dataclasses.replace(params, target_lufs=params.target_lufs + k_offset)
        self.last_parameters = params
        debug(f"[Continuous Space] Parameters: {params} (K-scale offset {k_offset:+.2f} dB)")
        return params
