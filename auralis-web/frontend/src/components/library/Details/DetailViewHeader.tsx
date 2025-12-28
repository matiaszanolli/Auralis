/**
 * DetailViewHeader Component
 *
 * Reusable header component for album and artist detail views.
 * Consolidates common header patterns: artwork, title, metadata, and action buttons.
 */

import React from 'react';

import { tokens } from '@/design-system';
import { Button } from '@/design-system';
import { Box, Typography, styled } from '@mui/material';

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
  marginBottom: tokens.spacing['2xl'],
  padding: `${tokens.spacing.xl} ${tokens.spacing.md}`,
  background: 'transparent', // Blend into background, not a card
  borderRadius: 0, // No container rounding
  backdropFilter: 'none', // No blur effect
  border: 'none', // No border
  boxShadow: 'none', // No elevation
  // Subtle bottom border for visual separation
  borderBottom: `1px solid ${tokens.colors.border.subtle}`,
  paddingBottom: tokens.spacing.xl,
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
  fontSize: tokens.typography.fontSize['4xl'],
  fontWeight: tokens.typography.fontWeight.bold,
  background: tokens.gradients.aurora,
  backgroundClip: 'text',
  WebkitBackgroundClip: 'text',
  WebkitTextFillColor: 'transparent',
  marginBottom: tokens.spacing.md, // More breathing room (was sm)
  lineHeight: 1.1, // Tighter line height for better presence
  letterSpacing: '0.01em', // Subtle letter spacing for refinement
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
