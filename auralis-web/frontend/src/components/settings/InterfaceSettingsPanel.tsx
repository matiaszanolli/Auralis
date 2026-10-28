
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
import { useTheme } from '@/contexts/ThemeContext';
import type { ThemeMode } from '@/theme/semanticTheme';
import { SettingsUpdate } from '@/services/settingsService';
import { SectionContainer, SectionDescription } from '@/components/library/Styles/Dialog.styles';

interface InterfaceSettingsPanelProps {
  showVisualizations: boolean;
  miniPlayerOnClose: boolean;
  onSettingChange: (key: keyof SettingsUpdate, value: SettingsUpdate[keyof SettingsUpdate]) => void;
}

/**
 * InterfaceSettingsPanel - UI and theme settings
 *
 * Manages:
 * - Theme selection (dark/light) — the live ThemeContext mode, not a stored string (#6019)
 * - Visualizations toggle
 * - Mini player on close toggle
 */
export const InterfaceSettingsPanel = ({
  showVisualizations,
  miniPlayerOnClose,
  onSettingChange
}: InterfaceSettingsPanelProps) => {
  const { mode, setTheme } = useTheme();

  const handleThemeChange = (next: ThemeMode) => {
    setTheme(next);
    onSettingChange('theme', next);
  };

  return (
    <Box>
      <SectionContainer>
        <FormControl fullWidth>
          <InputLabel id="settings-interface-theme-label">Theme</InputLabel>
          <Select
            labelId="settings-interface-theme-label"
            value={mode}
            onChange={(e) => handleThemeChange(e.target.value as ThemeMode)}
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
