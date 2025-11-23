import React from 'react';
import {
  Box,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Divider
} from '@mui/material';
import { SectionContainer, SectionDescription } from '../library/Styles/Dialog.styles';

interface AudioSettingsPanelProps {
  outputDevice: string;
  bitDepth: number;
  sampleRate: number;
  onSettingChange: (key: string, value: any) => void;
}

/**
 * AudioSettingsPanel - Audio device and quality settings
 *
 * Manages:
 * - Output device selection
 * - Bit depth (16, 24, 32 bit)
 * - Sample rate (44.1kHz, 48kHz, 96kHz, 192kHz)
 */
export const AudioSettingsPanel: React.FC<AudioSettingsPanelProps> = ({
  outputDevice,
  bitDepth,
  sampleRate,
  onSettingChange
}) => {
  return (
    <Box>
      <SectionContainer>
        <FormControl fullWidth>
          <InputLabel>Output Device</InputLabel>
          <Select
            value={outputDevice}
            onChange={(e) => onSettingChange('output_device', e.target.value)}
            label="Output Device"
          >
            <MenuItem value="default">Default</MenuItem>
            {/* Add more devices here when available */}
          </Select>
        </FormControl>
      </SectionContainer>

      <Divider sx={{ my: 3 }} />

      <SectionContainer>
        <FormControl fullWidth>
          <InputLabel>Bit Depth</InputLabel>
          <Select
            value={bitDepth}
            onChange={(e) => onSettingChange('bit_depth', e.target.value)}
            label="Bit Depth"
          >
            <MenuItem value={16}>16-bit</MenuItem>
            <MenuItem value={24}>24-bit</MenuItem>
            <MenuItem value={32}>32-bit</MenuItem>
          </Select>
        </FormControl>
        <SectionDescription>
          Higher bit depth provides better dynamic range
        </SectionDescription>
      </SectionContainer>

      <Divider sx={{ my: 3 }} />

      <SectionContainer>
        <FormControl fullWidth>
          <InputLabel>Sample Rate</InputLabel>
          <Select
            value={sampleRate}
            onChange={(e) => onSettingChange('sample_rate', e.target.value)}
            label="Sample Rate"
          >
            <MenuItem value={44100}>44.1 kHz (CD Quality)</MenuItem>
            <MenuItem value={48000}>48 kHz (Studio)</MenuItem>
            <MenuItem value={96000}>96 kHz (Hi-Res)</MenuItem>
            <MenuItem value={192000}>192 kHz (Ultra Hi-Res)</MenuItem>
          </Select>
        </FormControl>
        <SectionDescription>
          Higher sample rates capture more audio detail
        </SectionDescription>
      </SectionContainer>
    </Box>
  );
};

export default AudioSettingsPanel;
