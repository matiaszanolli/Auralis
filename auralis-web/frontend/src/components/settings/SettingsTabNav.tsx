import React from 'react';
import { Box, Tab } from '@mui/material';
import { StyledTabs } from '../library/Dialog.styles';

interface SettingsTabNavProps {
  activeTab: number;
  onTabChange: (event: React.SyntheticEvent, newValue: number) => void;
}

/**
 * SettingsTabNav - Tab navigation for settings dialog
 *
 * Manages switching between different settings categories:
 * - Library (folder scanning, auto-scan)
 * - Playback (gapless, crossfade, replay gain, volume)
 * - Audio (output device, bit depth, sample rate)
 * - Interface (theme, visualizations, mini player)
 * - Enhancement (preset, auto-enhance, intensity)
 * - Advanced (cache, concurrent scans, analytics, debug)
 */
export const SettingsTabNav: React.FC<SettingsTabNavProps> = ({ activeTab, onTabChange }) => {
  return (
    <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
      <StyledTabs value={activeTab} onChange={onTabChange}>
        <Tab label="Library" />
        <Tab label="Playback" />
        <Tab label="Audio" />
        <Tab label="Interface" />
        <Tab label="Enhancement" />
        <Tab label="Advanced" />
      </StyledTabs>
    </Box>
  );
};

export default SettingsTabNav;
