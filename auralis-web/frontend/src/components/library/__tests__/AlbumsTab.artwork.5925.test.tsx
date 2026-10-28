/**
 * AlbumsTab only requests artwork for albums that have it (#5925)
 *
 * AlbumInArtist carried no artwork field, so the tab passed hasArtwork unconditionally and every
 * album without art issued a thumbnail request that 404ed.
 */

import { describe, it, expect } from 'vitest';
import { render } from '@/test/test-utils';
import AlbumsTab from '@/components/library/Views/AlbumsTab';

const WITH_ART = { id: 1, title: 'Oktubre', year: 1986, track_count: 8, total_duration: 2400, artwork_url: '/api/albums/1/artwork' };
const WITHOUT_ART = { id: 2, title: 'Gulp!', year: 1985, track_count: 9, total_duration: 2700, artwork_url: null };

describe('AlbumsTab artwork requests (#5925)', () => {
  it('requests artwork only for the album that has it', () => {
    const { container } = render(
      <AlbumsTab albums={[WITH_ART, WITHOUT_ART]} artistName="Patricio Rey" onAlbumClick={() => {}} />,
    );

    const sources = Array.from(container.querySelectorAll('img')).map((img) => img.getAttribute('src') ?? '');

    expect(sources.filter((src) => src.includes('/api/albums/1/artwork'))).not.toHaveLength(0);
    expect(sources.filter((src) => src.includes('/api/albums/2/artwork'))).toHaveLength(0);
  });
});
