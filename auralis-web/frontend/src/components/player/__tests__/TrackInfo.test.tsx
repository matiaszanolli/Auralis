/**
 * TrackInfo Component Tests
 */

import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';
import TrackInfo from '@/components/player/TrackInfo';
import { selectCurrentTrack } from '@/store/slices/playerSlice';

vi.mock('react-redux', async () => {
  const actual = await vi.importActual('react-redux');
  return { ...actual, useSelector: vi.fn() };
});

import { useSelector } from 'react-redux';

function mockCurrentTrack(track: ReturnType<typeof selectCurrentTrack>) {
  vi.mocked(useSelector).mockImplementation((selector: any) => {
    if (selector === selectCurrentTrack) return track;
    return undefined;
  });
}

describe('TrackInfo', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should display track information when track is loaded', () => {
    mockCurrentTrack({
      id: 1,
      title: 'Song Title',
      artist: 'Artist Name',
      album: 'Album Name',
      duration: 180,
      artworkUrl: 'https://example.com/artwork.jpg',
    });

    render(<TrackInfo />);

    expect(screen.getByText('Song Title')).toBeInTheDocument();
    expect(screen.getByText('Artist Name')).toBeInTheDocument();
    expect(screen.getByText('Album Name')).toBeInTheDocument();
  });

  it('should display artwork image when available', () => {
    mockCurrentTrack({
      id: 1,
      title: 'Song Title',
      artist: 'Artist Name',
      album: 'Album Name',
      duration: 180,
      artworkUrl: 'https://example.com/artwork.jpg',
    });

    render(<TrackInfo />);

    const img = screen.getByAltText('Song Title');
    expect(img).toHaveAttribute('src', 'https://example.com/artwork.jpg');
  });

  it('should show placeholder when no track is loaded', () => {
    mockCurrentTrack(null);

    render(<TrackInfo />);

    expect(screen.getByText(/no track playing/i)).toBeInTheDocument();
  });

  it('should display year and genre when available', () => {
    mockCurrentTrack({
      id: 1,
      title: 'Song Title',
      artist: 'Artist Name',
      album: 'Album Name',
      duration: 180,
      year: 2023,
      genre: 'Rock',
    } as any);

    render(<TrackInfo />);

    expect(screen.getByText(/2023/)).toBeInTheDocument();
    expect(screen.getByText(/rock/i)).toBeInTheDocument();
  });
});
