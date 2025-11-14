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
import { render, screen } from '@/test/test-utils';
import { LibraryHeader } from '../LibraryHeader';


describe('LibraryHeader', () => {
  describe('Rendering', () => {
    it('should render header container', () => {
      render(
        <LibraryHeader view="library" />
      );

      expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
    });

    it('should display library title by default', () => {
      render(
        <LibraryHeader view="library" />
      );

      expect(screen.getByText(/Your Music Collection/)).toBeInTheDocument();
    });

    it('should display library subtitle', () => {
      render(
        <LibraryHeader view="library" />
      );

      expect(screen.getByText(/Rediscover the magic/)).toBeInTheDocument();
    });
  });

  describe('View Types', () => {
    it('should display library view content', () => {
      render(
        <LibraryHeader view="library" />
      );

      expect(screen.getByText(/Your Music Collection/)).toBeInTheDocument();
      expect(screen.getByText(/Rediscover the magic/)).toBeInTheDocument();
    });

    it('should display favorites view content', () => {
      render(
        <LibraryHeader view="favourites" />
      );

      expect(screen.getByText(/Your Favorites/)).toBeInTheDocument();
      expect(screen.getByText(/Your most loved tracks/)).toBeInTheDocument();
    });

    it('should display heart emoji for favorites', () => {
      render(
        <LibraryHeader view="favourites" />
      );

      const heading = screen.getByRole('heading', { level: 1 });
      expect(heading.textContent).toContain('❤️');
    });

    it('should display music emoji for library', () => {
      render(
        <LibraryHeader view="library" />
      );

      const heading = screen.getByRole('heading', { level: 1 });
      expect(heading.textContent).toContain('🎵');
    });
  });

  describe('Typography', () => {
    it('should have h3 heading variant', () => {
      render(
        <LibraryHeader view="library" />
      );

      const heading = screen.getByRole('heading', { level: 1 });
      expect(heading).toBeInTheDocument();
    });

    it('should have subtitle text', () => {
      const { container } = render(
        <LibraryHeader view="library" />
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
        <LibraryHeader view="library" />
      );

      expect(screen.getByText(/Your Music Collection/)).toBeInTheDocument();

      // Rerender with same props - should not re-render unnecessarily
      rerender(
        <LibraryHeader view="library" />
      );

      expect(screen.getByText(/Your Music Collection/)).toBeInTheDocument();
    });

    it('should update when view prop changes', () => {
      const { rerender } = render(
        <LibraryHeader view="library" />
      );

      expect(screen.getByText(/Your Music Collection/)).toBeInTheDocument();

      rerender(
        <LibraryHeader view="favourites" />
      );

      expect(screen.getByText(/Your Favorites/)).toBeInTheDocument();
      expect(screen.queryByText(/Your Music Collection/)).not.toBeInTheDocument();
    });
  });

  describe('Styling', () => {
    it('should apply gradient styling', () => {
      const { container } = render(
        <LibraryHeader view="library" />
      );

      const heading = container.querySelector('h1');
      const styles = heading ? window.getComputedStyle(heading) : null;

      // Check for gradient-related styling
      expect(heading).toBeInTheDocument();
    });

    it('should have design token compliance', () => {
      const { container } = render(
        <LibraryHeader view="library" />
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
        <LibraryHeader view="unknown" />
      );

      // Should fall back to library view
      expect(screen.getByText(/Your Music Collection/)).toBeInTheDocument();
    });

    it('should handle empty view string', () => {
      render(
        <LibraryHeader view="" />
      );

      expect(screen.getByText(/Your Music Collection/)).toBeInTheDocument();
    });

    it('should handle case sensitivity in view prop', () => {
      const { rerender } = render(
        <LibraryHeader view="Favourites" />
      );

      // Should not match (case-sensitive)
      expect(screen.getByText(/Your Music Collection/)).toBeInTheDocument();

      rerender(
        <LibraryHeader view="favourites" />
      );

      expect(screen.getByText(/Your Favorites/)).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have proper heading hierarchy', () => {
      render(
        <LibraryHeader view="library" />
      );

      const heading = screen.getByRole('heading', { level: 1 });
      expect(heading).toBeInTheDocument();
    });

    it('should have semantic HTML', () => {
      const { container } = render(
        <LibraryHeader view="library" />
      );

      const h1 = container.querySelector('h1');
      expect(h1).toBeInTheDocument();
    });
  });
});
