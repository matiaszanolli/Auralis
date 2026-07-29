"""
Processing Branch Base
~~~~~~~~~~~~~~~~~~~~~~~

Abstract base class for the mastering processing path.

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import numpy as np

from ...utils.audio_validation import validate_audio_finite
from ..mastering_config import SimpleMasteringConfig
from ..utils import FingerprintUnpacker

if TYPE_CHECKING:
    from ..simple_mastering import SimpleMasteringPipeline


class ProcessingBranch(ABC):
    """
    Shared interface for the single measurement-driven mastering path.

    ``SimpleMasteringPipeline._process()`` performs the safety pre-stage, then
    calls one fixed stage order for every source. Fingerprint values continuously
    modulate individual DSP controls; no content label selects an implementation.
    """

    def __init__(self, pipeline: 'SimpleMasteringPipeline'):
        """
        Initialize processing branch.

        Args:
            pipeline: SimpleMasteringPipeline instance for enhancement method delegation
        """
        self.pipeline = pipeline

    def _assert_finite(self, audio: np.ndarray, stage: str) -> np.ndarray:
        """Inter-stage NaN/Inf spot-check (#4099).

        The pipeline validates only at entry and (with repair) at exit, so a
        non-finite value produced by any one of the ~10 intermediate stages
        propagates silently to the end, where ``sanitize_audio`` zeros the whole
        output — erasing which stage was at fault. Calling this at stage-group
        boundaries with ``repair=False`` raises immediately, naming the group,
        so the root-cause stage is localized. The all-finite fast path is two
        cheap array scans. The final ``sanitize_audio`` boundary is unchanged,
        preserving production resilience.

        Returns ``audio`` unchanged (for inline use:
        ``processed = self._assert_finite(processed, "...")``).
        """
        return validate_audio_finite(audio, context=f"SimpleMastering {stage}", repair=False)

    @abstractmethod
    def apply(
        self,
        audio: np.ndarray,
        unpacker: FingerprintUnpacker,
        peak_db: float,
        effective_intensity: float,
        sample_rate: int,
        config: SimpleMasteringConfig,
        verbose: bool
    ) -> tuple[np.ndarray, dict]:
        """
        Apply branch-specific processing.

        Args:
            audio: Input audio (channels, samples)
            unpacker: Fingerprint unpacker with all 25 dimensions
            peak_db: WHOLE-SONG peak level in dB (scanned once in master_file,
                not this chunk's own peak) — used as the headroom reference for
                makeup gain so every chunk gets consistent gain-staging. Distinct from the
                per-chunk peak_db used earlier in _process() for clip
                prevention.
            effective_intensity: Adaptive intensity (from _calculate_intensity)
            sample_rate: Sample rate in Hz
            config: Configuration constants
            verbose: Print progress

        Returns:
            Tuple of (processed_audio, info_dict)
        """
        pass
