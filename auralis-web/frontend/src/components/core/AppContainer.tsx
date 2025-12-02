import React from 'react';
import { Box } from '@mui/material';
import { DragDropContext, DropResult } from '@hello-pangea/dnd';

/**
 * Props for the AppContainer component.
 */
export interface AppContainerProps {
  /**
   * Handler for drag-and-drop operations.
   * Called when a user drops an item in a droppable area.
   */
  onDragEnd: (result: DropResult) => void;

  /**
   * Child components to render inside the container.
   * Typically includes sidebar, main content, and enhancement pane.
   */
  children: React.ReactNode;
}

/**
 * AppContainer is the top-level layout wrapper for the Auralis application.
 *
 * Responsibilities:
 * - Wrap entire app in DragDropContext for drag-and-drop support
 * - Provide the main layout container with proper styling
 * - Handle responsive layout structure
 * - Manage z-index and overflow behavior
 *
 * Structure:
 * ```
 * AppContainer
 * └── DragDropContext
 *     └── Box (main layout)
 *         ├── Main content area (flex: 1)
 *         ├── Bottom player bar (fixed position)
 *         └── Dialogs/modals
 * ```
 *
 * Note: The player bar is positioned OUTSIDE the DragDropContext
 * to ensure drag-drop operations don't interfere with player controls.
 *
 * @param props Component props
 * @returns Rendered app container with drag-drop support
 *
 * @example
 * ```tsx
 * function App() {
 *   const { handleDragEnd } = useAppDragDrop({ info, success });
 *
 *   return (
 *     <AppContainer onDragEnd={handleDragEnd}>
 *       <AppSidebar {...props} />
 *       <Box sx={{ flex: 1 }}>
 *         <AppTopBar {...props} />
 *         <AppMainContent {...props} />
 *       </Box>
 *       <AppEnhancementPane {...props} />
 *     </AppContainer>
 *   );
 * }
 * ```
 */
export const AppContainer: React.FC<AppContainerProps> = ({
  onDragEnd,
  children,
}) => {
  return (
    <DragDropContext onDragEnd={onDragEnd}>
      <Box
        sx={{
          flex: 1,
          background: 'var(--midnight-blue)',
          color: 'var(--silver)',
          display: 'flex',
          flexDirection: 'row',
          overflow: 'hidden',
          position: 'relative',
        }}
      >
        {/* Main layout area: sidebar + content + enhancement pane arranged horizontally */}
        {children}
      </Box>
    </DragDropContext>
  );
};

export default AppContainer;
