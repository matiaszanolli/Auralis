# -*- coding: utf-8 -*-

"""
Auralis Preview Creator
~~~~~~~~~~~~~~~~~~~~~~

Preview generation for A/B comparison

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.

Refactored from Matchering 2.0 by Sergree and contributors
"""

import numpy as np
from .logging import debug, info


def create_preview(target: np.ndarray, result: np.ndarray, config, preview_target=None, preview_result=None):
    """
    Create preview files for A/B comparison

    Args:
        target: Original target audio
        result: Processed result audio
        config: Processing configuration
        preview_target: Preview target result object
        preview_result: Preview result result object
    """
    debug("Creating preview files")

    def _extract_preview(audio: np.ndarray) -> np.ndarray:
        """
        Extract preview from audio with fades to prevent clicks.

        Args:
            audio: Input audio array

        Returns:
            Preview audio (first preview_size samples with fades applied)
        """
        preview_size = int(config.preview_size)
        fade_size = int(config.preview_fade_size)
        fade_coefficient = config.preview_fade_coefficient

        # Ensure preview doesn't exceed audio length
        preview_len = min(preview_size, len(audio))
        preview = audio[:preview_len].copy()

        # Apply fade in at the beginning
        if fade_size > 0 and len(preview) > fade_size:
            fade_in = np.linspace(0, 1, fade_size) ** (1 / fade_coefficient)
            preview[:fade_size] *= fade_in

        # Apply fade out at the end
        if fade_size > 0 and len(preview) > fade_size:
            fade_out_start = max(0, len(preview) - fade_size)
            fade_out = np.linspace(1, 0, len(preview) - fade_out_start) ** (1 / fade_coefficient)
            preview[fade_out_start:] *= fade_out

        return preview

    if preview_target:
        from ..io.saver import save
        preview_audio = _extract_preview(target)
        save(preview_target.file, preview_audio, config.internal_sample_rate, preview_target.subtype)
        debug(f"Preview target created: {len(preview_audio)} samples (~{len(preview_audio) / config.internal_sample_rate:.1f}s)")

    if preview_result:
        from ..io.saver import save
        preview_audio = _extract_preview(result)
        save(preview_result.file, preview_audio, config.internal_sample_rate, preview_result.subtype)
        debug(f"Preview result created: {len(preview_audio)} samples (~{len(preview_audio) / config.internal_sample_rate:.1f}s)")

    info("Preview files created")