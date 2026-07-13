import { MouseEvent, useCallback } from 'react';
import QueueMusic from '@mui/icons-material/QueueMusic';
import Add from '@mui/icons-material/Add';
import ExpandMore from '@mui/icons-material/ExpandMore';
import ExpandLess from '@mui/icons-material/ExpandLess';
import { SectionHeader, SectionTitle, AddButton } from './PlaylistList.styles';
import { Tooltip, tokens } from '@/design-system';
import { Box } from '@mui/material';

interface PlaylistListHeaderProps {
  playlistCount: number;
  expanded: boolean;
  onExpandToggle: () => void;
  onCreateClick: () => void;
}

/**
 * PlaylistListHeader - Header with section title, count, and create button
 *
 * Displays:
 * - Playlist icon and count
 * - Create playlist button
 * - Expand/collapse toggle
 *
 * @example
 * <PlaylistListHeader
 *   playlistCount={5}
 *   expanded={true}
 *   onExpandToggle={handleToggle}
 *   onCreateClick={handleCreate}
 * />
 */
export const PlaylistListHeader = ({
  playlistCount,
  expanded,
  onExpandToggle,
  onCreateClick,
}: PlaylistListHeaderProps) => {
  const handleCreateClick = useCallback(
    (e: MouseEvent) => {
      e.stopPropagation();
      onCreateClick();
    },
    [onCreateClick]
  );

  return (
    <SectionHeader
      onClick={onExpandToggle}
      role="button"
      aria-label={expanded ? 'Collapse playlists' : 'Expand playlists'}
      aria-expanded={expanded}
    >
      <SectionTitle>
        <QueueMusic sx={{ fontSize: tokens.typography.fontSize.lg }} />
        Playlists ({playlistCount})
      </SectionTitle>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
        <Tooltip title="Create playlist">
          <AddButton onClick={handleCreateClick}>
            <Add />
          </AddButton>
        </Tooltip>
        {expanded ? <ExpandLess /> : <ExpandMore />}
      </Box>
    </SectionHeader>
  );
};

export default PlaylistListHeader;
