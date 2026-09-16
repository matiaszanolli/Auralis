import { ReactNode } from 'react';
import { Box } from '@mui/material';
import { tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';

/**
 * Props for the AppMainContent component.
 */
export interface AppMainContentProps {
  /**
   * Child components to render in the main content area.
   * Typically the library view (CozyLibraryView or similar).
   */
  children: ReactNode;
}

/**
 * AppMainContent component provides the main content area wrapper.
 *
 * Responsibilities:
 * - Wrap library view component
 * - Provide proper padding and spacing for player bar
 * - Handle layout and scrolling
 *
 * Track play/queue actions are wired inside the library views themselves;
 * this wrapper takes no track callbacks (the unused onPlayTrack/onQueueTrack
 * props were removed in #5396).
 *
 * Layout Structure:
 * ```
 * AppMainContent (full viewport, scrollable)
 * └── Library view or other main content
 *     └── Player bar consideration (padding-bottom)
 * ```
 *
 * Note: This component handles layout considerations for the fixed player bar
 * at the bottom. The actual player bar is positioned outside this component.
 *
 * @param props Component props
 * @returns Rendered main content area
 *
 * @example
 * ```tsx
 * function App() {
 *   return (
 *     <AppMainContent>
 *       <CozyLibraryView {...props} />
 *     </AppMainContent>
 *   );
 * }
 * ```
 */
export const AppMainContent = ({ children }: AppMainContentProps) => {
  return (
    <Box
      component="main"
      aria-label="Main content"
      sx={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        backgroundColor: `color-mix(in srgb, ${themeVars.canvas} 82%, transparent)`,
      }}
    >
      {/* Main scrollable content area */}
      <Box
        id="app-main-content-scroll"
        sx={{
          flex: 1,
          overflow: 'auto',
          // Custom scrollbar styling (Design Language v1.2.0 §4.4)
          '&::-webkit-scrollbar': {
            width: '8px',
          },
          '&::-webkit-scrollbar-track': {
            background: 'transparent',
          },
          '&::-webkit-scrollbar-thumb': {
            background: themeVars.surfaceRaised,
            borderRadius: tokens.borderRadius.sm,              // 8px - organic curves
            '&:hover': {
              background: themeVars.accent,
            },
          },
        }}
      >
        {children}
      </Box>
    </Box>
  );
};

export default AppMainContent;
