import React from 'react';
import { Box } from '@mui/material';
import { auroraOpacity } from '../library/Color.styles';

/**
 * Props for the AppMainContent component.
 */
export interface AppMainContentProps {
  /**
   * Child components to render in the main content area.
   * Typically the library view (CozyLibraryView or similar).
   */
  children: React.ReactNode;

  /**
   * Optional callback when a track is clicked to play.
   * Receives the track ID.
   */
  onPlayTrack?: (trackId: number) => void;

  /**
   * Optional callback when a track is queued.
   * Receives the track ID.
   */
  onQueueTrack?: (trackId: number) => void;
}

/**
 * AppMainContent component provides the main content area wrapper.
 *
 * Responsibilities:
 * - Wrap library view component
 * - Provide proper padding and spacing for player bar
 * - Handle layout and scrolling
 * - Manage track interaction callbacks
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
 *     <AppMainContent onPlayTrack={handlePlayTrack}>
 *       <CozyLibraryView {...props} />
 *     </AppMainContent>
 *   );
 * }
 * ```
 */
export const AppMainContent: React.FC<AppMainContentProps> = ({
  children,
  onPlayTrack,
  onQueueTrack,
}) => {
  return (
    <Box
      sx={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      {/* Main scrollable content area */}
      <Box
        sx={{
          flex: 1,
          overflow: 'auto',
          // Padding to prevent content from going under player bar
          // Player bar height is typically 80-100px
          paddingBottom: '100px',
          // Custom scrollbar styling
          '&::-webkit-scrollbar': {
            width: '8px',
          },
          '&::-webkit-scrollbar-track': {
            background: 'transparent',
          },
          '&::-webkit-scrollbar-thumb': {
            background: auroraOpacity.strong,
            borderRadius: '4px',
            '&:hover': {
              background: auroraOpacity.stronger,
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
