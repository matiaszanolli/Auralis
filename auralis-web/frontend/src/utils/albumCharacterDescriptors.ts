/**
 * Album Character Descriptors
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Generates human-readable descriptors from audio fingerprints.
 * Maps technical metrics to perceptual qualities.
 *
 * Used by Album Character Pane to show textual descriptions
 * of album's sonic identity.
 */

import type { AudioFingerprint } from './fingerprintToGradient';

/**
 * Character tag (short descriptor)
 */
export interface CharacterTag {
  label: string;
  category: 'energy' | 'tone' | 'dynamics' | 'space' | 'texture';
}

/**
 * Album character profile
 */
export interface AlbumCharacter {
  /** Short descriptive tags (3-5 tags) */
  tags: CharacterTag[];
  /** Energy level (0-1, for CALM ↔ AGGRESSIVE slider) */
  energyLevel: number;
  /** Brief textual description */
  description: string;
  /** Multiple descriptions for rotation during playback */
  rotatingDescriptions: string[];
}

/**
 * Analyze energy level from fingerprint
 * Returns 0 (calm) to 1 (aggressive)
 */
function analyzeEnergy(fp: AudioFingerprint): number {
  // Factors contributing to energy:
  // - Loudness (LUFS)
  // - Transient density (percussive content)
  // - Dynamic range (crest factor)
  // - Tempo

  const lufsNormalized = Math.max(0, Math.min(1, (fp.lufs + 40) / 30)); // -40 to -10 → 0 to 1
  const transientWeight = fp.transient_density ?? 0.5;
  const tempoWeight = Math.min(1, (fp.tempo_bpm ?? 120) / 180); // 0-180 BPM → 0-1
  const crestWeight = Math.min(1, (fp.crest_db ?? 10) / 20); // 0-20 dB → 0-1

  // Weighted average
  const energy =
    lufsNormalized * 0.35 +
    transientWeight * 0.3 +
    tempoWeight * 0.2 +
    crestWeight * 0.15;

  return Math.max(0, Math.min(1, energy));
}

/**
 * Analyze tonal character from frequency distribution
 */
function analyzeTone(fp: AudioFingerprint): CharacterTag[] {
  const tags: CharacterTag[] = [];

  const bassEnergy = fp.sub_bass + fp.bass;
  const midEnergy = fp.mid + fp.upper_mid;
  const trebleEnergy = fp.presence + fp.air;

  // Dominant frequency region
  if (bassEnergy > midEnergy && bassEnergy > trebleEnergy) {
    if (bassEnergy > 0.5) {
      tags.push({ label: 'Bass-heavy', category: 'tone' });
    } else {
      tags.push({ label: 'Warm', category: 'tone' });
    }
  } else if (trebleEnergy > midEnergy && trebleEnergy > bassEnergy) {
    if (trebleEnergy > 0.4) {
      tags.push({ label: 'Bright', category: 'tone' });
    } else {
      tags.push({ label: 'Airy', category: 'tone' });
    }
  } else {
    tags.push({ label: 'Balanced', category: 'tone' });
  }

  // Spectral centroid
  if (fp.spectral_centroid > 3500) {
    tags.push({ label: 'Crisp', category: 'tone' });
  } else if (fp.spectral_centroid < 1500) {
    tags.push({ label: 'Dark', category: 'tone' });
  }

  return tags;
}

/**
 * Analyze dynamics from dynamic range metrics
 */
function analyzeDynamics(fp: AudioFingerprint): CharacterTag[] {
  const tags: CharacterTag[] = [];

  // Crest factor (dynamic range)
  if (fp.crest_db > 15) {
    tags.push({ label: 'Dynamic', category: 'dynamics' });
  } else if (fp.crest_db < 8) {
    tags.push({ label: 'Compressed', category: 'dynamics' });
  }

  // Loudness variation
  const loudnessVar = fp.loudness_variation ?? 1.5;
  if (loudnessVar > 2.5) {
    tags.push({ label: 'Variable', category: 'dynamics' });
  } else if (loudnessVar < 1.0) {
    tags.push({ label: 'Consistent', category: 'dynamics' });
  }

  return tags;
}

/**
 * Analyze spatial characteristics
 */
function analyzeSpatial(fp: AudioFingerprint): CharacterTag[] {
  const tags: CharacterTag[] = [];

  // Stereo width
  if (fp.stereo_width > 0.7) {
    tags.push({ label: 'Wide stereo', category: 'space' });
  } else if (fp.stereo_width < 0.3) {
    tags.push({ label: 'Narrow', category: 'space' });
  }

  // Phase correlation
  if (fp.phase_correlation < 0.7) {
    tags.push({ label: 'Spacious', category: 'space' });
  }

  return tags;
}

/**
 * Analyze texture from harmonic and spectral characteristics
 */
function analyzeTexture(fp: AudioFingerprint): CharacterTag[] {
  const tags: CharacterTag[] = [];

  // Harmonic ratio
  if (fp.harmonic_ratio > 0.75) {
    tags.push({ label: 'Melodic', category: 'texture' });
  } else if (fp.harmonic_ratio < 0.4) {
    tags.push({ label: 'Percussive', category: 'texture' });
  }

  // Spectral flatness (tonality vs noisiness)
  if (fp.spectral_flatness > 0.7) {
    tags.push({ label: 'Noisy', category: 'texture' });
  } else if (fp.spectral_flatness < 0.3) {
    tags.push({ label: 'Tonal', category: 'texture' });
  }

  // Transient density
  const transientDensity = fp.transient_density ?? 0.5;
  if (transientDensity > 0.7) {
    tags.push({ label: 'Punchy', category: 'texture' });
  } else if (transientDensity < 0.3) {
    tags.push({ label: 'Smooth', category: 'texture' });
  }

  return tags;
}

/**
 * Analyze energy characteristics
 */
function analyzeEnergyTags(fp: AudioFingerprint): CharacterTag[] {
  const tags: CharacterTag[] = [];

  const energy = analyzeEnergy(fp);

  if (energy > 0.75) {
    tags.push({ label: 'High-energy', category: 'energy' });
  } else if (energy < 0.35) {
    tags.push({ label: 'Relaxed', category: 'energy' });
  } else {
    tags.push({ label: 'Moderate', category: 'energy' });
  }

  // Tempo-based tags
  const tempo = fp.tempo_bpm ?? 120;
  if (tempo > 140) {
    tags.push({ label: 'Fast-paced', category: 'energy' });
  } else if (tempo < 80) {
    tags.push({ label: 'Slow', category: 'energy' });
  }

  return tags;
}

/**
 * Generate textual description from fingerprint
 */
function generateDescription(fp: AudioFingerprint, _tags: CharacterTag[]): string {
  const energy = analyzeEnergy(fp);
  const stereoWidth = fp.stereo_width;

  // Build description from characteristics
  const parts: string[] = [];

  // Energy descriptor
  if (energy > 0.7) {
    parts.push('Energetic & dynamic');
  } else if (energy < 0.4) {
    parts.push('Calm & relaxed');
  } else {
    parts.push('Balanced & controlled');
  }

  // Spatial descriptor
  if (stereoWidth > 0.6) {
    parts.push('with a wide, immersive stereo field');
  } else if (stereoWidth < 0.4) {
    parts.push('with focused, centered imaging');
  }

  return parts.join(' ') + '.';
}

/**
 * Generate multiple rotating descriptions for playback mode
 * Creates the impression that the system is continuously interpreting.
 *
 * IMPORTANT: Descriptors must be orthogonal, not contradictory.
 * Each category describes a DISTINCT perceptual dimension:
 * - Frequency: Tonal balance (bass/mid/treble focus)
 * - Dynamics: Loudness variation (compression level)
 * - Spatial: Stereo imaging (width/center)
 * - Texture: Attack character (transient handling)
 * - Energy: Overall intensity (calm/driving)
 * - Harmonic: Tonal vs noise content (melodic quality)
 *
 * No two descriptors should use overlapping vocabulary.
 */
function generateRotatingDescriptions(fp: AudioFingerprint): string[] {
  const descriptions: string[] = [];
  const energy = analyzeEnergy(fp);
  const transientDensity = fp.transient_density ?? 0.5;

  // ─────────────────────────────────────────────────────────────────
  // 1. FREQUENCY BALANCE (what frequency region dominates)
  // ─────────────────────────────────────────────────────────────────
  const bassEnergy = fp.sub_bass + fp.bass;
  const midEnergy = fp.mid + fp.upper_mid;
  const trebleEnergy = fp.presence + fp.air;

  if (bassEnergy > midEnergy && bassEnergy > trebleEnergy) {
    descriptions.push('Grounded low-end with controlled warmth.');
  } else if (trebleEnergy > midEnergy && trebleEnergy > bassEnergy) {
    descriptions.push('Forward presence with open air frequencies.');
  } else {
    descriptions.push('Focused midrange with vocal clarity.');
  }

  // ─────────────────────────────────────────────────────────────────
  // 2. DYNAMICS (loudness variation / compression character)
  // ─────────────────────────────────────────────────────────────────
  if (fp.crest_db > 15) {
    descriptions.push('Wide dynamic range with natural headroom.');
  } else if (fp.crest_db > 10) {
    descriptions.push('Balanced loudness with expressive peaks.');
  } else {
    descriptions.push('Consistent levels with dense layering.');
  }

  // ─────────────────────────────────────────────────────────────────
  // 3. SPATIAL (stereo field character)
  // ─────────────────────────────────────────────────────────────────
  if (fp.stereo_width > 0.7) {
    descriptions.push('Expansive stereo field with immersive depth.');
  } else if (fp.stereo_width < 0.4) {
    descriptions.push('Centered imaging with mono-compatible focus.');
  } else {
    descriptions.push('Balanced spatial presentation.');
  }

  // ─────────────────────────────────────────────────────────────────
  // 4. TEXTURE (attack / transient character)
  // ─────────────────────────────────────────────────────────────────
  if (transientDensity > 0.6) {
    descriptions.push('Crisp transients with defined attack.');
  } else if (transientDensity < 0.35) {
    descriptions.push('Smooth textures with gentle onset.');
  } else {
    descriptions.push('Natural attack with organic decay.');
  }

  // ─────────────────────────────────────────────────────────────────
  // 5. ENERGY (overall intensity / pacing feel)
  // ─────────────────────────────────────────────────────────────────
  if (energy > 0.75) {
    descriptions.push('High-energy character with forward drive.');
  } else if (energy < 0.35) {
    descriptions.push('Relaxed intensity with atmospheric space.');
  } else {
    descriptions.push('Moderate pacing with controlled momentum.');
  }

  // ─────────────────────────────────────────────────────────────────
  // 6. HARMONIC (melodic vs noise content - only if distinctive)
  // Skip if transient already emphasizes similar character to avoid redundancy
  // ─────────────────────────────────────────────────────────────────
  if (fp.harmonic_ratio > 0.7) {
    descriptions.push('Rich harmonic overtones with tonal depth.');
  } else if (fp.harmonic_ratio < 0.4 && transientDensity <= 0.6) {
    // Only add percussive harmonic description if texture didn't already
    // emphasize transients, to avoid saying "crisp transients" + "percussive"
    descriptions.push('Noise-forward spectrum with textured character.');
  }

  return descriptions;
}

/**
 * Compute album character from fingerprint
 *
 * @param fingerprint - Album's median fingerprint
 * @returns Character profile with tags, energy level, and description
 */
export function computeAlbumCharacter(fingerprint: AudioFingerprint): AlbumCharacter {
  // Analyze all dimensions
  const toneTags = analyzeTone(fingerprint);
  const dynamicsTags = analyzeDynamics(fingerprint);
  const spatialTags = analyzeSpatial(fingerprint);
  const textureTags = analyzeTexture(fingerprint);
  const energyTags = analyzeEnergyTags(fingerprint);

  // Combine all tags
  const allTags = [
    ...toneTags,
    ...dynamicsTags,
    ...spatialTags,
    ...textureTags,
    ...energyTags,
  ];

  // Select top 4-5 most distinctive tags
  // Prioritize: energy > tone > space > dynamics > texture
  const priorityOrder: Record<CharacterTag['category'], number> = {
    energy: 5,
    tone: 4,
    space: 3,
    dynamics: 2,
    texture: 1,
  };

  const selectedTags = allTags
    .sort((a, b) => priorityOrder[b.category] - priorityOrder[a.category])
    .slice(0, 5);

  // Compute energy level
  const energyLevel = analyzeEnergy(fingerprint);

  // Generate description
  const description = generateDescription(fingerprint, selectedTags);

  // Generate rotating descriptions for playback mode
  const rotatingDescriptions = generateRotatingDescriptions(fingerprint);

  return {
    tags: selectedTags,
    energyLevel,
    description,
    rotatingDescriptions,
  };
}
