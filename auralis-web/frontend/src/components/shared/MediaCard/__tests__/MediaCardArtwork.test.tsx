/**
 * MediaCardArtwork onError fallback (#4437)
 *
 * When a set artwork URL fails to load (403/404/5xx), the <img> is removed and
 * the gradient placeholder is shown instead of the browser's broken-image glyph,
 * mirroring the album path's ProgressiveImage onError handling.
 */

import { describe, it, expect } from 'vitest';
import { fireEvent } from '@testing-library/react';
import { render } from '@/test/test-utils';
import { MediaCardArtwork } from '@/components/shared/MediaCard/MediaCardArtwork';

describe('MediaCardArtwork onError fallback (#4437)', () => {
  it('renders the <img> when a URL is provided', () => {
    const { getByRole } = render(
      <MediaCardArtwork artworkUrl="/api/albums/1/artwork" fallbackText="Album" variant="album" />
    );
    expect(getByRole('img')).toBeInTheDocument();
  });

  it('falls back to the gradient placeholder after the image fails to load', () => {
    const { getByRole, queryByRole } = render(
      <MediaCardArtwork artworkUrl="/api/albums/1/artwork" fallbackText="Album" variant="album" />
    );

    const img = getByRole('img');
    fireEvent.error(img);

    // The img is unmounted; only the gradient-background container remains.
    expect(queryByRole('img')).not.toBeInTheDocument();
  });

  it('shows no <img> when no URL is provided (gradient placeholder only)', () => {
    const { queryByRole } = render(
      <MediaCardArtwork fallbackText="Album" variant="album" />
    );
    expect(queryByRole('img')).not.toBeInTheDocument();
  });
});
