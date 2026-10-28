import { Box, Container } from '@mui/material';
import ArrowBack from '@mui/icons-material/ArrowBack';
import { Button, tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';
import { EmptyState } from '@/components/shared/ui/feedback';

interface DetailErrorProps {
  title: string;
  description?: string;
  /** Without it there is nowhere to go, so no button is rendered. */
  onBack?: () => void;
  backLabel: string;
  /** Announce the failure to assistive tech as an alert. */
  alert?: boolean;
}

/**
 * DetailError - the shared error / not-found state of the album and artist
 * detail views. Both carried the same EmptyState, but only the album view had a
 * Back control, leaving an artist error with nothing but the sidebar to leave by
 * (#6034).
 */
export const DetailError = ({ title, description, onBack, backLabel, alert }: DetailErrorProps) => (
  <Container
    maxWidth="xl"
    sx={{ py: tokens.spacing.xl, px: tokens.spacing.lg }}
    {...(alert ? { role: 'alert', 'aria-live': 'assertive' as const } : {})}
  >
    <EmptyState title={title} description={description} />
    {onBack && (
      <Box sx={{ textAlign: 'center', mt: tokens.spacing.lg }}>
        <Button
          onClick={onBack}
          startIcon={<ArrowBack />}
          sx={{
            background: tokens.gradients.aurora,
            color: themeVars.textPrimary,
            fontWeight: tokens.typography.fontWeight.semibold,
            padding: `${tokens.spacing.sm} ${tokens.spacing.lg}`,
            borderRadius: tokens.borderRadius.md,
            border: 'none',
            transition: tokens.transitions.all,
            boxShadow: tokens.shadows.md,
            '&:hover': {
              transform: 'translateY(-2px)',
              boxShadow: tokens.shadows.glowMd,
            },
          }}
        >
          {backLabel}
        </Button>
      </Box>
    )}
  </Container>
);

export default DetailError;
