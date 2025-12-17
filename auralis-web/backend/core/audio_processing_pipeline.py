"""
Audio Processing Pipeline
~~~~~~~~~~~~~~~~~~~~~~~~~~

Unified audio processing pipeline consolidating best practices from:
- chunked_processor.py (thread-safe processing, fixed targets)
- hybrid_processor.py (comprehensive validation)
- realtime_processor.py (quick processing path)

This utility provides a single source of truth for audio processing orchestration,
eliminating ~400 lines of duplicate validation and processing logic.

:copyright: (C) 2024 Auralis Team
:license: GPLv3
"""

import numpy as np
import logging
import asyncio
from typing import Optional, Dict, Any, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

# Minimum samples required for DSP processing (prevents Rust FFT panics)
MIN_SAMPLES = 1024  # ~23ms at 44.1kHz


class AudioProcessingPipeline:
    """
    Unified audio processing pipeline.

    Consolidates processing orchestration logic from:
    - chunked_processor._process_chunk_core()
    - chunked_processor._process_chunk_with_hybrid_processor()
    - hybrid_processor.process() / _process_adaptive_mode()
    - realtime_processor.process_chunk()

    This is a static utility class following the Utilities Pattern (Phase 7.2).
    Application code becomes thin wrappers that delegate to this pipeline.
    """

    @staticmethod
    def validate_audio(audio: np.ndarray, allow_empty: bool = False) -> np.ndarray:
        """
        Validate and normalize audio array.

        Consolidates validation from hybrid_processor.process() with best practices:
        - Empty array handling
        - Silence detection (all zeros)
        - Mono to stereo conversion
        - Minimum sample count check
        - NaN/infinite value detection

        Args:
            audio: Input audio array
            allow_empty: If True, allow empty arrays (return as-is)

        Returns:
            Validated and normalized audio array

        Raises:
            ValueError: If audio is invalid
        """
        # Validate type
        if not isinstance(audio, np.ndarray):
            raise ValueError(f"Audio must be NumPy array, got {type(audio)}")

        # Handle empty audio
        if len(audio) == 0:
            if allow_empty:
                logger.debug("Empty audio array (allowed)")
                return audio
            else:
                raise ValueError("Audio array is empty")

        # Handle silence (all zeros) - return as-is to avoid NaN in downstream processing
        if np.allclose(audio, 0.0, atol=1e-10):
            logger.debug("Audio is silence (all zeros), returning as-is")
            return audio.copy()

        # Convert mono to stereo if needed
        if audio.ndim == 1:
            audio = np.column_stack([audio, audio])
            logger.debug(f"Converted mono to stereo: shape now {audio.shape}")

        # Check for minimum sample count (prevents Rust FFT/DSP panics)
        if audio.shape[0] < MIN_SAMPLES:
            raise ValueError(
                f"Audio must have at least {MIN_SAMPLES} samples for DSP processing, "
                f"got {audio.shape[0]} samples (~{audio.shape[0]/44100*1000:.1f}ms at 44.1kHz)"
            )

        # Check for NaN or infinite values
        if not np.all(np.isfinite(audio)):
            num_nan = np.sum(np.isnan(audio))
            num_inf = np.sum(np.isinf(audio))
            raise ValueError(
                f"Audio contains invalid values: {num_nan} NaN, {num_inf} infinite"
            )

        logger.debug(f"Audio validated: shape={audio.shape}, dtype={audio.dtype}")
        return audio

    @staticmethod
    def select_processor(
        preset: Optional[str],
        intensity: float,
        processor_factory: Any,
        track_id: Optional[int] = None,
        mastering_targets: Optional[Dict[str, Any]] = None
    ) -> Optional[Any]:
        """
        Select appropriate processor based on preset/intensity.

        Consolidates processor selection logic from chunked_processor and hybrid_processor.

        Args:
            preset: Processing preset (adaptive, gentle, warm, bright, punchy) or None for original
            intensity: Processing intensity (0.0-1.0)
            processor_factory: ProcessorFactory instance (Phase 2: unified factory)
            track_id: Optional track ID for cache key
            mastering_targets: Optional pre-computed mastering targets

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
            mastering_targets=mastering_targets
        )

        logger.debug(f"Selected processor: preset={preset}, intensity={intensity}")
        return processor

    @staticmethod
    def apply_enhancement(
        audio: np.ndarray,
        processor: Optional[Any],
        targets: Optional[Dict[str, Any]] = None,
        intensity: float = 1.0,
        fast_start: bool = False,
        chunk_index: Optional[int] = None
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

        # Apply fixed targets if provided (Beta.9 optimization)
        if targets is not None:
            logger.debug(f"Processing with fixed targets (8x faster)")

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

        # Apply intensity blending if < 1.0
        if intensity < 1.0:
            logger.debug(f"Blending processed audio at intensity {intensity:.2f}")
            # Ensure both arrays have same length for blending
            min_len = min(len(audio), len(processed))
            processed = (
                audio[:min_len] * (1.0 - intensity) +
                processed[:min_len] * intensity
            )

        return processed

    @classmethod
    def process_audio(
        cls,
        audio: np.ndarray,
        preset: Optional[str] = None,
        intensity: float = 1.0,
        processor_factory: Optional[Any] = None,
        track_id: Optional[int] = None,
        targets: Optional[Dict[str, Any]] = None,
        fast_start: bool = False,
        chunk_index: Optional[int] = None,
        allow_empty: bool = False
    ) -> np.ndarray:
        """
        Main unified processing entry point.

        This is the single source of truth for audio processing orchestration.
        Replaces:
        - chunked_processor._process_chunk_core()
        - hybrid_processor.process() / _process_adaptive_mode()
        - realtime_processor.process_chunk()

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

        Returns:
            Processed audio array

        Raises:
            ValueError: If audio validation fails
        """
        # Step 1: Validate and normalize audio
        try:
            audio = cls.validate_audio(audio, allow_empty=allow_empty)
        except ValueError as e:
            logger.error(f"Audio validation failed: {e}")
            raise

        # Handle empty or silence after validation
        if len(audio) == 0 or np.allclose(audio, 0.0, atol=1e-10):
            return audio

        # Step 2: Select processor (None if preset is None)
        if processor_factory is None:
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
                mastering_targets=targets
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

    @classmethod
    async def process_audio_async(
        cls,
        audio: np.ndarray,
        preset: Optional[str] = None,
        intensity: float = 1.0,
        processor_factory: Optional[Any] = None,
        processor_lock: Optional[asyncio.Lock] = None,
        **kwargs: Any
    ) -> np.ndarray:
        """
        Async version of process_audio with thread-safe locking.

        Uses asyncio.Lock to prevent concurrent processor access (critical for
        maintaining compressor envelope followers and gain reduction tracking).

        Args:
            audio: Input audio array
            preset: Processing preset or None for original
            intensity: Processing intensity (0.0-1.0)
            processor_factory: ProcessorFactory instance (Phase 2: unified factory)
            processor_lock: Optional asyncio.Lock for thread safety
            **kwargs: Additional arguments passed to process_audio()

        Returns:
            Processed audio array
        """
        if processor_lock is not None:
            # Thread-safe processing with lock
            async with processor_lock:
                return cls.process_audio(
                    audio=audio,
                    preset=preset,
                    intensity=intensity,
                    processor_factory=processor_factory,
                    **kwargs
                )
        else:
            # No lock provided, process directly
            return cls.process_audio(
                audio=audio,
                preset=preset,
                intensity=intensity,
                processor_factory=processor_factory,
                **kwargs
            )


class AudioValidationError(ValueError):
    """Custom exception for audio validation failures"""
    pass


def validate_audio_array(
    audio: np.ndarray,
    min_samples: int = MIN_SAMPLES,
    allow_empty: bool = False,
    allow_silence: bool = True
) -> Tuple[bool, Optional[str]]:
    """
    Standalone validation function for quick checks.

    Returns:
        Tuple of (is_valid, error_message)
        If is_valid is True, error_message is None
        If is_valid is False, error_message describes the issue
    """
    try:
        AudioProcessingPipeline.validate_audio(audio, allow_empty=allow_empty)
        return (True, None)
    except ValueError as e:
        return (False, str(e))
