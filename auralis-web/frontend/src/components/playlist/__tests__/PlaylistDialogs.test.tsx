import { act, render, renderHook, screen } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { CreatePlaylistDialog } from '@/components/playlist/CreatePlaylistDialog';
import { EditPlaylistDialog } from '@/components/playlist/EditPlaylistDialog';
import { useEditPlaylistForm } from '@/components/playlist/useEditPlaylistForm';
import { createPlaylist, updatePlaylist, type Playlist } from '@/services/playlistService';

const toast = vi.hoisted(() => ({ success: vi.fn(), error: vi.fn() }));
vi.mock('@/components/shared/Toast', async (original) => ({
  ...await original<typeof import('@/components/shared/Toast')>(),
  useToast: () => toast,
}));
vi.mock('@/services/playlistService', () => ({
  createPlaylist: vi.fn(),
  updatePlaylist: vi.fn(),
}));

const playlist: Playlist = {
  id: 7, name: 'Morning', description: 'Original description', track_count: 2,
  is_smart: false, smart_criteria: null, auto_master_enabled: false, normalize_levels: false,
  total_duration: 60, created_at: '2026-01-01', updated_at: '2026-01-01',
};

beforeEach(() => vi.resetAllMocks());

describe('EditPlaylistDialog', () => {
  it('seeds the fields and submits trimmed edits with Enter before refreshing and closing', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const onPlaylistUpdated = vi.fn();
    vi.mocked(updatePlaylist).mockResolvedValue(undefined);
    render(<EditPlaylistDialog open playlist={playlist} onClose={onClose} onPlaylistUpdated={onPlaylistUpdated} />);

    const name = screen.getByRole('textbox', { name: 'Playlist Name' });
    const description = screen.getByRole('textbox', { name: /description/i });
    expect(name).toHaveValue('Morning');
    expect(description).toHaveValue('Original description');
    await user.clear(description);
    await user.type(description, '  New description  ');
    await user.clear(name);
    await user.type(name, '  Evening  {Enter}');

    expect(updatePlaylist).toHaveBeenCalledExactlyOnceWith(7, {
      name: 'Evening', description: 'New description',
    });
    expect(toast.success).toHaveBeenCalledWith(expect.stringMatching(/updated successfully/));
    expect(toast.success).toHaveBeenCalledBefore(onPlaylistUpdated);
    expect(onPlaylistUpdated).toHaveBeenCalledBefore(onClose);
  });

  it('keeps the dialog open while saving and shows a failed update', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const onPlaylistUpdated = vi.fn();
    let fail!: (reason: Error) => void;
    vi.mocked(updatePlaylist).mockImplementationOnce(() => new Promise((_, reject) => { fail = reject; }));
    render(<EditPlaylistDialog open playlist={playlist} onClose={onClose} onPlaylistUpdated={onPlaylistUpdated} />);

    await user.click(screen.getByRole('button', { name: 'Save Changes' }));
    expect(screen.getByRole('button', { name: 'Saving...' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled();
    await user.keyboard('{Escape}');
    expect(onClose).not.toHaveBeenCalled();

    await act(async () => fail(new Error('offline')));
    expect(toast.error).toHaveBeenCalledWith('Failed to update playlist: offline');
    expect(onPlaylistUpdated).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: 'Save Changes' })).toBeEnabled();
  });

  it('rejects a blank name at the form handler', async () => {
    const { result } = renderHook(() => useEditPlaylistForm({ playlist, onClose: vi.fn() }));
    act(() => result.current.setName('  '));
    await act(() => result.current.handleSave());
    expect(toast.error).toHaveBeenCalledWith('Please enter a playlist name');
    expect(updatePlaylist).not.toHaveBeenCalled();
  });
});

describe('CreatePlaylistDialog', () => {
  it('uses the form to create a playlist with the selected tracks', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const onPlaylistCreated = vi.fn();
    vi.mocked(createPlaylist).mockResolvedValue(playlist);
    render(<CreatePlaylistDialog open onClose={onClose} onPlaylistCreated={onPlaylistCreated} initialTrackIds={[4, 9]} />);

    expect(screen.getByRole('button', { name: /^create/i })).toBeDisabled();
    const name = screen.getByRole('textbox', { name: 'Playlist Name' });
    await user.type(name, '  Morning  {Enter}');

    expect(createPlaylist).toHaveBeenCalledExactlyOnceWith({
      name: 'Morning', description: '', track_ids: [4, 9],
    });
    expect(onPlaylistCreated).toHaveBeenCalledWith(playlist);
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(name).toHaveValue('');
  });
});
