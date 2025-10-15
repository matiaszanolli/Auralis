/**
 * LoadingBar Component
 *
 * A top-of-page loading indicator with aurora gradient styling.
 * Shows during page transitions, data fetching, or any async operations.
 *
 * Usage:
 * ```tsx
 * const [loading, setLoading] = useState(false);
 *
 * <LoadingBar loading={loading} />
 * ```
 */

import React from 'react';
import { LinearProgress, styled } from '@mui/material';
import { gradients, colors } from '../../theme/auralisTheme';

interface LoadingBarProps {
  loading: boolean;
}

const StyledLoadingBar = styled(LinearProgress)({
  position: 'fixed',
  top: 0,
  left: 0,
  right: 0,
  zIndex: 9999,
  height: '3px',
  background: colors.background.secondary,

  '& .MuiLinearProgress-bar': {
    background: gradients.aurora,
    boxShadow: '0 0 8px rgba(102, 126, 234, 0.6)',
  },

  // Smooth animation
  transition: 'opacity 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
});

/**
 * LoadingBar Component
 *
 * Displays a fixed top-of-page loading bar with aurora gradient.
 * Automatically hides when loading prop is false.
 *
 * @param loading - Whether the loading bar should be visible
 */
export const LoadingBar: React.FC<LoadingBarProps> = ({ loading }) => {
  if (!loading) return null;

  return <StyledLoadingBar />;
};

/**
 * Determinate LoadingBar (shows progress percentage)
 */
interface DeterminateLoadingBarProps {
  loading: boolean;
  progress: number; // 0-100
}

export const DeterminateLoadingBar: React.FC<DeterminateLoadingBarProps> = ({
  loading,
  progress
}) => {
  if (!loading) return null;

  return (
    <StyledLoadingBar
      variant="determinate"
      value={Math.min(100, Math.max(0, progress))}
    />
  );
};

export default LoadingBar;
