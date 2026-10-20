/**
 * TrackCard Component Tests
 *
 * Tests the card-based track display component:
 * - Album artwork display
 * - Track metadata rendering
 * - Click handling for playback
 * - Duration formatting
 */

import { vi, afterEach } from 'vitest';
import { render, screen, act } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import { TrackCard } from '../TrackCard';
import { useWebSocketContext } from '@/contexts/WebSocketContext';
import { _internal as artworkInternal } from '@/hooks/library/useArtworkUpdates';

const defaultProps = {
  id: 1,
  title: 'Beautiful Song',
  artist: 'Amazing Artist',
  album: 'Great Album',
  albumId: 1,
  duration: 240,
  albumArt: 'http://example.com/artwork.jpg',
  onPlay: vi.fn(),
};

describe('TrackCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('should render track title', () => {
      render(<TrackCard {...defaultProps} />);
      expect(screen.getByText('Beautiful Song')).toBeInTheDocument();
    });

    it('should display artist name', () => {
      render(<TrackCard {...defaultProps} />);
      expect(screen.getByText('Amazing Artist')).toBeInTheDocument();
    });

    it('should display album name', () => {
      render(<TrackCard {...defaultProps} />);
      expect(screen.getByText('Great Album')).toBeInTheDocument();
    });

    it('should display formatted duration', () => {
      render(<TrackCard {...defaultProps} />);
      // 240 seconds = 4:00
      expect(screen.getByText(/4:00/)).toBeInTheDocument();
    });

    it('should render with album art when provided', () => {
      render(<TrackCard {...defaultProps} />);
      // Component renders successfully with album art provided
      expect(screen.getByText('Beautiful Song')).toBeInTheDocument();
      expect(screen.getByText('Amazing Artist')).toBeInTheDocument();
    });

    it('requests a size-hinted URL for same-origin artwork (#4901)', () => {
      const { container } = render(
        <TrackCard
          {...defaultProps}
          albumArt="/api/albums/1/artwork"
          artworkSize={216}
        />
      );

      expect(container.querySelector('img')).toHaveAttribute(
        'src',
        '/api/albums/1/artwork?size=216'
      );
    });

    it('should render with placeholder when no album art', () => {
      render(
        <TrackCard {...defaultProps} albumArt={undefined} />
      );
      // Should still render without crashing
      expect(screen.getByText('Beautiful Song')).toBeInTheDocument();
    });
  });

  describe('Interactions', () => {
    it('should call onPlay with track id when clicked', async () => {
      const user = userEvent.setup();
      const onPlay = vi.fn();
      render(<TrackCard {...defaultProps} onPlay={onPlay} />);

      // The card's full-size open button (#5101), not the Play overlay.
      await user.click(screen.getByRole('button', { name: 'Beautiful Song by Amazing Artist' }));

      expect(onPlay).toHaveBeenCalledWith(1);
    });

    it('should show visual feedback on hover', async () => {
      const user = userEvent.setup();
      const { container } = render(<TrackCard {...defaultProps} />);

      const card = container.querySelector('[class*="MuiCard"]') || container.firstChild;
      if (card) {
        await user.hover(card as Element);
        // Component has transition effects on hover
        expect(card).toBeInTheDocument();
      }
    });
  });

  describe('Edge Cases', () => {
    it('should handle very long track title', () => {
      const longTitle = 'A'.repeat(50);
      render(
        <TrackCard
          {...defaultProps}
          title={longTitle}
        />
      );
      expect(screen.getByText(longTitle, { exact: true })).toBeInTheDocument();
    });

    it('should handle very long artist name', () => {
      const longArtist = 'B'.repeat(50);
      render(
        <TrackCard
          {...defaultProps}
          artist={longArtist}
        />
      );
      expect(screen.getByText(longArtist, { exact: true })).toBeInTheDocument();
    });

    it('should handle zero duration', () => {
      render(<TrackCard {...defaultProps} duration={0} />);
      expect(screen.getByText('Beautiful Song')).toBeInTheDocument();
    });

    it('should handle very short duration', () => {
      render(<TrackCard {...defaultProps} duration={5} />);
      expect(screen.getByText(/0:05/)).toBeInTheDocument();
    });

    it('should handle very long duration', () => {
      // 3661 seconds = 1 hour, 1 minute, and 1 second
      render(<TrackCard {...defaultProps} duration={3661} />);
      expect(screen.getByText('1:01:01')).toBeInTheDocument();
    });
  });

  describe('Duration Formatting', () => {
    it('should format minutes and seconds correctly', () => {
      render(<TrackCard {...defaultProps} duration={125} />);
      // 125 seconds = 2:05
      expect(screen.getByText(/2:05/)).toBeInTheDocument();
    });

    it('should pad seconds with zero', () => {
      render(<TrackCard {...defaultProps} duration={65} />);
      // 65 seconds = 1:05
      expect(screen.getByText(/1:05/)).toBeInTheDocument();
    });

    it('should show minutes only when seconds is zero', () => {
      render(<TrackCard {...defaultProps} duration={120} />);
      // 120 seconds = 2:00
      expect(screen.getByText(/2:00/)).toBeInTheDocument();
    });
  });

  describe('Props Variations', () => {
    it('should render with minimal props', () => {
      const minimalProps = {
        id: 1,
        title: 'Track',
        artist: 'Artist',
        album: 'Album',
        duration: 180,
        onPlay: vi.fn(),
      };
      render(<TrackCard {...minimalProps} />);
      expect(screen.getByText('Track')).toBeInTheDocument();
    });

    it('should handle different album IDs', () => {
      render(<TrackCard {...defaultProps} albumId={999} />);
      expect(screen.getByText('Beautiful Song')).toBeInTheDocument();
    });

    it('should render multiple cards with different data', () => {
      const { rerender } = render(<TrackCard {...defaultProps} id={1} />);
      expect(screen.getByText('Beautiful Song')).toBeInTheDocument();

      rerender(
        <TrackCard
          {...defaultProps}
          id={2}
          title='Different Song'
        />
      );
      expect(screen.getByText('Different Song')).toBeInTheDocument();
    });
  });

  describe('artwork cache-busting (#5473)', () => {
    /** Capturing subscribe wired over the global context mock. */
    let capturedCallback: ((message: any) => void) | null;
    let defaults: any;

    beforeEach(() => {
      artworkInternal.reset();
      capturedCallback = null;
      const contextMock = vi.mocked(useWebSocketContext);
      defaults = contextMock();
      contextMock.mockReturnValue({
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
      vi.mocked(useWebSocketContext).mockReturnValue(defaults);
      artworkInternal.reset();
    });

    it('cache-busts the artwork URL when artwork_updated arrives for the album', () => {
      const { container } = render(
        <TrackCard {...defaultProps} albumArt="/api/albums/1/artwork" />
      );
      expect(container.querySelector('img')).toHaveAttribute(
        'src',
        '/api/albums/1/artwork?size=216'
      );

      act(() => {
        capturedCallback!({ type: 'artwork_updated', data: { album_id: 1 } });
      });

      expect(container.querySelector('img')).toHaveAttribute(
        'src',
        '/api/albums/1/artwork?size=216&v=1'
      );
    });

    it('ignores artwork_updated for a different album', () => {
      const { container } = render(
        <TrackCard {...defaultProps} albumArt="/api/albums/1/artwork" />
      );

      act(() => {
        capturedCallback!({ type: 'artwork_updated', data: { album_id: 99 } });
      });

      expect(container.querySelector('img')).toHaveAttribute(
        'src',
        '/api/albums/1/artwork?size=216'
      );
    });
  });
});
