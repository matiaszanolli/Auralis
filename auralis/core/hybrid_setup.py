"""
Hybrid Processor Construction
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Component construction for HybridProcessor.__init__ and the one-time
module-level performance-optimization wrapping, split out of
hybrid_processor.py (#5463) to bring that file's coordinator role — stage
dispatch and the public API — closer to the 300-line convention. Behavior is
unchanged: `build_hybrid_components()` sets attributes directly on the
`processor` instance passed to it, exactly as the inline `__init__` body did.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import threading
from typing import TYPE_CHECKING

from ..analysis.fingerprint import AudioFingerprintAnalyzer
from ..dsp.advanced_dynamics import DynamicsMode, create_dynamics_processor
from ..dsp.dynamics import create_brick_wall_limiter
from ..dsp.eq.psychoacoustic_eq import EQSettings, PsychoacousticEQ
from ..learning.preference_engine import create_preference_engine
from ..optimization.performance_optimizer import get_performance_optimizer
from ..utils.logging import debug, info
from .analysis import AdaptiveTargetGenerator, ContentAnalyzer
from .analysis.spectrum_mapper import SpectrumMapper
from .config import UnifiedConfig
from .hybrid import DynamicsManager, PreferenceManager
from .processing import AdaptiveMode, ContinuousMode, EQProcessor, HybridMode

if TYPE_CHECKING:
    from .hybrid_processor import HybridProcessor


def build_hybrid_components(config: UnifiedConfig, processor: "HybridProcessor") -> None:
    """Construct every sub-component HybridProcessor.__init__ owns and set
    them as attributes on `processor`. Mirrors the free-function-takes-the-
    owning-instance pattern used by job_execution.py / job_lifecycle.py for
    ProcessingEngine (#4250)."""
    # Initialize analyzers
    processor.content_analyzer = ContentAnalyzer(config.internal_sample_rate)
    processor.target_generator = AdaptiveTargetGenerator(config, processor)
    processor.spectrum_mapper = SpectrumMapper()
    processor.fingerprint_analyzer = AudioFingerprintAnalyzer()

    # Initialize psychoacoustic EQ
    eq_settings = EQSettings(
        sample_rate=config.internal_sample_rate,
        fft_size=config.fft_size,
        adaptation_speed=config.adaptive.adaptation_strength
    )
    processor.psychoacoustic_eq = PsychoacousticEQ(eq_settings)

    # Dynamics management facade.
    #
    # #4873 deleted RealtimeDSPPipeline, the only caller of the old
    # DynamicsProcessor execution chain. #5295 retired that dead chain;
    # this object survives only for
    # the `reset_dynamics()`/`set_dynamics_mode()`/`get_dynamics_info()`
    # public API (`processing_engine._reset_processor_state` calls the
    # first). Do NOT insert it into the offline chain to "make it live":
    # ContinuousMode.process runs its own full-signal, fingerprint-driven
    # continuous-space dynamics (ContinuousMode._apply_dynamics), and adding
    # this on top would double-compress, fight the continuous-space LUFS
    # target with its own -14 LUFS makeup gain, and confound the
    # cross-dimensional guards.
    processor.dynamics_processor = create_dynamics_processor(
        mode=DynamicsMode.ADAPTIVE,
        sample_rate=config.internal_sample_rate,
        target_lufs=-14.0
    )
    processor.dynamics_processor.settings.enable_gate = False
    processor.dynamics_processor.settings.enable_compressor = True

    # Initialize brick-wall limiter for final peak control
    processor.brick_wall_limiter = create_brick_wall_limiter(
        threshold_db=-0.3,
        lookahead_ms=2.0,
        release_ms=50.0,
        sample_rate=config.internal_sample_rate
    )

    # Initialize preference learning engine
    processor.preference_engine = create_preference_engine()

    # Initialize component managers
    processor.dynamics_manager = DynamicsManager(processor.dynamics_processor)
    processor.preference_manager = PreferenceManager(processor.preference_engine)

    # Initialize mode processors
    processor.eq_processor = EQProcessor(processor.psychoacoustic_eq)
    processor.adaptive_mode = AdaptiveMode(
        config, processor.content_analyzer, processor.target_generator,
        processor.spectrum_mapper
    )
    processor.continuous_mode = ContinuousMode(
        config, processor.content_analyzer, processor.fingerprint_analyzer
    )
    processor.hybrid_mode = HybridMode(
        config, processor.content_analyzer, processor.target_generator,
        processor.adaptive_mode
    )
    # Shared state (backwards compatibility)
    processor.current_user_id = None

    # Initialize performance optimizer (optimizations applied once at module level)
    processor.performance_optimizer = get_performance_optimizer()

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
    processor._process_lock = threading.RLock()

    # Set by close(); see its docstring. Guards against double-close and
    # makes a release that currently frees nothing observable (#4744).
    processor._closed = False

    # Processing state
    processor.current_targets = None
    processor.processing_history = []
    processor.last_content_profile = {}


def apply_module_optimizations() -> None:
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
