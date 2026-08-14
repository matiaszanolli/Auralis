/**
 * AddToPlaylistMenu - Dropdown menu for the batch "Add to Playlist" action
 *
 * Fetches the user's playlists when opened and lets them pick one to add
 * the current selection to. Fixes #4240 — this action previously showed a
 * "Coming soon!" toast with no API call.
 */

import { useEffect, useState } from 'react';
import { Menu, MenuItem, CircularProgress, Typography } from '@mui/material';
import { tokens } from '@/design-system';
import { getPlaylists, type Playlist } from '@/services/playlistService';
import { themeVars } from '@/theme/semanticTheme';

interface AddToPlaylistMenuProps {
  anchorEl: HTMLElement | null;
  onClose: () => void;
  onAddToPlaylist: (playlistId: number, playlistName: string) => Promise<void>;
}

export const AddToPlaylistMenu = ({
  anchorEl,
  onClose,
  onAddToPlaylist,
}: AddToPlaylistMenuProps) => {
  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!anchorEl) return;
    // #4614: abort the in-flight request on close/reopen, not just discard its
    // result. The menu can be reopened faster than the fetch completes, and
    // before the factory could forward a signal the superseded request ran to
    // completion with no consumer.
    const controller = new AbortController();
    setLoading(true);
    getPlaylists(undefined, controller.signal)
      .then((response) => {
        if (!controller.signal.aborted) setPlaylists(response.playlists);
      })
      .catch(() => {
        // An abort is expected on close/reopen — not a user-facing failure.
        if (!controller.signal.aborted) setPlaylists([]);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => {
      controller.abort();
    };
  }, [anchorEl]);

  const handleSelect = (playlist: Playlist) => {
    onClose();
    void onAddToPlaylist(playlist.id, playlist.name);
  };

  return (
    <Menu
      anchorEl={anchorEl}
      open={Boolean(anchorEl)}
      onClose={onClose}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
      transformOrigin={{ vertical: 'top', horizontal: 'right' }}
      slotProps={{
        paper: {
          sx: {
            background: tokens.gradients.darkSubtle,
            border: `1px solid ${tokens.colors.opacityScale.accent.standard}`,
            borderRadius: '12px',
            mt: 1,
            minWidth: 220,
          },
        },
      }}
    >
      {loading && (
        <MenuItem disabled sx={{ justifyContent: 'center' }}>
          <CircularProgress size={20} />
        </MenuItem>
      )}

      {!loading && playlists.length === 0 && (
        <MenuItem disabled>
          <Typography variant="body2" sx={{ color: themeVars.textMuted }}>
            No playlists yet
          </Typography>
        </MenuItem>
      )}

      {!loading &&
        playlists.map((playlist) => (
          <MenuItem
            key={playlist.id}
            onClick={() => handleSelect(playlist)}
            sx={{ color: themeVars.textStrong }}
          >
            {playlist.name} ({playlist.track_count})
          </MenuItem>
        ))}
    </Menu>
  );
};

export default AddToPlaylistMenu;
