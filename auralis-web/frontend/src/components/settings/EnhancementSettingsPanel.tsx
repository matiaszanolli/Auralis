
import type { OnSettingChange } from '@/services/settingsService';
import { isEnhancementPreset } from '@/types/domain';
import { SectionContainer, SectionLabel, SectionDescription } from '@/components/library/Styles/Dialog.styles';
import { Slider } from '@/design-system';
import { Box, FormControl, InputLabel, Select, MenuItem, Switch, FormControlLabel, Divider } from '@mui/material';

interface EnhancementSettingsPanelProps {
  defaultPreset: string;
  autoEnhance: boolean;
  enhancementIntensity: number;
  onSettingChange: OnSettingChange;
}

/**
 * EnhancementSettingsPanel - Audio enhancement settings
 *
 * Manages:
 * - Default enhancement preset selection
 * - Auto-enhance toggle
 * - Enhancement intensity slider
 */
export const EnhancementSettingsPanel = ({
  defaultPreset,
  autoEnhance,
  enhancementIntensity,
  onSettingChange
}: EnhancementSettingsPanelProps) => {
  return (
    <Box>
      <SectionContainer>
        <FormControl fullWidth>
          <InputLabel id="settings-enhancement-default-preset-label">Default Preset</InputLabel>
          {/* Only 'adaptive' is a valid preset now (#4861 follow-up) --
              'gentle'/'warm'/'bright'/'punchy' removed, not just hidden. */}
          <Select
            labelId="settings-enhancement-default-preset-label"
            value={defaultPreset}
            onChange={(e) => {
              if (isEnhancementPreset(e.target.value)) onSettingChange('default_preset', e.target.value);
            }}
            label="Default Preset"
          >
            <MenuItem value="adaptive">Adaptive</MenuItem>
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
          onChange={(_e, v) => onSettingChange('enhancement_intensity', v as number)}
          min={0}
          max={1}
          step={0.1}
          valueLabelDisplay="auto"
          valueLabelFormat={(v) => `${Math.round(v * 100)}%`}
          aria-label="Enhancement intensity"
          getAriaValueText={(v) => `${Math.round(v * 100)} percent`}
        />
        <SectionDescription>
          Adjust the strength of audio enhancement
        </SectionDescription>
      </SectionContainer>
    </Box>
  );
};

export default EnhancementSettingsPanel;
