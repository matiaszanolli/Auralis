/**
 * Library Components Tests
 * ~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Comprehensive tests for Phase 2 library components:
 * - AlbumGrid: Responsive grid of album cards
 * - AlbumCard: Individual album with metadata and hover overlay
 * - MetadataEditorDialog: Modal for editing track metadata
 *
 * Note: ArtistList and LibraryView tests removed - these components have been
 * replaced by CozyArtistList and CozyLibraryView.
 *
 * @module components/library/__tests__/LibraryComponents.test
 */

import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { vi } from 'vitest';
import AlbumGrid from '@/components/library/AlbumGrid';
import { AlbumCard } from '@/components/album/AlbumCard/AlbumCard';
import MetadataEditorDialog from '@/components/library/MetadataEditorDialog';
import { useAlbumsQuery } from '@/hooks/library/useLibraryQuery';
import type { Album, Track } from '@/types/domain';

// Mock hooks
vi.mock('@/hooks/library/useLibraryQuery');

// Mock data
const mockAlbum: Album = {
  id: 1,
  title: 'Test Album',
  artist: 'Test Artist',
  year: 2023,
  trackCount: 10, // camelCase
  artworkUrl: 'https://example.com/album.jpg', // camelCase
};

const mockAlbum2: Album = {
  id: 2,
  title: 'Another Album',
  artist: 'Another Artist',
  year: 2024,
  trackCount: 12, // camelCase
  artworkUrl: 'https://example.com/album2.jpg', // camelCase
};

const mockTrack: Track = {
  id: 1,
  title: 'Test Song',
  artist: 'Test Artist',
  album: 'Test Album',
  duration: 180,
  filepath: '/path/to/song.wav',
};

describe('AlbumGrid', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render grid of albums', () => {
    vi.mocked(useAlbumsQuery).mockReturnValue({
      data: [mockAlbum, mockAlbum2],
      isLoading: false,
      error: null,
      total: 2,
      offset: 0,
      hasMore: false,
      fetchMore: vi.fn(),
      refetch: vi.fn(),
      clearError: vi.fn(),
    } as any);

    render(<AlbumGrid />);

    expect(screen.getByText('Test Album')).toBeInTheDocument();
    expect(screen.getByText('Another Album')).toBeInTheDocument();
  });

  it('should display loading state', () => {
    vi.mocked(useAlbumsQuery).mockReturnValue({
      data: [],
      isLoading: true,
      error: null,
      total: 0,
      offset: 0,
      hasMore: false,
      fetchMore: vi.fn(),
      refetch: vi.fn(),
      clearError: vi.fn(),
    } as any);

    render(<AlbumGrid />);

    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });

  it('should display error state', () => {
    vi.mocked(useAlbumsQuery).mockReturnValue({
      data: [],
      isLoading: false,
      error: { message: 'Failed to load albums', code: 'ERROR', status: 500 },
      total: 0,
      offset: 0,
      hasMore: false,
      fetchMore: vi.fn(),
      refetch: vi.fn(),
      clearError: vi.fn(),
    } as any);

    render(<AlbumGrid />);

    expect(screen.getByText(/failed/i)).toBeInTheDocument();
  });

  it('should display empty state', () => {
    vi.mocked(useAlbumsQuery).mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
      total: 0,
      offset: 0,
      hasMore: false,
      fetchMore: vi.fn(),
      refetch: vi.fn(),
      clearError: vi.fn(),
    } as any);

    render(<AlbumGrid />);

    expect(screen.getByText(/no albums/i)).toBeInTheDocument();
  });

  it('should use responsive grid layout', () => {
    vi.mocked(useAlbumsQuery).mockReturnValue({
      data: [mockAlbum],
      isLoading: false,
      error: null,
      total: 1,
      offset: 0,
      hasMore: false,
      fetchMore: vi.fn(),
      refetch: vi.fn(),
      clearError: vi.fn(),
    } as any);

    const { container } = render(<AlbumGrid />);

    const gridContainer = container.firstChild;
    expect(gridContainer).toBeInTheDocument();
  });
});

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

  it('should call onClick when clicked', () => {
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
    fireEvent.click(card);

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

describe('MetadataEditorDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should display dialog when open prop is true', () => {
    const mockOnClose = vi.fn();

    render(
      <MetadataEditorDialog
        open={true}
        track={mockTrack}
        onClose={mockOnClose}
        onSave={vi.fn()}
      />
    );

    expect(screen.getByText(/edit metadata/i)).toBeInTheDocument();
  });

  it('should not display dialog when open prop is false', () => {
    const mockOnClose = vi.fn();

    render(
      <MetadataEditorDialog
        open={false}
        track={mockTrack}
        onClose={mockOnClose}
        onSave={vi.fn()}
      />
    );

    expect(screen.queryByText(/edit track metadata/i)).not.toBeInTheDocument();
  });

  it('should display track title field', () => {
    const mockOnClose = vi.fn();

    render(
      <MetadataEditorDialog
        open={true}
        track={mockTrack}
        onClose={mockOnClose}
        onSave={vi.fn()}
      />
    );

    const titleInput = screen.getByDisplayValue('Test Song');
    expect(titleInput).toBeInTheDocument();
  });

  it('should display artist field', () => {
    const mockOnClose = vi.fn();

    render(
      <MetadataEditorDialog
        open={true}
        track={mockTrack}
        onClose={mockOnClose}
        onSave={vi.fn()}
      />
    );

    const artistInput = screen.getByDisplayValue('Test Artist');
    expect(artistInput).toBeInTheDocument();
  });

  it('should display album field', () => {
    const mockOnClose = vi.fn();

    render(
      <MetadataEditorDialog
        open={true}
        track={mockTrack}
        onClose={mockOnClose}
        onSave={vi.fn()}
      />
    );

    const albumInput = screen.getByDisplayValue('Test Album');
    expect(albumInput).toBeInTheDocument();
  });

  it('should call onClose when close button is clicked', () => {
    const mockOnClose = vi.fn();

    render(
      <MetadataEditorDialog
        open={true}
        track={mockTrack}
        onClose={mockOnClose}
        onSave={vi.fn()}
      />
    );

    const closeButton = screen.getByRole('button', { name: /close/i });
    fireEvent.click(closeButton);

    expect(mockOnClose).toHaveBeenCalled();
  });

  it('should call onSave with updated metadata', () => {
    const mockOnClose = vi.fn();
    const mockOnSave = vi.fn();

    render(
      <MetadataEditorDialog
        open={true}
        track={mockTrack}
        onClose={mockOnClose}
        onSave={mockOnSave}
      />
    );

    const titleInput = screen.getByDisplayValue('Test Song');
    fireEvent.change(titleInput, { target: { value: 'New Title' } });

    const saveButton = screen.getByRole('button', { name: /save/i });
    fireEvent.click(saveButton);

    expect(mockOnSave).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'New Title',
      })
    );
  });

  it('should display loading state while saving', () => {
    const mockOnClose = vi.fn();

    render(
      <MetadataEditorDialog
        open={true}
        track={mockTrack}
        onClose={mockOnClose}
        onSave={vi.fn()}
        isSaving={true}
      />
    );

    expect(screen.getByText(/saving/i)).toBeInTheDocument();
  });

  it('should disable save button while saving', () => {
    const mockOnClose = vi.fn();

    render(
      <MetadataEditorDialog
        open={true}
        track={mockTrack}
        onClose={mockOnClose}
        onSave={vi.fn()}
        isSaving={true}
      />
    );

    // When isSaving is true, button shows "Saving..." text
    const saveButton = screen.getByRole('button', { name: /saving/i });
    expect(saveButton).toBeDisabled();
  });

  it('should display error message if provided', () => {
    const mockOnClose = vi.fn();

    render(
      <MetadataEditorDialog
        open={true}
        track={mockTrack}
        onClose={mockOnClose}
        onSave={vi.fn()}
        error="Failed to save metadata"
      />
    );

    expect(screen.getByText('Failed to save metadata')).toBeInTheDocument();
  });

  it('should allow editing year field', () => {
    const mockOnClose = vi.fn();
    const mockOnSave = vi.fn();

    const trackWithYear = { ...mockTrack, year: 2023 };

    render(
      <MetadataEditorDialog
        open={true}
        track={trackWithYear}
        onClose={mockOnClose}
        onSave={mockOnSave}
      />
    );

    const yearInput = screen.getByDisplayValue('2023');
    fireEvent.change(yearInput, { target: { value: '2024' } });

    const saveButton = screen.getByRole('button', { name: /save/i });
    fireEvent.click(saveButton);

    expect(mockOnSave).toHaveBeenCalledWith(
      expect.objectContaining({
        year: 2024,
      })
    );
  });

  it('should allow editing genre field', () => {
    const mockOnClose = vi.fn();
    const mockOnSave = vi.fn();

    const trackWithGenre = { ...mockTrack, genre: 'Rock' };

    render(
      <MetadataEditorDialog
        open={true}
        track={trackWithGenre}
        onClose={mockOnClose}
        onSave={mockOnSave}
      />
    );

    const genreInput = screen.getByDisplayValue('Rock');
    fireEvent.change(genreInput, { target: { value: 'Pop' } });

    const saveButton = screen.getByRole('button', { name: /save/i });
    fireEvent.click(saveButton);

    expect(mockOnSave).toHaveBeenCalledWith(
      expect.objectContaining({
        genre: 'Pop',
      })
    );
  });
});
