/**
 * PlaylistListContent tells a failed load from an empty library (#5645)
 */

import { describe, expect, it, vi } from 'vitest';
import userEvent from '@testing-library/user-event';
import { render, screen } from '@/test/test-utils';
import { PlaylistListContent } from '../PlaylistListContent';

// The row needs a drag-and-drop context that is irrelevant to this spec.
vi.mock('../DroppablePlaylist', () => ({
  DroppablePlaylist: ({ playlistName }: { playlistName: string }) => <div>{playlistName}</div>,
}));

const baseProps = {
  playlists: [],
  loading: false,
  expanded: true,
  contextMenuState: { isOpen: false },
  contextActions: [],
  onContextMenuOpen: vi.fn(),
  onContextMenuClose: vi.fn(),
};

describe('PlaylistListContent (#5645)', () => {
  it('shows the empty message only when nothing failed', () => {
    render(<PlaylistListContent {...baseProps} />);

    expect(screen.getByText(/No playlists yet/)).toBeInTheDocument();
  });

  it('shows the error with a Retry button instead of "No playlists yet" when the load failed', async () => {
    const onRetry = vi.fn();
    render(<PlaylistListContent {...baseProps} error="Failed to load playlists" onRetry={onRetry} />);

    expect(screen.getByRole('alert')).toHaveTextContent('Failed to load playlists');
    expect(screen.queryByText(/No playlists yet/)).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('keeps showing the loaded playlists when a later refresh failed', () => {
    render(
      <PlaylistListContent
        {...baseProps}
        playlists={[{ id: 1, name: 'Focus', track_count: 12 }] as never}
        error="Failed to load playlists"
      />,
    );

    expect(screen.getByText('Focus')).toBeInTheDocument();
    expect(screen.queryByText(/No playlists yet/)).not.toBeInTheDocument();
  });
});
