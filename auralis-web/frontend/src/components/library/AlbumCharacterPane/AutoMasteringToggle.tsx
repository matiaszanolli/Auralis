import { useCallback } from 'react';
import { Box } from '@mui/material';
import { tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';
import { EnhancementToggle } from '@/components/shared/EnhancementToggle';
import { useToast } from '@/components/shared/Toast';
import { useEnhancementControl } from '@/hooks/enhancement/useEnhancementControl';

/**
 * The pane's Auto-Mastering switch (#6570).
 *
 * setEnabled() rejects when the toggle POST fails (429/500/503/timeout). The
 * switch's onToggle is synchronous, so the rejection used to escape unhandled
 * and the switch snapped back with no word why. A failure is now shown as a
 * toast, and the switch is disabled while the request is in flight.
 */
export const AutoMasteringToggle = () => {
  const { enabled, setEnabled, isLoading } = useEnhancementControl();
  const { error: showError } = useToast();

  const handleToggle = useCallback((next: boolean) => {
    setEnabled(next).catch((err: unknown) => {
      const reason = err instanceof Error ? err.message : String(err);
      showError(`Could not turn auto-mastering ${next ? 'on' : 'off'}: ${reason}`);
    });
  }, [setEnabled, showError]);

  return (
    <Box
      sx={{
        pb: tokens.spacing.lg,
        mb: tokens.spacing.lg,
        borderBottom: `1px solid ${themeVars.borderSubtle}`,
      }}
    >
      <EnhancementToggle
        variant="switch"
        isEnabled={enabled}
        onToggle={handleToggle}
        isProcessing={isLoading}
        label="Auto-Mastering"
        description={enabled ? 'Enhancing playback' : 'Original audio'}
        showDescription
      />
    </Box>
  );
};
