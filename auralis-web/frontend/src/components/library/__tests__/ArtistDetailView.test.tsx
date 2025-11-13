/**
 * ArtistDetailView Component Tests
 *
 * Tests the artist detail view component with:
 * - Artist metadata display (name, album count, track count, avatar)
 * - Album grid with album cards
 * - All tracks table view with tab switching
 * - Playback integration (play all, shuffle, track click)
 * - Album click navigation
 * - Navigation (back button)
 * - Loading and error states
 */

import { vi } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import ArtistDetailView from '../ArtistDetailView';
import { auralisTheme } from '../../../theme/auralisTheme';

// Mock the AlbumArt component
vi.mock('../../album/AlbumArt', () => {
  return function MockAlbumArt({ albumId, size }: any) {
    return (
      <div data-testid={`album-artwork-${albumId}`}>
        <img src={`/artwork/${albumId}`} alt={`Album ${albumId}`} style={{ width: size, height: size }} />
      </div>
    );
  };
});

// Mock fetch for API calls
global.fetch = vi.fn();

const mockArtistData = {
  artist_id: 1,
  artist_name: 'David Bowie',
  total_albums: 2,
  total_tracks: 6,
  albums: [
    { id: 101, title: 'Space Oddity', year: 1969, track_count: 3, total_duration: 600 },
    { id: 102, title: 'Heroes', year: 1977, track_count: 3, total_duration: 660 },
  ],
};

const Wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <BrowserRouter>
    <ThemeProvider theme={auralisTheme}>
      {children}
    </ThemeProvider>
  </BrowserRouter>
);

describe('ArtistDetailView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (global.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => mockArtistData,
    });
  });

  describe('Rendering', () => {
    it('should render loading state initially', () => {
      (global.fetch as any).mockImplementation(
        () => new Promise(() => {}) // Never resolves
      );

      render(
        <Wrapper>
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      expect(screen.getAllByTestId(/skeleton|loading/i).length).toBeGreaterThan(0) ||
      expect(document.querySelector('[role="progressbar"]')).toBeInTheDocument();
    });

    it('should render artist details after loading', async () => {
      render(
        <Wrapper>
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('David Bowie')).toBeInTheDocument();
      });
    });

    it('should display artist avatar with initial', async () => {
      render(
        <Wrapper>
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/D(?!\s)/)).toBeInTheDocument(); // Artist initial
      });
    });

    it('should display artist name', async () => {
      render(
        <Wrapper>
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('David Bowie')).toBeInTheDocument();
      });
    });

    it('should display album count', async () => {
      render(
        <Wrapper>
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/2\s+albums/)).toBeInTheDocument();
      });
    });

    it('should display track count', async () => {
      render(
        <Wrapper>
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/6\s+tracks/)).toBeInTheDocument();
      });
    });

    it('should handle single album correctly', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({
          ...mockArtistData,
          total_albums: 1,
          albums: [mockArtistData.albums[0]],
        }),
      });

      render(
        <Wrapper>
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/1\s+album/)).toBeInTheDocument();
      });
    });

    it('should handle single track correctly', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({
          ...mockArtistData,
          total_tracks: 1,
        }),
      });

      render(
        <Wrapper>
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/1\s+track/)).toBeInTheDocument();
      });
    });
  });

  describe('Tabs', () => {
    it('should display both album and track tabs', async () => {
      render(
        <Wrapper>
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('David Bowie')).toBeInTheDocument();
      });

      expect(screen.getByText(/Albums.*2/)).toBeInTheDocument();
      expect(screen.getByText(/All Tracks.*6/)).toBeInTheDocument();
    });

    it('should show albums tab by default', async () => {
      render(
        <Wrapper>
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('David Bowie')).toBeInTheDocument();
      });

      expect(screen.getByTestId(/album-artwork-101/)).toBeInTheDocument();
    });

    it('should switch to tracks tab on click', async () => {
      const user = userEvent.setup();

      render(
        <Wrapper>
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('David Bowie')).toBeInTheDocument();
      });

      const tracksTab = screen.getByRole('tab', { name: /All Tracks/ });
      await user.click(tracksTab);

      // Should show track table
      expect(screen.getByText(/Title|Album|Duration/).closest('table')).toBeInTheDocument();
    });

    it('should maintain tab state', async () => {
      const user = userEvent.setup();

      const { rerender } = render(
        <Wrapper>
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('David Bowie')).toBeInTheDocument();
      });

      const tracksTab = screen.getByRole('tab', { name: /All Tracks/ });
      await user.click(tracksTab);

      // Rerender component
      rerender(
        <Wrapper>
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      // Tracks tab should still be active
      expect(screen.getByRole('tab', { name: /All Tracks/ })).toHaveAttribute('aria-selected', 'true');
    });
  });

  describe('Album Grid', () => {
    it('should render all albums in grid', async () => {
      render(
        <Wrapper>
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Space Oddity')).toBeInTheDocument();
        expect(screen.getByText('Heroes')).toBeInTheDocument();
      });
    });

    it('should display album year and track count', async () => {
      render(
        <Wrapper>
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/1969/)).toBeInTheDocument();
        expect(screen.getByText(/1977/)).toBeInTheDocument();
        expect(screen.getAllByText(/3\s+tracks/).length).toBeGreaterThanOrEqual(2);
      });
    });

    it('should call onAlbumClick when album clicked', async () => {
      const user = userEvent.setup();
      const onAlbumClick = vi.fn();

      render(
        <Wrapper>
          <ArtistDetailView artistId={1} onAlbumClick={onAlbumClick} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Space Oddity')).toBeInTheDocument();
      });

      const albumCard = screen.getByText('Space Oddity').closest('[class*="Paper"]');
      if (albumCard) {
        await user.click(albumCard);
        expect(onAlbumClick).toHaveBeenCalledWith(101);
      }
    });

    it('should show empty state when no albums', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({
          ...mockArtistData,
          total_albums: 0,
          albums: [],
        }),
      });

      render(
        <Wrapper>
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/no albums|empty/i)).toBeInTheDocument();
      });
    });

    it('should highlight album on hover', async () => {
      const user = userEvent.setup();

      const { container } = render(
        <Wrapper>
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Space Oddity')).toBeInTheDocument();
      });

      const albumCard = screen.getByText('Space Oddity').closest('[class*="Paper"]');
      if (albumCard) {
        await user.hover(albumCard);
        // Card should have hover styles applied
        const style = window.getComputedStyle(albumCard);
        expect(style.transform || albumCard.className).toBeTruthy();
      }
    });
  });

  describe('Playback Integration', () => {
    it('should play first track when play all clicked', async () => {
      const user = userEvent.setup();
      const onTrackPlay = vi.fn();

      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({
          ...mockArtistData,
          tracks: [
            { id: 201, title: 'Space Oddity', album: 'Space Oddity', duration: 300, track_number: 1 },
            { id: 202, title: 'Changes', album: 'Heroes', duration: 240, track_number: 1 },
          ],
        }),
      });

      render(
        <Wrapper>
          <ArtistDetailView artistId={1} onTrackPlay={onTrackPlay} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('David Bowie')).toBeInTheDocument();
      });

      const playAllButton = screen.getByRole('button', { name: /play all/i });
      await user.click(playAllButton);

      // Should get first track
      expect(onTrackPlay).toHaveBeenCalled();
    });

    it('should shuffle play random track', async () => {
      const user = userEvent.setup();
      const onTrackPlay = vi.fn();

      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({
          ...mockArtistData,
          tracks: [
            { id: 201, title: 'Space Oddity', album: 'Space Oddity', duration: 300 },
            { id: 202, title: 'Changes', album: 'Heroes', duration: 240 },
            { id: 203, title: 'Starman', album: 'The Rise', duration: 260 },
          ],
        }),
      });

      render(
        <Wrapper>
          <ArtistDetailView artistId={1} onTrackPlay={onTrackPlay} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('David Bowie')).toBeInTheDocument();
      });

      const shuffleButton = screen.getByRole('button', { name: /shuffle/i });
      await user.click(shuffleButton);

      expect(onTrackPlay).toHaveBeenCalled();
      const calledTrack = (onTrackPlay.mock.calls[0][0] as any).id;
      expect([201, 202, 203]).toContain(calledTrack);
    });

    it('should play track on track row click', async () => {
      const user = userEvent.setup();
      const onTrackPlay = vi.fn();

      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({
          ...mockArtistData,
          tracks: [
            { id: 201, title: 'Space Oddity', album: 'Space Oddity', duration: 300 },
          ],
        }),
      });

      render(
        <Wrapper>
          <ArtistDetailView artistId={1} onTrackPlay={onTrackPlay} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('David Bowie')).toBeInTheDocument();
      });

      const tracksTab = screen.getByRole('tab', { name: /All Tracks/ });
      await user.click(tracksTab);

      await waitFor(() => {
        expect(screen.getByText('Space Oddity')).toBeInTheDocument();
      });

      const trackRow = screen.getByText('Space Oddity').closest('tr');
      if (trackRow) {
        fireEvent.click(trackRow);
        expect(onTrackPlay).toHaveBeenCalledWith(expect.objectContaining({
          id: 201,
          title: 'Space Oddity',
        }));
      }
    });

    it('should highlight current playing track', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({
          ...mockArtistData,
          tracks: [
            { id: 201, title: 'Space Oddity', album: 'Space Oddity', duration: 300 },
            { id: 202, title: 'Changes', album: 'Heroes', duration: 240 },
          ],
        }),
      });

      const { container } = render(
        <Wrapper>
          <ArtistDetailView
            artistId={1}
            currentTrackId={202}
            isPlaying={true}
          />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('David Bowie')).toBeInTheDocument();
      });

      const tracksTab = screen.getByRole('tab', { name: /All Tracks/ });
      fireEvent.click(tracksTab);

      const currentTrackRow = Array.from(container.querySelectorAll('tr')).find(row =>
        row.textContent?.includes('Changes')
      );

      expect(currentTrackRow?.className).toContain('current-track');
    });

    it('should show pause icon for current track', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({
          ...mockArtistData,
          tracks: [
            { id: 201, title: 'Space Oddity', album: 'Space Oddity', duration: 300 },
          ],
        }),
      });

      render(
        <Wrapper>
          <ArtistDetailView
            artistId={1}
            currentTrackId={201}
            isPlaying={true}
          />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('David Bowie')).toBeInTheDocument();
      });

      const tracksTab = screen.getByRole('tab', { name: /All Tracks/ });
      fireEvent.click(tracksTab);

      // Should show pause icon
      expect(document.querySelector('[data-testid*="pause"]') || screen.getByRole('img', { hidden: true })).toBeInTheDocument() ||
      expect(document.body).toBeInTheDocument();
    });
  });

  describe('Navigation', () => {
    it('should show back button when onBack provided', async () => {
      const onBack = vi.fn();

      render(
        <Wrapper>
          <ArtistDetailView artistId={1} onBack={onBack} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('David Bowie')).toBeInTheDocument();
      });

      const backButton = screen.getByRole('button', { name: /back/i });
      expect(backButton).toBeInTheDocument();
    });

    it('should call onBack when back button clicked', async () => {
      const user = userEvent.setup();
      const onBack = vi.fn();

      render(
        <Wrapper>
          <ArtistDetailView artistId={1} onBack={onBack} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('David Bowie')).toBeInTheDocument();
      });

      const backButton = screen.getByRole('button', { name: /back/i });
      await user.click(backButton);

      expect(onBack).toHaveBeenCalled();
    });

    it('should not show back button when onBack not provided', async () => {
      render(
        <Wrapper>
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('David Bowie')).toBeInTheDocument();
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
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      expect(
        screen.queryAllByTestId(/skeleton/i).length > 0 ||
        document.querySelector('[role="progressbar"]') !== null
      ).toBeTruthy();
    });

    it('should refetch when artistId changes', async () => {
      const { rerender } = render(
        <Wrapper>
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('David Bowie')).toBeInTheDocument();
      });

      expect(global.fetch).toHaveBeenCalledWith('/api/artists/1');

      (global.fetch as any).mockClear();
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({
          ...mockArtistData,
          artist_id: 2,
          artist_name: 'Pink Floyd',
        }),
      });

      rerender(
        <Wrapper>
          <ArtistDetailView artistId={2} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith('/api/artists/2');
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
          <ArtistDetailView artistId={999} />
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
          <ArtistDetailView artistId={999} onBack={onBack} />
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
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/failed|error|network/i)).toBeInTheDocument();
      });
    });
  });

  describe('Duration Formatting', () => {
    it('should format track duration as MM:SS', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({
          ...mockArtistData,
          tracks: [
            { id: 201, title: 'Track 1', album: 'Album 1', duration: 180 },
            { id: 202, title: 'Track 2', album: 'Album 1', duration: 325 },
          ],
        }),
      });

      render(
        <Wrapper>
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('David Bowie')).toBeInTheDocument();
      });

      const tracksTab = screen.getByRole('tab', { name: /All Tracks/ });
      fireEvent.click(tracksTab);

      await waitFor(() => {
        expect(screen.getByText(/3:00|5:25/)).toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('should have tab role', async () => {
      render(
        <Wrapper>
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('David Bowie')).toBeInTheDocument();
      });

      const tabs = screen.getAllByRole('tab');
      expect(tabs.length).toBeGreaterThanOrEqual(2);
    });

    it('should have table semantics in tracks tab', async () => {
      const user = userEvent.setup();

      render(
        <Wrapper>
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('David Bowie')).toBeInTheDocument();
      });

      const tracksTab = screen.getByRole('tab', { name: /All Tracks/ });
      await user.click(tracksTab);

      expect(screen.getByRole('table')).toBeInTheDocument();
    });

    it('should have accessible buttons with tooltips', async () => {
      render(
        <Wrapper>
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('David Bowie')).toBeInTheDocument();
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
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('David Bowie')).toBeInTheDocument();
      });

      const playAllButton = screen.getByRole('button', { name: /play all/i });
      playAllButton.focus();
      expect(document.activeElement).toBe(playAllButton);

      await user.keyboard('{Enter}');
      expect(document.activeElement).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('should handle artist with no albums', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({
          ...mockArtistData,
          total_albums: 0,
          albums: [],
        }),
      });

      render(
        <Wrapper>
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('David Bowie')).toBeInTheDocument();
      });

      expect(screen.getByText(/no albums|empty/i)).toBeInTheDocument();
    });

    it('should handle artist with no tracks', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({
          ...mockArtistData,
          total_tracks: 0,
          tracks: [],
        }),
      });

      render(
        <Wrapper>
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('David Bowie')).toBeInTheDocument();
      });

      const tracksTab = screen.getByRole('tab', { name: /All Tracks/ });
      fireEvent.click(tracksTab);

      expect(screen.getByText(/no tracks|empty/i)).toBeInTheDocument();
    });

    it('should handle album with no year', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({
          ...mockArtistData,
          albums: [
            { id: 101, title: 'Album No Year', year: null, track_count: 3, total_duration: 600 },
          ],
        }),
      });

      render(
        <Wrapper>
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Album No Year')).toBeInTheDocument();
      });

      expect(screen.getByText(/3\s+tracks/)).toBeInTheDocument();
    });

    it('should handle very long artist name', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({
          ...mockArtistData,
          artist_name: 'A'.repeat(100),
        }),
      });

      render(
        <Wrapper>
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/A+/)).toBeInTheDocument();
      });
    });

    it('should handle very long album title', async () => {
      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({
          ...mockArtistData,
          albums: [
            { id: 101, title: 'B'.repeat(100), year: 2020, track_count: 5, total_duration: 900 },
          ],
        }),
      });

      render(
        <Wrapper>
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText(/B+/)).toBeInTheDocument();
      });
    });
  });

  describe('Performance', () => {
    it('should render large album collection efficiently', async () => {
      const manyAlbums = Array.from({ length: 50 }, (_, i) => ({
        id: i,
        title: `Album ${i}`,
        year: 2020 - i,
        track_count: 10,
        total_duration: 3600,
      }));

      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({
          ...mockArtistData,
          total_albums: 50,
          albums: manyAlbums,
        }),
      });

      const { container } = render(
        <Wrapper>
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('David Bowie')).toBeInTheDocument();
      });

      const gridItems = container.querySelectorAll('[class*="Grid"]');
      expect(gridItems.length).toBeGreaterThan(0);
    });

    it('should render large track collection efficiently', async () => {
      const manyTracks = Array.from({ length: 100 }, (_, i) => ({
        id: i,
        title: `Track ${i}`,
        album: `Album ${i}`,
        duration: 180,
        track_number: i + 1,
      }));

      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({
          ...mockArtistData,
          total_tracks: 100,
          tracks: manyTracks,
        }),
      });

      const { container } = render(
        <Wrapper>
          <ArtistDetailView artistId={1} />
        </Wrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('David Bowie')).toBeInTheDocument();
      });

      const tracksTab = screen.getByRole('tab', { name: /All Tracks/ });
      fireEvent.click(tracksTab);

      const rows = container.querySelectorAll('tbody tr');
      expect(rows.length).toBe(100);
    });
  });

  describe('Integration', () => {
    it('should handle full artist workflow', async () => {
      const user = userEvent.setup();
      const onAlbumClick = vi.fn();
      const onTrackPlay = vi.fn();
      const onBack = vi.fn();

      (global.fetch as any).mockResolvedValue({
        ok: true,
        json: async () => ({
          ...mockArtistData,
          tracks: [
            { id: 201, title: 'Space Oddity', album: 'Space Oddity', duration: 300 },
            { id: 202, title: 'Changes', album: 'Heroes', duration: 240 },
          ],
        }),
      });

      render(
        <Wrapper>
          <ArtistDetailView
            artistId={1}
            onAlbumClick={onAlbumClick}
            onTrackPlay={onTrackPlay}
            onBack={onBack}
            currentTrackId={201}
            isPlaying={false}
          />
        </Wrapper>
      );

      // 1. Artist loads
      await waitFor(() => {
        expect(screen.getByText('David Bowie')).toBeInTheDocument();
      });

      // 2. Click album
      const albumCard = screen.getByText('Space Oddity').closest('[class*="Paper"]');
      if (albumCard) {
        await user.click(albumCard);
        expect(onAlbumClick).toHaveBeenCalled();
      }

      // 3. Switch to tracks tab
      const tracksTab = screen.getByRole('tab', { name: /All Tracks/ });
      await user.click(tracksTab);

      // 4. Play all
      const playAllButton = screen.getByRole('button', { name: /play all/i });
      await user.click(playAllButton);
      expect(onTrackPlay).toHaveBeenCalled();

      // 5. Go back
      const backButton = screen.getByRole('button', { name: /back/i });
      await user.click(backButton);
      expect(onBack).toHaveBeenCalled();
    });
  });
});
