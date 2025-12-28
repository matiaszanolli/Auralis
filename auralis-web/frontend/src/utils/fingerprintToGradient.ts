/**
 * Fingerprint-to-Gradient Mapping Utility
 *
 * Converts 25D audio fingerprints into unique CSS gradients
 * Maps perceptually meaningful dimensions to visual properties:
 *
 * - Frequency Distribution → Gradient Colors (bass=warm, treble=cool)
 * - Spectral Centroid → Brightness
 * - LUFS (Loudness) → Saturation
 * - Stereo Width → Gradient Angle
 * - Harmonic Ratio → Gradient Smoothness
 */

export interface AudioFingerprint {
  // Frequency Distribution (7D)
  sub_bass: number;      // 20-60 Hz
  bass: number;          // 60-250 Hz
  low_mid: number;       // 250-500 Hz
  mid: number;           // 500-2000 Hz
  upper_mid: number;     // 2000-4000 Hz
  presence: number;      // 4000-8000 Hz
  air: number;           // 8000-20000 Hz

  // Dynamics (3D)
  lufs: number;          // -120 to 0 dB
  crest_db: number;      // Peak-to-RMS ratio
  bass_mid_ratio: number;

  // Spectral (3D)
  spectral_centroid: number;  // Brightness
  spectral_rolloff: number;
  spectral_flatness: number;

  // Harmonic (3D)
  harmonic_ratio: number;     // 0-1
  pitch_stability: number;
  chroma_energy: number;

  // Stereo (2D)
  stereo_width: number;       // 0-1
  phase_correlation: number;

  // Temporal (4D) - not used for gradients
  tempo_bpm?: number;
  rhythm_stability?: number;
  transient_density?: number;
  silence_ratio?: number;

  // Variation (3D) - not used for gradients
  dynamic_range_variation?: number;
  loudness_variation?: number;
  peak_consistency?: number;
}

/**
 * Compute dominant frequency region from frequency distribution
 * Returns: 'bass' | 'mid' | 'treble'
 */
function getDominantFrequencyRegion(fp: AudioFingerprint): 'bass' | 'mid' | 'treble' {
  const bassEnergy = fp.sub_bass + fp.bass + fp.low_mid;
  const midEnergy = fp.mid + fp.upper_mid;
  const trebleEnergy = fp.presence + fp.air;

  const max = Math.max(bassEnergy, midEnergy, trebleEnergy);

  if (bassEnergy === max) return 'bass';
  if (midEnergy === max) return 'mid';
  return 'treble';
}

/**
 * Map frequency region to base hue (HSL color space)
 * Bass → Warm (0-60°: reds, oranges)
 * Mid → Neutral (60-180°: yellows, greens)
 * Treble → Cool (180-270°: blues, purples)
 */
function frequencyToHue(fp: AudioFingerprint): number {
  const region = getDominantFrequencyRegion(fp);

  // Compute weighted hue within region
  const bassEnergy = fp.sub_bass + fp.bass + fp.low_mid;
  const midEnergy = fp.mid + fp.upper_mid;
  const trebleEnergy = fp.presence + fp.air;

  const total = bassEnergy + midEnergy + trebleEnergy;
  if (total < 0.01) return 220; // Default blue for silent tracks

  // Weighted blend based on energy distribution
  const bassWeight = bassEnergy / total;
  const midWeight = midEnergy / total;
  const trebleWeight = trebleEnergy / total;

  // Map to hue ranges:
  // Bass: 0-40° (reds, oranges)
  // Mid: 40-180° (yellows, greens)
  // Treble: 180-280° (blues, purples)
  const bassHue = 20;      // Warm orange
  const midHue = 120;      // Green
  const trebleHue = 220;   // Blue

  const hue = bassHue * bassWeight + midHue * midWeight + trebleHue * trebleWeight;
  return Math.round(hue);
}

/**
 * Map LUFS (loudness) to saturation percentage
 * Quiet tracks (-40 LUFS) → Low saturation (muted)
 * Loud tracks (-10 LUFS) → High saturation (vivid)
 */
function lufsToSaturation(lufs: number): number {
  // LUFS range: -120 to 0 (typical music: -40 to -10)
  const normalizedLufs = Math.max(-40, Math.min(-10, lufs));

  // Map to saturation: -40 → 30%, -10 → 70%
  const saturation = 30 + ((normalizedLufs + 40) / 30) * 40;
  return Math.round(saturation);
}

/**
 * Map spectral centroid to lightness percentage
 * Low centroid (bass-heavy) → Darker
 * High centroid (bright) → Lighter
 */
function spectralCentroidToLightness(centroid: number): number {
  // Typical range: 500-8000 Hz
  const normalizedCentroid = Math.max(500, Math.min(8000, centroid));

  // Map to lightness: 500 Hz → 35%, 8000 Hz → 65%
  const lightness = 35 + ((normalizedCentroid - 500) / 7500) * 30;
  return Math.round(lightness);
}

/**
 * Map stereo width to gradient angle
 * Narrow (mono) → Vertical (180°)
 * Wide (stereo) → Diagonal (135°)
 */
function stereoWidthToAngle(width: number): number {
  // Width range: 0 (mono) to 1 (wide stereo)
  const angle = 180 - (width * 45); // 180° to 135°
  return Math.round(angle);
}

/**
 * Generate secondary color for gradient (complementary or analogous)
 * Harmonic tracks → Analogous (smooth)
 * Percussive tracks → Complementary (contrast)
 */
function getSecondaryHue(primaryHue: number, harmonicRatio: number): number {
  // Harmonic (smooth) → Analogous (+30°)
  // Percussive (transient) → Complementary (+180°)
  const shift = 30 + (1 - harmonicRatio) * 150; // 30° to 180°
  return (primaryHue + shift) % 360;
}

/**
 * Generate CSS gradient from audio fingerprint
 *
 * @param fingerprint - 25D audio fingerprint
 * @returns CSS gradient string (linear-gradient)
 */
export function fingerprintToGradient(fingerprint: AudioFingerprint): string {
  // 1. Compute primary color from frequency distribution
  const hue = frequencyToHue(fingerprint);
  const saturation = lufsToSaturation(fingerprint.lufs);
  const lightness = spectralCentroidToLightness(fingerprint.spectral_centroid);

  const primaryColor = `hsl(${hue}, ${saturation}%, ${lightness}%)`;

  // 2. Compute secondary color from harmonic ratio
  const secondaryHue = getSecondaryHue(hue, fingerprint.harmonic_ratio);
  const secondaryColor = `hsl(${secondaryHue}, ${saturation}%, ${lightness}%)`;

  // 3. Compute gradient angle from stereo width
  const angle = stereoWidthToAngle(fingerprint.stereo_width);

  // 4. Generate gradient
  // Harmonic tracks → Smooth blend
  // Percussive tracks → Sharper transitions
  const blendMidpoint = 50 + (fingerprint.harmonic_ratio - 0.5) * 20; // 40-60%

  return `linear-gradient(${angle}deg, ${primaryColor} 0%, ${secondaryColor} ${blendMidpoint}%, ${primaryColor} 100%)`;
}

/**
 * Generate CSS gradient from partial fingerprint (fallback)
 * Used when fingerprint is incomplete or missing dimensions
 */
export function fingerprintToGradientSafe(fingerprint: Partial<AudioFingerprint>): string {
  // Default values for missing fields
  const safeFp: AudioFingerprint = {
    sub_bass: fingerprint.sub_bass ?? 0.1,
    bass: fingerprint.bass ?? 0.15,
    low_mid: fingerprint.low_mid ?? 0.15,
    mid: fingerprint.mid ?? 0.25,
    upper_mid: fingerprint.upper_mid ?? 0.2,
    presence: fingerprint.presence ?? 0.1,
    air: fingerprint.air ?? 0.05,
    lufs: fingerprint.lufs ?? -23,
    crest_db: fingerprint.crest_db ?? 10,
    bass_mid_ratio: fingerprint.bass_mid_ratio ?? 0.5,
    spectral_centroid: fingerprint.spectral_centroid ?? 2000,
    spectral_rolloff: fingerprint.spectral_rolloff ?? 8000,
    spectral_flatness: fingerprint.spectral_flatness ?? 0.5,
    harmonic_ratio: fingerprint.harmonic_ratio ?? 0.7,
    pitch_stability: fingerprint.pitch_stability ?? 0.75,
    chroma_energy: fingerprint.chroma_energy ?? 0.6,
    stereo_width: fingerprint.stereo_width ?? 0.5,
    phase_correlation: fingerprint.phase_correlation ?? 0.95,
  };

  return fingerprintToGradient(safeFp);
}

/**
 * Compute median fingerprint from array of track fingerprints
 * Used for album-level aggregation
 */
export function computeMedianFingerprint(fingerprints: AudioFingerprint[]): AudioFingerprint {
  if (fingerprints.length === 0) {
    throw new Error('Cannot compute median of empty fingerprint array');
  }

  if (fingerprints.length === 1) {
    return fingerprints[0];
  }

  // Compute median for each dimension
  const median = (values: number[]): number => {
    const sorted = [...values].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    return sorted.length % 2 === 0
      ? (sorted[mid - 1] + sorted[mid]) / 2
      : sorted[mid];
  };

  return {
    sub_bass: median(fingerprints.map(fp => fp.sub_bass)),
    bass: median(fingerprints.map(fp => fp.bass)),
    low_mid: median(fingerprints.map(fp => fp.low_mid)),
    mid: median(fingerprints.map(fp => fp.mid)),
    upper_mid: median(fingerprints.map(fp => fp.upper_mid)),
    presence: median(fingerprints.map(fp => fp.presence)),
    air: median(fingerprints.map(fp => fp.air)),
    lufs: median(fingerprints.map(fp => fp.lufs)),
    crest_db: median(fingerprints.map(fp => fp.crest_db)),
    bass_mid_ratio: median(fingerprints.map(fp => fp.bass_mid_ratio)),
    spectral_centroid: median(fingerprints.map(fp => fp.spectral_centroid)),
    spectral_rolloff: median(fingerprints.map(fp => fp.spectral_rolloff)),
    spectral_flatness: median(fingerprints.map(fp => fp.spectral_flatness)),
    harmonic_ratio: median(fingerprints.map(fp => fp.harmonic_ratio)),
    pitch_stability: median(fingerprints.map(fp => fp.pitch_stability)),
    chroma_energy: median(fingerprints.map(fp => fp.chroma_energy)),
    stereo_width: median(fingerprints.map(fp => fp.stereo_width)),
    phase_correlation: median(fingerprints.map(fp => fp.phase_correlation)),
  };
}
