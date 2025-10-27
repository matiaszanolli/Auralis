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

  // Get enhancement settings (MUST be before using enhancementSettings!)
  const { settings: enhancementSettings } = useEnhancement();

  // MSE only works with unenhanced playback (for now)
  // When enhancement is enabled, fall back to HTML5 Audio which supports real-time enhancement
  const mseCompatible = isMSESupported && !enhancementSettings.enabled;
  const [useMSE, setUseMSE] = useState(mseCompatible);

  // Get player state from API
  const {
    currentTrack,
    isPlaying,
    currentTime: apiCurrentTime,
    duration,
    queue,
    queueIndex
  } = usePlayerAPI();

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
        console.log('✅ MSE: Track initialized successfully');

        // DON'T auto-play here - playback is handled by the sync effect below (lines 129-139)
        // This avoids browser autoplay restrictions which would cause initialization to fail
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
    // Don't sync if MSE not active or player not initialized
    if (!useMSE || !msePlayer.player) return;

    // Wait for player to be ready before syncing playback
    // States: 'idle' (not initialized), 'loading' (initializing), 'ready' (can play), 'playing', 'paused', 'error'
    if (msePlayer.state === 'idle' || msePlayer.state === 'loading') return;

    const syncPlayback = async () => {
      try {
        if (isPlaying && msePlayer.state !== 'playing') {
          console.log('🎵 MSE: Backend playing - starting playback');
          await msePlayer.play();
        } else if (!isPlaying && msePlayer.state === 'playing') {
          console.log('⏸️ MSE: Backend paused - pausing playback');
          msePlayer.pause();
        }
      } catch (error) {
        // Handle autoplay restrictions gracefully
        if (error instanceof DOMException && error.name === 'NotAllowedError') {
          console.warn('⚠️ MSE: Autoplay blocked by browser (user interaction required)');
          // Don't fall back - user just needs to click play button
        } else {
          console.error('MSE playback sync failed:', error);
          // Only fall back for actual errors, not autoplay restrictions
          setUseMSE(false);
          info('Falling back to standard player');
        }
      }
    };

    syncPlayback();
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

  // Update MSE state when enhancement settings change
  useEffect(() => {
    const shouldUseMSE = isMSESupported && !enhancementSettings.enabled;
    if (shouldUseMSE !== useMSE) {
      console.log(`🔄 Switching player mode: MSE=${shouldUseMSE} (enhancement=${enhancementSettings.enabled})`);

      // If switching FROM MSE to HTML5 Audio, destroy the MSE player completely
      if (useMSE && !shouldUseMSE && msePlayer.player) {
        console.log('🧹 Destroying MSE player (switching to HTML5 Audio mode)');
        msePlayer.player.destroy();
      }

      setUseMSE(shouldUseMSE);
    }
  }, [enhancementSettings.enabled, isMSESupported, useMSE, msePlayer]);

  // Show MSE status in console
  useEffect(() => {
    if (useMSE) {
      console.log('✅ MSE Player: Enabled (instant preset switching available, unenhanced mode only)');
    } else if (!isMSESupported) {
      console.log('⚠️ MSE Player: Not supported (falling back to HTML5 Audio)');
    } else {
      console.log('📢 MSE Player: Disabled (enhancement enabled - using HTML5 Audio for real-time processing)');
    }
  }, [useMSE, isMSESupported]);

  // Cleanup: Destroy MSE player when component unmounts
  useEffect(() => {
    return () => {
      if (msePlayer.player) {
        console.log('🧹 Component unmounting - destroying MSE player');
        msePlayer.player.destroy();
      }
    };
  }, [msePlayer]);

  // If MSE not supported or disabled, use original player
  if (!useMSE) {
    return <OriginalPlayerBar onToggleLyrics={onToggleLyrics} onTimeUpdate={onTimeUpdate} />;
  }

  // Get MSE audio element to pass to original player
  const mseAudioElement = msePlayer.getAudioElement();

  // Render original UI with MSE audio element
  // The original player will use our MSE audio element instead of creating its own
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

      {/* Original Player UI with MSE audio element */}
      <OriginalPlayerBar
        audioElement={mseAudioElement}
        onToggleLyrics={onToggleLyrics}
        onTimeUpdate={onTimeUpdate}
      />
    </>
  );
};

export default BottomPlayerBarConnectedMSE;
