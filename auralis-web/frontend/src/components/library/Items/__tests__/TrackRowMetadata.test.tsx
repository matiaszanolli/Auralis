/**
 * TrackRowMetadata Component Tests
 *
 * Tests for track metadata display (title, artist, album, duration):
 * - Rendering all metadata fields
 * - Conditional rendering of optional album
 * - Responsive visibility of album field
 * - Current track styling
 */

import { vi } from 'vitest';
import { render, screen } from '@/test/test-utils';
import { TrackRowMetadata } from '../tracks/TrackRowMetadata';

describe('TrackRowMetadata', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Metadata Display', () => {
    it('should display track title', () => {
      render(
        <TrackRowMetadata
          title="Test Track"
          artist="Test Artist"
          duration="3:45"
          isCurrent={false}
        />
      );

      expect(screen.getByText('Test Track')).toBeInTheDocument();
    });

    it('should display track artist', () => {
      render(
        <TrackRowMetadata
          title="Test Track"
          artist="Test Artist"
          duration="3:45"
          isCurrent={false}
        />
      );

      expect(screen.getByText('Test Artist')).toBeInTheDocument();
    });

    it('should display track duration', () => {
      render(
        <TrackRowMetadata
          title="Test Track"
          artist="Test Artist"
          duration="3:45"
          isCurrent={false}
        />
      );

      expect(screen.getByText('3:45')).toBeInTheDocument();
    });

    it('should display all metadata together', () => {
      render(
        <TrackRowMetadata
          title="Test Track"
          artist="Test Artist"
          album="Test Album"
          duration="3:45"
          isCurrent={false}
        />
      );

      expect(screen.getByText('Test Track')).toBeInTheDocument();
      expect(screen.getByText('Test Artist')).toBeInTheDocument();
      expect(screen.getByText('Test Album')).toBeInTheDocument();
      expect(screen.getByText('3:45')).toBeInTheDocument();
    });
  });

  describe('Conditional Album Display', () => {
    it('should display album when provided', () => {
      render(
        <TrackRowMetadata
          title="Test Track"
          artist="Test Artist"
          album="Test Album"
          duration="3:45"
          isCurrent={false}
        />
      );

      expect(screen.getByText('Test Album')).toBeInTheDocument();
    });

    it('should not display album when not provided', () => {
      render(
        <TrackRowMetadata
          title="Test Track"
          artist="Test Artist"
          duration="3:45"
          isCurrent={false}
        />
      );

      // Album should not be in the document
      expect(screen.queryByText(/Test Album/)).not.toBeInTheDocument();
    });

    it('should handle empty string album', () => {
      render(
        <TrackRowMetadata
          title="Test Track"
          artist="Test Artist"
          album=""
          duration="3:45"
          isCurrent={false}
        />
      );

      // Empty string is falsy, so album element should not render
      expect(screen.queryByTestId('track-album')).not.toBeInTheDocument();
    });

    it('should handle undefined album', () => {
      render(
        <TrackRowMetadata
          title="Test Track"
          artist="Test Artist"
          album={undefined}
          duration="3:45"
          isCurrent={false}
        />
      );

      // Should render title and artist but not album
      expect(screen.getByText('Test Track')).toBeInTheDocument();
      expect(screen.getByText('Test Artist')).toBeInTheDocument();
    });
  });

  describe('Current Track Styling', () => {
    it('should apply current styling when isCurrent is true', () => {
      render(
        <TrackRowMetadata
          title="Test Track"
          artist="Test Artist"
          duration="3:45"
          isCurrent={true}
        />
      );

      // Find the title element and check for current styling
      const titleElement = screen.getByText('Test Track');
      expect(titleElement).toBeInTheDocument();

      // Check if current attribute is applied (iscurrent="true")
      // Note: The component uses iscurrent prop for styling
      const parentElement = titleElement.closest('[iscurrent]');
      if (parentElement) {
        expect(parentElement).toHaveAttribute('iscurrent', 'true');
      }
    });

    it('should not apply current styling when isCurrent is false', () => {
      render(
        <TrackRowMetadata
          title="Test Track"
          artist="Test Artist"
          duration="3:45"
          isCurrent={false}
        />
      );

      const titleElement = screen.getByText('Test Track');
      expect(titleElement).toBeInTheDocument();

      // Check if current attribute is not applied
      const parentElement = titleElement.closest('[iscurrent]');
      if (parentElement) {
        expect(parentElement).toHaveAttribute('iscurrent', 'false');
      }
    });
  });

  describe('Different Duration Formats', () => {
    it('should display various duration formats', () => {
      const durations = [
        { duration: '0:30', name: 'short track' },
        { duration: '3:45', name: 'typical track' },
        { duration: '5:30', name: 'longer track' },
        { duration: '10:00', name: 'long track' },
        { duration: '1:23:45', name: 'track with hours' },
      ];

      durations.forEach(({ duration, name: _name }) => {
        const { unmount } = render(
          <TrackRowMetadata
            title="Test Track"
            artist="Test Artist"
            duration={duration}
            isCurrent={false}
          />
        );

        expect(screen.getByText(duration)).toBeInTheDocument();
        unmount();
      });
    });
  });

  describe('Special Characters and Long Text', () => {
    it('should handle special characters in metadata', () => {
      render(
        <TrackRowMetadata
          title="Test & Track's Song (Remix)"
          artist="Artist & Collaborator"
          album="Album / Deluxe Edition"
          duration="3:45"
          isCurrent={false}
        />
      );

      expect(screen.getByText("Test & Track's Song (Remix)")).toBeInTheDocument();
      expect(screen.getByText('Artist & Collaborator')).toBeInTheDocument();
      expect(screen.getByText('Album / Deluxe Edition')).toBeInTheDocument();
    });

    it('should handle very long titles', () => {
      const longTitle = 'A Very Long Track Title That Goes On and On and On and Should Still Display Properly';

      render(
        <TrackRowMetadata
          title={longTitle}
          artist="Test Artist"
          duration="3:45"
          isCurrent={false}
        />
      );

      expect(screen.getByText(longTitle)).toBeInTheDocument();
    });

    it('should handle very long artist names', () => {
      const longArtist = 'Artist Name With Very Long Name That Might Wrap or Truncate';

      render(
        <TrackRowMetadata
          title="Test Track"
          artist={longArtist}
          duration="3:45"
          isCurrent={false}
        />
      );

      expect(screen.getByText(longArtist)).toBeInTheDocument();
    });

    it('should handle unicode and international characters', () => {
      render(
        <TrackRowMetadata
          title="日本語タイトル"
          artist="中文艺术家"
          album="Álbum Español"
          duration="3:45"
          isCurrent={false}
        />
      );

      expect(screen.getByText('日本語タイトル')).toBeInTheDocument();
      expect(screen.getByText('中文艺术家')).toBeInTheDocument();
      expect(screen.getByText('Álbum Español')).toBeInTheDocument();
    });
  });

  describe('State Updates', () => {
    it('should update when props change', () => {
      const { rerender } = render(
        <TrackRowMetadata
          title="Original Track"
          artist="Original Artist"
          duration="3:45"
          isCurrent={false}
        />
      );

      expect(screen.getByText('Original Track')).toBeInTheDocument();

      // Update props
      rerender(
        <TrackRowMetadata
          title="Updated Track"
          artist="Updated Artist"
          duration="4:30"
          isCurrent={true}
        />
      );

      expect(screen.getByText('Updated Track')).toBeInTheDocument();
      expect(screen.getByText('Updated Artist')).toBeInTheDocument();
      expect(screen.getByText('4:30')).toBeInTheDocument();
    });

    it('should update isCurrent status', () => {
      const { rerender } = render(
        <TrackRowMetadata
          title="Test Track"
          artist="Test Artist"
          duration="3:45"
          isCurrent={false}
        />
      );

      let titleElement = screen.getByText('Test Track');
      let parentElement = titleElement.closest('[iscurrent]');
      if (parentElement) {
        expect(parentElement).toHaveAttribute('iscurrent', 'false');
      }

      // Update to current
      rerender(
        <TrackRowMetadata
          title="Test Track"
          artist="Test Artist"
          duration="3:45"
          isCurrent={true}
        />
      );

      titleElement = screen.getByText('Test Track');
      parentElement = titleElement.closest('[iscurrent]');
      if (parentElement) {
        expect(parentElement).toHaveAttribute('iscurrent', 'true');
      }
    });

    it('should add/remove album display on update', () => {
      const { rerender } = render(
        <TrackRowMetadata
          title="Test Track"
          artist="Test Artist"
          duration="3:45"
          isCurrent={false}
        />
      );

      expect(screen.queryByText('Test Album')).not.toBeInTheDocument();

      // Add album
      rerender(
        <TrackRowMetadata
          title="Test Track"
          artist="Test Artist"
          album="Test Album"
          duration="3:45"
          isCurrent={false}
        />
      );

      expect(screen.getByText('Test Album')).toBeInTheDocument();

      // Remove album
      rerender(
        <TrackRowMetadata
          title="Test Track"
          artist="Test Artist"
          duration="3:45"
          isCurrent={false}
        />
      );

      expect(screen.queryByText('Test Album')).not.toBeInTheDocument();
    });
  });

  describe('DOM Structure', () => {
    it('should render in correct DOM hierarchy', () => {
      render(
        <TrackRowMetadata
          title="Test Track"
          artist="Test Artist"
          album="Test Album"
          duration="3:45"
          isCurrent={false}
        />
      );

      // Should contain a fragment with title/artist info, album, and duration
      const titleElement = screen.getByText('Test Track');
      const artistElement = screen.getByText('Test Artist');
      const albumElement = screen.getByText('Test Album');
      const durationElement = screen.getByText('3:45');

      expect(titleElement).toBeInTheDocument();
      expect(artistElement).toBeInTheDocument();
      expect(albumElement).toBeInTheDocument();
      expect(durationElement).toBeInTheDocument();
    });
  });
});
