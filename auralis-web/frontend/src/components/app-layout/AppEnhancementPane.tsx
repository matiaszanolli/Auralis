import React, { useState } from 'react';
import { Box, IconButton, Tooltip } from '@mui/material';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';

/**
 * Props for the AppEnhancementPane component.
 */
export interface AppEnhancementPaneProps {
  /**
   * Callback when enhancement parameters are changed.
   * Receives the updated parameters object.
   */
  onEnhancementChange?: (params: Record<string, any>) => void;

  /**
   * Callback when V2 toggle is activated.
   */
  onToggleV2?: () => void;

  /**
   * Whether to show the V2 enhancement pane.
   * If false, shows the legacy enhancement interface.
   */
  useV2?: boolean;

  /**
   * Whether enhancement pane is initially collapsed.
   * On tablet/mobile, may auto-collapse to save space.
   */
  initiallyCollapsed?: boolean;

  /**
   * Child components to render inside the pane.
   * Typically the enhancement controls (EnhancementPaneV1 or EnhancementPaneV2).
   */
  children: React.ReactNode;
}

/**
 * AppEnhancementPane component provides the right panel for audio enhancement controls.
 *
 * Responsibilities:
 * - Wrap enhancement controls (V1 or V2)
 * - Handle pane collapse/expand toggle
 * - Toggle between V1 and V2 enhancement interfaces
 * - Manage responsive layout (collapsible on mobile/tablet)
 * - Delegate enhancement parameter changes to parent
 *
 * Layout Structure:
 * ```
 * AppEnhancementPane (fixed width or collapsible)
 * ├── Header with toggle and V2 switch
 * └── Enhancement controls (V1 or V2)
 * ```
 *
 * Responsive Behavior:
 * - Desktop (≥1200px): Fixed 320px wide pane, always visible
 * - Tablet (<1200px): Collapsible, defaults to collapsed
 * - Mobile (<900px): Hidden (enhancement via modal instead)
 *
 * @param props Component props
 * @returns Rendered enhancement pane with controls
 *
 * @example
 * ```tsx
 * function App() {
 *   const [useV2, setUseV2] = useState(false);
 *
 *   return (
 *     <AppEnhancementPane
 *       useV2={useV2}
 *       onToggleV2={() => setUseV2(!useV2)}
 *       onEnhancementChange={handleEnhancementChange}
 *     >
 *       {useV2 ? <EnhancementPaneV2 /> : <EnhancementPaneV1 />}
 *     </AppEnhancementPane>
 *   );
 * }
 * ```
 */
export const AppEnhancementPane: React.FC<AppEnhancementPaneProps> = ({
  onEnhancementChange,
  onToggleV2,
  useV2 = false,
  initiallyCollapsed = false,
  children,
}) => {
  const [isCollapsed, setIsCollapsed] = useState(initiallyCollapsed);

  const handleCollapsedToggle = () => {
    setIsCollapsed(!isCollapsed);
  };

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--midnight-blue)',
        borderLeft: '1px solid rgba(102, 126, 234, 0.1)',
        transition: 'width 0.3s ease',
        width: isCollapsed ? 60 : 320,
        minWidth: isCollapsed ? 60 : 320,
        height: '100%',
        overflow: 'hidden',
      }}
    >
      {/* Header with collapse toggle */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 8px',
          borderBottom: '1px solid rgba(102, 126, 234, 0.1)',
          gap: 4,
        }}
      >
        {!isCollapsed && (
          <Box
            sx={{
              fontSize: '12px',
              fontWeight: 600,
              color: 'rgba(255, 255, 255, 0.5)',
              textTransform: 'uppercase',
              letterSpacing: '0.5px',
              flex: 1,
            }}
          >
            {useV2 ? 'Enhancement V2' : 'Enhancement'}
          </Box>
        )}

        {/* Collapse toggle button */}
        <Tooltip title={isCollapsed ? 'Expand' : 'Collapse'}>
          <IconButton
            onClick={handleCollapsedToggle}
            size="small"
            sx={{
              color: 'rgba(255, 255, 255, 0.5)',
              padding: '4px',
              '&:hover': {
                color: 'var(--silver)',
                background: 'rgba(102, 126, 234, 0.1)',
              },
            }}
          >
            {isCollapsed ? (
              <ExpandMoreIcon fontSize="small" />
            ) : (
              <ExpandLessIcon fontSize="small" />
            )}
          </IconButton>
        </Tooltip>
      </Box>

      {/* Content area */}
      {!isCollapsed && (
        <Box
          sx={{
            flex: 1,
            overflow: 'auto',
            padding: '16px 12px',
            // Custom scrollbar styling
            '&::-webkit-scrollbar': {
              width: '6px',
            },
            '&::-webkit-scrollbar-track': {
              background: 'transparent',
            },
            '&::-webkit-scrollbar-thumb': {
              background: 'rgba(102, 126, 234, 0.3)',
              borderRadius: '3px',
              '&:hover': {
                background: 'rgba(102, 126, 234, 0.5)',
              },
            },
          }}
        >
          {children}
        </Box>
      )}

      {/* V2 toggle button (always visible, below content when collapsed) */}
      {!isCollapsed && (
        <Box
          sx={{
            padding: '12px 8px',
            borderTop: '1px solid rgba(102, 126, 234, 0.1)',
            display: 'flex',
            gap: 8,
          }}
        >
          <Tooltip title={useV2 ? 'Switch to V1' : 'Switch to V2'}>
            <IconButton
              onClick={onToggleV2}
              size="small"
              fullWidth
              sx={{
                background: useV2
                  ? 'rgba(102, 126, 234, 0.2)'
                  : 'rgba(102, 126, 234, 0.05)',
                color: useV2 ? 'rgb(102, 126, 234)' : 'rgba(255, 255, 255, 0.5)',
                fontSize: '11px',
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: '0.5px',
                padding: '8px',
                border: `1px solid ${
                  useV2
                    ? 'rgba(102, 126, 234, 0.3)'
                    : 'rgba(102, 126, 234, 0.1)'
                }`,
                borderRadius: '4px',
                '&:hover': {
                  background: useV2
                    ? 'rgba(102, 126, 234, 0.3)'
                    : 'rgba(102, 126, 234, 0.1)',
                },
              }}
            >
              {useV2 ? 'V2 Active' : 'V1'}
            </IconButton>
          </Tooltip>
        </Box>
      )}
    </Box>
  );
};

export default AppEnhancementPane;
