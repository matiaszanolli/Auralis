/**
 * SidebarContent playlist navigation tests (#6007)
 *
 * SidebarContent is where `playlist-N` view ids are minted from the
 * PlaylistList's numeric selections. The delete flow passes the sentinel
 * -1 ("selected playlist was deleted") — that must navigate to songs,
 * never to the malformed `playlist--1` view id.
 */

import { vi } from 'vitest';
import { render, screen } from '@/test/test-utils';
import SidebarContent from '../SidebarContent';

// PlaylistList is where the sentinel originates (usePlaylistOperations'
// handleDelete calls onPlaylistSelect(-1)); mock it so this spec asserts
// SidebarContent's translation in isolation.
vi.mock('@/components/playlist/PlaylistList', () => ({
  default: function MockPlaylistList({ onPlaylistSelect, selectedPlaylistId }: any) {
    return (
      <div>
        <div data-testid="playlist-list">
          selected: {String(selectedPlaylistId)}
        </div>
        <button
          data-testid="fire-select"
          onClick={() => onPlaylistSelect(42)}
        >
          fire-select
        </button>
        <button
          data-testid="fire-delete-sentinel"
          onClick={() => onPlaylistSelect(-1)}
        >
          fire-delete-sentinel
        </button>
      </div>
    );
  },
}));

describe('SidebarContent playlist view ids (#6007)', () => {
  it('mints playlist-N view ids for playlist selections', () => {
    const onItemClick = vi.fn();
    render(<SidebarContent selectedItem="songs" onItemClick={onItemClick} />);

    screen.getByTestId('fire-select').click();
    expect(onItemClick).toHaveBeenCalledWith('playlist-42');
  });

  it('navigates to songs when the selected playlist is deleted (-1 sentinel)', () => {
    const onItemClick = vi.fn();
    render(<SidebarContent selectedItem="playlist-42" onItemClick={onItemClick} />);

    screen.getByTestId('fire-delete-sentinel').click();
    // Never `playlist--1` (#6007): the delete sentinel lands on songs.
    expect(onItemClick).toHaveBeenCalledWith('songs');
    expect(onItemClick).not.toHaveBeenCalledWith('playlist--1');
  });
});
