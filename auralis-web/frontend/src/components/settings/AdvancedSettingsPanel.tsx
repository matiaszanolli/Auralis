import React from 'react';
import {
  Box,
  TextField,
  Switch,
  FormControlLabel,
  Divider
} from '@mui/material';
import { SettingsUpdate } from '../../services/settingsService';
import { SectionContainer, SectionLabel, SectionDescription } from '../library/Styles/Dialog.styles';

interface AdvancedSettingsPanelProps {
  cacheSize: number;
  maxConcurrentScans: number;
  enableAnalytics: boolean;
  debugMode: boolean;
  onSettingChange: (key: keyof SettingsUpdate, value: any) => void;
}

/**
 * AdvancedSettingsPanel - Advanced/developer settings
 *
 * Manages:
 * - Cache size configuration
 * - Max concurrent scans
 * - Analytics toggle
 * - Debug mode toggle
 */
export const AdvancedSettingsPanel: React.FC<AdvancedSettingsPanelProps> = ({
  cacheSize,
  maxConcurrentScans,
  enableAnalytics,
  debugMode,
  onSettingChange
}) => {
  return (
    <Box>
      <SectionContainer>
        <SectionLabel>Cache Size (MB)</SectionLabel>
        <TextField
          type="number"
          fullWidth
          value={cacheSize}
          onChange={(e) => onSettingChange('cache_size', parseInt(e.target.value))}
          inputProps={{ min: 128, max: 8192 }}
        />
        <SectionDescription>
          Amount of disk space for processed audio cache
        </SectionDescription>
      </SectionContainer>

      <Divider sx={{ my: 3 }} />

      <SectionContainer>
        <SectionLabel>Max Concurrent Scans</SectionLabel>
        <TextField
          type="number"
          fullWidth
          value={maxConcurrentScans}
          onChange={(e) => onSettingChange('max_concurrent_scans', parseInt(e.target.value))}
          inputProps={{ min: 1, max: 16 }}
        />
        <SectionDescription>
          Number of parallel threads for library scanning
        </SectionDescription>
      </SectionContainer>

      <Divider sx={{ my: 3 }} />

      <SectionContainer>
        <FormControlLabel
          control={
            <Switch
              checked={enableAnalytics}
              onChange={(e) => onSettingChange('enable_analytics', e.target.checked)}
            />
          }
          label="Enable analytics"
        />
        <SectionDescription>
          Collect anonymous usage data to improve Auralis
        </SectionDescription>
      </SectionContainer>

      <Divider sx={{ my: 3 }} />

      <SectionContainer>
        <FormControlLabel
          control={
            <Switch
              checked={debugMode}
              onChange={(e) => onSettingChange('debug_mode', e.target.checked)}
            />
          }
          label="Debug mode"
        />
        <SectionDescription>
          Show detailed logging and diagnostic information
        </SectionDescription>
      </SectionContainer>
    </Box>
  );
};

export default AdvancedSettingsPanel;
