/**
 * Enhanced Playback Controls Component - Phase 3: Layered Architecture
 *
 * UI controls for triggering and managing WebSocket-based PCM audio streaming.
 * Now uses a two-layer architecture:
 * - IdentityLayer: Always visible, ambient minimal display
 * - InspectionLayer: Revealed on interaction, detailed controls
 *
 * This component is now a thin wrapper around EnhancementPane for backward compatibility.
 *
 * Features:
 * - Play Enhanced button with preset selector
 * - Intensity slider (0.0-1.0)
 * - Real-time streaming status indicator
 * - Pause/stop buttons during streaming
 * - Error message display
 * - Two-layer interaction model (ambient → detailed on click)
 */

import React from 'react';
import { EnhancementPane } from './EnhancementPane';
import type { PresetName } from '@/store/slices/playerSlice';

/**
 * Props for EnhancedPlaybackControls component
 */
export interface EnhancedPlaybackControlsProps {
  /** Track ID to play enhanced */
  trackId: number;

  /** Callback when playback starts */
  onPlayEnhanced?: (preset: PresetName, intensity: number) => void;

  /** Disable controls */
  disabled?: boolean;

  /** Show detailed status (DEPRECATED: Now always shown in InspectionLayer) */
  showStatus?: boolean;
}

/**
 * EnhancedPlaybackControls Component - Phase 3: Thin Wrapper
 *
 * Main interface for initiating enhanced audio playback streaming.
 * Now delegates to EnhancementPane for layered architecture.
 */
export const EnhancedPlaybackControls: React.FC<
  EnhancedPlaybackControlsProps
> = ({ trackId, onPlayEnhanced, disabled = false }) => {
  // Forward all props to EnhancementPane (showStatus is deprecated, ignored)
  return (
    <EnhancementPane
      trackId={trackId}
      onPlayEnhanced={onPlayEnhanced}
      disabled={disabled}
    />
  );
};

export default EnhancedPlaybackControls;
