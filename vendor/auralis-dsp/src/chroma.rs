/// Constant-Q Chroma Features
///
/// Extracts 12-dimensional chromagram from audio using constant-Q representation
///
/// Reference:
/// Brown, Judith C. "Calculation of a constant Q spectral transform." JASA 89, 1991.

use ndarray::Array2;

/// Extract chromagram using constant-Q transform
///
/// # Arguments
/// * `y` - Audio signal [n_samples]
/// * `sr` - Sample rate (Hz)
///
/// # Returns
/// Chromagram [12, n_frames] - energy per semitone
pub fn chroma_cqt(y: &[f64], sr: usize) -> Array2<f64> {
    // TODO: Implement Constant-Q chroma extraction
    // 1. Compute Constant-Q Transform (logarithmic frequency spacing)
    // 2. Map 252 bins (7 octaves × 36 bins) to 12 semitones
    // 3. Normalize by frame

    Array2::zeros((12, 0))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_chroma_cqt_stub() {
        let audio = vec![0.0; 44100];
        let chroma = chroma_cqt(&audio, 44100);
        assert_eq!(chroma.nrows(), 12);
    }
}
