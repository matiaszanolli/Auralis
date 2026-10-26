"""
Hybrid Audio Processor
~~~~~~~~~~~~~~~~~~~~~~

Unified processor supporting both reference-based and adaptive mastering

Component construction and input-validation/reference-mode dispatch live in
hybrid_setup.py / hybrid_stage_dispatch.py (#5463); the three mode bodies
(reference / adaptive / hybrid) live in processing/mode_dispatch.py (#6272).
The mode methods on this class stay thin delegators so `patch.object` targets
and the lock discipline in `process()` are unchanged, and the delegation
methods below keep their real locking rationale inline.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)

Main processing engine that bridges Matchering and Auralis systems
"""

import threading
from .config.settings import PROCESSING_MODES
from typing import TYPE_CHECKING, Any

import numpy as np

from ..utils.audio_validation import validate_audio_finite
from ..utils.logging import debug, info
from .analysis import AdaptiveTargetGenerator, ContentAnalyzer  # re-exported: tests/test_adaptive_processing.py
from .config import UnifiedConfig
from .hybrid_setup import apply_module_optimizations, build_hybrid_components
from .hybrid_stage_dispatch import validate_and_normalize_input
from .processing.mode_dispatch import (
    process_adaptive_mode as _dispatch_adaptive,
    process_hybrid_mode as _dispatch_hybrid,
    process_reference_mode as _dispatch_reference,
)

if TYPE_CHECKING:
    # Only needed for the class-level attribute annotations below — the
    # attributes themselves are constructed in hybrid_setup.py (#5463).
    from ..analysis.fingerprint import AudioFingerprintAnalyzer
    from ..dsp.dynamics.brick_wall_limiter import BrickWallLimiter
    from ..dsp.eq.psychoacoustic_eq import PsychoacousticEQ
    from ..optimization.performance_optimizer import PerformanceOptimizer
    from .analysis.spectrum_mapper import SpectrumMapper
    from .processing import AdaptiveMode, ContinuousMode, EQProcessor, HybridMode


#: Attributes that are process-wide singletons rather than resources this
#: instance owns, and so must never be closed by an eviction. Generic
#: forwarding in `HybridProcessor.close()` would otherwise let one evicted
#: processor tear down state every other processor is still using (#4744).
#: `performance_optimizer` comes from `get_performance_optimizer()`, a
#: double-checked global.
_NOT_OWNED_BY_PROCESSOR = frozenset({"performance_optimizer"})


class HybridProcessor:
    """
    Main hybrid processor supporting reference-based and adaptive mastering

    This is a thin orchestrator that delegates to specialized mode processors:
    - AdaptiveMode: Spectrum-based adaptive processing
    - HybridMode: Combines reference matching with adaptive intelligence
    - RealtimeProcessor: Low-latency chunk processing for streaming
    """

    # Declared here, not assigned here: every attribute below is set by
    # build_hybrid_components() in hybrid_setup.py (#5463), which __init__
    # calls. Declaring them at class scope keeps mypy/pyright aware of the
    # attributes despite construction living in a sibling module.
    content_analyzer: "ContentAnalyzer"
    target_generator: "AdaptiveTargetGenerator"
    spectrum_mapper: "SpectrumMapper"
    fingerprint_analyzer: "AudioFingerprintAnalyzer"
    psychoacoustic_eq: "PsychoacousticEQ"
    brick_wall_limiter: "BrickWallLimiter"
    eq_processor: "EQProcessor"
    adaptive_mode: "AdaptiveMode"
    continuous_mode: "ContinuousMode"
    hybrid_mode: "HybridMode"
    performance_optimizer: "PerformanceOptimizer"
    _process_lock: threading.RLock
    _closed: bool
    current_targets: dict[str, Any] | None
    last_content_profile: dict[str, Any]

    def __init__(self, config: UnifiedConfig):
        self.config = config
        # Sub-component construction lives in hybrid_setup.py (#5463); it
        # sets every attribute below directly on `self`, exactly as this
        # constructor's inline body used to.
        build_hybrid_components(config, self)
        debug(f"Hybrid processor initialized in {config.adaptive.mode} mode with psychoacoustic EQ")

    def close(self) -> None:
        """Disposal hook for an evicted processor. **Releases nothing today.**

        Called by every cache eviction path (the module-level
        `_processor_cache` here, `ProcessorFactory` and `ProcessorPool` in
        auralis-web/backend) so a processor being dropped gets a chance to let
        go of anything it owns.

        Right now it has nothing to let go of, and saying so is the point
        (#4744). #3746 added this because `fingerprint_analyzer` owned a
        5-thread executor (up to 50 idle threads across a 10-entry cache)
        that was later rewritten into a thin Rust facade whose `close()` is a
        documented no-op — kept rather than deleted so the *next* resource
        that needs releasing doesn't also need a new hook plumbed through
        seven eviction sites.

        The forwarding is deliberately generic (every *owned* attribute
        exposing a callable `close()` is closed, not `fingerprint_analyzer`
        by name) so a future sub-component can't silently inherit a no-op
        release path. Sub-component failures are logged and swallowed:
        eviction runs on shutdown/cache-clear paths where one bad component
        must not abort the rest.

        Idempotent — `_closed` makes a second call a no-op and makes the
        first observable. Set *before* the loop so a sub-component holding a
        back-reference (``target_generator`` is built with ``self``) can't
        recurse.
        """
        if self._closed:
            return
        self._closed = True

        for name, component in list(vars(self).items()):
            if name.startswith("_") or name in _NOT_OWNED_BY_PROCESSOR:
                continue
            if component is self:
                continue
            close_fn = getattr(component, "close", None)
            if not callable(close_fn):
                continue
            try:
                close_fn()
            except Exception as exc:  # pragma: no cover - defensive
                debug(f"HybridProcessor.close: {name}.close() failed: {exc}")

    def set_fixed_mastering_targets(self, targets: dict[str, Any] | None) -> None:
        """
        Set fixed mastering targets to use for all chunks (Beta.9 optimization).

        When fixed targets are set, content analysis is skipped and the
        pre-computed targets (target_lufs, target_crest_db,
        eq_adjustments_db, compression) are used directly — 8x faster
        processing and instant preset switching. `None` disables fixed-target
        mode and restores normal content analysis.

        #3714: this is a public mutator on a potentially-shared instance
        (see ProcessorFactory cache). It MUST acquire `_process_lock` so a
        concurrent `process()` call cannot read `self.current_targets`
        mid-update. The RLock allows re-entry from `process()` if a future
        refactor calls this from within the processing chain.
        """
        with self._process_lock:
            self.current_targets = targets
            if targets:
                debug(f"Fixed mastering targets set: LUFS={targets.get('target_lufs')}, "
                      f"Crest={targets.get('target_crest_db')}")
            else:
                debug("Fixed mastering targets cleared, using normal content analysis")

    def process(
        self,
        target: np.ndarray,
        reference: np.ndarray | None = None,
    ) -> np.ndarray | None:
        """
        Main processing function supporting both reference and adaptive modes

        Args:
            target: Target audio array (pre-loaded NumPy array)
            reference: Reference audio array (optional for adaptive mode)

        Returns:
            Processed audio array (if no file output specified)
        """
        with self._process_lock:
            return self._process_impl(target, reference)

    def _process_impl(
        self,
        target: np.ndarray,
        reference: np.ndarray | None = None,
    ) -> np.ndarray | None:
        """Inner implementation called under _process_lock."""
        info(f"Starting hybrid processing in {self.config.adaptive.mode} mode")

        # Callers pass a pre-loaded NumPy array (#4035). Validation/mono-to-
        # stereo/empty/too-short/silence handling lives in
        # hybrid_stage_dispatch.py (#5463) — see validate_and_normalize_input's
        # docstring for why each check is ordered the way it is.
        target_audio, early_result = validate_and_normalize_input(self, target)
        if early_result is not None:
            return early_result

        # A non-finite reference fails fast at the same boundary `target` is
        # validated (#6105). Hybrid mode used to carry a NaN reference into
        # the blend, where the old unconditional repair zeroed whole buffers
        # into silent chunks; reference mode already raised from its own
        # output guard, later and with a vaguer message.
        if reference is not None:
            reference = validate_audio_finite(reference, context="reference audio", repair=False)

        # Process based on mode
        if self.config.is_reference_mode() and reference is not None:
            return self._process_reference_mode(target_audio, reference)
        elif self.config.is_adaptive_mode():
            return self._process_adaptive_mode(target_audio)
        elif self.config.is_hybrid_mode():
            return self._process_hybrid_mode(target_audio, reference)
        else:
            raise ValueError(f"Invalid processing mode: {self.config.adaptive.mode}")

    def _process_reference_mode(self, target_audio: np.ndarray,
                               reference: np.ndarray) -> np.ndarray:
        """Reference-based matching; body in processing/mode_dispatch.py (#6272)."""
        return _dispatch_reference(self, target_audio, reference)

    def _process_adaptive_mode(self, target_audio: np.ndarray) -> np.ndarray:
        """Adaptive mastering; body in processing/mode_dispatch.py (#6272)."""
        return _dispatch_adaptive(self, target_audio)

    def _process_hybrid_mode(self, target_audio: np.ndarray,
                            reference: np.ndarray | None) -> np.ndarray:
        """Hybrid reference+adaptive; body in processing/mode_dispatch.py (#6272)."""
        return _dispatch_hybrid(self, target_audio, reference)

    # Delegation methods for component managers

    def reset_psychoacoustic_eq(self) -> None:
        """Reset the adaptive/continuous psychoacoustic EQ's gain-smoothing
        state (``current_gains``/``target_gains``, persisted across
        ``process()`` calls for intra-track continuity) at a track/job
        boundary, so one master's EQ curve can't bleed into the next. The
        separate real-time-EQ reset path (#2400) went with #4873, so this is
        the only psychoacoustic-EQ reset left."""
        with self._process_lock:
            self.psychoacoustic_eq.reset()

    def reset_limiter(self) -> None:
        """Reset the brick-wall limiter's cross-call gain-reduction state (#3787: locked).

        ``current_gain`` persists across ``process()`` calls for intra-track
        continuity (#2390); left unreset between pooled/cached jobs, a loud
        track leaves the limiter deep into gain reduction and the next track
        starts already attenuated by that leftover gain (fixes #4811).
        """
        with self._process_lock:
            self.brick_wall_limiter.reset()

    def get_processing_info(self) -> dict[str, Any]:
        """Get information about current processing configuration"""
        return {
            "mode": self.config.adaptive.mode,
            "sample_rate": self.config.internal_sample_rate,
            "fft_size": self.config.fft_size,
            "adaptation_strength": self.config.adaptive.adaptation_strength,
            "enable_genre_detection": self.config.adaptive.enable_genre_detection,
            "available_genres": list(self.config.genre_profiles.keys()),
            "current_targets": self.current_targets
        }

    def set_processing_mode(self, mode: str) -> None:
        """Change processing mode.

        #3714: holds `_process_lock` because the mode write into
        `self.config` is read by `process()` to dispatch between
        adaptive / reference / hybrid pipelines. A concurrent
        cache-shared caller swapping modes mid-process would otherwise
        send chunks down the wrong pipeline.
        """
        # Validation lives in config.set_processing_mode (PROCESSING_MODES,
        # settings.py) — re-typing the list here could drift from it (#6218).
        if mode not in PROCESSING_MODES:
            raise ValueError(f"Invalid processing mode: {mode}")
        with self._process_lock:
            self.config.set_processing_mode(mode)  # type: ignore[arg-type]
            debug(f"Processing mode changed to: {mode}")


# Apply performance optimizations once at module import time. See
# hybrid_setup.apply_module_optimizations() (#5463) for the full rationale
# (why profiling-only, never memoization; idempotency guard for re-import).
apply_module_optimizations()
