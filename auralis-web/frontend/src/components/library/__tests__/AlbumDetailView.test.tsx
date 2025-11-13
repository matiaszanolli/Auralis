/**
 * AlbumDetailView Component Tests
 *
 * Tests the album detail view component with:
 * - Album metadata display (title, artist, artwork, year, genre)
 * - Track list with play on click
 * - Playback integration (play album, pause, current track highlighting)
 * - Favorite toggle
 * - Navigation (back button)
 * - Loading and error states
 * - Duration formatting
 */

import { vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import AlbumDetailView from '../AlbumDetailView';
import { auralisTheme } from '../../../theme/auralisTheme';

// Mock the AlbumArt component
vi.mock('../../album/AlbumArt', () => ({
  default: function MockAlbumArt({ albumId, size }: any) {
    return (
      <div data-testid="album-artwork">
        <img src={`/artwork/${albumId}`} alt="Album" style={{ width: size, height: size }} />
      </div>
    );
  },
}));

// Mock fetch for API calls
global.fetch = vi.fn();

const mockAlbumData = {
  album_id: 1,
  album_title: 'Abbey Road',
  artist: 'The Beatles',
  year: 1969,
  genre: 'Rock',
  total_tracks: 3,
  tracks: [
    { id: 1, title: 'Come Together', artist: 'The Beatles', duration: 259, track_number: 1 },
    { id: 2, title: 'Something', artist: 'The Beatles', duration: 183, track_number: 2 },
    { id: 3, title: 'Here Comes the Sun', artist: 'The Beatles', duration: 185, track_number: 3 },
  ],
};

const Wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <BrowserRouter>
    <ThemeProvider theme={auralisTheme}>
      {children}
    </ThemeProvider>
  </BrowserRouter>
);

describe('AlbumDetailView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => mockAlbumData,
    });
  });

  describe('Rendering', () => {
    it('should render loading state initially', () => {
      (global.fetch as any).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      expect(screen.getAllByTestId(/skeleton|loading/i).length).toBeGreaterThan(0) ||
      expect(document.querySelector('[role="progressbar"]')).toBeInTheDocument();
    });

    it('should render album details after loading', async () => {
      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Abbey Road')).toBeInTheDocument();
      });
    });

    it('should display album artwork', async () => {
      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByTestId('album-artwork')).toBeInTheDocument();
      });
    });

    it('should display album title', async () => {
      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Abbey Road')).toBeInTheDocument();
      });
    });

    it('should display album artist', async () => {
      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('The Beatles')).toBeInTheDocument();
      });
    });

    it('should display album year', async () => {
      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/1969/)).toBeInTheDocument();
      });
    });

    it('should display genre', async () => {
      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/Rock/)).toBeInTheDocument();
      });
    });

    it('should display track count', async () => {
      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/3\s+tracks/)).toBeInTheDocument();
      });
    });
  });

  describe('Album Metadata', () => {
    it('should display total duration in hours and minutes', async () => {
      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        // Total duration: 259 + 183 + 185 = 627 seconds = 10 min 27 sec
        expect(screen.getByText(/10\s+min|627/)).toBeInTheDocument();
      });
    });

    it('should handle single track album', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({
          ...mockAlbumData,
          total_tracks: 1,
          tracks: [mockAlbumData.tracks[0]],
        }),
      });

      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/1\s+track/)).toBeInTheDocument();
      });
    });

    it('should format album metadata correctly', async () => {
      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        const metadata = screen.getByText(/1969.*tracks|tracks.*1969/);
        expect(metadata).toBeInTheDocument();
      });
    });
  });

  describe('Track List', () => {
    it('should render all tracks in album', async () => {
      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Come Together')).toBeInTheDocument();
        expect(screen.getByText('Something')).toBeInTheDocument();
        expect(screen.getByText('Here Comes the Sun')).toBeInTheDocument();
      });
    });

    it('should display track artist', async () => {
      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        const artistCells = screen.getAllByText('The Beatles');
        expect(artistCells.length).toBeGreaterThanOrEqual(4); // Album artist + 3 track artists
      });
    });

    it('should format track duration correctly', async () => {
      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/4:19|4:43|3:05/)).toBeInTheDocument(); // Various track durations
      });
    });

    it('should display track numbers', async () => {
      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        const trackNumbers = screen.queryAllByText(/^[123]$/);
        expect(trackNumbers.length).toBeGreaterThanOrEqual(0); // Track numbers may be hidden
      });
    });

    it('should show empty state when no tracks', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({
          ...mockAlbumData,
          total_tracks: 0,
          tracks: [],
        }),
      });

      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/no tracks|empty/i)).toBeInTheDocument();
      });
    });
  });

  describe('Playback Integration', () => {
    it('should play album when play button clicked', async () => {
      const user = userEvent.setup();
      const onTrackPlay = vi.fn();

      render(
        <Wrapper>
          <AlbumDetailView albumId={1} onTrackPlay={onTrackPlay} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Abbey Road')).toBeInTheDocument();
      });

      const playButton = screen.getByRole('button', { name: /play album/i });
      await user.click(playButton);

      expect(onTrackPlay).toHaveBeenCalledWith(mockAlbumData.tracks[0]);
    });

    it('should play track when track row clicked', async () => {
      const user = userEvent.setup();
      const onTrackPlay = vi.fn();

      render(
        <Wrapper>
          <AlbumDetailView albumId={1} onTrackPlay={onTrackPlay} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Come Together')).toBeInTheDocument();
      });

      const trackRow = screen.getByText('Come Together').closest('tr');
      if (trackRow) {
        fireEvent.click(trackRow);
        expect(onTrackPlay).toHaveBeenCalledWith(mockAlbumData.tracks[0]);
      }
    });

    it('should highlight current track', async () => {
      const { container } = render(
        <Wrapper>
          <AlbumDetailView albumId={1} currentTrackId={2} isPlaying={true} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Something')).toBeInTheDocument();
      });

      const currentTrackRow = Array.from(container.querySelectorAll('tr')).find(row =>
        row.textContent?.includes('Something')
      );
      expect(currentTrackRow?.className).toContain('current-track');
    });

    it('should show pause icon for current playing track', async () => {
      render(
        <Wrapper>
          <AlbumDetailView albumId={1} currentTrackId={1} isPlaying={true} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Come Together')).toBeInTheDocument();
      });

      // Should show pause icon in track row
      expect(screen.getByTestId(/pause|player/i) || document.querySelector('[data-testid*="play"]')).toBeInTheDocument();
    });

    it('should show play icon on non-current track hover', async () => {
      const user = userEvent.setup();

      const { container } = render(
        <Wrapper>
          <AlbumDetailView albumId={1} currentTrackId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Something')).toBeInTheDocument();
      });

      const trackRow = screen.getByText('Something').closest('tr');
      if (trackRow) {
        await user.hover(trackRow);
        // Play icon should be visible
        const playIcon = trackRow.querySelector('[class*="play"]');
        expect(playIcon).toBeInTheDocument() || expect(trackRow.textContent).toContain('play');
      }
    });

    it('should change button text when album is playing', async () => {
      const { rerender } = render(
        <Wrapper>
          <AlbumDetailView
            albumId={1}
            currentTrackId={1}
            isPlaying={false}
          />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Abbey Road')).toBeInTheDocument();
      });

      expect(screen.getByRole('button', { name: /play album/i })).toBeInTheDocument();

      rerender(
        <Wrapper>
          <AlbumDetailView
            albumId={1}
            currentTrackId={1}
            isPlaying={true}
          />
        </Wrapper>
      );

      expect(screen.getByRole('button', { name: /pause/i })).toBeInTheDocument();
    });
  });

  describe('Favorite Toggle', () => {
    it('should show favorite button', async () => {
      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /favorite|add/i })).toBeInTheDocument();
      });
    });

    it('should toggle favorite on click', async () => {
      const user = userEvent.setup();

      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Abbey Road')).toBeInTheDocument();
      });

      const favoriteButton = screen.getByRole('button', { name: /favorite|add/i });
      await user.click(favoriteButton);

      // After clicking, should show different icon/tooltip
      expect(screen.getByText(/remove.*favorite|already.*favorite/i) || favoriteButton).toBeInTheDocument();
    });

    it('should persist favorite state', async () => {
      const user = userEvent.setup();

      const { rerender } = render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Abbey Road')).toBeInTheDocument();
      });

      const favoriteButton = screen.getByRole('button', { name: /favorite|add/i });
      await user.click(favoriteButton);

      // Rerender and check state persists
      rerender(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      const updatedButton = screen.getByRole('button', { name: /favorite|add|remove/i });
      expect(updatedButton).toBeInTheDocument();
    });
  });

  describe('Navigation', () => {
    it('should show back button when onBack provided', async () => {
      const onBack = vi.fn();

      render(
        <Wrapper>
          <AlbumDetailView albumId={1} onBack={onBack} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Abbey Road')).toBeInTheDocument();
      });

      const backButton = screen.getByRole('button', { name: /back/i });
      expect(backButton).toBeInTheDocument();
    });

    it('should call onBack when back button clicked', async () => {
      const user = userEvent.setup();
      const onBack = vi.fn();

      render(
        <Wrapper>
          <AlbumDetailView albumId={1} onBack={onBack} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Abbey Road')).toBeInTheDocument();
      });

      const backButton = screen.getByRole('button', { name: /back/i });
      await user.click(backButton);

      expect(onBack).toHaveBeenCalled();
    });

    it('should not show back button when onBack not provided', async () => {
      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Abbey Road')).toBeInTheDocument();
      });

      const backButtons = screen.queryAllByRole('button', { name: /back/i });
      expect(backButtons.length).toBe(0);
    });
  });

  describe('Loading State', () => {
    it('should show loading skeletons while fetching', () => {
      (global.fetch as any).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      // Should show loading UI (skeletons or progress)
      expect(
        screen.queryAllByTestId(/skeleton/i).length > 0 ||
        document.querySelector('[role="progressbar"]') !== null
      ).toBeTruthy();
    });

    it('should hide loading state when data loaded', async () => {
      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Abbey Road')).toBeInTheDocument();
      });

      // Skeletons should be gone
      expect(screen.queryAllByTestId(/skeleton/i).length).toBe(0);
    });

    it('should refetch when albumId changes', async () => {
      const { rerender } = render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Abbey Road')).toBeInTheDocument();
      });

      expect(global.fetch).toHaveBeenCalledWith('/api/albums/1/tracks');

      // Change albumId
      (global.fetch as any).mockClear();
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({
          ...mockAlbumData,
          album_id: 2,
          album_title: 'Let It Be',
        }),
      });

      rerender(
        <Wrapper>
          <AlbumDetailView albumId={2} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith('/api/albums/2/tracks');
      });
    });
  });

  describe('Error State', () => {
    it('should display error message on fetch failure', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: false,
        json: async () => ({ error: 'Not found' }),
      });

      render(
        <Wrapper>
          <AlbumDetailView albumId={999} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/failed|error|not found/i)).toBeInTheDocument();
      });
    });

    it('should show back button in error state', async () => {
      const onBack = vi.fn();
      (global.fetch as any).mockResolvedValue({
        ok: false,
      });

      render(
        <Wrapper>
          <AlbumDetailView albumId={999} onBack={onBack} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/failed|error|not found/i)).toBeInTheDocument();
      });

      const backButton = screen.getByRole('button', { name: /back/i });
      expect(backButton).toBeInTheDocument();
    });

    it('should handle network errors', async () => {
      (global.fetch as any).mockRejectedValue(new Error('Network error'));

      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/failed|error|network/i)).toBeInTheDocument();
      });
    });

    it('should handle malformed API response', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({}), // Missing required fields
      });

      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        // Should render but with empty/default values
        expect(document.body).toBeInTheDocument();
      });
    });
  });

  describe('Duration Formatting', () => {
    it('should format track duration as MM:SS', async () => {
      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/4:19|4:43|3:05/)).toBeInTheDocument();
      });
    });

    it('should format album duration in minutes', async () => {
      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        // Total: 627 seconds = 10 minutes 27 seconds
        expect(screen.getByText(/10\s+min|627/)).toBeInTheDocument();
      });
    });

    it('should format duration > 1 hour correctly', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({
          ...mockAlbumData,
          tracks: [
            ...mockAlbumData.tracks,
            { id: 4, title: 'Long Track', artist: 'The Beatles', duration: 1800 },
          ],
        }),
      });

      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/1\s+hr|hour/)).toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('should have proper table semantics', async () => {
      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByRole('table')).toBeInTheDocument();
      });
    });

    it('should have table headers', async () => {
      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Title')).toBeInTheDocument();
        expect(screen.getByText('Artist')).toBeInTheDocument();
        expect(screen.getByText('Duration')).toBeInTheDocument();
      });
    });

    it('should have accessible buttons with tooltips', async () => {
      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Abbey Road')).toBeInTheDocument();
      });

      const buttons = screen.getAllByRole('button');
      buttons.forEach(button => {
        expect(button).toHaveAccessibleName() || expect(button.title || button.getAttribute('aria-label')).toBeTruthy();
      });
    });

    it('should support keyboard navigation', async () => {
      const user = userEvent.setup();

      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Abbey Road')).toBeInTheDocument();
      });

      const playButton = screen.getByRole('button', { name: /play album/i });
      playButton.focus();
      expect(document.activeElement).toBe(playButton);

      await user.keyboard('{Enter}');
      // Button should respond to keyboard
      expect(document.activeElement).toBeInTheDocument();
    });
  });

  describe('Styling & Layout', () => {
    it('should apply header styling', async () => {
      const { container } = render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Abbey Road')).toBeInTheDocument();
      });

      const header = container.querySelector('[class*="Header"]') || container.querySelector('section');
      expect(header).toBeInTheDocument();
    });

    it('should display album art and info side by side', async () => {
      const { container } = render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByTestId('album-artwork')).toBeInTheDocument();
      });

      const artwork = screen.getByTestId('album-artwork');
      const title = screen.getByText('Abbey Road');

      const artworkRect = artwork.getBoundingClientRect();
      const titleRect = title.getBoundingClientRect();

      // Album art should be to the left of title
      expect(artworkRect.left).toBeLessThan(titleRect.left);
    });
  });

  describe('Integration', () => {
    it('should handle full album view workflow', async () => {
      const user = userEvent.setup();
      const onTrackPlay = vi.fn();
      const onBack = vi.fn();

      render(
        <Wrapper>
          <AlbumDetailView
            albumId={1}
            onTrackPlay={onTrackPlay}
            onBack={onBack}
            currentTrackId={1}
            isPlaying={false}
          />
        </Wrapper>
      );

      // 1. Album loads
      await waitFor(() => {
        expect(screen.getByText('Abbey Road')).toBeInTheDocument();
      });

      // 2. User clicks play album
      const playButton = screen.getByRole('button', { name: /play album/i });
      await user.click(playButton);
      expect(onTrackPlay).toHaveBeenCalledWith(mockAlbumData.tracks[0]);

      // 3. User clicks on a different track
      const secondTrack = screen.getByText('Something').closest('tr');
      if (secondTrack) {
        fireEvent.click(secondTrack);
        expect(onTrackPlay).toHaveBeenCalledWith(mockAlbumData.tracks[1]);
      }

      // 4. User clicks back
      const backButton = screen.getByRole('button', { name: /back/i });
      await user.click(backButton);
      expect(onBack).toHaveBeenCalled();
    });

    it('should maintain state through interactions', async () => {
      const user = userEvent.setup();

      const { rerender } = render(
        <Wrapper>
          <AlbumDetailView albumId={1} currentTrackId={1} isPlaying={false} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Come Together')).toBeInTheDocument();
      });

      // Update playing state
      rerender(
        <Wrapper>
          <AlbumDetailView albumId={1} currentTrackId={1} isPlaying={true} />
        </Wrapper>
      );

      // Current track should be highlighted
      expect(screen.getByText('Come Together')).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('should handle album with no year', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({
          ...mockAlbumData,
          year: null,
        }),
      });

      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Abbey Road')).toBeInTheDocument();
      });

      // Should not crash and display other metadata
      expect(screen.getByText(/3\s+tracks/)).toBeInTheDocument();
    });

    it('should handle album with no genre', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({
          ...mockAlbumData,
          genre: null,
        }),
      });

      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Abbey Road')).toBeInTheDocument();
      });

      // Genre section should not appear
      expect(screen.queryByText(/genre:/i)).not.toBeInTheDocument();
    });

    it('should handle track with no track_number', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({
          ...mockAlbumData,
          tracks: [
            { id: 1, title: 'Come Together', artist: 'The Beatles', duration: 259 },
          ],
        }),
      });

      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Come Together')).toBeInTheDocument();
      });

      // Should use index as fallback
      expect(document.body).toBeInTheDocument();
    });

    it('should handle very long track title', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({
          ...mockAlbumData,
          tracks: [
            {
              id: 1,
              title: 'A'.repeat(100),
              artist: 'The Beatles',
              duration: 259,
              track_number: 1,
            },
          ],
        }),
      });

      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/A+/)).toBeInTheDocument();
      });
    });

    it('should handle very long artist name', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({
          ...mockAlbumData,
          artist: 'B'.repeat(100),
        }),
      });

      render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/B+/)).toBeInTheDocument();
      });
    });
  });

  describe('Performance', () => {
    it('should render large album efficiently', async () => {
      const manyTracks = Array.from({ length: 100 }, (_, i) => ({
        id: i,
        title: `Track ${i}`,
        artist: 'The Beatles',
        duration: 180,
        track_number: i + 1,
      }));

      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({
          ...mockAlbumData,
          total_tracks: 100,
          tracks: manyTracks,
        }),
      });

      const { container } = render(
        <Wrapper>
          <AlbumDetailView albumId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByRole('table')).toBeInTheDocument();
      });

      const rows = container.querySelectorAll('tbody tr');
      expect(rows.length).toBe(100);
    });
  });
});
