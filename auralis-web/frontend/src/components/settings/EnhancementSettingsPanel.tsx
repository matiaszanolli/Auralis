import React from 'react';

import { SettingsUpdate } from '../../services/settingsService';
import { SectionContainer, SectionLabel, SectionDescription } from '../library/Styles/Dialog.styles';
import { Slider } from '@/design-system';
import { Box, FormControl, InputLabel, Select, MenuItem, Switch, FormControlLabel, Divider } from '@mui/material';

interface EnhancementSettingsPanelProps {
  defaultPreset: string;
  autoEnhance: boolean;
  enhancementIntensity: number;
  onSettingChange: (key: keyof SettingsUpdate, value: any) => void;
}

/**
 * EnhancementSettingsPanel - Audio enhancement settings
 *
 * Manages:
 * - Default enhancement preset selection
 * - Auto-enhance toggle
 * - Enhancement intensity slider
 */
export const EnhancementSettingsPanel: React.FC<EnhancementSettingsPanelProps> = ({
  defaultPreset,
  autoEnhance,
  enhancementIntensity,
  onSettingChange
}) => {
  return (
    <Box>
      <SectionContainer>
        <FormControl fullWidth>
          <InputLabel>Default Preset</InputLabel>
          <Select
            value={defaultPreset}
            onChange={(e) => onSettingChange('default_preset', e.target.value)}
            label="Default Preset"
          >
            <MenuItem value="adaptive">Adaptive</MenuItem>
            <MenuItem value="gentle">Gentle</MenuItem>
            <MenuItem value="warm">Warm</MenuItem>
            <MenuItem value="bright">Bright</MenuItem>
            <MenuItem value="punchy">Punchy</MenuItem>
          </Select>
        </FormControl>
        <SectionDescription>
          Default audio enhancement preset for playback
        </SectionDescription>
      </SectionContainer>

      <Divider sx={{ my: 3 }} />

      <SectionContainer>
        <FormControlLabel
          control={
            <Switch
              checked={autoEnhance}
              onChange={(e) => onSettingChange('auto_enhance', e.target.checked)}
            />
          }
          label="Auto-enhance playback"
        />
        <SectionDescription>
          Automatically apply enhancement to all tracks
        </SectionDescription>
      </SectionContainer>

      <Divider sx={{ my: 3 }} />

      <SectionContainer>
        <SectionLabel>Enhancement Intensity: {Math.round(enhancementIntensity * 100)}%</SectionLabel>
        <Slider
          value={enhancementIntensity}
          onChange={(e, v) => onSettingChange('enhancement_intensity', v)}
          min={0}
          max={1}
          step={0.1}
          valueLabelDisplay="auto"
          valueLabelFormat={(v) => `${Math.round(v * 100)}%`}
        />
        <SectionDescription>
          Adjust the strength of audio enhancement
        </SectionDescription>
      </SectionContainer>
    </Box>
  );
};

export default EnhancementSettingsPanel;
