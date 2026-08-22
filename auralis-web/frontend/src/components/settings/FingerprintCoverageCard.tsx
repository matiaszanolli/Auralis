/**
 * FingerprintCoverageCard - Library-wide audio-analysis progress
 *
 * Shows how much of the library has a fingerprint, with a rough ETA for the
 * rest, and offers to queue whatever is still missing (#4865). The backend has
 * built `progress_percent`, a display-ready `status` line and
 * `estimated_remaining_seconds` since before there was anywhere to render them.
 *
 * Deliberately a sibling of `ScanStatusCard` rather than part of it: scanning
 * finds files, analysis fingerprints them, and the two run on different clocks —
 * a scan finishes in seconds, analysis of the tracks it added takes hours.
 */

import { Box, LinearProgress, Typography, Divider } from '@mui/material';
import AnalyseIcon from '@mui/icons-material/GraphicEq';
import { Button, tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';
import { useFingerprintCoverage } from '@/hooks/library/useFingerprintCoverage';

interface FingerprintCoverageCardProps {
  /** Skip fetching entirely (e.g. the Library tab is not visible). */
  enabled?: boolean;
}

/** "about 3 hours" / "about 12 minutes" / "under a minute". */
export function formatRemaining(seconds: number): string {
  if (seconds <= 0) return '';
  if (seconds < 60) return 'under a minute remaining';

  const minutes = Math.round(seconds / 60);
  if (minutes < 60) {
    return `about ${minutes} minute${minutes === 1 ? '' : 's'} remaining`;
  }

  const hours = Math.round(minutes / 60);
  return `about ${hours} hour${hours === 1 ? '' : 's'} remaining`;
}

export const FingerprintCoverageCard = ({ enabled = true }: FingerprintCoverageCardProps) => {
  const { coverage, loading, error, enqueueing, analyseRemaining } =
    useFingerprintCoverage(enabled);

  // Nothing to say yet — don't flash an empty card on first open.
  if (!coverage && !error) {
    return null;
  }

  const remaining = coverage ? formatRemaining(coverage.estimatedRemainingSeconds) : '';
  const hasPending = (coverage?.pendingTracks ?? 0) > 0;

  return (
    <Box
      aria-live="polite"
      role="status"
      sx={{
        ...tokens.glass.subtle,
        borderRadius: tokens.borderRadius.sm,
        overflow: 'hidden',
      }}
    >
      <Box sx={{ p: tokens.spacing.md }}>
        {error ? (
          <Typography variant="body2" sx={{ color: tokens.colors.semantic.error }}>
            {error}
          </Typography>
        ) : coverage ? (
          <>
            <Box
              sx={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                mb: 1,
              }}
            >
              <Typography
                variant="body2"
                sx={{
                  color: themeVars.textSecondary,
                  fontWeight: tokens.typography.fontWeight.medium,
                }}
              >
                Audio analysis
              </Typography>
              <Typography variant="caption" sx={{ color: themeVars.textMuted }}>
                {coverage.fingerprintedTracks} / {coverage.totalTracks}
              </Typography>
            </Box>

            <LinearProgress
              variant="determinate"
              value={coverage.progressPercent}
              aria-label="Library analysis progress"
              sx={{
                borderRadius: 2,
                height: 4,
                backgroundColor: tokens.colors.opacityScale.accent.ultraLight,
                '& .MuiLinearProgress-bar': {
                  background: `linear-gradient(90deg, ${tokens.colors.accent.primary}, ${tokens.colors.accent.secondary})`,
                  borderRadius: 2,
                },
              }}
            />

            <Typography
              variant="caption"
              sx={{ display: 'block', mt: 0.75, color: themeVars.textMuted }}
            >
              {/* The backend's own status line, so the wording lives in one
                  place; the ETA is appended only while work is outstanding. */}
              {coverage.status}
              {remaining && ` · ${remaining}`}
            </Typography>
          </>
        ) : null}
      </Box>

      {hasPending && (
        <>
          <Divider sx={{ borderColor: tokens.colors.opacityScale.accent.ultraLight }} />
          <Box sx={{ p: tokens.spacing.sm, display: 'flex', justifyContent: 'flex-end' }}>
            <Button
              variant="ghost"
              size="sm"
              startIcon={<AnalyseIcon fontSize="small" />}
              onClick={() => void analyseRemaining()}
              disabled={enqueueing || loading}
              sx={{ color: tokens.colors.accent.primary }}
            >
              {enqueueing ? 'Queueing…' : 'Analyse remaining'}
            </Button>
          </Box>
        </>
      )}
    </Box>
  );
};

export default FingerprintCoverageCard;
