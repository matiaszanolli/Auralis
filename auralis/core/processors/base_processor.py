# -*- coding: utf-8 -*-

"""
Base Processor
~~~~~~~~~~~~~~

Base class for audio processing modes

:copyright: (C) 2024 Auralis Team
:license: GPLv3, see LICENSE for more details.
"""

import numpy as np
from typing import Dict, Any
from abc import ABC, abstractmethod


class BaseProcessor(ABC):
    """Base class for audio processing modes"""

    def __init__(self, config, sample_rate: int):
        """
        Initialize base processor

        Args:
            config: Processing configuration
            sample_rate: Audio sample rate
        """
        self.config = config
        self.sample_rate = sample_rate

    @abstractmethod
    def process(self, target_audio: np.ndarray, **kwargs) -> np.ndarray:
        """
        Process audio

        Args:
            target_audio: Audio to process
            **kwargs: Additional mode-specific arguments

        Returns:
            Processed audio
        """
        pass

    def _load_audio_placeholder(self, file_path: str) -> np.ndarray:
        """Placeholder for audio loading - to be implemented by subclasses"""
        raise NotImplementedError("Audio loading not implemented")
