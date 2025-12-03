import React from 'react';

import {
  FolderOpen,
  Refresh
} from '@mui/icons-material';
import SearchBar from '../navigation/SearchBar';
import ViewToggle, { ViewMode } from '../navigation/ViewToggle';
import { tokens } from '@/design-system';
import { Tooltip, IconButton } from '@/design-system';
import { Box, Paper, Typography } from '@mui/material';

interface LibrarySearchControlsProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  viewMode: ViewMode;
  onViewModeChange: (mode: ViewMode) => void;
  onScanFolder: () => void;
  onRefresh: () => void;
  scanning: boolean;
  loading: boolean;
  trackCount: number;
}

/**
 * LibrarySearchControls - Search bar and control buttons for library view
 *
 * Displays:
 * - Search input field
 * - View mode toggle (grid/list)
 * - Scan folder button
 * - Refresh library button
 * - Track count indicator
 */
export const LibrarySearchControls: React.FC<LibrarySearchControlsProps> = ({
  searchQuery,
  onSearchChange,
  viewMode,
  onViewModeChange,
  onScanFolder,
  onRefresh,
  scanning,
  loading,
  trackCount
}) => {
  return (
    <Paper
      elevation={2}
      sx={{
        p: tokens.spacing.lg,
        mb: tokens.spacing.xl,
        background: `${tokens.colors.bg.elevated}80`,
        backdropFilter: 'blur(10px)',
        borderRadius: tokens.borderRadius.lg
      }}
    >
      <Box sx={{ display: 'flex', gap: tokens.spacing.md, alignItems: 'center', flexWrap: 'wrap' }}>
        <Box sx={{ maxWidth: 400, flex: 1 }}>
          <SearchBar
            value={searchQuery}
            onChange={onSearchChange}
            placeholder="Search your music..."
          />
        </Box>

        <Box sx={{ display: 'flex', gap: 1, ml: 'auto' }}>
          <Tooltip title="Scan Folder">
            <span>
              <IconButton
                color="primary"
                onClick={onScanFolder}
                disabled={scanning}
              >
                <FolderOpen />
              </IconButton>
            </span>
          </Tooltip>

          <Tooltip title="Refresh Library">
            <span>
              <IconButton
                onClick={onRefresh}
                disabled={loading}
              >
                <Refresh />
              </IconButton>
            </span>
          </Tooltip>

          <ViewToggle value={viewMode} onChange={onViewModeChange} />
        </Box>

        <Typography variant="body2" color="text.secondary">
          {trackCount} songs
        </Typography>
      </Box>
    </Paper>
  );
};

export default LibrarySearchControls;
