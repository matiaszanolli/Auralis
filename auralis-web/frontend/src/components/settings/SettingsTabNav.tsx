import React from 'react';
import { Box, Tab } from '@mui/material';
import {
  LibraryMusic as LibraryMusicIcon,
  PlayArrow as PlayArrowIcon,
  Tune as TuneIcon,
  Palette as PaletteIcon,
  AutoAwesome as AutoAwesomeIcon,
  Build as BuildIcon,
  FiberManualRecord as ScanDotIcon,
} from '@mui/icons-material';
import { StyledTabs } from '../library/Styles/Dialog.styles';
import { tokens } from '@/design-system';

interface SettingsTabNavProps {
  activeTab: number;
  onTabChange: (event: React.SyntheticEvent, newValue: number) => void;
  isScanning?: boolean;
}

/**
 * SettingsTabNav - Tab navigation for settings dialog
 *
 * Manages switching between different settings categories.
 * Shows a pulsing indicator on the Library tab while a scan is running.
 */
export const SettingsTabNav: React.FC<SettingsTabNavProps> = ({
  activeTab,
  onTabChange,
  isScanning = false,
}) => {
  const libraryLabel = (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
      Library
      {isScanning && (
        <ScanDotIcon
          sx={{
            fontSize: 8,
            color: tokens.colors.semantic.success,
            '@keyframes pulse': {
              '0%, 100%': { opacity: 1 },
              '50%': { opacity: 0.3 },
            },
            animation: 'pulse 1.5s ease-in-out infinite',
          }}
        />
      )}
    </Box>
  );

  return (
    <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
      <StyledTabs value={activeTab} onChange={onTabChange}>
        <Tab icon={<LibraryMusicIcon fontSize="small" />} iconPosition="start" label={libraryLabel} />
        <Tab icon={<PlayArrowIcon fontSize="small" />} iconPosition="start" label="Playback" />
        <Tab icon={<TuneIcon fontSize="small" />} iconPosition="start" label="Audio" />
        <Tab icon={<PaletteIcon fontSize="small" />} iconPosition="start" label="Interface" />
        <Tab icon={<AutoAwesomeIcon fontSize="small" />} iconPosition="start" label="Enhancement" />
        <Tab icon={<BuildIcon fontSize="small" />} iconPosition="start" label="Advanced" />
      </StyledTabs>
    </Box>
  );
};

export default SettingsTabNav;
