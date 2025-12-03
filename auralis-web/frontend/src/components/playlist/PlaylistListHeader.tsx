import React, { useCallback } from 'react';

import { QueueMusic, Add, ExpandMore, ExpandLess } from '@mui/icons-material';
import { SectionHeader, SectionTitle, AddButton } from './PlaylistList.styles';
import { Tooltip } from '@/design-system';
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
export const PlaylistListHeader: React.FC<PlaylistListHeaderProps> = ({
  playlistCount,
  expanded,
  onExpandToggle,
  onCreateClick,
}) => {
  const handleCreateClick = useCallback(
    (e: React.MouseEvent) => {
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
        <QueueMusic sx={{ fontSize: '18px' }} />
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
