import { useState, useCallback } from 'react';
import {
  Box,
  TextField,
  Switch,
  FormControlLabel,
  Divider
} from '@mui/material';
import { tokens } from '@/design-system';
import { SettingsUpdate, resetLibrary } from '@/services/settingsService';
import { SectionContainer, SectionLabel, SectionDescription } from '@/components/library/Styles/Dialog.styles';
import { ConfirmationDialog } from '@/components/shared/ui/ConfirmationDialog';

interface AdvancedSettingsPanelProps {
  cacheSize: number;
  maxConcurrentScans: number;
  enableAnalytics: boolean;
  debugMode: boolean;
  onSettingChange: (key: keyof SettingsUpdate, value: SettingsUpdate[keyof SettingsUpdate]) => void;
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
export const AdvancedSettingsPanel = ({
  cacheSize,
  maxConcurrentScans,
  enableAnalytics,
  debugMode,
  onSettingChange
}: AdvancedSettingsPanelProps) => {
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [isResetting, setIsResetting] = useState(false);

  const handleResetLibrary = useCallback(async () => {
    setIsResetting(true);
    try {
      await resetLibrary();
      setShowResetConfirm(false);
      // Reload the page so all views reflect the empty library
      window.location.reload();
    } catch (error) {
      console.error('Failed to reset library:', error);
      setIsResetting(false);
    }
  }, []);

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

      {/* Danger Zone */}
      <div
        style={{
          marginTop: tokens.spacing.xl,
          padding: tokens.spacing.lg,
          borderRadius: '8px',
          border: `1px solid ${tokens.colors.semantic.error}`,
          background: 'rgba(239, 68, 68, 0.06)',
        }}
      >
        <div
          style={{
            fontSize: tokens.typography.fontSize.lg,
            fontWeight: tokens.typography.fontWeight.semibold,
            color: tokens.colors.semantic.error,
            marginBottom: tokens.spacing.sm,
          }}
        >
          Danger Zone
        </div>
        <div
          style={{
            fontSize: tokens.typography.fontSize.sm,
            color: tokens.colors.text.secondary,
            marginBottom: tokens.spacing.md,
            lineHeight: tokens.typography.lineHeight.normal,
          }}
        >
          Permanently delete all tracks, albums, artists, playlists, fingerprints,
          and playback history from your library. Your audio files on disk will not
          be affected.
        </div>
        <button
          onClick={() => setShowResetConfirm(true)}
          style={{
            padding: `${tokens.spacing.sm} ${tokens.spacing.lg}`,
            background: tokens.colors.semantic.error,
            border: 'none',
            borderRadius: '6px',
            color: tokens.colors.text.primary,
            fontSize: tokens.typography.fontSize.sm,
            fontWeight: tokens.typography.fontWeight.semibold,
            cursor: 'pointer',
            opacity: 0.9,
            transition: 'all 0.2s',
          }}
          onMouseOver={(e) => {
            e.currentTarget.style.opacity = '1';
          }}
          onMouseOut={(e) => {
            e.currentTarget.style.opacity = '0.9';
          }}
        >
          Reset Library
        </button>
      </div>

      {showResetConfirm && (
        <ConfirmationDialog
          title="Reset Library?"
          message="This will permanently delete all tracks, albums, artists, playlists, fingerprints, and playback history. Your audio files on disk will not be deleted. This action cannot be undone."
          confirmText={isResetting ? 'Resetting...' : 'Yes, Reset Library'}
          isDangerous
          disabled={isResetting}
          onConfirm={handleResetLibrary}
          onCancel={() => setShowResetConfirm(false)}
        />
      )}
    </Box>
  );
};

export default AdvancedSettingsPanel;
