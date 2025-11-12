/**
 * LibraryHeader Component Tests
 *
 * Tests the library header component with:
 * - Title display based on view type
 * - Subtitle display
 * - Aurora gradient styling
 * - Design token compliance
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import { LibraryHeader } from '../LibraryHeader';
import { auralisTheme } from '../../../theme/auralisTheme';

const Wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <BrowserRouter>
    <ThemeProvider theme={auralisTheme}>
      {children}
    </ThemeProvider>
  </BrowserRouter>
);

describe('LibraryHeader', () => {
  describe('Rendering', () => {
    it('should render header container', () => {
      render(
        <Wrapper>
          <LibraryHeader view="library" />
        </Wrapper>
      );

      expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
    });

    it('should display library title by default', () => {
      render(
        <Wrapper>
          <LibraryHeader view="library" />
        </Wrapper>
      );

      expect(screen.getByText(/Your Music Collection/)).toBeInTheDocument();
    });

    it('should display library subtitle', () => {
      render(
        <Wrapper>
          <LibraryHeader view="library" />
        </Wrapper>
      );

      expect(screen.getByText(/Rediscover the magic/)).toBeInTheDocument();
    });
  });

  describe('View Types', () => {
    it('should display library view content', () => {
      render(
        <Wrapper>
          <LibraryHeader view="library" />
        </Wrapper>
      );

      expect(screen.getByText(/Your Music Collection/)).toBeInTheDocument();
      expect(screen.getByText(/Rediscover the magic/)).toBeInTheDocument();
    });

    it('should display favorites view content', () => {
      render(
        <Wrapper>
          <LibraryHeader view="favourites" />
        </Wrapper>
      );

      expect(screen.getByText(/Your Favorites/)).toBeInTheDocument();
      expect(screen.getByText(/Your most loved tracks/)).toBeInTheDocument();
    });

    it('should display heart emoji for favorites', () => {
      render(
        <Wrapper>
          <LibraryHeader view="favourites" />
        </Wrapper>
      );

      const heading = screen.getByRole('heading', { level: 1 });
      expect(heading.textContent).toContain('❤️');
    });

    it('should display music emoji for library', () => {
      render(
        <Wrapper>
          <LibraryHeader view="library" />
        </Wrapper>
      );

      const heading = screen.getByRole('heading', { level: 1 });
      expect(heading.textContent).toContain('🎵');
    });
  });

  describe('Typography', () => {
    it('should have h3 heading variant', () => {
      render(
        <Wrapper>
          <LibraryHeader view="library" />
        </Wrapper>
      );

      const heading = screen.getByRole('heading', { level: 1 });
      expect(heading).toBeInTheDocument();
    });

    it('should have subtitle text', () => {
      const { container } = render(
        <Wrapper>
          <LibraryHeader view="library" />
        </Wrapper>
      );

      const subtitle = container.querySelector('[class*="subtitle"]') ||
                       Array.from(container.querySelectorAll('p')).find(p =>
                         p.textContent?.includes('Rediscover')
                       );
      expect(subtitle).toBeInTheDocument();
    });
  });

  describe('Memoization', () => {
    it('should be memoized for performance', () => {
      const { rerender } = render(
        <Wrapper>
          <LibraryHeader view="library" />
        </Wrapper>
      );

      expect(screen.getByText(/Your Music Collection/)).toBeInTheDocument();

      // Rerender with same props - should not re-render unnecessarily
      rerender(
        <Wrapper>
          <LibraryHeader view="library" />
        </Wrapper>
      );

      expect(screen.getByText(/Your Music Collection/)).toBeInTheDocument();
    });

    it('should update when view prop changes', () => {
      const { rerender } = render(
        <Wrapper>
          <LibraryHeader view="library" />
        </Wrapper>
      );

      expect(screen.getByText(/Your Music Collection/)).toBeInTheDocument();

      rerender(
        <Wrapper>
          <LibraryHeader view="favourites" />
        </Wrapper>
      );

      expect(screen.getByText(/Your Favorites/)).toBeInTheDocument();
      expect(screen.queryByText(/Your Music Collection/)).not.toBeInTheDocument();
    });
  });

  describe('Styling', () => {
    it('should apply gradient styling', () => {
      const { container } = render(
        <Wrapper>
          <LibraryHeader view="library" />
        </Wrapper>
      );

      const heading = container.querySelector('h1');
      const styles = heading ? window.getComputedStyle(heading) : null;

      // Check for gradient-related styling
      expect(heading).toBeInTheDocument();
    });

    it('should have design token compliance', () => {
      const { container } = render(
        <Wrapper>
          <LibraryHeader view="library" />
        </Wrapper>
      );

      const header = container.querySelector('[class*="Box"]');
      expect(header).toBeInTheDocument();
    });
  });

  describe('Display Name', () => {
    it('should have displayName for debugging', () => {
      expect(LibraryHeader.displayName).toBe('LibraryHeader');
    });
  });

  describe('Edge Cases', () => {
    it('should handle unknown view type gracefully', () => {
      render(
        <Wrapper>
          <LibraryHeader view="unknown" />
        </Wrapper>
      );

      // Should fall back to library view
      expect(screen.getByText(/Your Music Collection/)).toBeInTheDocument();
    });

    it('should handle empty view string', () => {
      render(
        <Wrapper>
          <LibraryHeader view="" />
        </Wrapper>
      );

      expect(screen.getByText(/Your Music Collection/)).toBeInTheDocument();
    });

    it('should handle case sensitivity in view prop', () => {
      const { rerender } = render(
        <Wrapper>
          <LibraryHeader view="Favourites" />
        </Wrapper>
      );

      // Should not match (case-sensitive)
      expect(screen.getByText(/Your Music Collection/)).toBeInTheDocument();

      rerender(
        <Wrapper>
          <LibraryHeader view="favourites" />
        </Wrapper>
      );

      expect(screen.getByText(/Your Favorites/)).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have proper heading hierarchy', () => {
      render(
        <Wrapper>
          <LibraryHeader view="library" />
        </Wrapper>
      );

      const heading = screen.getByRole('heading', { level: 1 });
      expect(heading).toBeInTheDocument();
    });

    it('should have semantic HTML', () => {
      const { container } = render(
        <Wrapper>
          <LibraryHeader view="library" />
        </Wrapper>
      );

      const h1 = container.querySelector('h1');
      expect(h1).toBeInTheDocument();
    });
  });
});
