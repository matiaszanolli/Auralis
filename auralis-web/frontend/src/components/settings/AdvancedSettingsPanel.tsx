import { useState, useCallback, useEffect } from 'react';
import {
  Box,
  TextField,
  Switch,
  FormControlLabel,
  Divider
} from '@mui/material';
import { tokens } from '@/design-system';
import { resetLibrary, type OnSettingChange } from '@/services/settingsService';
import { SectionContainer, SectionLabel, SectionDescription } from '@/components/library/Styles/Dialog.styles';
import { ConfirmationDialog } from '@/components/shared/ui/ConfirmationDialog';
import { CacheStatsDashboard } from '@/components/shared/CacheStatsDashboard';
import { themeVars } from '@/theme/semanticTheme';

interface AdvancedSettingsPanelProps {
  cacheSize: number;
  maxConcurrentScans: number;
  enableAnalytics: boolean;
  debugMode: boolean;
  onSettingChange: OnSettingChange;
}

interface NumericSettingFieldProps {
  label: string;
  ariaLabel: string;
  description: string;
  value: number;
  min: number;
  max: number;
  onCommit: (value: number) => void;
}

/**
 * Numeric field that edits a local draft string and commits a clamped number
 * only when the draft parses (#5635). parseInt('') is NaN, which a controlled
 * TextField renders as the React NaN warning and JSON.stringify serialises as
 * null in the Save body; a cleared draft instead just stops committing until
 * the field parses again, and the last committed value rides out the gap.
 */
function NumericSettingField({
  label,
  ariaLabel,
  description,
  value,
  min,
  max,
  onCommit,
}: NumericSettingFieldProps) {
  const [draft, setDraft] = useState(String(value));

  useEffect(() => {
    // Re-sync only when the committed value changed elsewhere (settings
    // loaded/reset); the parent round-tripping the value just typed must not
    // clobber the draft mid-edit.
    setDraft((prev) => (Number.parseInt(prev, 10) === value ? prev : String(value)));
  }, [value]);

  return (
    <SectionContainer>
      <SectionLabel>{label}</SectionLabel>
      <TextField
        type="number"
        fullWidth
        value={draft}
        onChange={(e) => {
          setDraft(e.target.value);
          const parsed = Number.parseInt(e.target.value, 10);
          if (!Number.isNaN(parsed)) {
            onCommit(Math.min(max, Math.max(min, parsed)));
          }
        }}
        slotProps={{ htmlInput: { min, max, 'aria-label': ariaLabel } }}
      />
      <SectionDescription>{description}</SectionDescription>
    </SectionContainer>
  );
}

/**
 * AdvancedSettingsPanel - Advanced/developer settings
 *
 * Manages:
 * - Cache size configuration
 * - Live cache statistics (#4579 — CacheStatsDashboard had no render site, so
 *   the cache telemetry endpoints and their WS invalidation were unreachable)
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
      <NumericSettingField
        label="Cache Size (MB)"
        ariaLabel="Cache size (MB)"
        description="Amount of disk space for processed audio cache"
        value={cacheSize}
        min={128}
        max={8192}
        onCommit={(v) => onSettingChange('cache_size', v)}
      />

      <Divider sx={{ my: 3 }} />

      <SectionContainer>
        <SectionLabel>Cache Statistics</SectionLabel>
        <CacheStatsDashboard />
        <SectionDescription>
          Live hit rates and cache sizes. Refreshes automatically, and
          immediately when a cache is cleared.
        </SectionDescription>
      </SectionContainer>

      <Divider sx={{ my: 3 }} />

      <NumericSettingField
        label="Max Concurrent Scans"
        ariaLabel="Max concurrent scans"
        description="Number of parallel threads for library scanning"
        value={maxConcurrentScans}
        min={1}
        max={16}
        onCommit={(v) => onSettingChange('max_concurrent_scans', v)}
      />

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
          borderRadius: tokens.borderRadius.sm,
          border: `1px solid ${tokens.colors.semantic.error}`,
          background: tokens.colors.utility.errorBg,
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
            color: themeVars.textSecondary,
            marginBottom: tokens.spacing.md,
            lineHeight: tokens.typography.lineHeight.normal,
          }}
        >
          Permanently delete all tracks, albums, artists, playlists, fingerprints,
          and playback history from your library. Your audio files on disk will not
          be affected.
        </div>
        <Box
          component="button"
          onClick={() => setShowResetConfirm(true)}
          sx={{
            padding: `${tokens.spacing.sm} ${tokens.spacing.lg}`,
            background: tokens.colors.semantic.error,
            border: 'none',
            borderRadius: '6px',
            color: themeVars.textPrimary,
            fontSize: tokens.typography.fontSize.sm,
            fontWeight: tokens.typography.fontWeight.semibold,
            cursor: 'pointer',
            opacity: 0.9,
            transition: tokens.transitions.hover_out,
            '&:hover': {
              opacity: 1,
            },
          }}
        >
          Reset Library
        </Box>
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
