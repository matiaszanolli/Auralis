"""
Processing Branch Base
~~~~~~~~~~~~~~~~~~~~~~~

Abstract base class for material-specific mastering strategies (#4252).

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
    Base class for material-specific processing strategies.

    Each branch handles one type of audio material with appropriate
    processing tailored to its characteristics.

    Canonical stage order & gain-staging contract (#4103)
    -----------------------------------------------------
    All branches are dispatched from ``SimpleMasteringPipeline._process()``
    (simple_mastering.py) AFTER a shared pre-stage (loudness target derivation +
    optional initial peak reduction). Each ``apply()`` runs a FIXED stage order;
    the orders intentionally differ by material type:

    * **CompressedLoudBranch** (LUFS > -12, crest < 13 dB — modern/squashed):
      resonance-notches → RMS-reduction expansion (skipped if hyper-compressed)
      → stereo-expansion → pre-EQ headroom attenuation → harmonic-exciter →
      clarity-boost → presence → air → safety-limiter.
      Restores some lost dynamics via expansion before spectral work.

    * **DynamicLoudBranch** (LUFS > -12, crest >= 13 dB — well-mastered):
      resonance-notches → stereo-expansion → pre-EQ headroom → harmonic-exciter
      → clarity-boost → presence (gentle) → air (gentle) → safety-limiter.
      No expansion and reduced spectral intensity — preserve existing dynamics.

    * **QuietBranch** (LUFS <= -12 — needs makeup gain):
      resonance-notches → adaptive makeup-gain → bass-enhancement →
      sub-bass-control → transient-shaper → mid-warmth → harmonic-exciter →
      clarity-boost → presence → air → multi-dimension-aware soft-clip →
      stereo-expansion → branch-local final ``normalize``.

    Gain-staging / ``needs_output_normalize`` contract — each ``apply()`` returns
    an ``info`` dict whose ``needs_output_normalize`` flag tells the pipeline's
    unified STAGE 3 (simple_mastering.py, ``output_target = 0.95``) whether to
    run a final loudness/peak normalization:

    * Loud branches set ``needs_output_normalize=True`` (defer): they deliberately
      attenuate for pre-EQ headroom and may RMS-expand, so the single unified
      normalize compensates and brings the result to the ceiling.
    * QuietBranch sets ``needs_output_normalize=False`` (self-normalize): it boosts
      with makeup gain up front, ends with soft-clip + its own ``normalize`` to an
      adapted peak, and opts out of the unified stage to avoid double-normalizing.
      This is the mirror-opposite gain-staging of the loud branches and is
      intentional, not an inconsistency.

    Divergence from the ``HybridProcessor`` flow: HybridProcessor's adaptive /
    continuous modes use one canonical EQ → dynamics → stereo → final LUFS/peak
    normalization path with a single output-normalize step. These SimpleMastering
    branches instead interleave spectral and dynamics stages per material type and
    split the normalization contract (loud defers to the unified stage; quiet
    self-normalizes). Keep the per-branch order and the True/False contract in
    sync with this docstring when editing.
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
                not this chunk's own peak) — used only as the headroom
                reference for QuietBranch's makeup-gain clamp so every chunk
                of a song gets consistent gain-staging. Distinct from the
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
