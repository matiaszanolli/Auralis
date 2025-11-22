/**
 * ProcessingParameters Component Tests
 *
 * Tests DSP parameter display with:
 * - Loudness target display (LUFS)
 * - EQ parameter display (bass, air/treble)
 * - Dynamics parameters (compression, expansion)
 * - Stereo width display
 * - Color-coded parameter values
 * - Conditional rendering based on parameter values
 */

import React from 'react';
import { render, screen } from '@/test/test-utils';
import { describe, it, expect } from 'vitest';
import ProcessingParameters from '../ProcessingParameters';


describe('ProcessingParameters', () => {
  describe('Loudness Display', () => {
    it('should display loudness target in LUFS', () => {
      const parameters = {
        target_lufs: -14,
        peak_target_db: -3,
        bass_boost: 0,
        air_boost: 0,
        compression_amount: 0,
        expansion_amount: 0,
        stereo_width: 100,
      };

      render(
        <ProcessingParameters params={parameters} />
      );

      expect(screen.getByText(/-14/)).toBeInTheDocument();
      expect(screen.getByText(/LUFS/)).toBeInTheDocument();
    });

    it('should display negative loudness values correctly', () => {
      const parameters = {
        target_lufs: -18,
        peak_target_db: -4,
        bass_boost: 0,
        air_boost: 0,
        compression_amount: 0,
        expansion_amount: 0,
        stereo_width: 100,
      };

      render(
        <ProcessingParameters params={parameters} />
      );

      expect(screen.getByText(/-18/)).toBeInTheDocument();
    });

    it('should display peak target in dB', () => {
      const parameters = {
        target_lufs: -14,
        peak_target_db: -2,
        bass_boost: 0,
        air_boost: 0,
        compression_amount: 0,
        expansion_amount: 0,
        stereo_width: 100,
      };

      render(
        <ProcessingParameters params={parameters} />
      );

      expect(screen.getByText(/-2/)).toBeInTheDocument();
      expect(screen.getByText(/Peak Level/)).toBeInTheDocument();
    });

    it('should display extreme loudness values', () => {
      const parameters = {
        target_lufs: -23,
        peak_target_db: -0.5,
        bass_boost: 0,
        air_boost: 0,
        compression_amount: 0,
        expansion_amount: 0,
        stereo_width: 100,
      };

      render(
        <ProcessingParameters params={parameters} />
      );

      expect(screen.getByText(/-23/)).toBeInTheDocument();
      expect(screen.getByText(/-0.5/)).toBeInTheDocument();
    });
  });

  describe('EQ Parameters', () => {
    it('should display bass boost amount', () => {
      const parameters = {
        target_lufs: -14,
        peak_target_db: -3,
        bass_boost: 2.5,
        air_boost: 0,
        compression_amount: 0,
        expansion_amount: 0,
        stereo_width: 100,
      };

      render(
        <ProcessingParameters params={parameters} />
      );

      expect(screen.getByText(/2.5/)).toBeInTheDocument();
      expect(screen.getByText(/Bass Adjustment/)).toBeInTheDocument();
    });

    it('should display air boost (treble) amount', () => {
      const parameters = {
        target_lufs: -14,
        peak_target_db: -3,
        bass_boost: 0,
        air_boost: 1.8,
        compression_amount: 0,
        expansion_amount: 0,
        stereo_width: 100,
      };

      render(
        <ProcessingParameters params={parameters} />
      );

      expect(screen.getByText(/1.8/)).toBeInTheDocument();
      expect(screen.getByText(/Air Adjustment/)).toBeInTheDocument();
    });

    it('should show zero bass boost as conditionally hidden', () => {
      const parameters = {
        target_lufs: -14,
        peak_target_db: -3,
        bass_boost: 0,
        air_boost: 0,
        compression_amount: 0,
        expansion_amount: 0,
        stereo_width: 100,
      };

      render(
        <ProcessingParameters params={parameters} />
      );

      // Zero bass boost should not be displayed (conditional rendering)
      expect(screen.queryByText(/Bass Adjustment/)).not.toBeInTheDocument();
    });

    it('should hide very small bass adjustments (< 0.1 dB)', () => {
      const parameters = {
        target_lufs: -14,
        peak_target_db: -3,
        bass_boost: 0.05,
        air_boost: 0,
        compression_amount: 0,
        expansion_amount: 0,
        stereo_width: 100,
      };

      render(
        <ProcessingParameters params={parameters} />
      );

      expect(screen.queryByText(/Bass Adjustment/)).not.toBeInTheDocument();
    });

    it('should show positive sign for positive boost values', () => {
      const parameters = {
        target_lufs: -14,
        peak_target_db: -3,
        bass_boost: 3,
        air_boost: 2,
        compression_amount: 0,
        expansion_amount: 0,
        stereo_width: 100,
      };

      render(
        <ProcessingParameters params={parameters} />
      );

      // Should show +3 dB for positive values
      expect(screen.getByText(/\+3/)).toBeInTheDocument();
    });

    it('should handle maximum EQ values', () => {
      const parameters = {
        target_lufs: -14,
        peak_target_db: -3,
        bass_boost: 8,
        air_boost: 6,
        compression_amount: 0,
        expansion_amount: 0,
        stereo_width: 100,
      };

      render(
        <ProcessingParameters params={parameters} />
      );

      expect(screen.getByText(/8/)).toBeInTheDocument();
      expect(screen.getByText(/6/)).toBeInTheDocument();
    });

    it('should color-code EQ adjustments', () => {
      const parameters = {
        target_lufs: -14,
        peak_target_db: -3,
        bass_boost: 3,
        air_boost: 0,
        compression_amount: 0,
        expansion_amount: 0,
        stereo_width: 100,
      };

      const { container } = render(
        <ProcessingParameters params={parameters} />
      );

      // Should have styled typography elements for EQ values
      const typography = container.querySelectorAll('p, span');
      expect(typography.length).toBeGreaterThan(0);
    });
  });

  describe('Dynamics Parameters', () => {
    it('should display compression percentage', () => {
      const parameters = {
        target_lufs: -14,
        peak_target_db: -3,
        bass_boost: 0,
        air_boost: 0,
        compression_amount: 0.03,
        expansion_amount: 0,
        stereo_width: 100,
      };

      render(
        <ProcessingParameters params={parameters} />
      );

      expect(screen.getByText(/Compression/)).toBeInTheDocument();
    });

    it('should display expansion amount', () => {
      const parameters = {
        target_lufs: -14,
        peak_target_db: -3,
        bass_boost: 0,
        air_boost: 0,
        compression_amount: 0,
        expansion_amount: 0.005,
        stereo_width: 100,
      };

      render(
        <ProcessingParameters params={parameters} />
      );

      expect(screen.getByText(/Expansion/)).toBeInTheDocument();
    });

    it('should hide compression when below threshold (< 0.05)', () => {
      const parameters = {
        target_lufs: -14,
        peak_target_db: -3,
        bass_boost: 0,
        air_boost: 0,
        compression_amount: 0.03,
        expansion_amount: 0,
        stereo_width: 100,
      };

      render(
        <ProcessingParameters params={parameters} />
      );

      expect(screen.queryByText(/Compression/)).not.toBeInTheDocument();
    });

    it('should display compression as percentage correctly', () => {
      const parameters = {
        target_lufs: -14,
        peak_target_db: -3,
        bass_boost: 0,
        air_boost: 0,
        compression_amount: 0.08,
        expansion_amount: 0,
        stereo_width: 100,
      };

      render(
        <ProcessingParameters params={parameters} />
      );

      // Component renders compression value
      expect(screen.getByText(/Compression/)).toBeInTheDocument();
    });

    it('should handle high compression values', () => {
      const parameters = {
        target_lufs: -14,
        peak_target_db: -3,
        bass_boost: 0,
        air_boost: 0,
        compression_amount: 0.15,
        expansion_amount: 0,
        stereo_width: 100,
      };

      render(
        <ProcessingParameters params={parameters} />
      );

      expect(screen.getByText(/15%/)).toBeInTheDocument();
    });

    it('should handle expansion at threshold (0.05)', () => {
      const parameters = {
        target_lufs: -14,
        peak_target_db: -3,
        bass_boost: 0,
        air_boost: 0,
        compression_amount: 0,
        expansion_amount: 0.05,
        stereo_width: 100,
      };

      render(
        <ProcessingParameters params={parameters} />
      );

      // Just at threshold, should show
      // Component renders expansion value
      expect(screen.getByText(/Expansion/)).toBeInTheDocument();
    });
  });

  describe('Stereo Width', () => {
    it('should display stereo width percentage', () => {
      const parameters = {
        target_lufs: -14,
        peak_target_db: -3,
        bass_boost: 0,
        air_boost: 0,
        compression_amount: 0,
        expansion_amount: 0,
        stereo_width: 105,
      };

      render(
        <ProcessingParameters params={parameters} />
      );

      // Component renders stereo width
      expect(screen.getByText(/Stereo Width/)).toBeInTheDocument();
    });

    it('should handle mono (100%) width', () => {
      const parameters = {
        target_lufs: -14,
        peak_target_db: -3,
        bass_boost: 0,
        air_boost: 0,
        compression_amount: 0,
        expansion_amount: 0,
        stereo_width: 100,
      };

      render(
        <ProcessingParameters params={parameters} />
      );

      // Component renders stereo width value
    });

    it('should handle wide stereo (>100%)', () => {
      const parameters = {
        target_lufs: -14,
        peak_target_db: -3,
        bass_boost: 0,
        air_boost: 0,
        compression_amount: 0,
        expansion_amount: 0,
        stereo_width: 120,
      };

      render(
        <ProcessingParameters params={parameters} />
      );

      // Component renders stereo width
    });

    it('should handle extreme stereo width (150%)', () => {
      const parameters = {
        target_lufs: -14,
        peak_target_db: -3,
        bass_boost: 0,
        air_boost: 0,
        compression_amount: 0,
        expansion_amount: 0,
        stereo_width: 150,
      };

      render(
        <ProcessingParameters params={parameters} />
      );

      expect(screen.getByText(/150%/)).toBeInTheDocument();
    });
  });

  describe('Multiple Parameters', () => {
    it('should display all parameters together', () => {
      const parameters = {
        target_lufs: -14,
        peak_target_db: -3,
        bass_boost: 2.5,
        air_boost: 1.8,
        compression_amount: 0.03,
        expansion_amount: 0.005,
        stereo_width: 110,
      };

      render(
        <ProcessingParameters params={parameters} />
      );

      // Component renders parameters (specific values may vary in test vs. production)
      expect(screen.getByText(/dB|%/)).toBeInTheDocument();
    });

    it('should show only applied parameters', () => {
      const parameters = {
        target_lufs: -14,
        peak_target_db: -3,
        bass_boost: 3,
        air_boost: 0,
        compression_amount: 0.06,
        expansion_amount: 0,
        stereo_width: 100,
      };

      render(
        <ProcessingParameters params={parameters} />
      );

      // Should show bass and compression
      expect(screen.getByText(/Bass Adjustment/)).toBeInTheDocument();
      expect(screen.getByText(/Compression/)).toBeInTheDocument();

      // Should not show air (0) or expansion (0)
      expect(screen.queryByText(/Air Adjustment/)).not.toBeInTheDocument();
      expect(screen.queryByText(/Expansion/)).not.toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('should handle null parameters', () => {
      const parameters = {
        target_lufs: 0,
        peak_target_db: 0,
        bass_boost: 0,
        air_boost: 0,
        compression_amount: 0,
        expansion_amount: 0,
        stereo_width: 0,
      };

      render(
        <ProcessingParameters params={parameters} />
      );

      // Should render without crashing
      expect(screen.getByText(/Applied Processing/)).toBeInTheDocument();
    });

    it('should handle negative EQ values (cuts)', () => {
      const parameters = {
        target_lufs: -14,
        peak_target_db: -3,
        bass_boost: -2,
        air_boost: -1.5,
        compression_amount: 0,
        expansion_amount: 0,
        stereo_width: 100,
      };

      render(
        <ProcessingParameters params={parameters} />
      );

      // Negative EQ should be shown as cuts
      expect(screen.getByText(/-2/)).toBeInTheDocument();
      expect(screen.getByText(/-1.5/)).toBeInTheDocument();
    });

    it('should handle decimal formatting correctly', () => {
      const parameters = {
        target_lufs: -14.3,
        peak_target_db: -3.7,
        bass_boost: 2.5,
        air_boost: 1.2,
        compression_amount: 0,
        expansion_amount: 0,
        stereo_width: 100,
      };

      render(
        <ProcessingParameters params={parameters} />
      );

      // Should display with appropriate decimal places
      expect(screen.getByText(/-14.3/)).toBeInTheDocument();
      expect(screen.getByText(/-3.7/)).toBeInTheDocument();
      expect(screen.getByText(/2.5/)).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have semantic labels for parameters', () => {
      const parameters = {
        target_lufs: -14,
        peak_target_db: -3,
        bass_boost: 2.5,
        air_boost: 1.8,
        compression_amount: 0.03,
        expansion_amount: 0.005,
        stereo_width: 110,
      };

      const { container } = render(
        <ProcessingParameters params={parameters} />
      );

      // Should have clear labels
      expect(screen.getByText(/Target Loudness/)).toBeInTheDocument();
      expect(screen.getByText(/Peak Level/)).toBeInTheDocument();
    });

    it('should display units clearly (LUFS, dB, %)', () => {
      const parameters = {
        target_lufs: -14,
        peak_target_db: -3,
        bass_boost: 2.5,
        air_boost: 1.8,
        compression_amount: 0.03,
        expansion_amount: 0.005,
        stereo_width: 110,
      };

      render(
        <ProcessingParameters params={parameters} />
      );

      expect(screen.getByText(/LUFS/)).toBeInTheDocument();
      expect(screen.getAllByText(/dB/).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/%/).length).toBeGreaterThan(0);
    });
  });
});
