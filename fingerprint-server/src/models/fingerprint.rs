use serde::{Deserialize, Serialize};

/// 25-dimensional audio fingerprint
///
/// Organized into 7 categories covering all aspects of audio:
/// - Frequency (7D): Energy distribution across frequency bands
/// - Dynamics (3D): Loudness and dynamic range
/// - Temporal (4D): Rhythm and temporal patterns
/// - Spectral (3D): Brightness and tonal characteristics
/// - Harmonic (3D): Harmonic content and pitch
/// - Variation (3D): Dynamic variation over time
/// - Stereo (2D): Stereo field characteristics
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Fingerprint {
    // Frequency Distribution (7D)
    pub sub_bass_pct: f64,       // Energy in sub-bass (20-60 Hz)
    pub bass_pct: f64,            // Energy in bass (60-250 Hz)
    pub low_mid_pct: f64,         // Energy in low-mids (250-500 Hz)
    pub mid_pct: f64,             // Energy in mids (500-2k Hz)
    pub upper_mid_pct: f64,       // Energy in upper-mids (2k-4k Hz)
    pub presence_pct: f64,        // Energy in presence (4k-6k Hz)
    pub air_pct: f64,             // Energy in air/high-freq (6k-20k Hz)

    // Dynamics (3D)
    pub lufs: f64,                // Integrated loudness (LUFS)
    pub crest_db: f64,            // Crest factor in dB
    pub bass_mid_ratio: f64,      // Bass to mid energy ratio

    // Temporal (4D)
    pub tempo_bpm: f64,           // Detected tempo in BPM
    pub rhythm_stability: f64,    // Rhythm consistency (0-1)
    pub transient_density: f64,   // Transient density (0-1)
    pub silence_ratio: f64,       // Silence proportion (0-1)

    // Spectral (3D)
    pub spectral_centroid: f64,   // Brightness (0-1)
    pub spectral_rolloff: f64,    // High-freq content (0-1)
    pub spectral_flatness: f64,   // Noise vs tonal (0-1)

    // Harmonic (3D)
    pub harmonic_ratio: f64,      // Harmonic vs percussive (0-1)
    pub pitch_stability: f64,     // Pitch consistency (0-1)
    pub chroma_energy: f64,       // Chroma strength (0-1)

    // Variation (3D)
    pub dynamic_range_variation: f64,   // Crest variation (0-1)
    pub loudness_variation_std: f64,    // Loudness std dev (dB)
    pub peak_consistency: f64,          // Peak consistency (0-1)

    // Stereo (2D)
    pub stereo_width: f64,        // Stereo width (0-1)
    pub phase_correlation: f64,   // Phase correlation (-1 to +1)
}

impl Default for Fingerprint {
    fn default() -> Self {
        Self {
            sub_bass_pct: 0.0,
            bass_pct: 0.0,
            low_mid_pct: 0.0,
            mid_pct: 0.0,
            upper_mid_pct: 0.0,
            presence_pct: 0.0,
            air_pct: 0.0,
            lufs: 0.0,
            crest_db: 0.0,
            bass_mid_ratio: 0.0,
            tempo_bpm: 0.0,
            rhythm_stability: 0.0,
            transient_density: 0.0,
            silence_ratio: 0.0,
            spectral_centroid: 0.0,
            spectral_rolloff: 0.0,
            spectral_flatness: 0.0,
            harmonic_ratio: 0.0,
            pitch_stability: 0.0,
            chroma_energy: 0.0,
            dynamic_range_variation: 0.0,
            loudness_variation_std: 0.0,
            peak_consistency: 0.0,
            stereo_width: 0.0,
            phase_correlation: 0.0,
        }
    }
}

impl Fingerprint {
    /// Count number of valid (non-NaN, non-infinite) dimensions
    pub fn valid_dimensions(&self) -> usize {
        [
            self.sub_bass_pct,
            self.bass_pct,
            self.low_mid_pct,
            self.mid_pct,
            self.upper_mid_pct,
            self.presence_pct,
            self.air_pct,
            self.lufs,
            self.crest_db,
            self.bass_mid_ratio,
            self.tempo_bpm,
            self.rhythm_stability,
            self.transient_density,
            self.silence_ratio,
            self.spectral_centroid,
            self.spectral_rolloff,
            self.spectral_flatness,
            self.harmonic_ratio,
            self.pitch_stability,
            self.chroma_energy,
            self.dynamic_range_variation,
            self.loudness_variation_std,
            self.peak_consistency,
            self.stereo_width,
            self.phase_correlation,
        ]
        .iter()
        .filter(|&&v| v.is_finite())
        .count()
    }

    /// Check if fingerprint is valid (all 25 dimensions present)
    pub fn is_valid(&self) -> bool {
        self.valid_dimensions() == 25
    }
}
