/**
 * TrackRow artwork cache-busting tests (#5473)
 *
 * A mounted row must re-fetch its artwork when an `artwork_updated` broadcast
 * arrives for the track's album — the same mechanism AlbumArt/AlbumCard use —
 * instead of showing the stale (or deleted) image until an unrelated refetch.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, act } from '@/test/test-utils';
import TrackRow from '../TrackRow';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import { _internal as artworkInternal } from '@/hooks/library/useArtworkUpdates';

// Mock hooks and components to reduce noise (same isolation as
// TrackRowMemoization.test.tsx).
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
  albumId: 7,
  duration: 180,
  artworkUrl: '/api/albums/7/artwork',
};

describe('TrackRow artwork cache-busting (#5473)', () => {
  let capturedCallback: ((message: any) => void) | null;

  beforeEach(() => {
    artworkInternal.reset();
    capturedCallback = null;
    const defaults = vi.mocked(useWebSocketContext)() as any;
    vi.mocked(useWebSocketContext).mockReturnValue({
      ...defaults,
      // The provider tree subscribes to several message types; capture only
      // the artwork_updated handler so broadcasts reach the right one.
      subscribe: vi.fn((type: string, handler: (message: any) => void) => {
        if (type === 'artwork_updated') capturedCallback = handler;
        return () => undefined;
      }),
    });
  });

  afterEach(() => {
    artworkInternal.reset();
  });

  it('requests the size-hinted URL at revision 0 initially', () => {
    const { container } = render(<TrackRow track={mockTrack} index={0} onPlay={vi.fn()} />);

    expect(container.querySelector('img')).toHaveAttribute(
      'src',
      '/api/albums/7/artwork?size=80'
    );
  });

  it('cache-busts the row artwork when artwork_updated arrives for its album', () => {
    const { container } = render(<TrackRow track={mockTrack} index={0} onPlay={vi.fn()} />);

    act(() => {
      capturedCallback!({ type: 'artwork_updated', data: { album_id: 7 } });
    });

    expect(container.querySelector('img')).toHaveAttribute(
      'src',
      '/api/albums/7/artwork?size=80&v=1'
    );
  });

  it('ignores artwork_updated for a different album', () => {
    const { container } = render(<TrackRow track={mockTrack} index={0} onPlay={vi.fn()} />);

    act(() => {
      capturedCallback!({ type: 'artwork_updated', data: { album_id: 99 } });
    });

    expect(container.querySelector('img')).toHaveAttribute(
      'src',
      '/api/albums/7/artwork?size=80'
    );
  });
});
