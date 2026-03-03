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
export const AppTopBarStatusIndicator = ({
  color,
}: AppTopBarStatusIndicatorProps) => {
  return <StatusIndicator color={color} />;
};

export default AppTopBarStatusIndicator;
