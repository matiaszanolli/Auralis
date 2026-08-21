"""
Hybrid Audio Processor
~~~~~~~~~~~~~~~~~~~~~~

Unified processor supporting both reference-based and adaptive mastering

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Main processing engine that bridges Matchering and Auralis systems
"""

import threading
from typing import Any

import numpy as np

from ..analysis.fingerprint import AudioFingerprintAnalyzer
from ..dsp.advanced_dynamics import DynamicsMode, create_dynamics_processor
from ..dsp.dynamics import create_brick_wall_limiter
from ..dsp.eq.psychoacoustic_eq import EQSettings, PsychoacousticEQ
from ..io.results import Result
from ..learning.preference_engine import create_preference_engine
from ..optimization.performance_optimizer import get_performance_optimizer
from ..utils.audio_validation import validate_audio_finite
from ..utils.logging import debug, info, warning
from .analysis import AdaptiveTargetGenerator, ContentAnalyzer
from .analysis.spectrum_mapper import SpectrumMapper
from .config import UnifiedConfig
from .hybrid import DynamicsManager, PreferenceManager
from .processing import (
    AdaptiveMode,
    ContinuousMode,
    EQProcessor,
    HybridMode,
)
from .processors import apply_reference_matching


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

    def __init__(self, config: UnifiedConfig):
        self.config = config

        # Initialize analyzers
        self.content_analyzer = ContentAnalyzer(config.internal_sample_rate)
        self.target_generator = AdaptiveTargetGenerator(config, self)
        self.spectrum_mapper = SpectrumMapper()
        self.fingerprint_analyzer = AudioFingerprintAnalyzer()

        # Initialize psychoacoustic EQ
        eq_settings = EQSettings(
            sample_rate=config.internal_sample_rate,
            fft_size=config.fft_size,
            adaptation_speed=config.adaptive.adaptation_strength
        )
        self.psychoacoustic_eq = PsychoacousticEQ(eq_settings)

        # Advanced dynamics processor.
        #
        # #4873 deleted RealtimeDSPPipeline, its only `process()` caller, so
        # nothing currently runs this processor's chain — it survives only for
        # the `reset_dynamics()`/`set_dynamics_mode()`/`get_dynamics_info()`
        # public API (`processing_engine._reset_processor_state` calls the
        # first). Do NOT insert it into the offline chain to "make it live":
        # ContinuousMode.process runs its own full-signal, fingerprint-driven
        # continuous-space dynamics (ContinuousMode._apply_dynamics), and adding
        # this on top would double-compress, fight the continuous-space LUFS
        # target with its own -14 LUFS makeup gain, and confound the
        # cross-dimensional guards. Retiring it is tracked separately.
        self.dynamics_processor = create_dynamics_processor(
            mode=DynamicsMode.ADAPTIVE,
            sample_rate=config.internal_sample_rate,
            target_lufs=-14.0
        )
        self.dynamics_processor.settings.enable_gate = False
        self.dynamics_processor.settings.enable_compressor = True

        # Initialize brick-wall limiter for final peak control
        self.brick_wall_limiter = create_brick_wall_limiter(
            threshold_db=-0.3,
            lookahead_ms=2.0,
            release_ms=50.0,
            sample_rate=config.internal_sample_rate
        )

        # Initialize preference learning engine
        self.preference_engine = create_preference_engine()

        # Initialize component managers
        self.dynamics_manager = DynamicsManager(self.dynamics_processor)
        self.preference_manager = PreferenceManager(self.preference_engine)

        # Initialize mode processors
        self.eq_processor = EQProcessor(self.psychoacoustic_eq)
        self.adaptive_mode = AdaptiveMode(
            config, self.content_analyzer, self.target_generator,
            self.spectrum_mapper
        )
        self.continuous_mode = ContinuousMode(
            config, self.content_analyzer, self.fingerprint_analyzer
        )
        self.hybrid_mode = HybridMode(
            config, self.content_analyzer, self.target_generator,
            self.adaptive_mode
        )
        # Shared state (backwards compatibility)
        self.current_user_id: str | None = None

        # Initialize performance optimizer (optimizations applied once at module level)
        self.performance_optimizer = get_performance_optimizer()

        # Per-instance lock: serialises all public state mutations and
        # process() invocations on the same HybridProcessor instance.
        # The cached-processor cache (ProcessorFactory / _processor_cache)
        # legitimately shares one instance across callers — every
        # mutating entry point MUST acquire this lock so two callers
        # don't observe a half-applied mastering_targets / fingerprint /
        # profile update.
        # - #3349: initial process() serialization.
        # - #3714: extended to set_fixed_mastering_targets and the other
        #   public setters so cache-hit re-apply / mid-stream fingerprint
        #   load can't mutate the instance while another thread is
        #   iterating chunks.
        # RLock so process()->_process_impl re-acquisition is safe.
        self._process_lock = threading.RLock()

        # Set by close(); see its docstring. Guards against double-close and
        # makes a release that currently frees nothing observable (#4744).
        self._closed = False

        # Processing state
        self.current_targets: dict[str, Any] | None = None
        self.processing_history: list[Any] = []
        self.last_content_profile: dict[str, Any] = {}

        debug(f"Hybrid processor initialized in {config.adaptive.mode} mode with psychoacoustic EQ")

    def close(self) -> None:
        """Disposal hook for an evicted processor. **Releases nothing today.**

        Called by every cache eviction path (the module-level
        `_processor_cache` here, `ProcessorFactory` and `ProcessorPool` in
        auralis-web/backend) so a processor being dropped gets a chance to let
        go of anything it owns.

        Right now it has nothing to let go of, and saying so is the point
        (#4744). #3746 added this because `fingerprint_analyzer` owned a
        5-thread executor — up to 50 idle threads across a 10-entry cache.
        `AudioFingerprintAnalyzer` was later rewritten as a thin facade over
        the in-process Rust engine and its `close()` became a documented
        no-op, but the comments at every call site went on describing a thread
        pool being reclaimed. The hook is kept rather than deleted because
        removing it would mean the *next* resource needs both a new `close()`
        and a re-plumbing of all seven eviction sites.

        The forwarding is deliberately generic: every *owned* attribute
        exposing a callable `close()` is closed, rather than
        `fingerprint_analyzer` being named. That is what stops a future
        sub-component from silently inheriting a no-op release path — the
        failure mode #4744 was filed about. Sub-component failures are logged
        and swallowed: eviction runs on shutdown and cache-clear paths where
        one bad component must not abort the rest.

        Idempotent — `_closed` makes a second call a no-op and makes the
        first observable, since "did close() run?" is otherwise unanswerable
        for a function that does nothing. It is set *before* the loop so a
        sub-component holding a back-reference (``target_generator`` is built
        with ``self``) cannot recurse.
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
        Set fixed mastering targets to use for all chunks (Beta.9 optimization)

        When fixed targets are set, content analysis is skipped and the pre-computed
        targets are used directly. This enables 8x faster processing and instant preset
        switching.

        #3714: this is a public mutator on a potentially-shared instance
        (see ProcessorFactory cache). It MUST acquire `_process_lock` so
        a concurrent `process()` call cannot read `self.current_targets`
        mid-update. The RLock allows re-entry from `process()` if a
        future refactor calls this from within the processing chain.

        Args:
            targets: Mastering targets dict with keys:
                - target_lufs: Target loudness in LUFS
                - target_crest_db: Target crest factor in dB
                - eq_adjustments_db: Dict of frequency band adjustments
                - compression: Dict with ratio and amount
                Set to None to disable fixed-target mode and use normal content analysis.

        Example:
            processor.set_fixed_mastering_targets({
                'target_lufs': -14.0,
                'target_crest_db': 12.0,
                'eq_adjustments_db': {'sub_bass': -1.5, 'bass': 0.5, ...},
                'compression': {'ratio': 2.5, 'amount': 0.6}
            })
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

        # Callers pass a pre-loaded NumPy array (#4035).
        target_audio = target

        # Validate audio array
        if not isinstance(target_audio, np.ndarray):
            raise ValueError(f"Target audio must be a NumPy array, got {type(target_audio)}")

        # Convert mono to stereo if needed.
        #
        # This runs BEFORE the empty-audio check (#4976). With the order
        # reversed, an empty mono buffer returned 1-D `(0,)` while every other
        # path — including the all-zeros return a few lines below, which sits
        # after this conversion — returned 2-D `(N, 2)`. A caller that indexes
        # `result[:, 0]`, reasonable given the shape this processor otherwise
        # always guarantees, hit an IndexError only on the empty-mono path.
        if target_audio.ndim == 1:
            target_audio = np.column_stack([target_audio, target_audio])
            debug(f"Converted mono audio to stereo: shape now {target_audio.shape}")

        # Handle empty audio before any further processing. Post-conversion
        # this returns (0, 2) for mono and stereo alike.
        if len(target_audio) == 0:
            return target_audio.copy()

        # Audio shorter than one analysis window (1024 samples, ~23ms at
        # 44.1kHz) is returned unprocessed rather than rejected (#4520).
        #
        # This used to `raise ValueError`, which broke the pipeline's core
        # invariant — `len(output) == len(input)`, load-bearing for gapless
        # playback — for any short buffer, and made a caller's only options
        # "crash" or "pre-check the length itself". Returning it untouched is
        # what the empty-audio and silence branches immediately above already
        # do, and no meaningful mastering decision can be made from 23ms
        # anyway: the fingerprint stage alone needs 11025 samples.
        #
        # The raise was originally defensive against Rust FFT panics on tiny
        # audio. Those are fixed at the source — vendor/auralis-dsp hpss.rs
        # short-circuits below one FFT frame, verified here for n=0..2048 —
        # so the guard now only blocks work the DSP layer handles correctly.
        MIN_SAMPLES = 1024
        if target_audio.shape[0] < MIN_SAMPLES:
            warning(
                f"Audio too short to master ({target_audio.shape[0]} samples, "
                f"~{target_audio.shape[0]/44100*1000:.1f}ms at 44.1kHz); "
                f"returning it unprocessed (need {MIN_SAMPLES} samples)"
            )
            return target_audio.copy()

        # Handle silence (all zeros) - return as-is to avoid NaN production in downstream processing
        if np.allclose(target_audio, 0.0, atol=1e-10):
            return target_audio.copy()

        # Validate input audio for NaN/Inf (fail fast on corrupted input)
        target_audio = validate_audio_finite(target_audio, context="input audio", repair=False)
        debug("Input audio validated: no NaN/Inf detected")

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
        """Process using traditional reference-based matching"""
        info("Processing in reference mode")

        # Reference is a pre-loaded NumPy array (#4035).
        reference_audio = reference

        # Delegate to reference matching
        processed = apply_reference_matching(target_audio, reference_audio)

        # Apply brick-wall limiter for final peak control (same as adaptive/hybrid)
        processed = self.brick_wall_limiter.process(processed)
        assert processed.shape == target_audio.shape, (
            f"Sample count mismatch after limiter (reference): "
            f"expected {target_audio.shape}, got {processed.shape}"
        )

        # Fail fast on NaN/Inf in mastering output — surface DSP bugs rather than
        # silently masking them with zero-replacement (fixes #2520).
        processed = validate_audio_finite(processed, context="reference mode output", repair=False)

        return processed

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
        """Reset the main adaptive/continuous psychoacoustic EQ smoothing state.

        This is the EQ used by the adaptive and continuous processing paths
        (via ``self.eq_processor``). Its ``current_gains``/``target_gains``
        gain-smoothing state persists across ``process()`` calls for
        intra-track streaming continuity; resetting it at a track/job boundary
        keeps one master from bleeding the previous track's EQ curve into the
        next. Was distinct from ``reset_realtime_eq()``, which reset the
        *separate* psychoacoustic EQ owned by the real-time EQ path (#2400);
        that path and its reset went with #4873, so this is now the only
        psychoacoustic-EQ reset."""
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


# ===== Module-level performance optimizations (applied once) =====

def _apply_module_optimizations() -> None:
    """
    Apply performance optimizations at module level (once, not per-instance)

    This prevents redundant wrapping of methods every time HybridProcessor is created.
    Optimizations are cached and reused across all instances.

    Guarded by an idempotency flag so repeated calls (e.g., in worker
    processes that re-import the module) do not double-wrap (#3353).
    """
    if getattr(AdaptiveMode, '_optimized', False):
        return

    try:
        perf_opt = get_performance_optimizer()

        # Wrap AdaptiveMode.process with PROFILING ONLY — never memoization
        # (#4524). `optimize_real_time_processing` also layers a SmartCache on
        # top, and `AdaptiveMode.process` is not a pure function: it mutates
        # `self.last_content_profile`, which `adaptive_mode.py` reads later to
        # derive bass_pct / transient_density. On a cache hit the body never
        # runs, so that field keeps a *previous track's* profile. A generic
        # memoizing decorator is the wrong tool for this method regardless of
        # how good the key is, and mastering is not a hot inner loop — the
        # memoization bought little while risking wrong-audio output.
        original_process = AdaptiveMode.process
        AdaptiveMode.process = perf_opt.profiler.time_function(  # type: ignore[method-assign]
            original_process.__name__
        )(original_process)
        AdaptiveMode._optimized = True  # type: ignore[attr-defined]

        # Note: we don't optimize HybridProcessor.process() at module level
        # because it's an instance method. It will use the optimizer's cached methods
        # if called frequently (the optimizer tracks hot methods internally).

        # Note: ContentAnalyzer.analyze_content caching is managed by the
        # performance_optimizer internally for cache coherency

        info("Module-level performance optimizations applied (one-time)")
    except Exception as e:
        debug(f"Warning: Could not apply module optimizations: {e}")


# Apply optimizations once at module import time
_apply_module_optimizations()
