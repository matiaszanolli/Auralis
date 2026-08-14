/**
 * PlaylistSection Component
 *
 * Subcomponent for ContextMenu that handles playlist-specific options:
 * - List of existing playlists
 * - Add to playlist actions
 * - Create new playlist action
 */

import {
  Divider,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Box,
  styled,
} from '@mui/material';
import PlaylistAdd from '@mui/icons-material/PlaylistAdd';
import Add from '@mui/icons-material/Add';
import * as playlistService from '@/services/playlistService';
import { tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';

const PlaylistMenuItem = styled(MenuItem)({
  fontSize: tokens.typography.fontSize.sm,
  color: themeVars.textSecondary,
  // 48px is a nesting indent for sub-items, not a spacing step — kept
  // literal deliberately (#4663); the rest map to the scale exactly.
  padding: `${tokens.spacing.cluster} ${tokens.spacing.group} ${tokens.spacing.cluster} 48px`,
  transition: tokens.transitions.hover_out,
  '&:hover': {
    background: tokens.colors.opacityScale.accent.veryLight,
    color: themeVars.textPrimary,
    transform: 'translateX(2px)',
  },
});

const CreateNewMenuItem = styled(MenuItem)({
  fontSize: tokens.typography.fontSize.sm,
  color: tokens.colors.accent.primary,
  // 48px is a nesting indent for sub-items, not a spacing step — kept
  // literal deliberately (#4663); the rest map to the scale exactly.
  padding: `${tokens.spacing.cluster} ${tokens.spacing.group} ${tokens.spacing.cluster} 48px`,
  fontWeight: tokens.typography.fontWeight.semibold,
  transition: tokens.transitions.hover_out,
  '&:hover': {
    background: tokens.colors.opacityScale.accent.lighter,
    transform: 'translateX(2px)',
  },
});

const SectionLabel = styled(Box)({
  fontSize: tokens.typography.fontSize.xs,
  fontWeight: tokens.typography.fontWeight.semibold,
  // #4635: xs label text needs AA 4.5:1; disabled (40%) is only calibrated
  // for the 3:1 large-text floor. Same fix as the sidebar labels in #4451.
  color: themeVars.textMuted,
  textTransform: 'uppercase',
  letterSpacing: '0.5px',
  padding: `${tokens.spacing.cluster} ${tokens.spacing.group} ${tokens.spacing.xs} ${tokens.spacing.group}`,
});

export interface PlaylistSectionProps {
  playlists: playlistService.Playlist[];
  isLoadingPlaylists: boolean;
  onAddToPlaylist: (playlistId: number, playlistName: string) => Promise<void>;
  onCreateNewPlaylist: () => void;
}

export const PlaylistSection = ({
  playlists,
  isLoadingPlaylists: _isLoadingPlaylists,
  onAddToPlaylist,
  onCreateNewPlaylist,
}: PlaylistSectionProps) => {
  return (
    <>
      <Divider sx={{ borderColor: tokens.colors.opacityScale.accent.minimal, my: 1 }} />
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
        <Add sx={{ fontSize: tokens.typography.fontSize.md, mr: 1 }} />
        Create New Playlist
      </CreateNewMenuItem>
    </>
  );
};

export default PlaylistSection;
