"""
Hybrid Audio Processor
~~~~~~~~~~~~~~~~~~~~~~

Unified processor supporting both reference-based and adaptive mastering

Component construction and input-validation/reference-mode dispatch split out
to hybrid_setup.py / hybrid_stage_dispatch.py (#5463), following the
coordinator/sibling pattern #4250 established for ProcessingEngine (599 ->
402 LOC). `_process_adaptive_mode()` / `_process_hybrid_mode()` stay inline
rather than moving too: tests/regression/test_sample_count_invariant.py
inspects their source directly via `inspect.getsource()`, so the sample-count
assertion has to live in the bound method's own body, not a helper it calls.
402 LOC is this file's explicit waiver ceiling (matching the
processing_engine.py precedent, #5454) -- the remainder is those two
test-pinned methods, `close()`'s docstring (two tests assert specific
substrings in it), and delegation methods carrying real locking rationale,
not further-splittable bulk.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)

Main processing engine that bridges Matchering and Auralis systems
"""

import threading
from typing import TYPE_CHECKING, Any

import numpy as np

from ..io.results import Result
from ..utils.audio_validation import validate_audio_finite
from ..utils.logging import debug, info
from .analysis import AdaptiveTargetGenerator, ContentAnalyzer  # re-exported: tests/test_adaptive_processing.py
from .config import UnifiedConfig
from .hybrid_setup import apply_module_optimizations, build_hybrid_components
from .hybrid_stage_dispatch import process_reference_mode, validate_and_normalize_input

if TYPE_CHECKING:
    # Only needed for the class-level attribute annotations below — the
    # attributes themselves are constructed in hybrid_setup.py (#5463).
    from ..analysis.fingerprint import AudioFingerprintAnalyzer
    from ..dsp.advanced_dynamics import DynamicsProcessor
    from ..dsp.dynamics.brick_wall_limiter import BrickWallLimiter
    from ..dsp.eq.psychoacoustic_eq import PsychoacousticEQ
    from ..learning.preference_engine import PreferenceLearningEngine
    from ..optimization.performance_optimizer import PerformanceOptimizer
    from .analysis.spectrum_mapper import SpectrumMapper
    from .hybrid import DynamicsManager, PreferenceManager
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
    dynamics_processor: "DynamicsProcessor"
    brick_wall_limiter: "BrickWallLimiter"
    preference_engine: "PreferenceLearningEngine"
    dynamics_manager: "DynamicsManager"
    preference_manager: "PreferenceManager"
    eq_processor: "EQProcessor"
    adaptive_mode: "AdaptiveMode"
    continuous_mode: "ContinuousMode"
    hybrid_mode: "HybridMode"
    current_user_id: str | None
    performance_optimizer: "PerformanceOptimizer"
    _process_lock: threading.RLock
    _closed: bool
    current_targets: dict[str, Any] | None
    processing_history: list[Any]
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
        results: str | list[str] | Result | list[Result] | None = None
    ) -> np.ndarray | None:
        """
        Main processing function supporting both reference and adaptive modes

        Args:
            target: Target audio array (pre-loaded NumPy array)
            reference: Reference audio array (optional for adaptive mode)
            results: Output file path(s) or Result object(s)

        Returns:
            Processed audio array (if no file output specified)
        """
        with self._process_lock:
            return self._process_impl(target, reference, results)

    def _process_impl(
        self,
        target: np.ndarray,
        reference: np.ndarray | None = None,
        results: str | list[str] | Result | list[Result] | None = None
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

        # Process based on mode
        if self.config.is_reference_mode() and reference is not None:
            return self._process_reference_mode(target_audio, reference, results)
        elif self.config.is_adaptive_mode():
            return self._process_adaptive_mode(target_audio, results)
        elif self.config.is_hybrid_mode():
            return self._process_hybrid_mode(target_audio, reference, results)
        else:
            raise ValueError(f"Invalid processing mode: {self.config.adaptive.mode}")

    def _process_reference_mode(self, target_audio: np.ndarray,
                               reference: np.ndarray,
                               results: Any) -> np.ndarray:
        """Process using traditional reference-based matching. See
        hybrid_stage_dispatch.process_reference_mode() (#5463)."""
        return process_reference_mode(self, target_audio, reference, results)

    def _process_adaptive_mode(self, target_audio: np.ndarray, results: Any) -> np.ndarray:
        """
        Process using adaptive mastering without reference.

        NOTE: This method still exists for backward compatibility but now uses
        the internal processor logic directly since hybrid_processor is the
        actual processor being called by AudioProcessingPipeline.
        """
        info("Processing in adaptive mode")

        # Choose processing mode based on config
        if self.config.use_continuous_space:
            debug(f"HybridProcessor: use_continuous_space={self.config.use_continuous_space}, using ContinuousMode")
            info("Using continuous parameter space (fingerprint-based)")

            # NEW (Beta.9): Use fixed targets if set (from .25d file)
            # This bypasses expensive fingerprint extraction on every chunk
            fixed_params = self.current_targets if self.current_targets is not None else None

            # Delegate to continuous mode processor
            processed = self.continuous_mode.process(target_audio, self.eq_processor,
                                                    fixed_params=fixed_params)

            # Store fingerprint and parameters for learning/debugging
            self.last_content_profile = {
                'fingerprint': self.continuous_mode.last_fingerprint,
                'coordinates': self.continuous_mode.last_coordinates,
                'parameters': self.continuous_mode.last_parameters,
            }
        else:
            info("Using legacy preset-based processing")
            # Delegate to legacy adaptive mode processor
            processed = self.adaptive_mode.process(target_audio, self.eq_processor)

            # Store content profile for user learning
            profile = self.adaptive_mode.get_last_content_profile()
            if profile is not None:
                self.last_content_profile = profile

        self.preference_manager.set_content_profile(self.last_content_profile)

        # Apply brick-wall limiter for final peak control
        # Ensures output never clips and stays within safe range
        processed = self.brick_wall_limiter.process(processed)
        # Sample-count invariant: limiter must preserve length (fixes #2519)
        assert processed.shape == target_audio.shape, (
            f"Sample count mismatch after limiter (adaptive): "
            f"expected {target_audio.shape}, got {processed.shape}"
        )

        # Fail fast on NaN/Inf in mastering output — surface DSP bugs rather than
        # silently masking them with zero-replacement (fixes #2520).
        processed = validate_audio_finite(processed, context="adaptive mode output", repair=False)

        return processed

    def _process_hybrid_mode(self, target_audio: np.ndarray,
                            reference: np.ndarray | None,
                            results: Any) -> np.ndarray:
        """Process using hybrid approach combining reference and adaptive"""
        info("Processing in hybrid mode")

        # Reference, if provided, is a pre-loaded NumPy array (#4035).
        reference_audio = reference

        # Delegate to hybrid mode processor
        processed = self.hybrid_mode.process(target_audio, reference_audio, self.eq_processor)

        # Apply brick-wall limiter for final peak control
        # Ensures output never clips and stays within safe range
        processed = self.brick_wall_limiter.process(processed)
        # Sample-count invariant: limiter must preserve length (fixes #2519)
        assert processed.shape == target_audio.shape, (
            f"Sample count mismatch after limiter (hybrid): "
            f"expected {target_audio.shape}, got {processed.shape}"
        )

        # Fail fast on NaN/Inf in mastering output — surface DSP bugs rather than
        # silently masking them with zero-replacement (fixes #2520).
        processed = validate_audio_finite(processed, context="hybrid mode output", repair=False)

        return processed

    # Delegation methods for component managers

    def get_dynamics_info(self) -> dict[str, Any]:
        """Get dynamics processing information"""
        return self.dynamics_manager.get_info()

    def set_dynamics_mode(self, mode: str) -> None:
        """Set dynamics processing mode (#3787: locked)."""
        with self._process_lock:
            self.dynamics_manager.set_mode(mode)

    def reset_dynamics(self) -> None:
        """Reset dynamics processing state (#3787: locked)."""
        with self._process_lock:
            self.dynamics_manager.reset()

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

    def set_user(self, user_id: str) -> None:
        """Set the current user for preference learning (#3787: locked).

        Both writes (`current_user_id` AND the underlying preference
        manager) are inside the lock so a concurrent process() reads a
        consistent (user, preferences) pair."""
        with self._process_lock:
            self.current_user_id = user_id
            self.preference_manager.set_user(user_id)

    def record_user_feedback(self, rating: float,
                           parameters_before: dict[str, float] | None = None,
                           parameters_after: dict[str, float] | None = None) -> None:
        """Record user feedback for learning (#3787: locked)."""
        with self._process_lock:
            self.preference_manager.record_feedback(rating, parameters_before, parameters_after)

    def record_parameter_adjustment(self, parameter_name: str,
                                  old_value: float, new_value: float) -> None:
        """Record user parameter adjustment for learning (#3787: locked)."""
        with self._process_lock:
            self.preference_manager.record_adjustment(parameter_name, old_value, new_value)

    def get_user_insights(self, user_id: str | None = None) -> dict[str, Any]:
        """Get user preference insights"""
        return self.preference_manager.get_insights(user_id)

    def save_user_preferences(self, user_id: str | None = None) -> bool:
        """Save user preferences to storage"""
        return self.preference_manager.save_preferences(user_id)

    def get_performance_stats(self) -> dict[str, Any]:
        """Get performance optimization statistics"""
        return self.performance_optimizer.get_optimization_stats()

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
        if mode not in ["reference", "adaptive", "hybrid"]:
            raise ValueError(f"Invalid processing mode: {mode}")
        with self._process_lock:
            self.config.set_processing_mode(mode)  # type: ignore[arg-type]
            debug(f"Processing mode changed to: {mode}")


# Apply performance optimizations once at module import time. See
# hybrid_setup.apply_module_optimizations() (#5463) for the full rationale
# (why profiling-only, never memoization; idempotency guard for re-import).
apply_module_optimizations()
