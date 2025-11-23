import React from 'react';
import {
  Box,
  Switch,
  FormControlLabel,
  Slider,
  Divider
} from '@mui/material';
import { SectionContainer, SectionLabel, SectionDescription } from '../library/Styles/Dialog.styles';

interface PlaybackSettingsPanelProps {
  gaplessEnabled: boolean;
  crossfadeEnabled: boolean;
  crossfadeDuration: number;
  replayGainEnabled: boolean;
  volume: number;
  onSettingChange: (key: string, value: any) => void;
}

/**
 * PlaybackSettingsPanel - Playback control settings
 *
 * Manages:
 * - Gapless playback toggle
 * - Crossfade toggle and duration slider
 * - Replay gain toggle
 * - Default volume slider
 */
export const PlaybackSettingsPanel: React.FC<PlaybackSettingsPanelProps> = ({
  gaplessEnabled,
  crossfadeEnabled,
  crossfadeDuration,
  replayGainEnabled,
  volume,
  onSettingChange
}) => {
  return (
    <Box>
      <SectionContainer>
        <FormControlLabel
          control={
            <Switch
              checked={gaplessEnabled}
              onChange={(e) => onSettingChange('gapless_enabled', e.target.checked)}
            />
          }
          label="Gapless playback"
        />
        <SectionDescription>
          Eliminate silence between tracks for seamless listening
        </SectionDescription>
      </SectionContainer>

      <Divider sx={{ my: 3 }} />

      <SectionContainer>
        <FormControlLabel
          control={
            <Switch
              checked={crossfadeEnabled}
              onChange={(e) => onSettingChange('crossfade_enabled', e.target.checked)}
            />
          }
          label="Crossfade"
        />
        <SectionDescription>
          Smoothly transition between tracks
        </SectionDescription>
      </SectionContainer>

      {crossfadeEnabled && (
        <SectionContainer>
          <SectionLabel>Crossfade Duration: {crossfadeDuration.toFixed(1)}s</SectionLabel>
          <Slider
            value={crossfadeDuration}
            onChange={(e, v) => onSettingChange('crossfade_duration', v)}
            min={0}
            max={10}
            step={0.5}
            valueLabelDisplay="auto"
          />
        </SectionContainer>
      )}

      <Divider sx={{ my: 3 }} />

      <SectionContainer>
        <FormControlLabel
          control={
            <Switch
              checked={replayGainEnabled}
              onChange={(e) => onSettingChange('replay_gain_enabled', e.target.checked)}
            />
          }
          label="Replay Gain"
        />
        <SectionDescription>
          Normalize volume levels across tracks
        </SectionDescription>
      </SectionContainer>

      <Divider sx={{ my: 3 }} />

      <SectionContainer>
        <SectionLabel>Default Volume: {Math.round(volume * 100)}%</SectionLabel>
        <Slider
          value={volume}
          onChange={(e, v) => onSettingChange('volume', v)}
          min={0}
          max={1}
          step={0.01}
          valueLabelDisplay="auto"
          valueLabelFormat={(v) => `${Math.round(v * 100)}%`}
        />
      </SectionContainer>
    </Box>
  );
};

export default PlaybackSettingsPanel;
