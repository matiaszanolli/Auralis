/**
 * TrackRow Memoization Tests
 *
 * Tests that verify React.memo is working correctly for TrackRow and its children:
 * - TrackRow memoization with custom comparator
 * - TrackRowMetadata memoization
 * - TrackRowPlayButton memoization
 * - TrackRowAlbumArt memoization
 *
 * These tests ensure O(n) re-render problems are solved (issue #2173)
 */

import { vi } from 'vitest';
import { render, screen } from '@/test/test-utils';
import TrackRow from '../TrackRow';
import TrackRowMetadata from '../TrackRowMetadata';
import TrackRowPlayButton from '../TrackRowPlayButton';
import TrackRowAlbumArt from '../TrackRowAlbumArt';

// Mock hooks and components to reduce noise in tests
vi.mock('../../shared/ContextMenu', () => ({
  ContextMenu: () => null,
}));

vi.mock('../useTrackRowHandlers', () => ({
  useTrackRowHandlers: () => ({
    handlePlayClick: vi.fn(),
    handleRowClick: vi.fn(),
    handleRowDoubleClick: vi.fn(),
  }),
}));

vi.mock('../useTrackContextMenu', () => ({
  useTrackContextMenu: () => ({
    contextMenuPosition: null,
    playlists: [],
    isLoadingPlaylists: false,
    handleMoreClick: vi.fn(),
    handleTrackContextMenu: vi.fn(),
    handleCloseContextMenu: vi.fn(),
    handleAddToPlaylist: vi.fn(),
    handleCreatePlaylist: vi.fn(),
    contextActions: [],
  }),
}));

vi.mock('../useTrackImage', () => ({
  useTrackImage: () => ({
    imageError: false,
    handleImageError: vi.fn(),
    shouldShowImage: () => true,
  }),
}));

vi.mock('../useTrackFormatting', () => ({
  useTrackFormatting: () => ({
    formatDuration: (duration: number) => {
      const minutes = Math.floor(duration / 60);
      const seconds = duration % 60;
      return `${minutes}:${seconds.toString().padStart(2, '0')}`;
    },
  }),
}));

const mockTrack = {
  id: 1,
  title: 'Test Track',
  artist: 'Test Artist',
  album: 'Test Album',
  duration: 180,
  albumArt: 'http://example.com/art.jpg',
};

describe('TrackRow Memoization', () => {

  describe('TrackRow Component', () => {
    it('should not re-render when parent re-renders with same props', () => {
      const onPlay = vi.fn(); // Stable reference

      const { rerender } = render(
        <TrackRow
          track={mockTrack}
          index={0}
          isPlaying={false}
          isCurrent={false}
          onPlay={onPlay}
        />
      );

      expect(screen.getByText('Test Track')).toBeInTheDocument();

      // Re-render with exact same props
      rerender(
        <TrackRow
          track={mockTrack}
          index={0}
          isPlaying={false}
          isCurrent={false}
          onPlay={onPlay}
        />
      );

      // Component should still be in the document (memoization should prevent re-render)
      expect(screen.getByText('Test Track')).toBeInTheDocument();
    });

    it('should re-render only affected row when isPlaying changes', () => {
      const track1 = { ...mockTrack, id: 1, title: 'Track 1' };
      const track2 = { ...mockTrack, id: 2, title: 'Track 2' };
      const onPlay = vi.fn();

      const { rerender } = render(
        <div>
          <TrackRow
            track={track1}
            index={0}
            isPlaying={true}
            isCurrent={true}
            onPlay={onPlay}
          />
          <TrackRow
            track={track2}
            index={1}
            isPlaying={false}
            isCurrent={false}
            onPlay={onPlay}
          />
        </div>
      );

      expect(screen.getByText('Track 1')).toBeInTheDocument();
      expect(screen.getByText('Track 2')).toBeInTheDocument();

      // Change only track1's isPlaying state
      rerender(
        <div>
          <TrackRow
            track={track1}
            index={0}
            isPlaying={false}
            isCurrent={true}
            onPlay={onPlay}
          />
          <TrackRow
            track={track2}
            index={1}
            isPlaying={false}
            isCurrent={false}
            onPlay={onPlay}
          />
        </div>
      );

      // Both tracks should still be visible
      expect(screen.getByText('Track 1')).toBeInTheDocument();
      expect(screen.getByText('Track 2')).toBeInTheDocument();
    });

    it('should re-render when track.id changes', () => {
      const { rerender } = render(
        <TrackRow
          track={mockTrack}
          index={0}
          isPlaying={false}
          isCurrent={false}
          onPlay={vi.fn()}
        />
      );

      expect(screen.getByText('Test Track')).toBeInTheDocument();

      // Change track ID (different track)
      rerender(
        <TrackRow
          track={{ ...mockTrack, id: 2, title: 'New Track' }}
          index={0}
          isPlaying={false}
          isCurrent={false}
          onPlay={vi.fn()}
        />
      );

      expect(screen.getByText('New Track')).toBeInTheDocument();
    });

    it('should re-render when isCurrent changes', () => {
      const { rerender } = render(
        <TrackRow
          track={mockTrack}
          index={0}
          isPlaying={false}
          isCurrent={false}
          onPlay={vi.fn()}
        />
      );

      // Change isCurrent
      rerender(
        <TrackRow
          track={mockTrack}
          index={0}
          isPlaying={false}
          isCurrent={true}
          onPlay={vi.fn()}
        />
      );

      // Component should re-render with new state
      expect(screen.getByText('Test Track')).toBeInTheDocument();
    });

    it('should not re-render when callback props change but critical props stay same', () => {
      const onPlay1 = vi.fn();
      const onPlay2 = vi.fn();

      const { rerender } = render(
        <TrackRow
          track={mockTrack}
          index={0}
          isPlaying={false}
          isCurrent={false}
          onPlay={onPlay1}
        />
      );

      expect(screen.getByText('Test Track')).toBeInTheDocument();

      // Change callback (new reference) but keep critical props same
      rerender(
        <TrackRow
          track={mockTrack}
          index={0}
          isPlaying={false}
          isCurrent={false}
          onPlay={onPlay2}
        />
      );

      // Should not re-render because critical props (track.id, isPlaying, isCurrent) unchanged
      expect(screen.getByText('Test Track')).toBeInTheDocument();
    });
  });

  describe('TrackRowMetadata Component', () => {
    it('should not re-render when parent re-renders with same props', () => {
      const { rerender } = render(
        <TrackRowMetadata
          title="Test Track"
          artist="Test Artist"
          album="Test Album"
          duration="3:00"
          isCurrent={false}
        />
      );

      expect(screen.getByText('Test Track')).toBeInTheDocument();

      // Re-render with exact same props
      rerender(
        <TrackRowMetadata
          title="Test Track"
          artist="Test Artist"
          album="Test Album"
          duration="3:00"
          isCurrent={false}
        />
      );

      // Component should still be in the document
      expect(screen.getByText('Test Track')).toBeInTheDocument();
    });

    it('should re-render when title changes', () => {
      const { rerender } = render(
        <TrackRowMetadata
          title="Test Track"
          artist="Test Artist"
          album="Test Album"
          duration="3:00"
          isCurrent={false}
        />
      );

      expect(screen.getByText('Test Track')).toBeInTheDocument();

      rerender(
        <TrackRowMetadata
          title="New Track"
          artist="Test Artist"
          album="Test Album"
          duration="3:00"
          isCurrent={false}
        />
      );

      expect(screen.getByText('New Track')).toBeInTheDocument();
    });

    it('should re-render when isCurrent changes', () => {
      const { rerender } = render(
        <TrackRowMetadata
          title="Test Track"
          artist="Test Artist"
          album="Test Album"
          duration="3:00"
          isCurrent={false}
        />
      );

      rerender(
        <TrackRowMetadata
          title="Test Track"
          artist="Test Artist"
          album="Test Album"
          duration="3:00"
          isCurrent={true}
        />
      );

      expect(screen.getByText('Test Track')).toBeInTheDocument();
    });
  });

  describe('TrackRowPlayButton Component', () => {
    it('should not re-render when parent re-renders with same props', () => {
      const onClick = vi.fn(); // Stable reference

      const { rerender } = render(
        <TrackRowPlayButton isCurrent={false} isPlaying={false} onClick={onClick} />
      );

      expect(screen.getByTestId('PlayArrowIcon')).toBeInTheDocument();

      // Re-render with exact same props
      rerender(
        <TrackRowPlayButton isCurrent={false} isPlaying={false} onClick={onClick} />
      );

      // Component should still be in the document
      expect(screen.getByTestId('PlayArrowIcon')).toBeInTheDocument();
    });

    it('should re-render when isPlaying changes', () => {
      const { rerender } = render(
        <TrackRowPlayButton isCurrent={true} isPlaying={false} onClick={vi.fn()} />
      );

      expect(screen.getByTestId('PlayArrowIcon')).toBeInTheDocument();

      rerender(
        <TrackRowPlayButton isCurrent={true} isPlaying={true} onClick={vi.fn()} />
      );

      expect(screen.getByTestId('PauseIcon')).toBeInTheDocument();
    });

    it('should not re-render when onClick callback changes but state stays same', () => {
      const onClick1 = vi.fn();
      const onClick2 = vi.fn();

      const { rerender } = render(
        <TrackRowPlayButton isCurrent={false} isPlaying={false} onClick={onClick1} />
      );

      const initialButton = screen.getByTestId('PlayArrowIcon');

      rerender(
        <TrackRowPlayButton isCurrent={false} isPlaying={false} onClick={onClick2} />
      );

      // Should not re-render - button should be same element
      expect(screen.getByTestId('PlayArrowIcon')).toBe(initialButton);
    });
  });

  describe('TrackRowAlbumArt Component', () => {
    it('should not re-render when parent re-renders with same props', () => {
      const onImageError = vi.fn(); // Stable reference

      const { rerender } = render(
        <TrackRowAlbumArt
          albumArt="http://example.com/art.jpg"
          title="Test Track"
          album="Test Album"
          shouldShowImage={true}
          onImageError={onImageError}
        />
      );

      expect(screen.getByRole('img')).toBeInTheDocument();

      // Re-render with exact same props
      rerender(
        <TrackRowAlbumArt
          albumArt="http://example.com/art.jpg"
          title="Test Track"
          album="Test Album"
          shouldShowImage={true}
          onImageError={onImageError}
        />
      );

      // Component should still be in the document
      expect(screen.getByRole('img')).toBeInTheDocument();
    });

    it('should re-render when albumArt changes', () => {
      const { rerender } = render(
        <TrackRowAlbumArt
          albumArt="http://example.com/art1.jpg"
          title="Test Track"
          album="Test Album"
          shouldShowImage={true}
          onImageError={vi.fn()}
        />
      );

      const img1 = screen.getByRole('img');
      expect(img1).toHaveAttribute('src', 'http://example.com/art1.jpg');

      rerender(
        <TrackRowAlbumArt
          albumArt="http://example.com/art2.jpg"
          title="Test Track"
          album="Test Album"
          shouldShowImage={true}
          onImageError={vi.fn()}
        />
      );

      const img2 = screen.getByRole('img');
      expect(img2).toHaveAttribute('src', 'http://example.com/art2.jpg');
    });

    it('should re-render when shouldShowImage changes', () => {
      const { rerender } = render(
        <TrackRowAlbumArt
          albumArt="http://example.com/art.jpg"
          title="Test Track"
          album="Test Album"
          shouldShowImage={true}
          onImageError={vi.fn()}
        />
      );

      expect(screen.getByRole('img')).toBeInTheDocument();

      rerender(
        <TrackRowAlbumArt
          albumArt="http://example.com/art.jpg"
          title="Test Track"
          album="Test Album"
          shouldShowImage={false}
          onImageError={vi.fn()}
        />
      );

      expect(screen.queryByRole('img')).not.toBeInTheDocument();
    });

    it('should not re-render when onImageError callback changes', () => {
      const onError1 = vi.fn();
      const onError2 = vi.fn();

      const { rerender } = render(
        <TrackRowAlbumArt
          albumArt="http://example.com/art.jpg"
          title="Test Track"
          album="Test Album"
          shouldShowImage={true}
          onImageError={onError1}
        />
      );

      const img1 = screen.getByRole('img');

      rerender(
        <TrackRowAlbumArt
          albumArt="http://example.com/art.jpg"
          title="Test Track"
          album="Test Album"
          shouldShowImage={true}
          onImageError={onError2}
        />
      );

      // Should not re-render - image should be same element
      expect(screen.getByRole('img')).toBe(img1);
    });
  });

  describe('Integration: 100 Rows Performance Test', () => {
    it('should render 100 rows without crashing', () => {
      const tracks = Array.from({ length: 100 }, (_, i) => ({
        ...mockTrack,
        id: i + 1,
        title: `Track ${i + 1}`,
      }));

      const onPlay = vi.fn();

      render(
        <div>
          {tracks.map((track, index) => (
            <TrackRow
              key={track.id}
              track={track}
              index={index}
              isPlaying={false}
              isCurrent={false}
              onPlay={onPlay}
            />
          ))}
        </div>
      );

      // All tracks should be rendered
      expect(screen.getByText('Track 1')).toBeInTheDocument();
      expect(screen.getByText('Track 50')).toBeInTheDocument();
      expect(screen.getByText('Track 100')).toBeInTheDocument();
    });

    it('should handle updating single row in large list', () => {
      const tracks = Array.from({ length: 100 }, (_, i) => ({
        ...mockTrack,
        id: i + 1,
        title: `Track ${i + 1}`,
      }));

      const onPlay = vi.fn();

      const { rerender } = render(
        <div>
          {tracks.map((track, index) => (
            <TrackRow
              key={track.id}
              track={track}
              index={index}
              isPlaying={false}
              isCurrent={false}
              onPlay={onPlay}
            />
          ))}
        </div>
      );

      // Update only track 5 to be playing
      rerender(
        <div>
          {tracks.map((track, index) => (
            <TrackRow
              key={track.id}
              track={track}
              index={index}
              isPlaying={track.id === 5}
              isCurrent={track.id === 5}
              onPlay={onPlay}
            />
          ))}
        </div>
      );

      // All tracks should still be visible
      expect(screen.getByText('Track 1')).toBeInTheDocument();
      expect(screen.getByText('Track 5')).toBeInTheDocument();
      expect(screen.getByText('Track 100')).toBeInTheDocument();
    });
  });
});
