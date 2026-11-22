/**
 * PlaylistSection loading state (#6681)
 *
 * `isLoadingPlaylists` was destructured as `_isLoadingPlaylists` and never
 * read, so the section showed an empty list while playlists were loading.
 */

import { describe, it, expect, vi } from 'vitest';
import { MenuList } from '@mui/material';
import { render, screen } from '@/test/test-utils';
import { PlaylistSection } from '@/components/shared/ContextMenu/PlaylistSection';

const playlist = {
  id: 7,
  name: 'Road Trip',
  track_count: 3,
} as Parameters<typeof PlaylistSection>[0]['playlists'][number];

function renderSection(isLoadingPlaylists: boolean, playlists = [] as (typeof playlist)[]) {
  return render(
    <MenuList>
      <PlaylistSection
        playlists={playlists}
        isLoadingPlaylists={isLoadingPlaylists}
        onAddToPlaylist={vi.fn()}
        onCreateNewPlaylist={vi.fn()}
      />
    </MenuList>
  );
}

describe('PlaylistSection loading row (#6681)', () => {
  it('shows a loading row while playlists load and none are cached', () => {
    renderSection(true);
    expect(screen.getByText('Loading playlists…')).toBeInTheDocument();
  });

  it('hides the loading row once loading finishes', () => {
    renderSection(false);
    expect(screen.queryByText('Loading playlists…')).not.toBeInTheDocument();
  });

  it('keeps showing cached playlists instead of the loading row on a refetch', () => {
    renderSection(true, [playlist]);
    expect(screen.queryByText('Loading playlists…')).not.toBeInTheDocument();
    expect(screen.getByText('Road Trip (3)')).toBeInTheDocument();
  });
});
