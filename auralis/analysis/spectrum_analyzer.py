# -*- coding: utf-8 -*-

"""
Advanced Spectrum Analysis
~~~~~~~~~~~~~~~~~~~~~~~~~~

Real-time and offline spectrum analysis with configurable parameters.

DEPRECATED: Use BaseSpectrumAnalyzer instead. This module maintained for backward compatibility.
"""

import numpy as np
from typing import Dict, Optional
from .base_spectrum_analyzer import BaseSpectrumAnalyzer, SpectrumSettings
from .spectrum_operations import SpectrumOperations
from .fingerprint.common_metrics import AggregationUtils


class SpectrumAnalyzer(BaseSpectrumAnalyzer):
    """Advanced spectrum analyzer with real-time capabilities

    Thin wrapper around BaseSpectrumAnalyzer for backward compatibility.
    """

    def analyze_chunk(self, audio_chunk: np.ndarray, channel: int = 0) -> Dict:
        """
        Analyze a chunk of audio data

        Args:
            audio_chunk: Audio data (mono or stereo)
            channel: Channel to analyze (0=left, 1=right, -1=sum)

        Returns:
            Dictionary with analysis results
        """
        return self._create_chunk_result(audio_chunk, channel, self.settings.sample_rate)

    def analyze_file(self, audio_data: np.ndarray, sample_rate: int = None) -> Dict:
        """
        Analyze an entire audio file

        Args:
            audio_data: Complete audio data
            sample_rate: Sample rate (if different from settings)

        Returns:
            Dictionary with comprehensive analysis
        """
        if sample_rate:
            self.settings.sample_rate = sample_rate

        # Calculate hop size
        hop_size = int(self.settings.fft_size * (1 - self.settings.overlap))

        # Analyze in chunks
        num_chunks = (len(audio_data) - self.settings.fft_size) // hop_size + 1
        chunk_results = []

        for i in range(num_chunks):
            start_idx = i * hop_size
            end_idx = start_idx + self.settings.fft_size

            if end_idx <= len(audio_data):
                chunk = audio_data[start_idx:end_idx]
                if audio_data.ndim == 2:
                    chunk = chunk.reshape(-1, audio_data.shape[1])

                result = self.analyze_chunk(chunk)
                chunk_results.append(result)

        if not chunk_results:
            return {}

        # Aggregate results using SpectrumOperations
        aggregated = SpectrumOperations.aggregate_analysis_results(chunk_results)

        return {
            'spectrum': aggregated['spectrum'].tolist(),
            'frequency_bins': self.frequency_bins.tolist(),
            'peak_frequency': float(AggregationUtils.aggregate_frames_to_track(
                np.array([r['peak_frequency'] for r in chunk_results]), method='mean'
            )),
            'spectral_centroid': float(AggregationUtils.aggregate_frames_to_track(
                np.array([r['spectral_centroid'] for r in chunk_results]), method='mean'
            )),
            'spectral_rolloff': float(AggregationUtils.aggregate_frames_to_track(
                np.array([r['spectral_rolloff'] for r in chunk_results]), method='mean'
            )),
            'total_energy': float(AggregationUtils.aggregate_frames_to_track(
                np.array([r['total_energy'] for r in chunk_results]), method='mean'
            )),
            'num_chunks_analyzed': len(chunk_results),
            'analysis_duration': len(audio_data) / self.settings.sample_rate,
            'settings': {
                'fft_size': self.settings.fft_size,
                'frequency_bands': self.settings.frequency_bands,
                'weighting': self.settings.frequency_weighting,
                'overlap': self.settings.overlap
            }
        }