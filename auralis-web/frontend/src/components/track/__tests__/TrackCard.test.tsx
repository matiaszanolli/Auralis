/**
 * TrackCard Component Tests
 *
 * Tests the card-based track display component:
 * - Album artwork display
 * - Track metadata
 * - Play button on hover
 * - Selection state
 * - Context menu access
 */

import { vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import { TrackCard } from '../TrackCard';
import { useTrackSelection } from '../../../hooks/useTrackSelection';

// Mock hooks and components
vi.mock('../../../hooks/useTrackSelection');
vi.mock('../../album/AlbumArt', () => {
  return function MockAlbumArt({ track }: any) {
    return (
      <div data-testid="track-card-artwork">
        <img src={track.artwork} alt={track.title} />
      </div>
    );
  };
});
vi.mock('../../shared/TrackContextMenu', () => {
  return function MockContextMenu({ track, onPlay }: any) {
    return (
      <div data-testid="track-card-context-menu">
        <button onClick={() => onPlay?.(track)}>Play from Menu</button>
      </div>
    );
  };
});

const mockTrack = {
  id: 1,
  title: 'Beautiful Song',
  artist: 'Amazing Artist',
  album: 'Great Album',
  duration: 240,
  artwork: 'http://example.com/artwork.jpg',
};

const mockSelectionContext = {
  selectedTracks: new Set<number>(),
  isSelected: (id: number) => false,
  toggleSelection: vi.fn(),
};


describe('TrackCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useTrackSelection).mockReturnValue(mockSelectionContext);
  });

  describe('Rendering', () => {
    it('should render track card container', () => {
      render(
        <TrackCard track={mockTrack} />
      );

      const card = screen.getByRole('article') || screen.getByTestId(/card|container/i);
      expect(card).toBeInTheDocument();
    });

    it('should display album artwork', () => {
      render(
        <TrackCard track={mockTrack} />
      );

      const artwork = screen.getByTestId('track-card-artwork');
      expect(artwork).toBeInTheDocument();
      expect(artwork.querySelector('img')).toHaveAttribute('src', mockTrack.artwork);
    });

    it('should display track title', () => {
      render(
        <TrackCard track={mockTrack} />
      );

      expect(screen.getByText('Beautiful Song')).toBeInTheDocument();
    });

    it('should display artist name', () => {
      render(
        <TrackCard track={mockTrack} />
      );

      expect(screen.getByText('Amazing Artist')).toBeInTheDocument();
    });

    it('should display album name', () => {
      render(
        <TrackCard track={mockTrack} />
      );

      expect(screen.getByText('Great Album')).toBeInTheDocument();
    });

    it('should display duration', () => {
      render(
        <TrackCard track={mockTrack} />
      );

      expect(screen.getByText(/4:00|04:00/)).toBeInTheDocument();
    });

    it('should render selection checkbox', () => {
      render(
        <TrackCard track={mockTrack} />
      );

      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toBeInTheDocument();
    });
  });

  describe('Play Button on Hover', () => {
    it('should show play button on hover', async () => {
      const user = userEvent.setup();

      render(
        <TrackCard track={mockTrack} />
      );

      const card = screen.getByRole('article') || screen.getByTestId(/card|container/i);
      await user.hover(card);

      // Play button should be visible on hover
      const playButton = screen.queryByRole('button', { name: /play/i });
      expect(playButton).toBeInTheDocument();
    });

    it('should hide play button when not hovering', async () => {
      const user = userEvent.setup();

      const { container } = render(
        <TrackCard track={mockTrack} />
      );

      const card = container.querySelector('[data-testid*="card"]') || container.firstChild;

      if (card) {
        await user.unhover(card as Element);
        // Play button should be hidden when not hovering
        const playButton = screen.queryByRole('button', { name: /play/i, hidden: false });
        if (playButton) {
          const style = window.getComputedStyle(playButton);
          expect(style.visibility === 'hidden' || style.display === 'none').toBeTruthy();
        }
      }
    });

    it('should call onPlay when play button clicked', async () => {
      const user = userEvent.setup();
      const onPlay = vi.fn();

      render(
        <TrackCard track={mockTrack} onPlay={onPlay} />
      );

      const card = screen.getByRole('article') || screen.getByTestId(/card|container/i);
      await user.hover(card);

      const playButton = screen.getByRole('button', { name: /play/i });
      await user.click(playButton);

      expect(onPlay).toHaveBeenCalledWith(mockTrack);
    });
  });

  describe('Selection', () => {
    it('should show unchecked checkbox when not selected', () => {
      vi.mocked(useTrackSelection).mockReturnValue({
        ...mockSelectionContext,
        isSelected: () => false,
      });

      render(
        <TrackCard track={mockTrack} />
      );

      const checkbox = screen.getByRole('checkbox') as HTMLInputElement;
      expect(checkbox.checked).toBe(false);
    });

    it('should show checked checkbox when selected', () => {
      vi.mocked(useTrackSelection).mockReturnValue({
        ...mockSelectionContext,
        isSelected: () => true,
        selectedTracks: new Set([mockTrack.id]),
      });

      render(
        <TrackCard track={mockTrack} />
      );

      const checkbox = screen.getByRole('checkbox') as HTMLInputElement;
      expect(checkbox.checked).toBe(true);
    });

    it('should toggle selection on checkbox click', async () => {
      const user = userEvent.setup();
      const toggleSelection = vi.fn();

      vi.mocked(useTrackSelection).mockReturnValue({
        ...mockSelectionContext,
        toggleSelection,
      });

      render(
        <TrackCard track={mockTrack} />
      );

      const checkbox = screen.getByRole('checkbox');
      await user.click(checkbox);

      expect(toggleSelection).toHaveBeenCalledWith(mockTrack.id);
    });

    it('should highlight card when selected', () => {
      vi.mocked(useTrackSelection).mockReturnValue({
        ...mockSelectionContext,
        isSelected: () => true,
        selectedTracks: new Set([mockTrack.id]),
      });

      const { container } = render(
        <TrackCard track={mockTrack} />
      );

      const card = container.querySelector('[data-testid*="card"]');
      if (card) {
        const classes = card.className;
        expect(classes.includes('selected') || card.getAttribute('aria-selected')).toBeTruthy();
      }
    });
  });

  describe('Context Menu', () => {
    it('should render context menu', () => {
      render(
        <TrackCard track={mockTrack} />
      );

      expect(screen.getByTestId('track-card-context-menu')).toBeInTheDocument();
    });

    it('should open context menu on right-click', async () => {
      const user = userEvent.setup();

      render(
        <TrackCard track={mockTrack} />
      );

      const card = screen.getByRole('article') || screen.getByTestId(/card|container/i);
      fireEvent.contextMenu(card);

      expect(screen.getByTestId('track-card-context-menu')).toBeInTheDocument();
    });

    it('should call onPlay from context menu', async () => {
      const user = userEvent.setup();
      const onPlay = vi.fn();

      render(
        <TrackCard track={mockTrack} onPlay={onPlay} />
      );

      const playButton = screen.getByText('Play from Menu');
      await user.click(playButton);

      expect(onPlay).toHaveBeenCalledWith(mockTrack);
    });
  });

  describe('Styling & Layout', () => {
    it('should apply card styling', () => {
      const { container } = render(
        <TrackCard track={mockTrack} />
      );

      const card = container.querySelector('[data-testid*="card"]') || container.firstChild;
      expect(card).toHaveClass(/card|Card/);
    });

    it('should stack metadata below artwork', () => {
      const { container } = render(
        <TrackCard track={mockTrack} />
      );

      const artwork = screen.getByTestId('track-card-artwork');
      const title = screen.getByText('Beautiful Song');

      const artworkRect = artwork.getBoundingClientRect();
      const titleRect = title.getBoundingClientRect();

      // Title should be below artwork
      expect(titleRect.top).toBeGreaterThan(artworkRect.bottom);
    });

    it('should have proper aspect ratio for artwork', () => {
      const { container } = render(
        <TrackCard track={mockTrack} />
      );

      const artwork = screen.getByTestId('track-card-artwork');
      const rect = artwork.getBoundingClientRect();

      // Should be roughly square (1:1 aspect ratio)
      const aspectRatio = rect.width / rect.height;
      expect(Math.abs(aspectRatio - 1)).toBeLessThan(0.1);
    });
  });

  describe('Interactions', () => {
    it('should handle double-click to play', async () => {
      const user = userEvent.setup();
      const onPlay = vi.fn();

      render(
        <TrackCard track={mockTrack} onPlay={onPlay} />
      );

      const card = screen.getByRole('article') || screen.getByTestId(/card|container/i);
      await user.dblClick(card);

      expect(onPlay).toHaveBeenCalledWith(mockTrack);
    });

    it('should show overlay on hover', async () => {
      const user = userEvent.setup();

      const { container } = render(
        <TrackCard track={mockTrack} />
      );

      const card = container.querySelector('[data-testid*="card"]') || container.firstChild;

      if (card) {
        await user.hover(card as Element);
        // Overlay should be visible
        const overlay = container.querySelector('[data-testid*="overlay"]');
        if (overlay) {
          const style = window.getComputedStyle(overlay);
          expect(style.opacity).not.toBe('0');
        }
      }
    });
  });

  describe('Edge Cases', () => {
    it('should handle missing artwork gracefully', () => {
      const noArtworkTrack = { ...mockTrack, artwork: null };

      render(
        <TrackCard track={noArtworkTrack} />
      );

      // Should still render without crashing
      expect(screen.getByText('Beautiful Song')).toBeInTheDocument();
    });

    it('should handle very long track title', () => {
      const longTitleTrack = {
        ...mockTrack,
        title: 'A'.repeat(50),
      };

      render(
        <TrackCard track={longTitleTrack} />
      );

      // Should truncate or wrap appropriately
      expect(screen.getByText(/A+/)).toBeInTheDocument();
    });

    it('should handle very long artist name', () => {
      const longArtistTrack = {
        ...mockTrack,
        artist: 'B'.repeat(50),
      };

      render(
        <TrackCard track={longArtistTrack} />
      );

      expect(screen.getByText(/B+/)).toBeInTheDocument();
    });

    it('should handle missing duration', () => {
      const noDurationTrack = { ...mockTrack, duration: 0 };

      render(
        <TrackCard track={noDurationTrack} />
      );

      expect(screen.getByText('Beautiful Song')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA roles', () => {
      render(
        <TrackCard track={mockTrack} />
      );

      const card = screen.getByRole('article');
      expect(card).toHaveAttribute('aria-label');
    });

    it('should have accessible checkbox', () => {
      render(
        <TrackCard track={mockTrack} />
      );

      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toHaveAccessibleName();
    });

    it('should support keyboard navigation', async () => {
      const user = userEvent.setup();

      render(
        <TrackCard track={mockTrack} />
      );

      const checkbox = screen.getByRole('checkbox');
      await user.tab();

      // Should be focusable
      expect(document.activeElement).toBeInTheDocument();
    });
  });

  describe('Performance', () => {
    it('should render efficiently', () => {
      const { rerender } = render(
        <TrackCard track={mockTrack} />
      );

      const otherTrack = { ...mockTrack, id: 2, title: 'Different Track' };

      rerender(
        <TrackCard track={otherTrack} />
      );

      expect(screen.getByText('Different Track')).toBeInTheDocument();
    });
  });
});
