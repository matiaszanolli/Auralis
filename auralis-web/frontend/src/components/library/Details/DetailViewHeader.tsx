/**
 * DetailViewHeader Component
 *
 * Reusable header component for album and artist detail views.
 * Consolidates common header patterns: artwork, title, metadata, and action buttons.
 */

import React from 'react';
import { Box, Typography, Button, styled } from '@mui/material';
import { tokens } from '@/design-system/tokens';

interface DetailViewHeaderProps {
  /** Left side content (artwork or avatar) */
  artwork: React.ReactNode;
  /** Main title (album/artist name) */
  title: string;
  /** Secondary title (artist name or label) */
  subtitle?: string;
  /** Additional metadata items (year, track count, duration) */
  metadata?: React.ReactNode;
  /** Action buttons (play, favorite, etc.) */
  actions?: React.ReactNode;
  /** Custom layout direction - 'row' (default) or 'column' */
  direction?: 'row' | 'column';
}

const HeaderSection = styled(Box)({
  display: 'flex',
  gap: tokens.spacing.xl,
  marginBottom: tokens.spacing.xl,
  padding: tokens.spacing.xl,
  background: `rgba(${parseInt(tokens.colors.bg.level2.slice(1, 3), 16)}, ${parseInt(tokens.colors.bg.level2.slice(3, 5), 16)}, ${parseInt(tokens.colors.bg.level2.slice(5, 7), 16)}, 0.92)`,
  borderRadius: tokens.borderRadius.lg,
  backdropFilter: 'blur(12px)',
  border: `1px solid ${tokens.colors.border.light}`,
  boxShadow: tokens.shadows.md,
  '@media (max-width: 768px)': {
    flexDirection: 'column',
    gap: tokens.spacing.lg,
    padding: tokens.spacing.lg,
  },
});

const ArtworkWrapper = styled(Box)({
  flexShrink: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  '@media (max-width: 768px)': {
    alignSelf: 'center',
  },
});

const InfoSection = styled(Box)({
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'center',
  gap: tokens.spacing.md,
});

const Title = styled(Typography)({
  fontSize: tokens.typography.fontSize.xxxl,
  fontWeight: tokens.typography.fontWeight.bold,
  background: tokens.gradients.aurora,
  backgroundClip: 'text',
  WebkitBackgroundClip: 'text',
  WebkitTextFillColor: 'transparent',
  marginBottom: tokens.spacing.sm,
  lineHeight: 1.2,
});

const Subtitle = styled(Typography)({
  fontSize: tokens.typography.fontSize.lg,
  color: tokens.colors.text.secondary,
  marginBottom: tokens.spacing.md,
  fontWeight: tokens.typography.fontWeight.semibold,
});

const Metadata = styled(Typography)({
  fontSize: tokens.typography.fontSize.sm,
  color: tokens.colors.text.tertiary,
  marginBottom: tokens.spacing.xs,
});

const ActionsContainer = styled(Box)({
  display: 'flex',
  gap: tokens.spacing.md,
  marginTop: tokens.spacing.lg,
  alignItems: 'center',
  flexWrap: 'wrap',
});

export const DetailViewHeader: React.FC<DetailViewHeaderProps> = ({
  artwork,
  title,
  subtitle,
  metadata,
  actions,
  direction = 'row',
}) => {
  return (
    <HeaderSection sx={{ flexDirection: direction }}>
      <ArtworkWrapper>
        {artwork}
      </ArtworkWrapper>

      <InfoSection>
        <Box>
          <Title variant="h2">
            {title}
          </Title>
          {subtitle && (
            <Subtitle variant="h5">
              {subtitle}
            </Subtitle>
          )}
        </Box>

        {metadata && (
          <Box>
            {metadata}
          </Box>
        )}

        {actions && (
          <ActionsContainer>
            {actions}
          </ActionsContainer>
        )}
      </InfoSection>
    </HeaderSection>
  );
};

export default DetailViewHeader;
