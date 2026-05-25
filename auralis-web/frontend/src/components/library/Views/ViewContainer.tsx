/**
 * ViewContainer Component
 *
 * Reusable container for library views (albums, artists).
 * Handles layout, header with gradient title, and content scrolling.
 *
 * Layout:
 * - Main content area (full width if no right pane)
 * - Optional right pane (e.g., Album Character Pane)
 */

import { ReactNode } from 'react';
import { Container, Box, Typography } from '@mui/material';
import { tokens } from '@/design-system';

interface ViewContainerProps {
  icon: string;
  title: string;
  subtitle: string;
  children: ReactNode;
  /** Optional right sidebar content (e.g., Album Character Pane) */
  rightPane?: ReactNode;
  /** Optional header actions (e.g., sort selector) */
  headerActions?: ReactNode;
}

export const ViewContainer = ({
  icon,
  title,
  subtitle,
  children,
  rightPane,
  headerActions,
}: ViewContainerProps) => {
  return (
    <Box
      sx={{
        display: 'flex',
      }}
    >
      {/* Main content area — no overflow, scrolls within app-main-content-scroll */}
      <Box
        sx={{
          flex: 1,
        }}
      >
        <Container
          maxWidth="xl"
          sx={{
            py: 4,
          }}
        >
          <Box sx={{
            mb: 4,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
          }}>
            <Box>
              <Typography
                variant="h3"
                component="h1"
                gutterBottom
                sx={{
                  fontWeight: "bold",
                  background: `linear-gradient(45deg, ${tokens.colors.accent.primary}, ${tokens.colors.accent.secondary})`,
                  backgroundClip: 'text',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent'
                }}>
                {icon} {title}
              </Typography>
              <Typography variant="subtitle1" sx={{
                color: "text.secondary"
              }}>
                {subtitle}
              </Typography>
            </Box>
            {headerActions && (
              <Box sx={{ mt: tokens.spacing.sm }}>
                {headerActions}
              </Box>
            )}
          </Box>
          <Box sx={{ width: '100%' }}>
            {children}
          </Box>
        </Container>
      </Box>
      {/* Optional right pane */}
      {rightPane && (
        <Box
          sx={{
            flexShrink: 0,
            position: 'sticky',
            top: 0,
            alignSelf: 'flex-start',
            height: 'fit-content',
            maxHeight: '100vh',
            overflowY: 'auto',
          }}
        >
          {rightPane}
        </Box>
      )}
    </Box>
  );
};
