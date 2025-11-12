/**
 * ParameterBar Component Tests
 *
 * Tests reusable progress bar with label and chip:
 * - Label and chip rendering
 * - Progress bar fill calculation (value * 100)
 * - Gradient application
 * - Boundary values (0, 0.5, 1)
 * - Memoization
 * - Accessibility
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import { describe, it, expect } from 'vitest';
import ParameterBar from '../ParameterBar';
import { auralisTheme } from '../../../theme/auralisTheme';

const Wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <BrowserRouter>
    <ThemeProvider theme={auralisTheme}>
      {children}
    </ThemeProvider>
  </BrowserRouter>
);

describe('ParameterBar', () => {
  describe('Rendering', () => {
    it('should render label text', () => {
      render(
        <Wrapper>
          <ParameterBar
            label="Spectral Balance"
            value={0.5}
            gradient="linear-gradient(90deg, #000, #fff)"
            chipLabel="Balanced"
          />
        </Wrapper>
      );

      expect(screen.getByText('Spectral Balance')).toBeInTheDocument();
    });

    it('should render chip with label', () => {
      render(
        <Wrapper>
          <ParameterBar
            label="Dynamic Range"
            value={0.5}
            gradient="linear-gradient(90deg, #e0e0e0, #1976d2)"
            chipLabel="Moderate"
          />
        </Wrapper>
      );

      expect(screen.getByText('Moderate')).toBeInTheDocument();
    });

    it('should render progress bar element', () => {
      const { container } = render(
        <Wrapper>
          <ParameterBar
            label="Energy Level"
            value={0.5}
            gradient="linear-gradient(90deg, #ff6b6b, #ffd43b)"
            chipLabel="Medium"
          />
        </Wrapper>
      );

      const progressBar = container.querySelector('[role="progressbar"]');
      expect(progressBar).toBeTruthy();
    });

    it('should render all components together', () => {
      const { container } = render(
        <Wrapper>
          <ParameterBar
            label="Test Parameter"
            value={0.75}
            gradient="linear-gradient(90deg, blue, green)"
            chipLabel="High"
          />
        </Wrapper>
      );

      expect(screen.getByText('Test Parameter')).toBeInTheDocument();
      expect(screen.getByText('High')).toBeInTheDocument();
      expect(container.querySelector('[role="progressbar"]')).toBeTruthy();
    });
  });

  describe('Progress Bar Fill', () => {
    it('should display 0% fill for value 0', () => {
      const { container } = render(
        <Wrapper>
          <ParameterBar
            label="Low"
            value={0}
            gradient="linear-gradient(90deg, #ccc, #333)"
            chipLabel="Min"
          />
        </Wrapper>
      );

      const progressBar = container.querySelector('[role="progressbar"]');
      expect(progressBar?.getAttribute('aria-valuenow')).toBe('0');
    });

    it('should display 50% fill for value 0.5', () => {
      const { container } = render(
        <Wrapper>
          <ParameterBar
            label="Mid"
            value={0.5}
            gradient="linear-gradient(90deg, #ddd, #555)"
            chipLabel="Mid"
          />
        </Wrapper>
      );

      const progressBar = container.querySelector('[role="progressbar"]');
      expect(progressBar?.getAttribute('aria-valuenow')).toBe('50');
    });

    it('should display 100% fill for value 1', () => {
      const { container } = render(
        <Wrapper>
          <ParameterBar
            label="High"
            value={1}
            gradient="linear-gradient(90deg, #999, #000)"
            chipLabel="Max"
          />
        </Wrapper>
      );

      const progressBar = container.querySelector('[role="progressbar"]');
      expect(progressBar?.getAttribute('aria-valuenow')).toBe('100');
    });

    it('should calculate percentage correctly for 0.25 value', () => {
      const { container } = render(
        <Wrapper>
          <ParameterBar
            label="Quarter"
            value={0.25}
            gradient="linear-gradient(90deg, #e0e0e0, #5c6bc0)"
            chipLabel="Low"
          />
        </Wrapper>
      );

      const progressBar = container.querySelector('[role="progressbar"]');
      expect(progressBar?.getAttribute('aria-valuenow')).toBe('25');
    });

    it('should calculate percentage correctly for 0.75 value', () => {
      const { container } = render(
        <Wrapper>
          <ParameterBar
            label="ThreeQuarters"
            value={0.75}
            gradient="linear-gradient(90deg, #e0e0e0, #f57c00)"
            chipLabel="High"
          />
        </Wrapper>
      );

      const progressBar = container.querySelector('[role="progressbar"]');
      expect(progressBar?.getAttribute('aria-valuenow')).toBe('75');
    });
  });

  describe('Gradient Application', () => {
    it('should apply gradient to progress bar', () => {
      const { container } = render(
        <Wrapper>
          <ParameterBar
            label="Gradient Test"
            value={0.5}
            gradient="linear-gradient(90deg, #000000, #ffffff)"
            chipLabel="Test"
          />
        </Wrapper>
      );

      const progressBar = container.querySelector('.MuiLinearProgress-bar');
      expect(progressBar).toBeTruthy();
    });

    it('should support different gradient formats', () => {
      const gradients = [
        'linear-gradient(90deg, #ff0000, #00ff00)',
        'linear-gradient(180deg, #0000ff, #ffff00)',
        'radial-gradient(circle, #ff00ff, #00ffff)',
      ];

      gradients.forEach((gradient) => {
        const { container } = render(
          <Wrapper>
            <ParameterBar
              label="Gradient Test"
              value={0.5}
              gradient={gradient}
              chipLabel="Test"
            />
          </Wrapper>
        );

        expect(container.querySelector('[role="progressbar"]')).toBeTruthy();
      });
    });
  });

  describe('Boundary Values', () => {
    it('should handle zero value', () => {
      render(
        <Wrapper>
          <ParameterBar
            label="Zero"
            value={0}
            gradient="linear-gradient(90deg, #ddd, #999)"
            chipLabel="None"
          />
        </Wrapper>
      );

      expect(screen.getByText('Zero')).toBeInTheDocument();
      expect(screen.getByText('None')).toBeInTheDocument();
    });

    it('should handle maximum value (1)', () => {
      render(
        <Wrapper>
          <ParameterBar
            label="Maximum"
            value={1}
            gradient="linear-gradient(90deg, #000, #fff)"
            chipLabel="Full"
          />
        </Wrapper>
      );

      expect(screen.getByText('Maximum')).toBeInTheDocument();
      expect(screen.getByText('Full')).toBeInTheDocument();
    });

    it('should handle very small positive values', () => {
      const { container } = render(
        <Wrapper>
          <ParameterBar
            label="Tiny"
            value={0.01}
            gradient="linear-gradient(90deg, #e0e0e0, #1976d2)"
            chipLabel="Minimal"
          />
        </Wrapper>
      );

      const progressBar = container.querySelector('[role="progressbar"]');
      expect(progressBar?.getAttribute('aria-valuenow')).toBe('1');
    });

    it('should handle values very close to 1', () => {
      const { container } = render(
        <Wrapper>
          <ParameterBar
            label="Almost Full"
            value={0.99}
            gradient="linear-gradient(90deg, #e0e0e0, #ffd43b)"
            chipLabel="Nearly Max"
          />
        </Wrapper>
      );

      const progressBar = container.querySelector('[role="progressbar"]');
      expect(progressBar?.getAttribute('aria-valuenow')).toBe('99');
    });
  });

  describe('Real Audio Parameters', () => {
    it('should display spectral balance parameter', () => {
      render(
        <Wrapper>
          <ParameterBar
            label="Spectral Balance"
            value={0.6}
            gradient="linear-gradient(90deg, #000000, #ffffff)"
            chipLabel="Bright"
          />
        </Wrapper>
      );

      expect(screen.getByText('Spectral Balance')).toBeInTheDocument();
      expect(screen.getByText('Bright')).toBeInTheDocument();
    });

    it('should display dynamic range parameter', () => {
      render(
        <Wrapper>
          <ParameterBar
            label="Dynamic Range"
            value={0.3}
            gradient="linear-gradient(90deg, #e0e0e0, #1976d2)"
            chipLabel="Compressed"
          />
        </Wrapper>
      );

      expect(screen.getByText('Dynamic Range')).toBeInTheDocument();
      expect(screen.getByText('Compressed')).toBeInTheDocument();
    });

    it('should display energy level parameter', () => {
      render(
        <Wrapper>
          <ParameterBar
            label="Energy Level"
            value={0.8}
            gradient="linear-gradient(90deg, #ff6b6b, #ffd43b)"
            chipLabel="Loud"
          />
        </Wrapper>
      );

      expect(screen.getByText('Energy Level')).toBeInTheDocument();
      expect(screen.getByText('Loud')).toBeInTheDocument();
    });
  });

  describe('Memoization', () => {
    it('should be memoized component', () => {
      const { rerender } = render(
        <Wrapper>
          <ParameterBar
            label="Test"
            value={0.5}
            gradient="linear-gradient(90deg, #ddd, #999)"
            chipLabel="Mid"
          />
        </Wrapper>
      );

      expect(screen.getByText('Test')).toBeInTheDocument();

      rerender(
        <Wrapper>
          <ParameterBar
            label="Test"
            value={0.5}
            gradient="linear-gradient(90deg, #ddd, #999)"
            chipLabel="Mid"
          />
        </Wrapper>
      );

      expect(screen.getByText('Test')).toBeInTheDocument();
    });

    it('should update when props change', () => {
      const { rerender } = render(
        <Wrapper>
          <ParameterBar
            label="Original"
            value={0.3}
            gradient="linear-gradient(90deg, #ccc, #333)"
            chipLabel="Low"
          />
        </Wrapper>
      );

      expect(screen.getByText('Original')).toBeInTheDocument();
      expect(screen.getByText('Low')).toBeInTheDocument();

      rerender(
        <Wrapper>
          <ParameterBar
            label="Updated"
            value={0.7}
            gradient="linear-gradient(90deg, #ddd, #999)"
            chipLabel="High"
          />
        </Wrapper>
      );

      expect(screen.getByText('Updated')).toBeInTheDocument();
      expect(screen.getByText('High')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have accessible label text', () => {
      render(
        <Wrapper>
          <ParameterBar
            label="Accessible Parameter"
            value={0.5}
            gradient="linear-gradient(90deg, #e0e0e0, #1976d2)"
            chipLabel="Value"
          />
        </Wrapper>
      );

      const label = screen.getByText('Accessible Parameter');
      expect(label).toBeInTheDocument();
    });

    it('should have progress bar with aria attributes', () => {
      const { container } = render(
        <Wrapper>
          <ParameterBar
            label="Test"
            value={0.6}
            gradient="linear-gradient(90deg, #ddd, #999)"
            chipLabel="Test"
          />
        </Wrapper>
      );

      const progressBar = container.querySelector('[role="progressbar"]');
      expect(progressBar?.getAttribute('aria-valuenow')).toBe('60');
      expect(progressBar?.getAttribute('aria-valuemin')).toBe('0');
      expect(progressBar?.getAttribute('aria-valuemax')).toBe('100');
    });
  });

  describe('Display Name', () => {
    it('should have correct display name for debugging', () => {
      expect(ParameterBar.displayName).toBe('ParameterBar');
    });
  });
});
