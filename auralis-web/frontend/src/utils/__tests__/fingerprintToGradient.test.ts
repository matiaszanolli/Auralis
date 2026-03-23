import { describe, it, expect } from 'vitest';
import {
  AudioFingerprint,
  fingerprintToGradient,
  fingerprintToGradientSafe,
  computeMedianFingerprint,
} from '../fingerprintToGradient';

/** Minimal valid fingerprint with all required fields */
const baseFp: AudioFingerprint = {
  sub_bass: 0.1, bass: 0.15, low_mid: 0.15,
  mid: 0.25, upper_mid: 0.2,
  presence: 0.1, air: 0.05,
  lufs: -23, crest_db: 10, bass_mid_ratio: 0.5,
  spectral_centroid: 2000, spectral_rolloff: 8000, spectral_flatness: 0.5,
  harmonic_ratio: 0.7, pitch_confidence: 0.75, chroma_energy_mean: 0.6,
  stereo_width: 0.5, stereo_correlation: 0.95,
};

/** Helper: override specific fields */
const fp = (overrides: Partial<AudioFingerprint> = {}): AudioFingerprint => ({
  ...baseFp,
  ...overrides,
});

describe('fingerprintToGradient', () => {
  describe('fingerprintToGradient', () => {
    it('should return a valid CSS linear-gradient string', () => {
      const result = fingerprintToGradient(baseFp);
      expect(result).toMatch(/^linear-gradient\(\d+deg,\s*hsl\(.+\)\s+0%,\s*hsl\(.+\)\s+[\d.]+%,\s*hsl\(.+\)\s+100%\)$/);
    });

    it('bass-heavy fingerprint should produce warm hue (low degrees)', () => {
      const bassHeavy = fp({ sub_bass: 0.5, bass: 0.4, low_mid: 0.3, mid: 0.01, upper_mid: 0.01, presence: 0.01, air: 0.01 });
      const result = fingerprintToGradient(bassHeavy);
      // Extract primary hue
      const hue = parseInt(result.match(/hsl\((\d+)/)?.[1] ?? '0');
      expect(hue).toBeLessThan(60); // Warm colors
    });

    it('treble-heavy fingerprint should produce cool hue (high degrees)', () => {
      const trebleHeavy = fp({ sub_bass: 0.01, bass: 0.01, low_mid: 0.01, mid: 0.01, upper_mid: 0.01, presence: 0.5, air: 0.5 });
      const result = fingerprintToGradient(trebleHeavy);
      const hue = parseInt(result.match(/hsl\((\d+)/)?.[1] ?? '0');
      expect(hue).toBeGreaterThan(150); // Cool colors
    });

    it('loud track should have higher saturation than quiet track', () => {
      const loud = fingerprintToGradient(fp({ lufs: -10 }));
      const quiet = fingerprintToGradient(fp({ lufs: -40 }));
      const loudSat = parseInt(loud.match(/hsl\(\d+,\s*(\d+)%/)?.[1] ?? '0');
      const quietSat = parseInt(quiet.match(/hsl\(\d+,\s*(\d+)%/)?.[1] ?? '0');
      expect(loudSat).toBeGreaterThan(quietSat);
    });

    it('bright track should have higher lightness than dark track', () => {
      const bright = fingerprintToGradient(fp({ spectral_centroid: 8000 }));
      const dark = fingerprintToGradient(fp({ spectral_centroid: 500 }));
      const brightLight = parseInt(bright.match(/hsl\(\d+,\s*\d+%,\s*(\d+)%/)?.[1] ?? '0');
      const darkLight = parseInt(dark.match(/hsl\(\d+,\s*\d+%,\s*(\d+)%/)?.[1] ?? '0');
      expect(brightLight).toBeGreaterThan(darkLight);
    });

    it('wide stereo should have different angle than mono', () => {
      const wide = fingerprintToGradient(fp({ stereo_width: 1.0 }));
      const mono = fingerprintToGradient(fp({ stereo_width: 0.0 }));
      const wideAngle = parseInt(wide.match(/linear-gradient\((\d+)deg/)?.[1] ?? '0');
      const monoAngle = parseInt(mono.match(/linear-gradient\((\d+)deg/)?.[1] ?? '0');
      expect(monoAngle).toBe(180);
      expect(wideAngle).toBe(135);
    });

    it('should be deterministic (same input → same output)', () => {
      const a = fingerprintToGradient(baseFp);
      const b = fingerprintToGradient(baseFp);
      expect(a).toBe(b);
    });

    it('should handle near-zero energy gracefully', () => {
      const silent = fp({ sub_bass: 0, bass: 0, low_mid: 0, mid: 0, upper_mid: 0, presence: 0, air: 0 });
      const result = fingerprintToGradient(silent);
      expect(result).toMatch(/^linear-gradient/);
      // Default blue hue (220) for silent tracks
      const hue = parseInt(result.match(/hsl\((\d+)/)?.[1] ?? '0');
      expect(hue).toBe(220);
    });
  });

  describe('fingerprintToGradientSafe', () => {
    it('should accept an empty object and return a valid gradient', () => {
      const result = fingerprintToGradientSafe({});
      expect(result).toMatch(/^linear-gradient/);
    });

    it('should use provided values over defaults', () => {
      const withLufs = fingerprintToGradientSafe({ lufs: -10 });
      const withDefault = fingerprintToGradientSafe({});
      // Different lufs → different saturation
      expect(withLufs).not.toBe(withDefault);
    });

    it('should produce same result as full function when all fields provided', () => {
      const safe = fingerprintToGradientSafe(baseFp);
      const full = fingerprintToGradient(baseFp);
      expect(safe).toBe(full);
    });
  });

  describe('computeMedianFingerprint', () => {
    it('should throw on empty array', () => {
      expect(() => computeMedianFingerprint([])).toThrow('Cannot compute median of empty fingerprint array');
    });

    it('should return the single element for array of length 1', () => {
      const result = computeMedianFingerprint([baseFp]);
      expect(result).toBe(baseFp);
    });

    it('should compute median for odd-length array', () => {
      const fps = [fp({ lufs: -30 }), fp({ lufs: -20 }), fp({ lufs: -10 })];
      const result = computeMedianFingerprint(fps);
      expect(result.lufs).toBe(-20);
    });

    it('should compute average of two middle values for even-length array', () => {
      const fps = [fp({ lufs: -30 }), fp({ lufs: -20 }), fp({ lufs: -10 }), fp({ lufs: 0 })];
      const result = computeMedianFingerprint(fps);
      expect(result.lufs).toBe(-15);
    });

    it('should compute median independently per dimension', () => {
      const fps = [
        fp({ bass: 0.1, mid: 0.9 }),
        fp({ bass: 0.5, mid: 0.5 }),
        fp({ bass: 0.9, mid: 0.1 }),
      ];
      const result = computeMedianFingerprint(fps);
      expect(result.bass).toBe(0.5);
      expect(result.mid).toBe(0.5);
    });

    it('should include all 18 required dimensions in result', () => {
      const result = computeMedianFingerprint([baseFp, baseFp]);
      const requiredKeys: (keyof AudioFingerprint)[] = [
        'sub_bass', 'bass', 'low_mid', 'mid', 'upper_mid', 'presence', 'air',
        'lufs', 'crest_db', 'bass_mid_ratio',
        'spectral_centroid', 'spectral_rolloff', 'spectral_flatness',
        'harmonic_ratio', 'pitch_confidence', 'chroma_energy_mean',
        'stereo_width', 'stereo_correlation',
      ];
      for (const key of requiredKeys) {
        expect(result).toHaveProperty(key);
        expect(typeof result[key]).toBe('number');
      }
    });
  });
});
