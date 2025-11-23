/**
 * DetailViewHeader Component
 *
 * Reusable header component for album and artist detail views.
 * Consolidates common header patterns: artwork, title, metadata, and action buttons.
 */

import React from 'react';
import { Box, Typography, Button, styled } from '@mui/material';
import { auroraOpacity } from '../Styles/Color.styles';
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

const HeaderSection = styled(Box)(({ theme }) => ({
  display: 'flex',
  gap: theme.spacing(4),
  marginBottom: theme.spacing(4),
  padding: theme.spacing(4),
  background: auroraOpacity.minimal,
  borderRadius: theme.spacing(2),
  backdropFilter: 'blur(10px)',
  border: `1px solid ${auroraOpacity.ultraLight}`,
}));

const ArtworkWrapper = styled(Box)({
  flexShrink: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
});

const InfoSection = styled(Box)(({ theme }) => ({
  flex: 1,
  display: 'flex',
  flexDirection: 'column',
  justifyContent: 'center',
  gap: theme.spacing(2),
}));

const Title = styled(Typography)({
  fontSize: '2.5rem',
  fontWeight: 'bold',
  background: `linear-gradient(45deg, ${tokens.colors.accent.purple}, ${tokens.colors.accent.secondary})`,
  backgroundClip: 'text',
  WebkitBackgroundClip: 'text',
  WebkitTextFillColor: 'transparent',
  marginBottom: 8,
});

const Subtitle = styled(Typography)(({ theme }) => ({
  fontSize: '1.5rem',
  color: theme.palette.text.secondary,
  marginBottom: 16,
}));

const Metadata = styled(Typography)(({ theme }) => ({
  fontSize: '0.95rem',
  color: theme.palette.text.secondary,
  marginBottom: 4,
}));

const ActionsContainer = styled(Box)(({ theme }) => ({
  display: 'flex',
  gap: theme.spacing(2),
  marginTop: theme.spacing(2),
  alignItems: 'center',
  flexWrap: 'wrap',
}));

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
