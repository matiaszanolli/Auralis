/**
 * TrackInfo Component Tests (#3613)
 *
 * Uses the real Redux Provider via `@/test/test-utils` rather than
 * mocking `useSelector` directly — see #3613 for context. Tests seed
 * the player slice via `preloadedState`.
 */

import { describe, it, expect } from 'vitest';
import { screen } from '@testing-library/react';
import { render } from '@/test/test-utils';
import TrackInfo from '@/components/player/TrackInfo';

describe('TrackInfo', () => {
  it('should display track information when track is loaded', () => {
    render(<TrackInfo />, {
      preloadedState: {
        player: {
          currentTrack: {
            id: 1,
            title: 'Song Title',
            artist: 'Artist Name',
            album: 'Album Name',
            duration: 180,
            artworkUrl: 'https://example.com/artwork.jpg',
          },
        } as never,
      },
    });

    expect(screen.getByText('Song Title')).toBeInTheDocument();
    expect(screen.getByText('Artist Name')).toBeInTheDocument();
    expect(screen.getByText('Album Name')).toBeInTheDocument();
  });

  it('should display artwork image when available', () => {
    render(<TrackInfo />, {
      preloadedState: {
        player: {
          currentTrack: {
            id: 1,
            title: 'Song Title',
            artist: 'Artist Name',
            album: 'Album Name',
            duration: 180,
            artworkUrl: 'https://example.com/artwork.jpg',
          },
        } as never,
      },
    });

    // Real component renders `alt="Artwork for {title}"` — the previous
    // assertion silently passed only because react-redux was mocked.
    const img = screen.getByAltText('Artwork for Song Title');
    expect(img).toHaveAttribute('src', 'https://example.com/artwork.jpg');
  });

  it('should show placeholder when no track is loaded', () => {
    render(<TrackInfo />);
    expect(screen.getByText(/no track playing/i)).toBeInTheDocument();
  });

  // #3613 dropped: the prior "should display year and genre when available"
  // test claimed to verify year/genre rendering — but TrackInfo.tsx renders
  // neither field. The test passed under the previous react-redux mock
  // because `expect(...).toBeInTheDocument()` was wrapped in a `getByText`
  // matcher that never actually fired against real DOM (the mock returned
  // a track but TrackInfo's actual render path is title/artist/album only).
  // Removed rather than wired up — adding the fields is product work, not
  // test scaffolding.
});
