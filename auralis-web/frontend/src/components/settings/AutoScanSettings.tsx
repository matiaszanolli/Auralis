/**
 * AutoScanSettings - Auto-scan toggle and human-readable scan interval selector
 */

import React from 'react';
import { Box, Switch, FormControlLabel, Select, MenuItem, FormControl, Divider } from '@mui/material';
import { SettingsUpdate } from '../../services/settingsService';
import { SectionContainer, SectionLabel, SectionDescription } from '../library/Styles/Dialog.styles';

interface AutoScanSettingsProps {
  autoScan: boolean;
  scanInterval: number;
  onSettingChange: (key: keyof SettingsUpdate, value: any) => void;
}

const INTERVAL_OPTIONS: { label: string; seconds: number }[] = [
  { label: 'Every minute', seconds: 60 },
  { label: 'Every 5 minutes', seconds: 300 },
  { label: 'Every 15 minutes', seconds: 900 },
  { label: 'Every 30 minutes', seconds: 1800 },
  { label: 'Every hour', seconds: 3600 },
  { label: 'Every 6 hours', seconds: 21600 },
  { label: 'Every 24 hours', seconds: 86400 },
];

/** Map an arbitrary stored value to the nearest preset */
function nearestPreset(seconds: number): number {
  return INTERVAL_OPTIONS.reduce((prev, curr) =>
    Math.abs(curr.seconds - seconds) < Math.abs(prev.seconds - seconds) ? curr : prev
  ).seconds;
}

export const AutoScanSettings: React.FC<AutoScanSettingsProps> = ({
  autoScan,
  scanInterval,
  onSettingChange,
}) => {
  const selectedInterval = nearestPreset(scanInterval ?? 3600);

  return (
    <Box>
      <Divider sx={{ my: 3 }} />

      <SectionContainer>
        <FormControlLabel
          control={
            <Switch
              checked={autoScan}
              onChange={(e) => onSettingChange('auto_scan', e.target.checked)}
            />
          }
          label="Auto-scan library"
        />
        <SectionDescription>
          Automatically scan for new and removed files at regular intervals
        </SectionDescription>
      </SectionContainer>

      {autoScan && (
        <SectionContainer>
          <SectionLabel>Scan Interval</SectionLabel>
          <FormControl fullWidth size="small">
            <Select
              value={selectedInterval}
              onChange={(e) => onSettingChange('scan_interval', e.target.value)}
            >
              {INTERVAL_OPTIONS.map((opt) => (
                <MenuItem key={opt.seconds} value={opt.seconds}>
                  {opt.label}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </SectionContainer>
      )}
    </Box>
  );
};

export default AutoScanSettings;
