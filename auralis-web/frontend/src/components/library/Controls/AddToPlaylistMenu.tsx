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
    let cancelled = false;
    setLoading(true);
    getPlaylists()
      .then((response) => {
        if (!cancelled) setPlaylists(response.playlists);
      })
      .catch(() => {
        if (!cancelled) setPlaylists([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
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
          <Typography variant="body2" sx={{ color: tokens.colors.text.disabled }}>
            No playlists yet
          </Typography>
        </MenuItem>
      )}

      {!loading &&
        playlists.map((playlist) => (
          <MenuItem
            key={playlist.id}
            onClick={() => handleSelect(playlist)}
            sx={{ color: tokens.colors.text.primaryFull }}
          >
            {playlist.name} ({playlist.track_count})
          </MenuItem>
        ))}
    </Menu>
  );
};

export default AddToPlaylistMenu;
