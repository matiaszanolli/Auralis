"""
Audio Processing Pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~~

Unified audio processing pipeline consolidating best practices from:
- chunked_processor.py (thread-safe processing, fixed targets)
- hybrid_processor.py (comprehensive validation)
- auralis/player/realtime/processor.py (quick processing path)

This utility provides a single source of truth for audio processing orchestration,
eliminating ~400 lines of duplicate validation and processing logic.

:copyright: (C) 2024 Auralis Team
:license: AGPL-3.0-or-later (dual-licensed, see LICENSE / COMMERCIAL_LICENSE.md)
"""

import logging
from typing import Any

import numpy as np

from auralis.core.hybrid_stage_dispatch import MIN_SAMPLES
from core.audio_validation import finite_or_fallback, validate_audio

logger = logging.getLogger(__name__)


class AudioProcessingPipeline:
    """
    Unified audio processing pipeline.

    Consolidates processing orchestration logic from:
    - chunked_processor._process_chunk_core()
    - hybrid_processor.process() / _process_adaptive_mode()
    - RealtimeProcessor.process_chunk() (auralis/player/realtime/processor.py)

    This is a static utility class following the Utilities Pattern (Phase 7.2).
    Application code becomes thin wrappers that delegate to this pipeline.
    """

    @staticmethod
    def select_processor(
        preset: str | None,
        intensity: float,
        processor_factory: Any,
        track_id: int | None = None,
        mastering_targets: dict[str, Any] | None = None,
        config: Any | None = None
    ) -> Any | None:
        """
        Select appropriate processor based on preset/intensity.

        Consolidates processor selection logic from chunked_processor and hybrid_processor.

        Args:
            preset: Processing preset (only 'adaptive' is valid) or None for original
            intensity: Processing intensity (0.0-1.0)
            processor_factory: ProcessorFactory instance (Phase 2: unified factory)
            track_id: Optional track ID for cache key
            mastering_targets: Optional pre-computed mastering targets
            config: Optional UnifiedConfig carrying the track's REAL sample
                rate (#5306). None falls back to the factory's default
                44.1 kHz config, which is correct only for genuinely
                rate-agnostic callers — every real-audio caller must pass it,
                and must pass the SAME instance it keyed the processor on, or
                `_get_config_hash` addresses a different cache entry.

        Returns:
            HybridProcessor instance or None if preset is None (original audio)
        """
        # If preset is None, we're serving original/unprocessed audio
        if preset is None:
            logger.debug("No preset specified, will serve original audio")
            return None

        # Get or create processor via factory (Phase 2: unified factory)
        processor = processor_factory.get_or_create(
            track_id=track_id if track_id is not None else 0,  # Use 0 as default for non-track processing
            preset=preset,
            intensity=intensity,
            config=config,
            mastering_targets=mastering_targets
        )

        logger.debug(f"Selected processor: preset={preset}, intensity={intensity}")
        return processor

    @staticmethod
    def apply_enhancement(
        audio: np.ndarray,
        processor: Any | None,
        targets: dict[str, Any] | None = None,
        intensity: float = 1.0,
        fast_start: bool = False,
        chunk_index: int | None = None
    ) -> np.ndarray:
        """
        Apply enhancement processing to audio.

        Consolidates processing delegation from chunked_processor and hybrid_processor.
        Handles:
        - Original audio passthrough (processor=None)
        - Fixed target mode (targets provided)
        - Fast-start optimization (skip fingerprint on first chunk)
        - Intensity blending

        Args:
            audio: Input audio array (already validated)
            processor: HybridProcessor instance or None
            targets: Optional fixed mastering targets (for 8x faster processing)
            intensity: Processing intensity (0.0-1.0)
            fast_start: If True, skip expensive fingerprint analysis for first chunk
            chunk_index: Optional chunk index for fast-start detection

        Returns:
            Processed audio array
        """
        # SPECIAL CASE: No processor = original audio
        if processor is None:
            logger.debug("No processor, returning original audio")
            return audio

        processed: np.ndarray | None

        # Apply fixed targets if provided (Beta.9 optimization)
        if targets is not None:
            logger.debug(f"Processing with fixed targets (8x faster)")

            # #4354 (regression of #3808): the shared ProcessorFactory hands
            # the SAME HybridProcessor to concurrent callers, so the toggle
            # set/process/restore below must be atomic under the processor's
            # own `_process_lock` (RLock — process() re-enters it safely) —
            # otherwise interleaved set/restore across threads corrupts the
            # shared flag or leaves it permanently False.
            with processor._process_lock:
                # Temporarily disable per-chunk fingerprint analysis
                original_setting = getattr(
                    getattr(processor, 'content_analyzer', None),
                    'use_fingerprint_analysis',
                    None
                )

                if original_setting is not None:
                    processor.content_analyzer.use_fingerprint_analysis = False

                try:
                    processed = processor.process(audio)
                finally:
                    # Restore setting
                    if original_setting is not None:
                        processor.content_analyzer.use_fingerprint_analysis = original_setting

        # Fast-start optimization for first chunk (skip fingerprint analysis)
        elif fast_start and chunk_index == 0:
            logger.debug("Fast-start: Skipping fingerprint analysis for chunk 0")

            # #4354: same shared-processor toggle race as the branch above.
            with processor._process_lock:
                original_setting = getattr(
                    getattr(processor, 'content_analyzer', None),
                    'use_fingerprint_analysis',
                    None
                )

                if original_setting is not None:
                    processor.content_analyzer.use_fingerprint_analysis = False

                try:
                    processed = processor.process(audio)
                finally:
                    if original_setting is not None:
                        processor.content_analyzer.use_fingerprint_analysis = original_setting

        # Normal processing
        else:
            processed = processor.process(audio)

        # Validate processed output
        if processed is None:
            logger.error("Processor returned None, using original audio")
            return audio

        processed = finite_or_fallback(processed, audio, chunk_index)
        if processed is audio:
            return audio

        # Sample-count preservation is a critical gapless invariant (project
        # CLAUDE.md: len(output) == len(input)). The processor is expected to
        # uphold it upstream; if it ever returns a different length, fail
        # loudly rather than letting it flow downstream to be silently
        # padded/trimmed. Checked unconditionally — not just inside the
        # intensity < 1.0 blending branch — because intensity == 1.0 (the
        # default at every construction site) is the overwhelmingly common
        # path and was previously left completely unchecked (#4371, #4795).
        if len(processed) != len(audio):
            logger.error(
                "Processor violated sample-count invariant: "
                f"input={len(audio)} output={len(processed)}"
            )
            raise ValueError(
                "Processed audio length "
                f"({len(processed)}) does not match input "
                f"({len(audio)}); refusing to truncate-blend"
            )

        # Apply intensity blending if < 1.0
        if intensity < 1.0:
            logger.debug(f"Blending processed audio at intensity {intensity:.2f}")
            processed = audio * (1.0 - intensity) + processed * intensity

        return processed

    @classmethod
    def process_audio(
        cls,
        audio: np.ndarray,
        preset: str | None = None,
        intensity: float = 1.0,
        processor_factory: Any | None = None,
        track_id: int | None = None,
        targets: dict[str, Any] | None = None,
        fast_start: bool = False,
        chunk_index: int | None = None,
        allow_empty: bool = False,
        config: Any | None = None,
        processor: Any | None = None,
    ) -> np.ndarray:
        """
        Main unified processing entry point.

        This is the single source of truth for audio processing orchestration.
        Replaces:
        - chunked_processor._process_chunk_core()
        - hybrid_processor.process() / _process_adaptive_mode()
        - RealtimeProcessor.process_chunk() (auralis/player/realtime/processor.py)

        Args:
            audio: Input audio array
            preset: Processing preset or None for original
            intensity: Processing intensity (0.0-1.0)
            processor_factory: ProcessorFactory instance (Phase 2: unified factory)
            track_id: Optional track ID for cache key
            targets: Optional fixed mastering targets
            fast_start: Skip fingerprint analysis for first chunk
            chunk_index: Chunk index for fast-start detection
            allow_empty: Allow empty audio arrays
            config: Optional UnifiedConfig carrying the track's REAL sample
                rate (#5306) — forwarded to select_processor
            processor: A processor the caller already holds (a stream's lease,
                #6091). When given, nothing is selected from the factory.

        Returns:
            Processed audio array

        Raises:
            ValueError: If audio validation fails
        """
        # Step 1: Validate and normalize audio
        try:
            audio = validate_audio(audio, allow_empty=allow_empty)
        except ValueError as e:
            logger.error(f"Audio validation failed: {e}")
            raise

        # Return empty, too-short or silent audio unprocessed. The too-short
        # case arrives here because validate_audio() no longer raises for it
        # (#6194) — skipping processor selection and enhancement mirrors the
        # engine's early_result pass-through for buffers under MIN_SAMPLES.
        if len(audio) < MIN_SAMPLES or np.allclose(audio, 0.0, atol=1e-10):
            return audio

        # Step 2: Select processor (None if preset is None)
        if processor is not None:
            pass  # the caller's own lease
        elif processor_factory is None:
            # If no processor factory provided and preset is specified, we can't process
            if preset is not None:
                raise ValueError("processor_factory required when preset is specified")
            processor = None
        else:
            processor = cls.select_processor(
                preset=preset,
                intensity=intensity,
                processor_factory=processor_factory,
                track_id=track_id,
                mastering_targets=targets,
                config=config
            )

        # Step 3: Apply enhancement
        processed = cls.apply_enhancement(
            audio=audio,
            processor=processor,
            targets=targets,
            intensity=intensity,
            fast_start=fast_start,
            chunk_index=chunk_index
        )

        # Step 4: Return processed audio
        return processed

