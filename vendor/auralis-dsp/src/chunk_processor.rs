// Chunk Processor
// Optimized chunk-based audio processing for streaming
//
// Copyright (C) 2024 Auralis Team
// License: GPLv3

use ndarray::{Array1, Array2, ArrayView1, ArrayView2, Axis};

/// Chunk processing configuration
#[derive(Debug, Clone)]
pub struct ChunkConfig {
    pub chunk_size: usize,
    pub overlap: usize,
    pub num_channels: usize,
    pub crossfade_samples: usize,
}

impl Default for ChunkConfig {
    fn default() -> Self {
        Self {
            chunk_size: 131072, // ~3 seconds at 44.1kHz
            overlap: 2205,      // 50ms at 44.1kHz
            num_channels: 2,
            crossfade_samples: 2205, // 50ms crossfade
        }
    }
}

/// Chunk processor for streaming audio
pub struct ChunkProcessor {
    config: ChunkConfig,
    overlap_buffer: Array2<f64>, // Previous chunk overlap
}

impl ChunkProcessor {
    /// Create new chunk processor
    pub fn new(config: ChunkConfig) -> Self {
        let overlap_buffer = Array2::zeros((config.num_channels, config.overlap));

        Self {
            config,
            overlap_buffer,
        }
    }

    /// Process audio in chunks with overlap-add
    pub fn process_chunks<F>(&mut self, audio: &ArrayView2<f64>, mut process_fn: F) -> Array2<f64>
    where
        F: FnMut(&ArrayView2<f64>) -> Array2<f64>,
    {
        let num_channels = audio.shape()[0];
        let total_samples = audio.shape()[1];
        let chunk_size = self.config.chunk_size;
        let overlap = self.config.overlap;
        let hop_size = chunk_size - overlap;

        // Calculate number of chunks
        let num_chunks = (total_samples + hop_size - 1) / hop_size;

        // Allocate output
        let mut output = Array2::zeros((num_channels, total_samples));

        for chunk_idx in 0..num_chunks {
            let start = chunk_idx * hop_size;
            let end = (start + chunk_size).min(total_samples);
            let current_chunk_size = end - start;

            // Extract chunk
            let chunk = if current_chunk_size < chunk_size {
                // Pad last chunk
                let mut padded = Array2::zeros((num_channels, chunk_size));
                padded
                    .slice_mut(ndarray::s![.., ..current_chunk_size])
                    .assign(&audio.slice(ndarray::s![.., start..end]));
                padded
            } else {
                audio.slice(ndarray::s![.., start..end]).to_owned()
            };

            // Process chunk
            let mut processed = process_fn(&chunk.view());

            // Apply crossfade at chunk boundaries (except first chunk)
            if chunk_idx > 0 && self.config.crossfade_samples > 0 {
                self.apply_crossfade(&mut processed, chunk_idx);
            }

            // Write to output with overlap-add
            let write_start = start;
            let write_end = end.min(total_samples);
            let write_samples = write_end - write_start;

            output
                .slice_mut(ndarray::s![.., write_start..write_end])
                .assign(&processed.slice(ndarray::s![.., ..write_samples]));

            // Save overlap for next chunk
            if current_chunk_size == chunk_size && overlap > 0 {
                self.overlap_buffer
                    .assign(&processed.slice(ndarray::s![.., (chunk_size - overlap)..]));
            }
        }

        output
    }

    /// Apply crossfade between chunks
    fn apply_crossfade(&self, chunk: &mut Array2<f64>, _chunk_idx: usize) {
        let crossfade_len = self.config.crossfade_samples.min(chunk.shape()[1]);

        // Linear crossfade
        for i in 0..crossfade_len {
            let fade_in = i as f64 / crossfade_len as f64;
            let fade_out = 1.0 - fade_in;

            for ch in 0..chunk.shape()[0] {
                if i < self.overlap_buffer.shape()[1] {
                    chunk[[ch, i]] =
                        chunk[[ch, i]] * fade_in + self.overlap_buffer[[ch, i]] * fade_out;
                }
            }
        }
    }

    /// Reset processor state
    pub fn reset(&mut self) {
        self.overlap_buffer.fill(0.0);
    }
}

/// Process mono audio in chunks
pub fn process_mono_chunks<F>(
    audio: &ArrayView1<f64>,
    chunk_size: usize,
    overlap: usize,
    mut process_fn: F,
) -> Array1<f64>
where
    F: FnMut(&ArrayView1<f64>) -> Array1<f64>,
{
    let total_samples = audio.len();
    let hop_size = chunk_size - overlap;
    let num_chunks = (total_samples + hop_size - 1) / hop_size;

    let mut output = Array1::zeros(total_samples);

    for chunk_idx in 0..num_chunks {
        let start = chunk_idx * hop_size;
        let end = (start + chunk_size).min(total_samples);

        // Extract and process chunk
        let chunk = audio.slice(ndarray::s![start..end]);
        let processed = process_fn(&chunk);

        // Write to output
        let write_len = processed.len().min(total_samples - start);
        output
            .slice_mut(ndarray::s![start..(start + write_len)])
            .assign(&processed.slice(ndarray::s![..write_len]));
    }

    output
}

/// Chunk statistics for monitoring
#[derive(Debug, Clone)]
pub struct ChunkStats {
    pub peak: f64,
    pub rms: f64,
    pub crest_db: f64,
}

impl ChunkStats {
    /// Compute statistics for chunk
    pub fn compute(chunk: &ArrayView2<f64>) -> Self {
        let peak = chunk
            .iter()
            .map(|&x| x.abs())
            .fold(0.0_f64, f64::max);

        let rms = (chunk.iter().map(|&x| x * x).sum::<f64>() / chunk.len() as f64).sqrt();

        let crest_db = if rms > 0.0 {
            20.0 * (peak / rms).log10()
        } else {
            0.0
        };

        Self { peak, rms, crest_db }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use ndarray::Array2;

    #[test]
    fn test_chunk_processing() {
        let config = ChunkConfig {
            chunk_size: 1000,
            overlap: 100,
            num_channels: 2,
            crossfade_samples: 50,
        };

        let mut processor = ChunkProcessor::new(config);

        // Create test audio (2 channels, 3000 samples)
        let audio = Array2::ones((2, 3000));

        // Identity processing
        let output = processor.process_chunks(&audio.view(), |chunk| chunk.to_owned());

        // Output should match input size
        assert_eq!(output.shape(), audio.shape());
    }

    #[test]
    fn test_mono_chunk_processing() {
        let audio = Array1::ones(5000);

        // Amplify by 2x
        let output = process_mono_chunks(&audio.view(), 1000, 100, |chunk| chunk.mapv(|x| x * 2.0));

        // All samples should be amplified
        assert!((output[100] - 2.0).abs() < 1e-10);
    }

    #[test]
    fn test_chunk_stats() {
        let mut chunk = Array2::zeros((2, 1000));
        chunk[[0, 0]] = 1.0; // Peak at 1.0
        chunk[[1, 500]] = 0.5;

        let stats = ChunkStats::compute(&chunk.view());

        assert_eq!(stats.peak, 1.0);
        assert!(stats.rms > 0.0);
        assert!(stats.crest_db > 0.0);
    }
}
