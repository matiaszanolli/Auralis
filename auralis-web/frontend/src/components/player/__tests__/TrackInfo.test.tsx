/**
 * TrackInfo Component Tests
 */

import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';
import TrackInfo from '@/components/player/TrackInfo';
import { useCurrentTrack } from '@/hooks/player/usePlaybackState';

vi.mock('@/hooks/player/usePlaybackState');

describe('TrackInfo', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should display track information when track is loaded', () => {
    vi.mocked(useCurrentTrack).mockReturnValue({
      id: 1,
      title: 'Song Title',
      artist: 'Artist Name',
      album: 'Album Name',
      duration: 180,
      filepath: '/path/to/song.wav',
      artwork_url: 'https://example.com/artwork.jpg',
    } as any);

    render(<TrackInfo />);

    expect(screen.getByText('Song Title')).toBeInTheDocument();
    expect(screen.getByText('Artist Name')).toBeInTheDocument();
    expect(screen.getByText('Album Name')).toBeInTheDocument();
  });

  it('should display artwork image when available', () => {
    vi.mocked(useCurrentTrack).mockReturnValue({
      id: 1,
      title: 'Song Title',
      artist: 'Artist Name',
      album: 'Album Name',
      duration: 180,
      filepath: '/path/to/song.wav',
      artwork_url: 'https://example.com/artwork.jpg',
    } as any);

    render(<TrackInfo />);

    const img = screen.getByAltText('Song Title');
    expect(img).toHaveAttribute('src', 'https://example.com/artwork.jpg');
  });

  it('should show placeholder when no track is loaded', () => {
    vi.mocked(useCurrentTrack).mockReturnValue(null);

    render(<TrackInfo />);

    expect(screen.getByText(/no track playing/i)).toBeInTheDocument();
  });

  it('should display year and genre when available', () => {
    vi.mocked(useCurrentTrack).mockReturnValue({
      id: 1,
      title: 'Song Title',
      artist: 'Artist Name',
      album: 'Album Name',
      duration: 180,
      filepath: '/path/to/song.wav',
      year: 2023,
      genre: 'Rock',
    } as any);

    render(<TrackInfo />);

    expect(screen.getByText(/2023/)).toBeInTheDocument();
    expect(screen.getByText(/rock/i)).toBeInTheDocument();
  });
});
