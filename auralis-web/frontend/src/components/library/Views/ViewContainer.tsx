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
import { themeVars } from '@/theme/semanticTheme';

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
        minHeight: '100%',
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
            py: tokens.spacing.xl,
            px: { xs: tokens.spacing.lg, lg: tokens.spacing.section },
          }}
        >
          <Box sx={{
            mb: tokens.spacing.xl,
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
                  fontWeight: tokens.typography.fontWeight.semibold,
                  color: themeVars.textPrimary,
                  letterSpacing: '-0.02em',
                }}>
                <Box component="span" aria-hidden="true" sx={{ color: themeVars.accent, mr: tokens.spacing.cluster }}>
                  {icon}
                </Box>
                {title}
              </Typography>
              <Typography variant="subtitle1" sx={{
                color: themeVars.textSecondary,
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
            borderLeft: `1px solid ${themeVars.borderSubtle}`,
          }}
        >
          {rightPane}
        </Box>
      )}
    </Box>
  );
};
