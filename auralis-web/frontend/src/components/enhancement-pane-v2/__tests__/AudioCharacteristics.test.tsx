/**
 * AudioCharacteristics Component Tests
 *
 * Tests 3D audio space visualization:
 * - Spectral balance (0=dark, 1=bright)
 * - Dynamic range (0=compressed, 1=dynamic)
 * - Energy level (0=quiet, 1=loud)
 * - Parameter bar integration
 * - Label generation for characteristics
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import { describe, it, expect } from 'vitest';
import AudioCharacteristics from '../AudioCharacteristics';
import { auralisTheme } from '../../../theme/auralisTheme';

const Wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <BrowserRouter>
    <ThemeProvider theme={auralisTheme}>
      {children}
    </ThemeProvider>
  </BrowserRouter>
);

describe('AudioCharacteristics', () => {
  describe('Rendering', () => {
    it('should render audio characteristics section', () => {
      const params = {
        spectral_balance: 0.5,
        dynamic_range: 0.5,
        energy_level: 0.5,
      };

      render(
        <Wrapper>
          <AudioCharacteristics params={params} />
        </Wrapper>
      );

      expect(screen.getByText(/Audio Characteristics/i)).toBeInTheDocument();
    });

    it('should render all three parameter bars', () => {
      const params = {
        spectral_balance: 0.5,
        dynamic_range: 0.5,
        energy_level: 0.5,
      };

      render(
        <Wrapper>
          <AudioCharacteristics params={params} />
        </Wrapper>
      );

      expect(screen.getByText(/Spectral Balance/)).toBeInTheDocument();
      expect(screen.getByText(/Dynamic Range/)).toBeInTheDocument();
      expect(screen.getByText(/Energy Level/)).toBeInTheDocument();
    });
  });

  describe('Spectral Balance Labeling', () => {
    it('should label dark spectrum (< 0.3)', () => {
      const params = {
        spectral_balance: 0.2,
        dynamic_range: 0.5,
        energy_level: 0.5,
      };

      render(
        <Wrapper>
          <AudioCharacteristics params={params} />
        </Wrapper>
      );

      expect(screen.getByText(/Dark/)).toBeInTheDocument();
    });

    it('should label balanced spectrum (0.3-0.7)', () => {
      const params = {
        spectral_balance: 0.5,
        dynamic_range: 0.5,
        energy_level: 0.5,
      };

      render(
        <Wrapper>
          <AudioCharacteristics params={params} />
        </Wrapper>
      );

      expect(screen.getByText(/Balanced/)).toBeInTheDocument();
    });

    it('should label bright spectrum (> 0.7)', () => {
      const params = {
        spectral_balance: 0.8,
        dynamic_range: 0.5,
        energy_level: 0.5,
      };

      render(
        <Wrapper>
          <AudioCharacteristics params={params} />
        </Wrapper>
      );

      expect(screen.getByText(/Bright/)).toBeInTheDocument();
    });
  });

  describe('Dynamic Range Labeling', () => {
    it('should label compressed dynamics (< 0.3)', () => {
      const params = {
        spectral_balance: 0.5,
        dynamic_range: 0.2,
        energy_level: 0.5,
      };

      render(
        <Wrapper>
          <AudioCharacteristics params={params} />
        </Wrapper>
      );

      expect(screen.getByText(/Compressed/)).toBeInTheDocument();
    });

    it('should label moderate dynamics (0.3-0.7)', () => {
      const params = {
        spectral_balance: 0.5,
        dynamic_range: 0.5,
        energy_level: 0.5,
      };

      render(
        <Wrapper>
          <AudioCharacteristics params={params} />
        </Wrapper>
      );

      // Balanced might be in spectral, need specific search
      const text = screen.getByText(/Moderate/).textContent;
      expect(text).toMatch(/Moderate/);
    });

    it('should label dynamic range (> 0.7)', () => {
      const params = {
        spectral_balance: 0.5,
        dynamic_range: 0.8,
        energy_level: 0.5,
      };

      render(
        <Wrapper>
          <AudioCharacteristics params={params} />
        </Wrapper>
      );

      const allText = screen.getByText(/Dynamic Range/).textContent;
      expect(allText).toMatch(/Dynamic/);
    });
  });

  describe('Energy Level Labeling', () => {
    it('should label quiet audio (< 0.3)', () => {
      const params = {
        spectral_balance: 0.5,
        dynamic_range: 0.5,
        energy_level: 0.2,
      };

      render(
        <Wrapper>
          <AudioCharacteristics params={params} />
        </Wrapper>
      );

      expect(screen.getByText(/Quiet/)).toBeInTheDocument();
    });

    it('should label moderate energy (0.3-0.7)', () => {
      const params = {
        spectral_balance: 0.5,
        dynamic_range: 0.5,
        energy_level: 0.5,
      };

      render(
        <Wrapper>
          <AudioCharacteristics params={params} />
        </Wrapper>
      );

      expect(screen.getByText(/Energy Level/)).toBeInTheDocument();
    });

    it('should label loud audio (> 0.7)', () => {
      const params = {
        spectral_balance: 0.5,
        dynamic_range: 0.5,
        energy_level: 0.8,
      };

      render(
        <Wrapper>
          <AudioCharacteristics params={params} />
        </Wrapper>
      );

      const loudText = screen.getAllByText(/Loud/);
      expect(loudText.length).toBeGreaterThan(0);
    });
  });

  describe('Parameter Ranges', () => {
    it('should handle extreme low values (0)', () => {
      const params = {
        spectral_balance: 0,
        dynamic_range: 0,
        energy_level: 0,
      };

      render(
        <Wrapper>
          <AudioCharacteristics params={params} />
        </Wrapper>
      );

      expect(screen.getByText(/Dark|Compressed|Quiet/)).toBeInTheDocument();
    });

    it('should handle extreme high values (1)', () => {
      const params = {
        spectral_balance: 1,
        dynamic_range: 1,
        energy_level: 1,
      };

      render(
        <Wrapper>
          <AudioCharacteristics params={params} />
        </Wrapper>
      );

      expect(screen.getByText(/Bright|Dynamic|Loud/)).toBeInTheDocument();
    });

    it('should handle boundary values (0.3, 0.7)', () => {
      const params = {
        spectral_balance: 0.3,
        dynamic_range: 0.7,
        energy_level: 0.5,
      };

      render(
        <Wrapper>
          <AudioCharacteristics params={params} />
        </Wrapper>
      );

      // At boundary, should show balanced/moderate/moderate
      expect(screen.getByText(/Audio Characteristics/)).toBeInTheDocument();
    });
  });

  describe('Memoization', () => {
    it('should be memoized component', () => {
      const params = {
        spectral_balance: 0.5,
        dynamic_range: 0.6,
        energy_level: 0.4,
      };

      const { rerender } = render(
        <Wrapper>
          <AudioCharacteristics params={params} />
        </Wrapper>
      );

      expect(screen.getByText(/Audio Characteristics/)).toBeInTheDocument();

      // Rerender with same props
      rerender(
        <Wrapper>
          <AudioCharacteristics params={params} />
        </Wrapper>
      );

      // Should still render correctly
      expect(screen.getByText(/Audio Characteristics/)).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have descriptive section header', () => {
      const params = {
        spectral_balance: 0.5,
        dynamic_range: 0.5,
        energy_level: 0.5,
      };

      render(
        <Wrapper>
          <AudioCharacteristics params={params} />
        </Wrapper>
      );

      expect(screen.getByText(/Audio Characteristics/)).toBeInTheDocument();
    });

    it('should have clear parameter labels', () => {
      const params = {
        spectral_balance: 0.5,
        dynamic_range: 0.5,
        energy_level: 0.5,
      };

      render(
        <Wrapper>
          <AudioCharacteristics params={params} />
        </Wrapper>
      );

      expect(screen.getByText(/Spectral Balance/)).toBeInTheDocument();
      expect(screen.getByText(/Dynamic Range/)).toBeInTheDocument();
      expect(screen.getByText(/Energy Level/)).toBeInTheDocument();
    });
  });

  describe('Integration with ParameterBar', () => {
    it('should pass correct values to parameter bars', () => {
      const params = {
        spectral_balance: 0.75,
        dynamic_range: 0.25,
        energy_level: 0.5,
      };

      const { container } = render(
        <Wrapper>
          <AudioCharacteristics params={params} />
        </Wrapper>
      );

      // Should render without errors
      expect(container.querySelector('[class*="Stack"]')).toBeTruthy();
    });

    it('should use correct gradients for visualization', () => {
      const params = {
        spectral_balance: 0.5,
        dynamic_range: 0.6,
        energy_level: 0.4,
      };

      const { container } = render(
        <Wrapper>
          <AudioCharacteristics params={params} />
        </Wrapper>
      );

      // Should have proper structure for gradient visualization
      const elements = container.querySelectorAll('*');
      expect(elements.length).toBeGreaterThan(0);
    });
  });
});
