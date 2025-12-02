/**
 * PlaylistSection Component
 *
 * Subcomponent for ContextMenu that handles playlist-specific options:
 * - List of existing playlists
 * - Add to playlist actions
 * - Create new playlist action
 */

import React from 'react';
import {
  Divider,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Box,
  styled,
} from '@mui/material';
import { PlaylistAdd, Add } from '@mui/icons-material';
import * as playlistService from '../../../services/playlistService';
import { auroraOpacity } from '../../library/Styles/Color.styles';
import { tokens } from '@/design-system/tokens';

const PlaylistMenuItem = styled(MenuItem)({
  fontSize: '13px',
  color: tokens.colors.text.secondary,
  padding: '8px 16px 8px 48px',
  transition: 'all 0.2s ease',
  '&:hover': {
    background: auroraOpacity.veryLight,
    color: tokens.colors.text.primary,
    transform: 'translateX(2px)',
  },
});

const CreateNewMenuItem = styled(MenuItem)({
  fontSize: '13px',
  color: tokens.colors.accent.primary,
  padding: '8px 16px 8px 48px',
  fontWeight: 600,
  transition: 'all 0.2s ease',
  '&:hover': {
    background: auroraOpacity.lighter,
    transform: 'translateX(2px)',
  },
});

const SectionLabel = styled(Box)({
  fontSize: '11px',
  fontWeight: 600,
  color: tokens.colors.text.disabled,
  textTransform: 'uppercase',
  letterSpacing: '0.5px',
  padding: '8px 16px 4px 16px',
});

export interface PlaylistSectionProps {
  playlists: playlistService.Playlist[];
  isLoadingPlaylists: boolean;
  onAddToPlaylist: (playlistId: number, playlistName: string) => Promise<void>;
  onCreateNewPlaylist: () => void;
}

export const PlaylistSection: React.FC<PlaylistSectionProps> = ({
  playlists,
  isLoadingPlaylists,
  onAddToPlaylist,
  onCreateNewPlaylist,
}) => {
  return (
    <>
      <Divider sx={{ borderColor: auroraOpacity.minimal, my: 1 }} />
      <MenuItem disabled>
        <ListItemIcon>
          <PlaylistAdd />
        </ListItemIcon>
        <ListItemText>Add to Playlist</ListItemText>
      </MenuItem>

      {playlists.length > 0 && (
        <>
          <SectionLabel>Your Playlists</SectionLabel>
          {playlists.map((playlist) => (
            <PlaylistMenuItem
              key={playlist.id}
              onClick={() => onAddToPlaylist(playlist.id, playlist.name)}
            >
              {playlist.name} ({playlist.track_count})
            </PlaylistMenuItem>
          ))}
        </>
      )}

      <CreateNewMenuItem onClick={onCreateNewPlaylist}>
        <Add sx={{ fontSize: '16px', mr: 1 }} />
        Create New Playlist
      </CreateNewMenuItem>
    </>
  );
};

export default PlaylistSection;
