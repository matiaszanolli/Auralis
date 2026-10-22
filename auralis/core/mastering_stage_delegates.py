"""
Per-stage delegates for SimpleMasteringPipeline (split from
simple_mastering.py, #5838): one ``_apply_*`` method per DSP stage, each a
thin call into ``core/stages/`` with the pipeline's config.
"""

from typing import Any

import numpy as np

from .mastering_config import SimpleMasteringConfig
from .stages import (
    air_enhancement,
    bass_enhancement,
    clarity_boost,
    harmonic_exciter,
    loudness_maximizer,
    mid_warmth,
    presence_enhancement,
    stereo_expansion,
    sub_bass_control,
    transient_shaper,
)
from .stages import (
    resonance_notches as resonance_notches_stage,
)


class StageDelegatesMixin:
    """Reads ``config`` and ``_notches`` set by SimpleMasteringPipeline.__init__."""

    config: SimpleMasteringConfig
    _notches: Any

    def _apply_loudness_maximizer(
        self, audio: np.ndarray, source_lufs: float, source_crest_db: float,
        sample_rate: int, verbose: bool,
    ) -> tuple[np.ndarray, dict[str, Any] | None]:
        return loudness_maximizer.apply(
            audio, source_lufs, source_crest_db, sample_rate, verbose, self.config
        )

    def _apply_resonance_notches(
        self, audio: np.ndarray, sample_rate: int, verbose: bool
    ) -> tuple[np.ndarray, dict[str, Any] | None]:
        return resonance_notches_stage.apply(audio, sample_rate, self._notches, verbose)

    def _apply_transient_shaper(
        self, audio: np.ndarray, bass_pct: float, low_mid_pct: float,
        crest_db: float, intensity: float, sample_rate: int, verbose: bool,
    ) -> tuple[np.ndarray, dict[str, Any] | None]:
        return transient_shaper.apply(audio, bass_pct, low_mid_pct, crest_db, intensity, sample_rate, verbose, self.config)

    def _apply_clarity_boost(
        self, audio: np.ndarray, upper_mid_pct: float, intensity: float,
        sample_rate: int, verbose: bool, hf_lift: float = 1.0,
        bass_pct: float = 0.0, mid_pct: float = 0.0,
    ) -> tuple[np.ndarray, dict[str, Any] | None]:
        return clarity_boost.apply(audio, upper_mid_pct, intensity, sample_rate, verbose, self.config, hf_lift, bass_pct, mid_pct)

    def _apply_stereo_expansion(
        self, audio: np.ndarray, current_width: float, intensity: float,
        sample_rate: int, verbose: bool,
        spectral_centroid: float = 0.5, air_pct: float = 0.1,
        phase_correlation: float = 1.0,
    ) -> tuple[np.ndarray, dict[str, Any] | None]:
        return stereo_expansion.apply(audio, current_width, intensity, sample_rate, verbose,
                                       spectral_centroid=spectral_centroid,
                                       air_pct=air_pct, phase_correlation=phase_correlation)

    def _apply_bass_enhancement(
        self, audio: np.ndarray, bass_pct: float, intensity: float,
        sample_rate: int, verbose: bool,
        mid_pct: float = 0.0, upper_mid_pct: float = 0.0,
        presence_pct: float = 0.0,
    ) -> tuple[np.ndarray, dict[str, Any] | None]:
        return bass_enhancement.apply(
            audio,
            bass_pct,
            intensity,
            sample_rate,
            verbose,
            self.config,
            mid_pct,
            upper_mid_pct,
            presence_pct,
        )

    def _apply_sub_bass_control(
        self, audio: np.ndarray, sub_bass_pct: float, bass_pct: float,
        intensity: float, sample_rate: int, verbose: bool,
    ) -> tuple[np.ndarray, dict[str, Any] | None]:
        return sub_bass_control.apply(audio, sub_bass_pct, bass_pct, intensity, sample_rate, verbose, self.config)

    def _apply_mid_warmth(
        self, audio: np.ndarray, low_mid_pct: float, mid_pct: float,
        intensity: float, sample_rate: int, verbose: bool,
    ) -> tuple[np.ndarray, dict[str, Any] | None]:
        return mid_warmth.apply(audio, low_mid_pct, mid_pct, intensity, sample_rate, verbose, self.config)

    def _apply_presence_enhancement(
        self, audio: np.ndarray, presence_pct: float, upper_mid_pct: float,
        intensity: float, sample_rate: int, verbose: bool, hf_lift: float = 1.0,
    ) -> tuple[np.ndarray, dict[str, Any] | None]:
        return presence_enhancement.apply(audio, presence_pct, upper_mid_pct, intensity, sample_rate, verbose, self.config, hf_lift)

    def _apply_harmonic_exciter(
        self, audio: np.ndarray, presence_pct: float, air_pct: float,
        spectral_rolloff: float, intensity: float, sample_rate: int, verbose: bool,
        hf_lift: float = 1.0,
    ) -> tuple[np.ndarray, dict[str, Any] | None]:
        return harmonic_exciter.apply(audio, presence_pct, air_pct, spectral_rolloff, intensity, sample_rate, verbose, self.config, hf_lift)

    def _apply_air_enhancement(
        self, audio: np.ndarray, air_pct: float, spectral_rolloff: float,
        intensity: float, sample_rate: int, verbose: bool, hf_lift: float = 1.0,
    ) -> tuple[np.ndarray, dict[str, Any] | None]:
        return air_enhancement.apply(audio, air_pct, spectral_rolloff, intensity, sample_rate, verbose, self.config, hf_lift)
