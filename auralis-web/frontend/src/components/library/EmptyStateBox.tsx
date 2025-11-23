/**
 * EmptyStateBox - Reusable empty state component for list/grid views
 *
 * Displays centered empty state message with optional icon.
 * Used across paginated lists (albums, artists, tracks, etc.)
 */

import React from 'react';
import { Box, Typography, styled } from '@mui/material';
import { tokens } from '@/design-system/tokens';

interface EmptyStateBoxProps {
  /** Main message text */
  title: string;
  /** Secondary message text */
  subtitle?: string;
  /** Optional icon element to display above text */
  icon?: React.ReactNode;
}

const Container = styled(Box)({
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  justifyContent: 'center',
  minHeight: '400px',
  color: tokens.colors.text.disabled,
  textAlign: 'center',
  padding: '40px',
});

const Title = styled(Typography)({
  fontSize: '18px',
  fontWeight: 500,
  marginBottom: '8px',
  color: tokens.colors.text.secondary,
});

const Subtitle = styled(Typography)({
  fontSize: '14px',
  color: tokens.colors.text.disabled,
});

export const EmptyStateBox: React.FC<EmptyStateBoxProps> = ({
  title,
  subtitle,
  icon
}) => {
  return (
    <Container>
      {icon && (
        <Box sx={{ marginBottom: 2 }}>
          {icon}
        </Box>
      )}
      <Title>{title}</Title>
      {subtitle && <Subtitle>{subtitle}</Subtitle>}
    </Container>
  );
};

export default EmptyStateBox;
