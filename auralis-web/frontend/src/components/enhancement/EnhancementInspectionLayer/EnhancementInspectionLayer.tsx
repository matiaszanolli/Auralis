import React from 'react';
import { tokens } from '@/design-system';
import { FingerprintIndicator } from './FingerprintIndicator';
import { PresetSelector } from './PresetSelector';
import { PlaybackControls } from './PlaybackControls';
import { StreamingStatus } from './StreamingStatus';
import type { EnhancementInspectionLayerProps } from './types';

export const EnhancementInspectionLayer = ({
  selectedPreset,
  intensity,
  fingerprintStatus,
  fingerprintMessage,
  streamingState,
  progress,
  processedChunks,
  totalChunks,
  currentTime,
  isPaused,
  error,
  isStreaming,
  disabled = false,
  onPresetChange,
  onIntensityChange,
  onPlayEnhanced,
  onTogglePause,
  onStop,
  onDismissError,
}: EnhancementInspectionLayerProps) => {
  return (
    <div style={styles.container}>
      <FingerprintIndicator
        fingerprintStatus={fingerprintStatus}
        fingerprintMessage={fingerprintMessage}
      />

      <PresetSelector
        selectedPreset={selectedPreset}
        disabled={disabled}
        onPresetChange={onPresetChange}
      />

      <PlaybackControls
        intensity={intensity}
        isPaused={isPaused}
        isStreaming={isStreaming}
        disabled={disabled}
        error={error}
        onIntensityChange={onIntensityChange}
        onPlayEnhanced={onPlayEnhanced}
        onTogglePause={onTogglePause}
        onStop={onStop}
        onDismissError={onDismissError}
      />

      <StreamingStatus
        streamingState={streamingState}
        progress={progress}
        processedChunks={processedChunks}
        totalChunks={totalChunks}
        currentTime={currentTime}
        isStreaming={isStreaming}
      />
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: 'flex',
    flexDirection: 'column',
    gap: tokens.spacing.md,
    padding: tokens.spacing.lg,
    borderRadius: tokens.borderRadius.md,
    background: tokens.glass.medium.background,
    backdropFilter: tokens.glass.medium.backdropFilter,
    border: tokens.glass.medium.border,
    boxShadow: tokens.glass.medium.boxShadow,
  },
};

export default EnhancementInspectionLayer;
