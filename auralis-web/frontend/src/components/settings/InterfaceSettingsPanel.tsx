import React from 'react';
import {
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Switch,
  FormControlLabel,
  Divider
} from '@mui/material';
import { SettingsUpdate } from '../../services/settingsService';
import { SectionContainer, SectionDescription } from '../library/Styles/Dialog.styles';

interface InterfaceSettingsPanelProps {
  theme: string;
  showVisualizations: boolean;
  miniPlayerOnClose: boolean;
  onSettingChange: (key: keyof SettingsUpdate, value: any) => void;
}

/**
 * InterfaceSettingsPanel - UI and theme settings
 *
 * Manages:
 * - Theme selection (dark/light)
 * - Visualizations toggle
 * - Mini player on close toggle
 */
export const InterfaceSettingsPanel: React.FC<InterfaceSettingsPanelProps> = ({
  theme,
  showVisualizations,
  miniPlayerOnClose,
  onSettingChange
}) => {
  return (
    <Box>
      <SectionContainer>
        <FormControl fullWidth>
          <InputLabel>Theme</InputLabel>
          <Select
            value={theme}
            onChange={(e) => onSettingChange('theme', e.target.value)}
            label="Theme"
          >
            <MenuItem value="dark">Dark</MenuItem>
            <MenuItem value="light">Light</MenuItem>
          </Select>
        </FormControl>
      </SectionContainer>

      <Divider sx={{ my: 3 }} />

      <SectionContainer>
        <FormControlLabel
          control={
            <Switch
              checked={showVisualizations}
              onChange={(e) => onSettingChange('show_visualizations', e.target.checked)}
            />
          }
          label="Show visualizations"
        />
        <SectionDescription>
          Display audio visualizations and waveforms
        </SectionDescription>
      </SectionContainer>

      <Divider sx={{ my: 3 }} />

      <SectionContainer>
        <FormControlLabel
          control={
            <Switch
              checked={miniPlayerOnClose}
              onChange={(e) => onSettingChange('mini_player_on_close', e.target.checked)}
            />
          }
          label="Mini player on close"
        />
        <SectionDescription>
          Show mini player when closing main window
        </SectionDescription>
      </SectionContainer>
    </Box>
  );
};

export default InterfaceSettingsPanel;
