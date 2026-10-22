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
import {
  analyzeDynamics,
  analyzeEnergy,
  analyzeEnergyTags,
  analyzeSpatial,
  analyzeTexture,
  analyzeTone,
  type CharacterTag,
} from './albumCharacterAnalysis';

export type { CharacterTag };


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
 * Generate textual description from fingerprint
 */
function generateDescription(fp: AudioFingerprint): string {
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
  const description = generateDescription(fingerprint);

  // Generate rotating descriptions for playback mode
  const rotatingDescriptions = generateRotatingDescriptions(fingerprint);

  return {
    tags: selectedTags,
    energyLevel,
    description,
    rotatingDescriptions,
  };
}
