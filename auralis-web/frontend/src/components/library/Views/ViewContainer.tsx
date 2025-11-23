/**
 * ViewContainer Component
 *
 * Reusable container for library views (albums, artists).
 * Handles layout, header with gradient title, and content scrolling.
 */

import React from 'react';
import { Container, Box, Typography } from '@mui/material';
import { tokens } from '@/design-system/tokens';

interface ViewContainerProps {
  icon: string;
  title: string;
  subtitle: string;
  children: React.ReactNode;
}

export const ViewContainer: React.FC<ViewContainerProps> = ({
  icon,
  title,
  subtitle,
  children,
}) => {
  return (
    <Container
      maxWidth="xl"
      sx={{
        py: 4,
        height: '100%',
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <Box sx={{ mb: 4, flexShrink: 0 }}>
        <Typography
          variant="h3"
          component="h1"
          fontWeight="bold"
          gutterBottom
          sx={{
            background: `linear-gradient(45deg, ${tokens.colors.accent.purple}, ${tokens.colors.accent.secondary})`,
            backgroundClip: 'text',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
          }}
        >
          {icon} {title}
        </Typography>
        <Typography variant="subtitle1" color="text.secondary">
          {subtitle}
        </Typography>
      </Box>
      <Box sx={{ flex: 1, minHeight: 0 }}>
        {children}
      </Box>
    </Container>
  );
};
