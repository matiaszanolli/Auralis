/**
 * AutoScanSettings - Auto-scan toggle and scan interval configuration
 */

import React from 'react';
import { Box, Switch, FormControlLabel, TextField, Divider } from '@mui/material';
import { SectionContainer, SectionLabel, SectionDescription } from '../library/Styles/Dialog.styles';

interface AutoScanSettingsProps {
  autoScan: boolean;
  scanInterval: number;
  onSettingChange: (key: string, value: any) => void;
}

export const AutoScanSettings: React.FC<AutoScanSettingsProps> = ({
  autoScan,
  scanInterval,
  onSettingChange,
}) => {
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
          Automatically scan for new files at regular intervals
        </SectionDescription>
      </SectionContainer>

      {autoScan && (
        <SectionContainer>
          <SectionLabel>Scan Interval (seconds)</SectionLabel>
          <TextField
            type="number"
            fullWidth
            value={scanInterval}
            onChange={(e) => onSettingChange('scan_interval', parseInt(e.target.value))}
            inputProps={{ min: 60, max: 86400 }}
          />
        </SectionContainer>
      )}
    </Box>
  );
};

export default AutoScanSettings;
