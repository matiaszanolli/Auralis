import React from 'react';
import { StatusIndicator } from './AppTopBar.styles';

interface AppTopBarStatusIndicatorProps {
  color: string;
}

/**
 * AppTopBarStatusIndicator - Connection status dot with glow effect
 *
 * Displays colored dot with glow to indicate connection status.
 */
export const AppTopBarStatusIndicator: React.FC<AppTopBarStatusIndicatorProps> = ({
  color,
}) => {
  return <StatusIndicator color={color} />;
};

export default AppTopBarStatusIndicator;
