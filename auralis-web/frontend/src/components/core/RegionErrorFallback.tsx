/**
 * RegionErrorFallback
 * ~~~~~~~~~~~~~~~~~~~
 *
 * The one error-boundary fallback used by ComfortableApp's region boundaries
 * (library, settings, shortcuts help, Player) — #5627/#5631. Before this, all
 * four boundaries inlined near-identical static Boxes saying "Refresh the
 * page", which was also the ONLY instruction a user had: the boundary's built
 * -in retry UI never renders when a `fallback` node is supplied. This
 * component renders the region message plus a working "Try again" button
 * wired to the boundary's retry callback, so a transient render error no
 * longer requires a reload.
 */

import { Box } from '@mui/material';
import { tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';

interface RegionErrorFallbackProps {
  /** Which region failed and what still works, e.g. "Library failed to render. …" */
  message: string;
  /** The boundary's retry callback (second argument of the fallback function). */
  retry: () => void;
  /** 'panel' = boxed card inside the layout; 'bottomBar' = player-bar strip. */
  variant?: 'panel' | 'bottomBar';
}

export function RegionErrorFallback({ message, retry, variant = 'panel' }: RegionErrorFallbackProps) {
  const isBar = variant === 'bottomBar';

  return (
    <Box
      data-testid="region-error-fallback"
      sx={{
        background: themeVars.errorSoft,
        border: isBar ? 'none' : `1px solid ${themeVars.error}`,
        borderTop: isBar ? `1px solid ${themeVars.error}` : undefined,
        borderRadius: isBar ? 0 : tokens.borderRadius.md,
        color: themeVars.textPrimary,
        fontSize: tokens.typography.fontSize.sm,
        textAlign: 'center',
        p: isBar ? tokens.spacing.md : tokens.spacing.lg,
        m: isBar ? 0 : tokens.spacing.lg,
      }}
    >
      {message}
      <Box
        component="button"
        onClick={retry}
        sx={{
          display: 'block',
          mx: 'auto',
          mt: tokens.spacing.sm,
          px: tokens.spacing.md,
          py: tokens.spacing.sm,
          border: 'none',
          borderRadius: tokens.borderRadius.md,
          background: themeVars.accent,
          color: themeVars.onAccent,
          fontSize: tokens.typography.fontSize.sm,
          fontWeight: tokens.typography.fontWeight.medium,
          cursor: 'pointer',
        }}
      >
        Try again
      </Box>
    </Box>
  );
}

export default RegionErrorFallback;
