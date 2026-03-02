/**
 * TrackDisplay Component Tests
 *
 * Tests for track title, artist, album display, overflow handling, and accessibility.
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@/test/test-utils';
import TrackDisplay from '../TrackDisplay';

describe('TrackDisplay', () => {
  describe('Basic Rendering', () => {
    it('should render track title', () => {
      render(
        <TrackDisplay
          title="Song Title"
        />
      );

      expect(screen.getByTestId('track-display')).toBeInTheDocument();
      expect(screen.getByTestId('track-display-title')).toHaveTextContent('Song Title');
    });

    it('should render title, artist, and album', () => {
      render(
        <TrackDisplay
          title="Song Title"
          artist="Artist Name"
          album="Album Name"
        />
      );

      expect(screen.getByTestId('track-display-title')).toHaveTextContent('Song Title');
      expect(screen.getByTestId('track-display-artist')).toHaveTextContent('Artist Name');
      expect(screen.getByTestId('track-display-album')).toHaveTextContent('Album Name');
    });

    it('should render meta section only when artist or album provided', () => {
      render(
        <TrackDisplay
          title="Song Title"
        />
      );

      expect(screen.queryByTestId('track-display-meta')).not.toBeInTheDocument();
    });

    it('should render meta section with only artist', () => {
      render(
        <TrackDisplay
          title="Song Title"
          artist="Artist Name"
        />
      );

      expect(screen.getByTestId('track-display-meta')).toBeInTheDocument();
      expect(screen.getByTestId('track-display-artist')).toBeInTheDocument();
      expect(screen.queryByTestId('track-display-album')).not.toBeInTheDocument();
    });

    it('should render meta section with only album', () => {
      render(
        <TrackDisplay
          title="Song Title"
          album="Album Name"
        />
      );

      expect(screen.getByTestId('track-display-meta')).toBeInTheDocument();
      expect(screen.queryByTestId('track-display-artist')).not.toBeInTheDocument();
      expect(screen.getByTestId('track-display-album')).toBeInTheDocument();
    });
  });

  describe('Text Overflow Handling', () => {
    it('should apply ellipsis for long title', () => {
      render(
        <TrackDisplay
          title="This is a very very long song title that should be truncated"
        />
      );

      const title = screen.getByTestId('track-display-title');
      const styles = window.getComputedStyle(title);
      expect(styles.textOverflow).toBe('ellipsis');
      expect(styles.overflow).toBe('hidden');
      expect(styles.whiteSpace).toBe('nowrap');
    });

    it('should apply ellipsis for long artist and album', () => {
      render(
        <TrackDisplay
          title="Song"
          artist="Very Long Artist Name That Should Be Truncated"
          album="Very Long Album Name That Should Be Truncated"
        />
      );

      const meta = screen.getByTestId('track-display-meta');
      const styles = window.getComputedStyle(meta);
      expect(styles.textOverflow).toBe('ellipsis');
      expect(styles.overflow).toBe('hidden');
    });

    it('should have title attribute for accessibility', () => {
      render(
        <TrackDisplay
          title="Song Title"
          artist="Artist Name"
          album="Album Name"
        />
      );

      const title = screen.getByTestId('track-display-title');
      expect(title).toHaveAttribute('title', 'Song Title');
    });

    it('should have combined title attribute for meta', () => {
      render(
        <TrackDisplay
          title="Song Title"
          artist="Artist Name"
          album="Album Name"
        />
      );

      const meta = screen.getByTestId('track-display-meta');
      expect(meta).toHaveAttribute('title', 'Artist Name • Album Name');
    });
  });

  describe('Meta Separator', () => {
    it('should show separator between artist and album', () => {
      render(
        <TrackDisplay
          title="Song Title"
          artist="Artist Name"
          album="Album Name"
        />
      );

      const meta = screen.getByTestId('track-display-meta');
      expect(meta.textContent).toContain('Artist Name • Album Name');
    });

    it('should not show separator with only artist', () => {
      render(
        <TrackDisplay
          title="Song Title"
          artist="Artist Name"
        />
      );

      const meta = screen.getByTestId('track-display-meta');
      expect(meta.textContent).toBe('Artist Name');
    });

    it('should not show separator with only album', () => {
      render(
        <TrackDisplay
          title="Song Title"
          album="Album Name"
        />
      );

      const meta = screen.getByTestId('track-display-meta');
      expect(meta.textContent).toBe('Album Name');
    });
  });

  describe('Loading State', () => {
    it('should show loading placeholder when isLoading is true', () => {
      render(
        <TrackDisplay
          title="Song Title"
          isLoading={true}
        />
      );

      expect(screen.getByTestId('track-display-loading')).toBeInTheDocument();
      expect(screen.queryByTestId('track-display-title')).not.toBeInTheDocument();
    });

    it('should not show loading placeholder when isLoading is false', () => {
      render(
        <TrackDisplay
          title="Song Title"
          isLoading={false}
        />
      );

      expect(screen.queryByTestId('track-display-loading')).not.toBeInTheDocument();
      expect(screen.getByTestId('track-display-title')).toBeInTheDocument();
    });

    it('should show multiple placeholders when loading with artist', () => {
      render(
        <TrackDisplay
          title="Song Title"
          artist="Artist Name"
          isLoading={true}
        />
      );

      const placeholders = screen.getByTestId('track-display').querySelectorAll('[data-testid="track-display-loading"], div:first-child');
      expect(placeholders.length).toBeGreaterThanOrEqual(1);
    });

    it('should apply pulse animation to loading placeholder', () => {
      render(
        <TrackDisplay
          title="Song Title"
          isLoading={true}
        />
      );

      const loading = screen.getByTestId('track-display-loading');
      const styles = window.getComputedStyle(loading);
      expect(styles.animation).toContain('pulse');
    });
  });

  describe('Accessibility', () => {
    it('should have aria-label with title only', () => {
      render(
        <TrackDisplay
          title="Song Title"
        />
      );

      const container = screen.getByTestId('track-display');
      expect(container).toHaveAttribute('aria-label', 'Song Title');
    });

    it('should have aria-label with title and artist', () => {
      render(
        <TrackDisplay
          title="Song Title"
          artist="Artist Name"
        />
      );

      const container = screen.getByTestId('track-display');
      expect(container).toHaveAttribute('aria-label', 'Song Title • Artist Name');
    });

    it('should have aria-label with all information', () => {
      render(
        <TrackDisplay
          title="Song Title"
          artist="Artist Name"
          album="Album Name"
        />
      );

      const container = screen.getByTestId('track-display');
      expect(container).toHaveAttribute('aria-label', 'Song Title • Artist Name • Album Name');
    });

    it('should support custom aria-label', () => {
      render(
        <TrackDisplay
          title="Song Title"
          ariaLabel="Custom label"
        />
      );

      const container = screen.getByTestId('track-display');
      expect(container).toHaveAttribute('aria-label', 'Custom label');
    });
  });

  describe('CSS & Styling', () => {
    it('should accept custom className', () => {
      const { container } = render(
        <TrackDisplay
          title="Song Title"
          className="custom-track-class"
        />
      );

      expect(container.querySelector('.custom-track-class')).toBeInTheDocument();
    });

    it('should apply flex layout', () => {
      render(
        <TrackDisplay
          title="Song Title"
        />
      );

      const display = screen.getByTestId('track-display');
      const styles = window.getComputedStyle(display);
      expect(styles.display).toBe('flex');
      expect(styles.flexDirection).toBe('column');
    });

    it('should have proper test IDs', () => {
      render(
        <TrackDisplay
          title="Song Title"
          artist="Artist Name"
          album="Album Name"
        />
      );

      expect(screen.getByTestId('track-display')).toBeInTheDocument();
      expect(screen.getByTestId('track-display-title')).toBeInTheDocument();
      expect(screen.getByTestId('track-display-meta')).toBeInTheDocument();
    });

    it('should use design tokens for colors', () => {
      render(
        <TrackDisplay
          title="Song Title"
          artist="Artist Name"
        />
      );

      const title = screen.getByTestId('track-display-title');
      const styles = window.getComputedStyle(title);
      expect(styles.fontWeight).toBe('bold');
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty title gracefully', () => {
      render(
        <TrackDisplay
          title=""
        />
      );

      expect(screen.getByTestId('track-display-title')).toBeInTheDocument();
      expect(screen.getByTestId('track-display-title')).toHaveTextContent('');
    });

    it('should handle empty artist and album', () => {
      render(
        <TrackDisplay
          title="Song Title"
          artist=""
          album=""
        />
      );

      expect(screen.queryByTestId('track-display-meta')).not.toBeInTheDocument();
    });

    it('should handle very long single title', () => {
      const longTitle = 'A'.repeat(500);
      render(
        <TrackDisplay
          title={longTitle}
        />
      );

      expect(screen.getByTestId('track-display-title')).toHaveTextContent(longTitle);
    });

    it('should handle special characters in title', () => {
      render(
        <TrackDisplay
          title="Song: The (Remix) [2024 Edition]"
        />
      );

      expect(screen.getByTestId('track-display-title')).toHaveTextContent('Song: The (Remix) [2024 Edition]');
    });

    it('should handle unicode characters', () => {
      render(
        <TrackDisplay
          title="Μουσική Song 音楽"
          artist="Artiste Artista"
        />
      );

      expect(screen.getByTestId('track-display-title')).toHaveTextContent('Μουσική Song 音楽');
      expect(screen.getByTestId('track-display-artist')).toHaveTextContent('Artiste Artista');
    });
  });

  describe('Realistic Scenarios', () => {
    it('should handle typical music metadata', () => {
      render(
        <TrackDisplay
          title="Bohemian Rhapsody"
          artist="Queen"
          album="A Night at the Opera"
        />
      );

      expect(screen.getByTestId('track-display-title')).toHaveTextContent('Bohemian Rhapsody');
      expect(screen.getByTestId('track-display-artist')).toHaveTextContent('Queen');
      expect(screen.getByTestId('track-display-album')).toHaveTextContent('A Night at the Opera');
    });

    it('should handle tracks with featured artists in title', () => {
      render(
        <TrackDisplay
          title="Collaboration (feat. Artist 2)"
          artist="Artist 1"
          album="Album"
        />
      );

      expect(screen.getByTestId('track-display-title')).toHaveTextContent('Collaboration (feat. Artist 2)');
    });

    it('should handle transitions between loading and loaded states', () => {
      const { rerender } = render(
        <TrackDisplay
          title="Song Title"
          artist="Artist"
          isLoading={true}
        />
      );

      expect(screen.getByTestId('track-display-loading')).toBeInTheDocument();

      rerender(
        <TrackDisplay
          title="New Song"
          artist="New Artist"
          isLoading={false}
        />
      );

      expect(screen.queryByTestId('track-display-loading')).not.toBeInTheDocument();
      expect(screen.getByTestId('track-display-title')).toHaveTextContent('New Song');
      expect(screen.getByTestId('track-display-artist')).toHaveTextContent('New Artist');
    });

    it('should handle metadata updates', () => {
      const { rerender } = render(
        <TrackDisplay
          title="Song 1"
          artist="Artist 1"
          album="Album 1"
        />
      );

      expect(screen.getByTestId('track-display-title')).toHaveTextContent('Song 1');

      rerender(
        <TrackDisplay
          title="Song 2"
          artist="Artist 2"
          album="Album 2"
        />
      );

      expect(screen.getByTestId('track-display-title')).toHaveTextContent('Song 2');
      expect(screen.getByTestId('track-display-artist')).toHaveTextContent('Artist 2');
      expect(screen.getByTestId('track-display-album')).toHaveTextContent('Album 2');
    });
  });
});
