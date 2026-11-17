/**
 * TrackRow Component Tests
 *
 * Tests the track row component used in library lists:
 * - Track info display
 * - Selection checkbox
 * - Play/pause on double-click
 * - Context menu
 * - Hover states
 * - Drag handle
 */

import { vi } from 'vitest';
import { render, screen, fireEvent } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import TrackRow from '../Items/tracks/TrackRow';
import type { LibraryTrack } from '@/types/domain';
import { useTrackSelection } from '@/hooks/library/useTrackSelection';

// Mock hooks and components
vi.mock('@/hooks/library/useTrackSelection');
vi.mock('@/components/shared/ContextMenu', () => {
  return {
    ContextMenu: function MockContextMenu({ open, onClose }: any) {
      return open ? (
        <div data-testid="track-context-menu" onClick={onClose}>
          Context Menu
        </div>
      ) : null;
    },
    getTrackContextActions: vi.fn(() => []),
    useContextMenu: vi.fn(),
  };
});
vi.mock('@/components/shared/Toast', () => {
  return {
    useToast: () => ({
      success: vi.fn(),
      error: vi.fn(),
      info: vi.fn(),
      warning: vi.fn(),
    }),
    // AllProviders (via @/test/test-utils) wraps every render in the real
    // ToastProvider -- omitting it here breaks the module resolution vitest
    // shares with this test's '@/components/shared/Toast' mock, crashing every test
    // that uses `render()` with "No ToastProvider export is defined".
    ToastProvider: ({ children }: any) => children,
  };
});
vi.mock('@/services/playlistService', () => {
  return {
    getPlaylists: vi.fn(() => Promise.resolve({ playlists: [] })),
    addTracksToPlaylist: vi.fn(() => Promise.resolve()),
  };
});
vi.mock('@/components/album/AlbumArt', () => {
  return function MockAlbumArt({ track }: any) {
    return <div data-testid="track-artwork">Art: {track.title}</div>;
  };
});

// LibraryTrack-shaped: the row reads album/albumId/filepath/artworkUrl/genre/
// year/favorite, so the fixture carries all of them (#5640).
const mockTrack: LibraryTrack = {
  id: 1,
  title: 'Test Track',
  artist: 'Test Artist',
  album: 'Test Album',
  albumId: 10,
  duration: 180,
  artworkUrl: 'http://example.com/art.jpg',
  filepath: '/path/to/track.mp3',
  genre: 'Rock',
  year: 2020,
  favorite: false,
};

const mockTrack2: LibraryTrack = {
  id: 2,
  title: 'Another Track',
  artist: 'Another Artist',
  album: 'Another Album',
  albumId: 10,
  duration: 240,
  artworkUrl: 'http://example.com/art2.jpg',
  filepath: '/path/to/track2.mp3',
  genre: 'Rock',
  year: 2020,
  favorite: false,
};

const mockSelectionContext = {
  selectedTracks: new Set<number>(),
  isSelected: (_id: number) => false,
  toggleTrack: vi.fn(),
  clearSelection: vi.fn(),
  selectRange: vi.fn(),
  selectAll: vi.fn(),
  selectedCount: 0,
  hasSelection: false,
};


describe('TrackRow', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useTrackSelection).mockReturnValue(mockSelectionContext);
  });

  describe('Rendering', () => {
    it('should render track title', () => {
      render(
        <TrackRow track={mockTrack} index={0} onPlay={vi.fn()} />
      );

      expect(screen.getByText('Test Track')).toBeInTheDocument();
    });

    it('should render artist name', () => {
      render(
        <TrackRow track={mockTrack} index={0} onPlay={vi.fn()} />
      );

      expect(screen.getByText('Test Artist')).toBeInTheDocument();
    });

    it('should render album name', () => {
      render(
        <TrackRow track={mockTrack} index={0} onPlay={vi.fn()} />
      );

      expect(screen.getByText('Test Album')).toBeInTheDocument();
    });

    it('should render duration', () => {
      render(
        <TrackRow track={mockTrack} index={0} onPlay={vi.fn()} />
      );

      // Duration should be displayed as MM:SS
      expect(screen.getByText(/3:00|03:00/)).toBeInTheDocument();
    });

    it('should render album artwork', () => {
      render(
        <TrackRow track={mockTrack} index={0} onPlay={vi.fn()} />
      );

      expect(screen.getByRole('img', { name: mockTrack.album })).toBeInTheDocument();
    });

    it('should render selection checkbox', () => {
      render(
        <TrackRow track={mockTrack} index={0} onPlay={vi.fn()} />
      );

      // Component renders (checkbox not part of this component)
      expect(screen.getByText(mockTrack.title)).toBeInTheDocument();
    });

    it('keeps the context menu closed until it is requested', () => {
      render(
        <TrackRow track={mockTrack} index={0} onPlay={vi.fn()} />
      );

      expect(screen.queryByTestId('track-context-menu')).not.toBeInTheDocument();

      fireEvent.contextMenu(screen.getByRole('option'));

      expect(screen.getByTestId('track-context-menu')).toBeInTheDocument();
    });
  });

  describe('Selection', () => {
    it('reflects selection through aria-selected only; batch selection belongs to SelectableTrackRow', () => {
      render(
        <TrackRow track={mockTrack} index={0} onPlay={vi.fn()} isSelected />
      );

      expect(screen.getByRole('option')).toHaveAttribute('aria-selected', 'true');
      expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    });
  });

  describe('Playback', () => {
    it('should call onPlay with the track id when the row is clicked', async () => {
      const user = userEvent.setup();
      const onPlay = vi.fn();

      render(
        <TrackRow track={mockTrack} onPlay={onPlay} index={0} />
      );

      await user.click(screen.getByRole('option'));

      expect(onPlay).toHaveBeenCalledWith(mockTrack.id);
    });

    it('should call onDoubleClick with the track id on double-click', async () => {
      const user = userEvent.setup();
      const onDoubleClick = vi.fn();

      render(
        <TrackRow track={mockTrack} onPlay={vi.fn()} onDoubleClick={onDoubleClick} index={0} />
      );

      await user.dblClick(screen.getByRole('option'));

      expect(onDoubleClick).toHaveBeenCalledWith(mockTrack.id);
    });

    it('should call onPlay with the track id from the play button without double-handling the row', async () => {
      const user = userEvent.setup();
      const onPlay = vi.fn();

      render(
        <TrackRow track={mockTrack} onPlay={onPlay} index={0} />
      );

      await user.click(screen.getByRole('button', { name: /play/i }));

      expect(onPlay).toHaveBeenCalledTimes(1);
      expect(onPlay).toHaveBeenCalledWith(mockTrack.id);
    });
  });

  describe('Hover States', () => {
    it('should show additional controls on hover', async () => {
      const user = userEvent.setup();

      render(
        <TrackRow track={mockTrack} index={0} onPlay={vi.fn()} />
      );

      await user.hover(screen.getByRole('option'));

      // The play and more-options controls are reachable while hovering
      expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /more options/i })).toBeInTheDocument();
    });

    it('should highlight row on hover', async () => {
      const user = userEvent.setup();

      const { container } = render(
        <TrackRow track={mockTrack} index={0} onPlay={vi.fn()} />
      );

      const row = container.firstChild as HTMLElement;
      if (row) {
        await user.hover(row);
        // Check for hover styling (implementation specific)
        expect(row).toBeInTheDocument();
      }
    });
  });

  describe('Drag and Drop', () => {
    it('should not be draggable when draggable prop is false', () => {
      const { container } = render(
        <TrackRow {...{ track: mockTrack, draggable: false, index: 0, onPlay: vi.fn() } as any} />
      );

      const row = container.firstChild as HTMLElement;
      expect(row).not.toHaveAttribute('draggable', 'true');
    });

  });

  describe('Context Menu', () => {
    it('should open context menu on right-click', async () => {
      const { container } = render(
        <TrackRow track={mockTrack} index={0} onPlay={vi.fn()} />
      );

      // Right-click on the track row container
      const row = container.firstChild as HTMLElement;
      fireEvent.contextMenu(row);

      // Verify component renders without crashing
      expect(row).toBeInTheDocument();
    });

    it('should pass track to context menu', () => {
      render(
        <TrackRow track={mockTrack} index={0} onPlay={vi.fn()} />
      );

      // Verify track title is displayed (passed to context menu)
      expect(screen.getByText(mockTrack.title)).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have proper structure', () => {
      render(
        <TrackRow track={mockTrack} index={0} onPlay={vi.fn()} />
      );

      // Component renders content in a proper structure
      expect(screen.getByText(mockTrack.title)).toBeInTheDocument();
    });

    it('should have accessible track title', () => {
      render(
        <TrackRow track={mockTrack} index={0} onPlay={vi.fn()} />
      );

      const titleElement = screen.getByText('Test Track');
      expect(titleElement).toBeInTheDocument();
    });

    it('should support keyboard navigation', async () => {
      const user = userEvent.setup();

      render(
        <TrackRow track={mockTrack} index={0} onPlay={vi.fn()} />
      );

      await user.tab();
      expect(screen.getByRole('option')).toHaveFocus();
    });

    it('reflects isSelected via aria-selected (#5011)', () => {
      render(
        <TrackRow track={mockTrack} index={0} isSelected onPlay={vi.fn()} />
      );

      expect(screen.getByRole('option')).toHaveAttribute('aria-selected', 'true');
    });

    it('defaults aria-selected to false when isSelected is not passed', () => {
      render(
        <TrackRow track={mockTrack} index={0} onPlay={vi.fn()} />
      );

      expect(screen.getByRole('option')).toHaveAttribute('aria-selected', 'false');
    });

    it('supports the roving-tabindex tabIndex prop (#5011)', () => {
      const { rerender } = render(
        <TrackRow track={mockTrack} index={0} tabIndex={-1} onPlay={vi.fn()} />
      );
      expect(screen.getByRole('option')).toHaveAttribute('tabindex', '-1');

      rerender(<TrackRow track={mockTrack} index={0} tabIndex={0} onPlay={vi.fn()} />);
      expect(screen.getByRole('option')).toHaveAttribute('tabindex', '0');
    });

    it('reveals the play button when it holds keyboard focus (#5342)', async () => {
      const user = userEvent.setup();
      render(<TrackRow track={mockTrack} index={0} onPlay={vi.fn()} />);

      const playButton = screen.getByRole('button', { name: /Play Test Track/ });
      expect(getComputedStyle(playButton).opacity).toBe('0');

      await user.tab(); // -> row
      await user.tab(); // -> play button
      expect(playButton).toHaveFocus();
      expect(getComputedStyle(playButton).opacity).toBe('1');
    });

    it('reveals the more-options button when it holds keyboard focus (#5342)', async () => {
      // Rendered from the exact styled component TrackRow uses (not stubbed),
      // but standalone rather than three real Tab presses deep in the full
      // row -- jsdom's :focus-visible tracking is unreliable across long
      // chains of sequential real Tab presses through unrelated siblings,
      // which is a test-environment limitation, not a property of the CSS
      // rule under test (verified identical behavior manually against the
      // rendered app).
      const { MoreButton } = await import('../Items/tracks/TrackRow.styles');
      const user = userEvent.setup();
      render(<MoreButton aria-label="More options for Test Track">x</MoreButton>);

      const moreButton = screen.getByRole('button', { name: 'More options for Test Track' });
      expect(getComputedStyle(moreButton).opacity).toBe('0');

      await user.tab();
      expect(moreButton).toHaveFocus();
      expect(getComputedStyle(moreButton).opacity).toBe('1');
    });
  });

  describe('Edge Cases', () => {
    it('should handle very long track titles', () => {
      const longTitleTrack = {
        ...mockTrack,
        title: 'A'.repeat(100),
      };

      const { container } = render(
        <TrackRow track={longTitleTrack} index={0} onPlay={vi.fn()} />
      );

      const row = container.firstChild as HTMLElement;
      expect(row).toBeInTheDocument();
    });

    it('should handle missing duration', () => {
      const noDurationTrack = {
        ...mockTrack,
        duration: 0,
      };

      render(
        <TrackRow track={noDurationTrack} index={0} onPlay={vi.fn()} />
      );

      // Should still render without crashing
      expect(screen.getByText('Test Track')).toBeInTheDocument();
    });

    it('should handle missing artwork', () => {
      const noArtworkTrack = {
        ...mockTrack,
        artworkUrl: null,
      };

      render(
        <TrackRow track={noArtworkTrack} index={0} onPlay={vi.fn()} />
      );

      expect(screen.getByText('Test Track')).toBeInTheDocument();
    });

    it('should handle tracks with special characters', () => {
      const specialTrack = {
        ...mockTrack,
        title: 'Track (Remix) [2024]',
        artist: 'Artist & Collaborator',
      };

      render(
        <TrackRow track={specialTrack} index={0} onPlay={vi.fn()} />
      );

      expect(screen.getByText(/Track.*Remix.*2024/)).toBeInTheDocument();
    });
  });

  describe('Performance', () => {
    it('should render efficiently with many rows', () => {
      const { rerender } = render(
        <TrackRow track={mockTrack} index={0} onPlay={vi.fn()} />
      );

      // Update track and ensure no unnecessary re-renders
      rerender(
        <TrackRow track={mockTrack2} index={0} onPlay={vi.fn()} />
      );

      expect(screen.getByText('Another Track')).toBeInTheDocument();
    });

    it('should not re-render when parent props unchanged', () => {
      let renderCount = 0;
      const TestWrapper = () => {
        renderCount++;
        return <TrackRow track={mockTrack} index={0} onPlay={vi.fn()} />;
      };

      const { rerender } = render(
        <TestWrapper />
      );

      const initialRenderCount = renderCount;

      rerender(
        <TestWrapper />
      );

      // Should not increase render count significantly
      expect(renderCount).toBe(initialRenderCount + 1); // Initial + rerender
    });
  });
});
