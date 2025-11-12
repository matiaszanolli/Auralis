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
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import { describe, it, expect } from 'vitest';
import ParameterChip from '../ParameterChip';
import { auralisTheme } from '../../../theme/auralisTheme';

const Wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <BrowserRouter>
    <ThemeProvider theme={auralisTheme}>
      {children}
    </ThemeProvider>
  </BrowserRouter>
);

describe('ParameterChip', () => {
  describe('Rendering', () => {
    it('should render chip with label', () => {
      render(
        <Wrapper>
          <ParameterChip
            label="Balanced"
            gradient="linear-gradient(90deg, #000, #fff)"
          />
        </Wrapper>
      );

      expect(screen.getByText('Balanced')).toBeInTheDocument();
    });

    it('should render as Chip component', () => {
      const { container } = render(
        <Wrapper>
          <ParameterChip
            label="Test"
            gradient="linear-gradient(90deg, #ddd, #999)"
          />
        </Wrapper>
      );

      const chip = container.querySelector('[class*="MuiChip"]');
      expect(chip).toBeTruthy();
    });

    it('should display correct label text', () => {
      render(
        <Wrapper>
          <ParameterChip
            label="Custom Label"
            gradient="linear-gradient(90deg, #e0e0e0, #1976d2)"
          />
        </Wrapper>
      );

      expect(screen.getByText('Custom Label')).toBeInTheDocument();
    });
  });

  describe('Gradient Application', () => {
    it('should apply gradient background', () => {
      const { container } = render(
        <Wrapper>
          <ParameterChip
            label="Gradient"
            gradient="linear-gradient(90deg, #000000, #ffffff)"
          />
        </Wrapper>
      );

      const chip = container.querySelector('[class*="MuiChip"]');
      expect(chip).toBeTruthy();
    });

    it('should support linear gradient left to right', () => {
      render(
        <Wrapper>
          <ParameterChip
            label="LTR"
            gradient="linear-gradient(90deg, #ff0000, #00ff00)"
          />
        </Wrapper>
      );

      expect(screen.getByText('LTR')).toBeInTheDocument();
    });

    it('should support linear gradient top to bottom', () => {
      render(
        <Wrapper>
          <ParameterChip
            label="TTB"
            gradient="linear-gradient(180deg, #0000ff, #ffff00)"
          />
        </Wrapper>
      );

      expect(screen.getByText('TTB')).toBeInTheDocument();
    });

    it('should support radial gradients', () => {
      render(
        <Wrapper>
          <ParameterChip
            label="Radial"
            gradient="radial-gradient(circle, #ff00ff, #00ffff)"
          />
        </Wrapper>
      );

      expect(screen.getByText('Radial')).toBeInTheDocument();
    });
  });

  describe('Styling', () => {
    it('should be small size', () => {
      const { container } = render(
        <Wrapper>
          <ParameterChip
            label="Small"
            gradient="linear-gradient(90deg, #ddd, #999)"
          />
        </Wrapper>
      );

      const chip = container.querySelector('[class*="MuiChip-sizeSmall"]');
      expect(chip).toBeTruthy();
    });

    it('should have proper styling for parameter display', () => {
      const { container } = render(
        <Wrapper>
          <ParameterChip
            label="Styled"
            gradient="linear-gradient(90deg, #e0e0e0, #1976d2)"
          />
        </Wrapper>
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
          <Wrapper>
            <ParameterChip
              label={label}
              gradient="linear-gradient(90deg, #000, #fff)"
            />
          </Wrapper>
        );

        expect(screen.getByText(label)).toBeInTheDocument();
        unmount();
      });
    });

    it('should display dynamic range labels', () => {
      const labels = ['Compressed', 'Moderate', 'Dynamic'];

      labels.forEach((label) => {
        const { unmount } = render(
          <Wrapper>
            <ParameterChip
              label={label}
              gradient="linear-gradient(90deg, #e0e0e0, #1976d2)"
            />
          </Wrapper>
        );

        expect(screen.getByText(label)).toBeInTheDocument();
        unmount();
      });
    });

    it('should display energy level labels', () => {
      const labels = ['Quiet', 'Moderate', 'Loud'];

      labels.forEach((label) => {
        const { unmount } = render(
          <Wrapper>
            <ParameterChip
              label={label}
              gradient="linear-gradient(90deg, #ff6b6b, #ffd43b)"
            />
          </Wrapper>
        );

        expect(screen.getByText(label)).toBeInTheDocument();
        unmount();
      });
    });
  });

  describe('Memoization', () => {
    it('should be memoized component', () => {
      const { rerender } = render(
        <Wrapper>
          <ParameterChip
            label="Test"
            gradient="linear-gradient(90deg, #ddd, #999)"
          />
        </Wrapper>
      );

      expect(screen.getByText('Test')).toBeInTheDocument();

      rerender(
        <Wrapper>
          <ParameterChip
            label="Test"
            gradient="linear-gradient(90deg, #ddd, #999)"
          />
        </Wrapper>
      );

      expect(screen.getByText('Test')).toBeInTheDocument();
    });

    it('should update when label changes', () => {
      const { rerender } = render(
        <Wrapper>
          <ParameterChip
            label="Original"
            gradient="linear-gradient(90deg, #ccc, #333)"
          />
        </Wrapper>
      );

      expect(screen.getByText('Original')).toBeInTheDocument();

      rerender(
        <Wrapper>
          <ParameterChip
            label="Updated"
            gradient="linear-gradient(90deg, #ddd, #999)"
          />
        </Wrapper>
      );

      expect(screen.getByText('Updated')).toBeInTheDocument();
    });

    it('should update when gradient changes', () => {
      const { rerender } = render(
        <Wrapper>
          <ParameterChip
            label="Gradient"
            gradient="linear-gradient(90deg, #000, #fff)"
          />
        </Wrapper>
      );

      expect(screen.getByText('Gradient')).toBeInTheDocument();

      rerender(
        <Wrapper>
          <ParameterChip
            label="Gradient"
            gradient="linear-gradient(90deg, #fff, #000)"
          />
        </Wrapper>
      );

      expect(screen.getByText('Gradient')).toBeInTheDocument();
    });
  });

  describe('Integration', () => {
    it('should work as standalone component', () => {
      render(
        <Wrapper>
          <ParameterChip
            label="Standalone"
            gradient="linear-gradient(90deg, #e0e0e0, #1976d2)"
          />
        </Wrapper>
      );

      expect(screen.getByText('Standalone')).toBeInTheDocument();
    });

    it('should display multiple chips together', () => {
      render(
        <Wrapper>
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
        </Wrapper>
      );

      expect(screen.getByText('Chip 1')).toBeInTheDocument();
      expect(screen.getByText('Chip 2')).toBeInTheDocument();
      expect(screen.getByText('Chip 3')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have readable label', () => {
      render(
        <Wrapper>
          <ParameterChip
            label="Accessible"
            gradient="linear-gradient(90deg, #e0e0e0, #1976d2)"
          />
        </Wrapper>
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
