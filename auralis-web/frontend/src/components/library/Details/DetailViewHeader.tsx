/**
 * DetailViewHeader Component
 *
 * Reusable header component for album and artist detail views.
 * Consolidates common header patterns: artwork, title, metadata, and action buttons.
 */

import React from 'react';

import { tokens } from '@/design-system';
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
  /** Phase 1: Reduce header visual weight when playback is active */
  isPlaying?: boolean;
}

/**
 * HeaderSection - Detail view header container (Design Language v1.2.0)
 * Organic spacing and glass border for subtle separation
 * Phase 1: Reduces opacity when playback is active (listening-first posture)
 */
const HeaderSection = styled(Box)<{ isplaying?: string }>(({ isplaying }) => ({
  display: 'flex',
  gap: tokens.spacing.section,                            // 32px - organic section spacing
  marginBottom: tokens.spacing.xxl,                       // 40px - major section break
  padding: `${tokens.spacing.section} ${tokens.spacing.group}`, // 32px vertical, 16px horizontal
  background: 'transparent',                              // Blend into background, not a card
  borderRadius: 0,                                        // No container rounding
  backdropFilter: 'none',                                 // No blur effect
  border: 'none',                                         // No border
  boxShadow: 'none',                                      // No elevation

  // Subtle glass border for visual separation (Design Language §4.2)
  borderBottom: tokens.glass.subtle.border,               // Glass border catches light (10% white opacity)
  paddingBottom: tokens.spacing.section,                  // 32px - organic spacing

  // Phase 1: Reduce visual weight during playback (listening-first context)
  opacity: isplaying === 'true' ? 0.85 : 1,
  transition: `opacity ${tokens.transitions.base}`,      // 400ms smooth fade

  '@media (max-width: 768px)': {
    flexDirection: 'column',
    gap: tokens.spacing.group,                            // 16px - tighter on mobile
    padding: tokens.spacing.lg,
  },
}));

const ArtworkWrapper = styled(Box)({
  flexShrink: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  '@media (max-width: 768px)': {
    alignSelf: 'center',
  },
});

/**
 * InfoSection - Metadata and actions container
 * Organic group spacing for natural rhythm
 */
const InfoSection = styled(Box)({
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'center',
  gap: tokens.spacing.group,                              // 16px - organic group spacing
});

const Title = styled(Typography)({
  fontFamily: tokens.typography.fontFamily.header,  // Manrope for headers (Design Language v1.2.0 §3)
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
  fontFamily: tokens.typography.fontFamily.header,  // Manrope for subtitle hierarchy (R4)
  fontSize: tokens.typography.fontSize.xl,           // 24px - increased from lg (20px)
  color: tokens.colors.text.secondary,
  marginBottom: tokens.spacing.md,
  fontWeight: tokens.typography.fontWeight.semibold,
  letterSpacing: '-0.01em',                          // Tight tracking for headers
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
  isPlaying = false, // Phase 1: Default to false (no playback)
}) => {
  const isPlayingStr = isPlaying ? 'true' : 'false'; // Convert to string for styled-components

  return (
    <HeaderSection sx={{ flexDirection: direction }} isplaying={isPlayingStr}>
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
