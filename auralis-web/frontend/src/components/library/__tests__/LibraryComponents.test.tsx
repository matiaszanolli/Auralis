/**
 * Library Components Tests
 * ~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tests for the AlbumCard library component.
 *
 * Note: AlbumGrid and MetadataEditorDialog tests were removed with those dead
 * components (#4153, #4152). ArtistList and LibraryView tests were removed
 * earlier — replaced by CozyArtistList and CozyLibraryView.
 *
 * @module components/library/__tests__/LibraryComponents.test
 */

import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import { AlbumCard } from '@/components/album/AlbumCard/AlbumCard';
import type { Album } from '@/types/domain';

// Mock data
const mockAlbum: Album = {
  id: 1,
  title: 'Test Album',
  artist: 'Test Artist',
  year: 2023,
  trackCount: 10, // camelCase
  artworkUrl: 'https://example.com/album.jpg', // camelCase
};

describe('AlbumCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should display album title', () => {
    const mockOnClick = vi.fn();

    render(
      <AlbumCard
        albumId={mockAlbum.id}
        title={mockAlbum.title}
        artist={mockAlbum.artist}
        trackCount={mockAlbum.trackCount}
        hasArtwork={!!mockAlbum.artworkUrl}
        year={mockAlbum.year}
        onClick={mockOnClick}
      />
    );

    expect(screen.getByText('Test Album')).toBeInTheDocument();
  });

  it('should display artist name', () => {
    const mockOnClick = vi.fn();

    render(
      <AlbumCard
        albumId={mockAlbum.id}
        title={mockAlbum.title}
        artist={mockAlbum.artist}
        trackCount={mockAlbum.trackCount}
        hasArtwork={!!mockAlbum.artworkUrl}
        year={mockAlbum.year}
        onClick={mockOnClick}
      />
    );

    expect(screen.getByText('Test Artist')).toBeInTheDocument();
  });

  it('should display year', () => {
    const mockOnClick = vi.fn();

    render(
      <AlbumCard
        albumId={mockAlbum.id}
        title={mockAlbum.title}
        artist={mockAlbum.artist}
        trackCount={mockAlbum.trackCount}
        hasArtwork={!!mockAlbum.artworkUrl}
        year={mockAlbum.year}
        onClick={mockOnClick}
      />
    );

    // Year appears in secondary metadata as part of "10 tracks • 2023"
    expect(screen.getByText(/2023/)).toBeInTheDocument();
  });

  it('should display track count', () => {
    const mockOnClick = vi.fn();

    render(
      <AlbumCard
        albumId={mockAlbum.id}
        title={mockAlbum.title}
        artist={mockAlbum.artist}
        trackCount={mockAlbum.trackCount}
        hasArtwork={!!mockAlbum.artworkUrl}
        year={mockAlbum.year}
        onClick={mockOnClick}
      />
    );

    // Track count appears in both badge and secondary metadata
    const trackCountElements = screen.getAllByText(/10 tracks/i);
    expect(trackCountElements.length).toBeGreaterThan(0);
  });

  it('should call onClick when clicked', async () => {
    const user = userEvent.setup();
    const mockOnClick = vi.fn();

    const { container } = render(
      <AlbumCard
        albumId={mockAlbum.id}
        title={mockAlbum.title}
        artist={mockAlbum.artist}
        trackCount={mockAlbum.trackCount}
        hasArtwork={!!mockAlbum.artworkUrl}
        year={mockAlbum.year}
        onClick={mockOnClick}
      />
    );

    const card = container.firstChild as HTMLElement;
    await user.click(card);

    expect(mockOnClick).toHaveBeenCalled();
  });

  it('should handle missing artwork gracefully', () => {
    const mockOnClick = vi.fn();

    render(
      <AlbumCard
        albumId={mockAlbum.id}
        title={mockAlbum.title}
        artist={mockAlbum.artist}
        trackCount={mockAlbum.trackCount}
        hasArtwork={false}
        year={mockAlbum.year}
        onClick={mockOnClick}
      />
    );

    expect(screen.getByText('Test Album')).toBeInTheDocument();
  });
});
