/**
 * albumCharacterDescriptors — loudness variation key (#4429)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * `AudioFingerprint` declared `loudness_variation`; both backend emitters
 * (`routers/fingerprint_status.py` and `routers/albums.py`) send
 * `loudness_variation_std`, matching the DB column and every Python consumer.
 *
 * Because the field is optional, nothing failed to compile and nothing threw —
 * it was just `undefined` forever. `analyzeDynamics` reads it as
 * `?? 1.5`, and 1.5 falls between the two thresholds (`> 2.5` → "Variable",
 * `< 1.0` → "Consistent"), so neither tag could ever be produced for any album.
 * These tests pin that the tags react to real backend data again.
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { describe, it, expect } from 'vitest';
import type { AudioFingerprint } from '../fingerprintToGradient';
import { computeAlbumCharacter } from '../albumCharacterDescriptors';

/** Minimal valid fingerprint; crest_db sits between the Dynamic/Compressed
 *  thresholds so only the loudness-variation branch is under test. */
const baseFp: AudioFingerprint = {
  sub_bass: 0.1, bass: 0.15, low_mid: 0.15,
  mid: 0.25, upper_mid: 0.2,
  presence: 0.1, air: 0.05,
  lufs: -23, crest_db: 10, bass_mid_ratio: 0.5,
  spectral_centroid: 2000, spectral_rolloff: 8000, spectral_flatness: 0.5,
  harmonic_ratio: 0.7, pitch_confidence: 0.75, chroma_energy_mean: 0.6,
  stereo_width: 0.5, stereo_correlation: 0.95,
};

const labelsFor = (overrides: Partial<AudioFingerprint>): string[] =>
  computeAlbumCharacter({ ...baseFp, ...overrides }).tags.map((t) => t.label);

describe('analyzeDynamics loudness variation (#4429)', () => {
  it('emits "Variable" for a high loudness_variation_std', () => {
    expect(labelsFor({ loudness_variation_std: 3.0 })).toContain('Variable');
  });

  it('emits "Consistent" for a low loudness_variation_std', () => {
    expect(labelsFor({ loudness_variation_std: 0.5 })).toContain('Consistent');
  });

  it('emits neither tag in the middle band', () => {
    const labels = labelsFor({ loudness_variation_std: 1.5 });
    expect(labels).not.toContain('Variable');
    expect(labels).not.toContain('Consistent');
  });

  it('falls back to the neutral 1.5 when the field is absent', () => {
    const labels = labelsFor({});
    expect(labels).not.toContain('Variable');
    expect(labels).not.toContain('Consistent');
  });

  it('ignores the retired loudness_variation spelling', () => {
    // Guards the regression directly: if the consumer is reverted to the old
    // key, this value would produce "Variable" instead of the neutral fallback.
    const labels = labelsFor({ loudness_variation: 3.0 } as Partial<AudioFingerprint>);
    expect(labels).not.toContain('Variable');
    expect(labels).not.toContain('Consistent');
  });
});
