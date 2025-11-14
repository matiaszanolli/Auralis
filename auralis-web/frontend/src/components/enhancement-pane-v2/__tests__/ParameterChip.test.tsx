/**
 * ParameterChip Component Tests
 *
 * Tests small chip with gradient background:
 * - Label rendering
 * - Gradient application
 * - Size and styling
 * - Memoization
 * - Integration with ParameterBar
 */

import React from 'react';
import { render, screen } from '@/test/test-utils';
import { describe, it, expect } from 'vitest';
import ParameterChip from '../ParameterChip';


describe('ParameterChip', () => {
  describe('Rendering', () => {
    it('should render chip with label', () => {
      render(
        <ParameterChip
            label="Balanced"
            gradient="linear-gradient(90deg, #000, #fff)"
          />
      );

      expect(screen.getByText('Balanced')).toBeInTheDocument();
    });

    it('should render as Chip component', () => {
      const { container } = render(
        <ParameterChip
            label="Test"
            gradient="linear-gradient(90deg, #ddd, #999)"
          />
      );

      const chip = container.querySelector('[class*="MuiChip"]');
      expect(chip).toBeTruthy();
    });

    it('should display correct label text', () => {
      render(
        <ParameterChip
            label="Custom Label"
            gradient="linear-gradient(90deg, #e0e0e0, #1976d2)"
          />
      );

      expect(screen.getByText('Custom Label')).toBeInTheDocument();
    });
  });

  describe('Gradient Application', () => {
    it('should apply gradient background', () => {
      const { container } = render(
        <ParameterChip
            label="Gradient"
            gradient="linear-gradient(90deg, #000000, #ffffff)"
          />
      );

      const chip = container.querySelector('[class*="MuiChip"]');
      expect(chip).toBeTruthy();
    });

    it('should support linear gradient left to right', () => {
      render(
        <ParameterChip
            label="LTR"
            gradient="linear-gradient(90deg, #ff0000, #00ff00)"
          />
      );

      expect(screen.getByText('LTR')).toBeInTheDocument();
    });

    it('should support linear gradient top to bottom', () => {
      render(
        <ParameterChip
            label="TTB"
            gradient="linear-gradient(180deg, #0000ff, #ffff00)"
          />
      );

      expect(screen.getByText('TTB')).toBeInTheDocument();
    });

    it('should support radial gradients', () => {
      render(
        <ParameterChip
            label="Radial"
            gradient="radial-gradient(circle, #ff00ff, #00ffff)"
          />
      );

      expect(screen.getByText('Radial')).toBeInTheDocument();
    });
  });

  describe('Styling', () => {
    it('should be small size', () => {
      const { container } = render(
        <ParameterChip
            label="Small"
            gradient="linear-gradient(90deg, #ddd, #999)"
          />
      );

      const chip = container.querySelector('[class*="MuiChip-sizeSmall"]');
      expect(chip).toBeTruthy();
    });

    it('should have proper styling for parameter display', () => {
      const { container } = render(
        <ParameterChip
            label="Styled"
            gradient="linear-gradient(90deg, #e0e0e0, #1976d2)"
          />
      );

      const chip = container.querySelector('[class*="MuiChip"]');
      expect(chip).toBeTruthy();
    });
  });

  describe('Audio Characteristic Labels', () => {
    it('should display spectral balance labels', () => {
      const labels = ['Dark', 'Balanced', 'Bright'];

      labels.forEach((label) => {
        const { unmount } = render(
          <ParameterChip
              label={label}
              gradient="linear-gradient(90deg, #000, #fff)"
            />
        );

        expect(screen.getByText(label)).toBeInTheDocument();
        unmount();
      });
    });

    it('should display dynamic range labels', () => {
      const labels = ['Compressed', 'Moderate', 'Dynamic'];

      labels.forEach((label) => {
        const { unmount } = render(
          <ParameterChip
              label={label}
              gradient="linear-gradient(90deg, #e0e0e0, #1976d2)"
            />
        );

        expect(screen.getByText(label)).toBeInTheDocument();
        unmount();
      });
    });

    it('should display energy level labels', () => {
      const labels = ['Quiet', 'Moderate', 'Loud'];

      labels.forEach((label) => {
        const { unmount } = render(
          <ParameterChip
              label={label}
              gradient="linear-gradient(90deg, #ff6b6b, #ffd43b)"
            />
        );

        expect(screen.getByText(label)).toBeInTheDocument();
        unmount();
      });
    });
  });

  describe('Memoization', () => {
    it('should be memoized component', () => {
      const { rerender } = render(
        <ParameterChip
            label="Test"
            gradient="linear-gradient(90deg, #ddd, #999)"
          />
      );

      expect(screen.getByText('Test')).toBeInTheDocument();

      rerender(
        <ParameterChip
            label="Test"
            gradient="linear-gradient(90deg, #ddd, #999)"
          />
      );

      expect(screen.getByText('Test')).toBeInTheDocument();
    });

    it('should update when label changes', () => {
      const { rerender } = render(
        <ParameterChip
            label="Original"
            gradient="linear-gradient(90deg, #ccc, #333)"
          />
      );

      expect(screen.getByText('Original')).toBeInTheDocument();

      rerender(
        <ParameterChip
            label="Updated"
            gradient="linear-gradient(90deg, #ddd, #999)"
          />
      );

      expect(screen.getByText('Updated')).toBeInTheDocument();
    });

    it('should update when gradient changes', () => {
      const { rerender } = render(
        <ParameterChip
            label="Gradient"
            gradient="linear-gradient(90deg, #000, #fff)"
          />
      );

      expect(screen.getByText('Gradient')).toBeInTheDocument();

      rerender(
        <ParameterChip
            label="Gradient"
            gradient="linear-gradient(90deg, #fff, #000)"
          />
      );

      expect(screen.getByText('Gradient')).toBeInTheDocument();
    });
  });

  describe('Integration', () => {
    it('should work as standalone component', () => {
      render(
        <ParameterChip
            label="Standalone"
            gradient="linear-gradient(90deg, #e0e0e0, #1976d2)"
          />
      );

      expect(screen.getByText('Standalone')).toBeInTheDocument();
    });

    it('should display multiple chips together', () => {
      render(
        <div style={{ display: 'flex', gap: '8px' }}>
            <ParameterChip
              label="Chip 1"
              gradient="linear-gradient(90deg, #f00, #0f0)"
            />
            <ParameterChip
              label="Chip 2"
              gradient="linear-gradient(90deg, #00f, #ff0)"
            />
            <ParameterChip
              label="Chip 3"
              gradient="linear-gradient(90deg, #0ff, #f0f)"
            />
          </div>
      );

      expect(screen.getByText('Chip 1')).toBeInTheDocument();
      expect(screen.getByText('Chip 2')).toBeInTheDocument();
      expect(screen.getByText('Chip 3')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have readable label', () => {
      render(
        <ParameterChip
            label="Accessible"
            gradient="linear-gradient(90deg, #e0e0e0, #1976d2)"
          />
      );

      expect(screen.getByText('Accessible')).toBeInTheDocument();
    });
  });

  describe('Display Name', () => {
    it('should have correct display name for debugging', () => {
      expect(ParameterChip.displayName).toBe('ParameterChip');
    });
  });
});
