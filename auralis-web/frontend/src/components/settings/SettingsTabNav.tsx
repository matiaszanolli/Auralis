import { SyntheticEvent } from 'react';
import { Box, Tab } from '@mui/material';
import LibraryMusicIcon from '@mui/icons-material/LibraryMusic';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import TuneIcon from '@mui/icons-material/Tune';
import PaletteIcon from '@mui/icons-material/Palette';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import BuildIcon from '@mui/icons-material/Build';
import ScanDotIcon from '@mui/icons-material/FiberManualRecord';
import { DialogTabs } from '@/components/library/Styles/Dialog.styles';
import { tokens } from '@/design-system';

/** Ids shared by the tabs and the one visible panel (#6074). */
export const settingsTabId = (index: number): string => `settings-tab-${index}`;
export const SETTINGS_PANEL_ID = 'settings-panel';

interface SettingsTabNavProps {
  activeTab: number;
  onTabChange: (event: SyntheticEvent, newValue: number) => void;
  isScanning?: boolean;
}

const TABS = [
  { icon: <LibraryMusicIcon fontSize="small" />, label: 'Library' },
  { icon: <PlayArrowIcon fontSize="small" />, label: 'Playback' },
  { icon: <TuneIcon fontSize="small" />, label: 'Audio' },
  { icon: <PaletteIcon fontSize="small" />, label: 'Interface' },
  { icon: <AutoAwesomeIcon fontSize="small" />, label: 'Enhancement' },
  { icon: <BuildIcon fontSize="small" />, label: 'Advanced' },
];

/**
 * SettingsTabNav - Tab navigation for settings dialog
 *
 * Manages switching between different settings categories.
 * Shows a pulsing indicator on the Library tab while a scan is running.
 */
export const SettingsTabNav = ({
  activeTab,
  onTabChange,
  isScanning = false,
}: SettingsTabNavProps) => {
  const libraryLabel = (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
      Library
      {isScanning && (
        <ScanDotIcon
          sx={{
            fontSize: 8,
            color: tokens.colors.semantic.success,
            '@keyframes scanDotPulse': {
              '0%, 100%': { opacity: 1 },
              '50%': { opacity: 0.3 },
            },
            animation: 'scanDotPulse 1.5s ease-in-out infinite',
          }}
        />
      )}
    </Box>
  );

  return (
    <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
      <DialogTabs value={activeTab} onChange={onTabChange} aria-label="Settings sections">
        {TABS.map(({ icon, label }, index) => (
          <Tab
            key={index}
            id={settingsTabId(index)}
            aria-controls={SETTINGS_PANEL_ID}
            icon={icon}
            iconPosition="start"
            label={index === 0 ? libraryLabel : label}
          />
        ))}
      </DialogTabs>
    </Box>
  );
};

export default SettingsTabNav;
