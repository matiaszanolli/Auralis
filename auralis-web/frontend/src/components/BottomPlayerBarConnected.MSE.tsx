/**
 * BottomPlayerBarConnected - With MSE Support
 * ============================================
 *
 * Enhanced version with Media Source Extensions for instant preset switching.
 *
 * Key Changes:
 * - Detects MSE browser support
 * - Uses MSEPlayer when available for instant preset switching
 * - Falls back to HTML5 Audio for unsupported browsers
 * - Seamless switching between presets (<100ms vs 2-5s)
 *
 * Migration Strategy:
 * 1. Deploy this file alongside original
 * 2. Test MSE path thoroughly
 * 3. Once validated, replace original file
 *
 * @copyright (C) 2024 Auralis Team
 * @license: GPLv3
 */

import React, { useState, useEffect } from 'react';
import { useMSEPlayer } from '../hooks/useMSEPlayer';
import MSEPlayer from '../services/MSEPlayer';
import { useEnhancement } from '../contexts/EnhancementContext';
import { usePlayerAPI } from '../hooks/usePlayerAPI';
import { useToast } from './shared/Toast';

// Import original component to extend
import { BottomPlayerBarConnected as OriginalPlayerBar } from './BottomPlayerBarConnected';

/**
 * Wrapper component that adds MSE support to BottomPlayerBarConnected
 */
export const BottomPlayerBarConnectedMSE: React.FC<{
  onToggleLyrics?: () => void;
  onTimeUpdate?: (currentTime: number) => void;
}> = ({ onToggleLyrics, onTimeUpdate }) => {
  // Check MSE support
  const isMSESupported = MSEPlayer.isSupported();
  const [useMSE, setUseMSE] = useState(isMSESupported);

  // Get player state from API
  const {
    currentTrack,
    isPlaying,
    currentTime: apiCurrentTime,
    duration,
    queue,
    queueIndex
  } = usePlayerAPI();

  // Get enhancement settings
  const { settings: enhancementSettings } = useEnhancement();

  // Initialize MSE player if supported
  const msePlayer = useMSEPlayer({
    enhanced: enhancementSettings.enabled,
    preset: enhancementSettings.preset,
    intensity: enhancementSettings.intensity,
    debug: process.env.NODE_ENV === 'development',
    autoPlay: false
  });

  const { success, info } = useToast();

  // Track last preset to detect changes
  const lastPreset = React.useRef<string>(enhancementSettings.preset);

  // Initialize MSE player when track changes
  useEffect(() => {
    if (!useMSE || !currentTrack?.id) return;

    const initializeTrack = async () => {
      try {
        console.log('🎵 MSE: Initializing track', currentTrack.id);
        await msePlayer.initialize(currentTrack.id);

        // Start playback if backend says we should be playing
        if (isPlaying) {
          await msePlayer.play();
        }
      } catch (error) {
        console.error('MSE initialization failed, falling back to HTML5 Audio:', error);
        setUseMSE(false);
        info('Falling back to standard player');
      }
    };

    initializeTrack();
  }, [currentTrack?.id, useMSE]);

  // Handle preset changes with MSE (the magic!)
  useEffect(() => {
    if (!useMSE || !msePlayer.player) return;
    if (!enhancementSettings.enabled) return;

    const newPreset = enhancementSettings.preset;
    if (newPreset === lastPreset.current) return;

    const switchPreset = async () => {
      try {
        const startTime = performance.now();
        console.log(`🎨 MSE: Switching preset: ${lastPreset.current} → ${newPreset}`);

        await msePlayer.switchPreset(newPreset);

        const latency = performance.now() - startTime;
        console.log(`✨ Preset switched in ${latency.toFixed(1)}ms`);

        if (latency < 100) {
          success(`✨ Instant preset switch! (${latency.toFixed(0)}ms)`);
        } else if (latency < 500) {
          info(`Preset switched (${latency.toFixed(0)}ms)`);
        }

        lastPreset.current = newPreset;
      } catch (error) {
        console.error('Preset switch failed:', error);
        // Don't fall back - just log error
        // The old preset will continue playing
      }
    };

    switchPreset();
  }, [enhancementSettings.preset, useMSE, msePlayer.player]);

  // Sync playback state with backend
  useEffect(() => {
    if (!useMSE || !msePlayer.player || msePlayer.state === 'idle') return;

    if (isPlaying && msePlayer.state !== 'playing') {
      console.log('🎵 MSE: Backend playing - starting playback');
      msePlayer.play();
    } else if (!isPlaying && msePlayer.state === 'playing') {
      console.log('⏸️ MSE: Backend paused - pausing playback');
      msePlayer.pause();
    }
  }, [isPlaying, useMSE, msePlayer.state]);

  // Update enhancement enabled/disabled
  useEffect(() => {
    if (!useMSE || !msePlayer.player) return;

    msePlayer.updateSettings({
      enhanced: enhancementSettings.enabled,
      preset: enhancementSettings.preset,
      intensity: enhancementSettings.intensity
    });

    // If enhancement state changed, we need to reinitialize
    // (This is still a reload, but only when toggling on/off, not switching presets)
    if (currentTrack?.id) {
      console.log('🔄 MSE: Enhancement enabled/disabled - reinitializing');
      msePlayer.initialize(currentTrack.id).then(() => {
        if (isPlaying) {
          msePlayer.play();
        }
      });
    }
  }, [enhancementSettings.enabled, useMSE]);

  // Forward time updates
  useEffect(() => {
    if (!useMSE) return;

    if (onTimeUpdate) {
      onTimeUpdate(msePlayer.currentTime);
    }
  }, [msePlayer.currentTime, onTimeUpdate, useMSE]);

  // Show MSE status in console
  useEffect(() => {
    if (isMSESupported) {
      console.log('✅ MSE Player: Enabled (instant preset switching available)');
    } else {
      console.log('⚠️ MSE Player: Not supported (falling back to HTML5 Audio)');
    }
  }, [isMSESupported]);

  // If MSE not supported or disabled, use original player
  if (!useMSE) {
    return <OriginalPlayerBar onToggleLyrics={onToggleLyrics} onTimeUpdate={onTimeUpdate} />;
  }

  // If MSE supported, we still render the original UI but with MSE audio
  // The audio element from useMSEPlayer is automatically managed
  // We just need to override the controls to use MSE methods instead

  // For now, render original player with MSE running in background
  // TODO: Full UI integration to show MSE status and performance
  return (
    <>
      {/* MSE Status Indicator (development only) */}
      {process.env.NODE_ENV === 'development' && (
        <div
          style={{
            position: 'fixed',
            top: 10,
            right: 10,
            background: 'rgba(102, 126, 234, 0.9)',
            color: 'white',
            padding: '8px 12px',
            borderRadius: '4px',
            fontSize: '12px',
            zIndex: 10000,
            fontFamily: 'monospace'
          }}
        >
          <div>MSE: {msePlayer.state}</div>
          {msePlayer.lastChunk && (
            <div>
              Cache: {msePlayer.lastChunk.cache_tier} ({msePlayer.lastChunk.latency_ms?.toFixed(0)}ms)
            </div>
          )}
          {msePlayer.presetSwitchStats.count > 0 && (
            <div>
              Switches: {msePlayer.presetSwitchStats.count}
              (avg: {msePlayer.presetSwitchStats.avgLatencyMs.toFixed(0)}ms)
            </div>
          )}
        </div>
      )}

      {/* Original Player UI */}
      <OriginalPlayerBar onToggleLyrics={onToggleLyrics} onTimeUpdate={onTimeUpdate} />
    </>
  );
};

export default BottomPlayerBarConnectedMSE;
