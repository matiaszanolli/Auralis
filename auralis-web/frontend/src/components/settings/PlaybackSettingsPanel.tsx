import type { OnSettingChange } from '@/services/settingsService';
import { SectionContainer, SectionLabel } from '@/components/library/Styles/Dialog.styles';
import { Slider } from '@/design-system';
import { Box } from '@mui/material';

interface PlaybackSettingsPanelProps {
  volume: number;
  onSettingChange: OnSettingChange;
}

/**
 * PlaybackSettingsPanel - Playback control settings
 *
 * Manages the default volume. Do not add a playback toggle here before the
 * player or stream reads it: crossfade, gapless and replay-gain switches sat
 * here with no consumer (#6683).
 */
export const PlaybackSettingsPanel = ({ volume, onSettingChange }: PlaybackSettingsPanelProps) => {
  return (
    <Box>
      <SectionContainer>
        <SectionLabel>Default Volume: {Math.round(volume * 100)}%</SectionLabel>
        <Slider
          value={volume}
          onValueChange={(v) => onSettingChange('volume', v)}
          min={0}
          max={1}
          step={0.01}
          valueLabelDisplay="auto"
          valueLabelFormat={(v) => `${Math.round(v * 100)}%`}
          aria-label="Default volume"
          getAriaValueText={(v) => `${Math.round(v * 100)} percent`}
        />
      </SectionContainer>
    </Box>
  );
};

export default PlaybackSettingsPanel;
