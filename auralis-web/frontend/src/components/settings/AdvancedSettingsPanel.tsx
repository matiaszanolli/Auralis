import { useState, useCallback, useId } from 'react';
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
import { useDialogAccessibility } from '@/hooks/shared/useDialogAccessibility';

interface AdvancedSettingsPanelProps {
  cacheSize: number;
  maxConcurrentScans: number;
  enableAnalytics: boolean;
  debugMode: boolean;
  onSettingChange: (key: keyof SettingsUpdate, value: any) => void;
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
            (e.target as HTMLButtonElement).style.opacity = '1';
          }}
          onMouseOut={(e) => {
            (e.target as HTMLButtonElement).style.opacity = '0.9';
          }}
        >
          Reset Library
        </button>
      </div>

      {showResetConfirm && (
        <ResetLibraryConfirmation
          isResetting={isResetting}
          onConfirm={handleResetLibrary}
          onCancel={() => setShowResetConfirm(false)}
        />
      )}
    </Box>
  );
};

function ResetLibraryConfirmation({
  isResetting,
  onConfirm,
  onCancel,
}: {
  isResetting: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const dialogRef = useDialogAccessibility(onCancel);
  const titleId = useId();

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0, 0, 0, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1300,
      }}
      onClick={onCancel}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        style={{
          background: tokens.colors.bg.secondary,
          borderRadius: '12px',
          border: `1px solid ${tokens.colors.semantic.error}`,
          padding: tokens.spacing.lg,
          maxWidth: '420px',
          boxShadow: '0 10px 40px rgba(0, 0, 0, 0.3)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3
          id={titleId}
          style={{
            margin: `0 0 ${tokens.spacing.md} 0`,
            fontSize: tokens.typography.fontSize.lg,
            fontWeight: tokens.typography.fontWeight.semibold,
            color: tokens.colors.semantic.error,
          }}
        >
          Reset Library?
        </h3>

        <p
          style={{
            margin: `0 0 ${tokens.spacing.lg} 0`,
            fontSize: tokens.typography.fontSize.base,
            color: tokens.colors.text.secondary,
            lineHeight: tokens.typography.lineHeight.normal,
          }}
        >
          This will permanently delete all tracks, albums, artists, playlists,
          fingerprints, and playback history. Your audio files on disk will not
          be deleted. This action cannot be undone.
        </p>

        <div
          style={{
            display: 'flex',
            gap: tokens.spacing.md,
            justifyContent: 'flex-end',
          }}
        >
          <button
            onClick={onCancel}
            disabled={isResetting}
            style={{
              padding: `${tokens.spacing.sm} ${tokens.spacing.lg}`,
              background: tokens.colors.bg.tertiary,
              border: `1px solid ${tokens.colors.border.light}`,
              borderRadius: '6px',
              color: tokens.colors.text.primary,
              cursor: isResetting ? 'not-allowed' : 'pointer',
              fontSize: tokens.typography.fontSize.sm,
              fontWeight: tokens.typography.fontWeight.medium,
              transition: 'all 0.2s',
            }}
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={isResetting}
            style={{
              padding: `${tokens.spacing.sm} ${tokens.spacing.lg}`,
              background: tokens.colors.semantic.error,
              border: 'none',
              borderRadius: '6px',
              color: tokens.colors.text.primary,
              cursor: isResetting ? 'not-allowed' : 'pointer',
              fontSize: tokens.typography.fontSize.sm,
              fontWeight: tokens.typography.fontWeight.semibold,
              opacity: isResetting ? 0.6 : 0.9,
              transition: 'all 0.2s',
            }}
          >
            {isResetting ? 'Resetting...' : 'Yes, Reset Library'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default AdvancedSettingsPanel;
