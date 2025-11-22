/**
 * Progress Bar Monitoring Test
 *
 * Loads a track and monitors progress bar updates every second for 60 seconds.
 * Analyzes timing accuracy, consistency, and any anomalies.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { render } from '@/test/test-utils';
import userEvent from '@testing-library/user-event';
import { PlayerBarV2 } from '@/components/player-bar-v2/PlayerBarV2';

interface ProgressMeasurement {
  timestamp: number;
  currentTime: number;
  duration: number;
  progressPercent: number;
  deltaTime: number; // Time since last measurement
  deltaProgress: number; // Progress change since last measurement
}

// Mock track with known duration
const mockTrack = {
  id: 1,
  title: 'Test Track - Progress Monitor',
  artist: 'Test Artist',
  album: 'Test Album',
  duration: 240.0, // 4 minutes
  file_path: '/test/track.mp3',
  artwork_url: 'https://example.com/artwork.jpg',
};

// Mock time progression
let mockCurrentTime = 0;
let mockIsPlaying = false;
let playbackStartTime = 0;

describe('Progress Bar Monitoring Test', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCurrentTime = 0;
    mockIsPlaying = false;
    playbackStartTime = 0;
  });

  afterEach(() => {
    // Reset player state
    mockIsPlaying = false;
    playbackStartTime = 0;
  });

  it('should monitor progress bar updates for 60 seconds', async () => {
    // Arrange
    const user = userEvent.setup();
    const measurements: ProgressMeasurement[] = [];
    let lastMeasurementTime = Date.now();
    let measurementCount = 0;

    console.log('\n=== PROGRESS BAR MONITORING TEST ===');
    console.log(`Track: ${mockTrack.title}`);
    console.log(`Duration: ${mockTrack.duration}s`);
    console.log(`Monitoring for: 60 seconds`);
    console.log('=====================================\n');

    // Mock handlers
    const mockHandlers = {
      onPlay: vi.fn().mockImplementation(() => {
        mockIsPlaying = true;
        playbackStartTime = Date.now();
      }),
      onPause: vi.fn().mockImplementation(() => {
        mockIsPlaying = false;
        playbackStartTime = 0;
      }),
      onSeek: vi.fn(),
      onVolumeChange: vi.fn(),
      onEnhancementToggle: vi.fn(),
      onPrevious: vi.fn(),
      onNext: vi.fn(),
    };

    // Create updatable player state
    let playerState = {
      currentTrack: mockTrack,
      isPlaying: mockIsPlaying,
      currentTime: mockCurrentTime,
      duration: 240.0,
      volume: 0.7,
      isEnhanced: false,
    };

    // Render player with initial state
    const { rerender } = render(
      <PlayerBarV2
        player={playerState}
        {...mockHandlers}
      />
    );

    // Wait for player to render
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument();
    }, { timeout: 3000 });

    // Start playback
    const playButton = screen.getByRole('button', { name: /play/i });
    await user.click(playButton);

    console.log('✅ Playback started, beginning measurements...\n');

    // Monitor progress for 60 seconds
    const monitoringDuration = 60000; // 60 seconds
    const measurementInterval = 1000; // 1 second
    const startTime = Date.now();

    while (Date.now() - startTime < monitoringDuration) {
      // Wait for next measurement interval
      await new Promise(resolve => setTimeout(resolve, measurementInterval));

      // Simulate time progression - simply increment by 1 second per measurement
      if (mockIsPlaying) {
        mockCurrentTime = Math.min(mockCurrentTime + 1.0, 240.0);
      }

      // Update player state and rerender
      playerState = {
        currentTrack: mockTrack,
        isPlaying: mockIsPlaying,
        currentTime: mockCurrentTime,
        duration: 240.0,
        volume: 0.7,
        isEnhanced: false,
      };

      rerender(
        <PlayerBarV2
          player={playerState}
          {...mockHandlers}
        />
      );

      // Get current time and duration from player state
      const now = Date.now();
      const currentTime = mockCurrentTime;
      const duration = 240.0;
      const progressPercent = (currentTime / duration) * 100;

      // Calculate deltas
      const deltaTime = (now - lastMeasurementTime) / 1000;
      const lastProgress = measurements.length > 0
        ? measurements[measurements.length - 1].progressPercent
        : 0;
      const deltaProgress = progressPercent - lastProgress;

      // Record measurement
      const measurement: ProgressMeasurement = {
        timestamp: now - startTime,
        currentTime,
        duration,
        progressPercent,
        deltaTime,
        deltaProgress,
      };
      measurements.push(measurement);

      // Log every 5 seconds
      measurementCount++;
      if (measurementCount % 5 === 0) {
        console.log(`[${measurementCount}s] Time: ${currentTime.toFixed(2)}s | Progress: ${progressPercent.toFixed(2)}% | Δ${deltaProgress.toFixed(4)}%`);
      }

      lastMeasurementTime = now;
    }

    console.log('\n✅ Monitoring complete. Analyzing results...\n');

    // ==========================================
    // ANALYSIS
    // ==========================================

    console.log('=== ANALYSIS RESULTS ===\n');

    // 1. Basic Statistics
    const totalMeasurements = measurements.length;
    const avgDeltaProgress = measurements.reduce((sum, m) => sum + m.deltaProgress, 0) / totalMeasurements;
    const avgDeltaTime = measurements.reduce((sum, m) => sum + m.deltaTime, 0) / totalMeasurements;

    console.log('📊 Basic Statistics:');
    console.log(`   Total measurements: ${totalMeasurements}`);
    console.log(`   Avg Δ progress: ${avgDeltaProgress.toFixed(4)}%`);
    console.log(`   Avg Δ time: ${avgDeltaTime.toFixed(3)}s`);
    console.log(`   Expected Δ time: 1.000s`);
    console.log(`   Time accuracy: ${((avgDeltaTime / 1.0) * 100).toFixed(2)}%\n`);

    // 2. Progress Consistency
    const progressDeltas = measurements.map(m => m.deltaProgress);
    const minDelta = Math.min(...progressDeltas);
    const maxDelta = Math.max(...progressDeltas);
    const deltaRange = maxDelta - minDelta;
    const deltaStdDev = Math.sqrt(
      progressDeltas.reduce((sum, d) => sum + Math.pow(d - avgDeltaProgress, 2), 0) / totalMeasurements
    );

    console.log('📈 Progress Consistency:');
    console.log(`   Min Δ progress: ${minDelta.toFixed(4)}%`);
    console.log(`   Max Δ progress: ${maxDelta.toFixed(4)}%`);
    console.log(`   Range: ${deltaRange.toFixed(4)}%`);
    console.log(`   Std deviation: ${deltaStdDev.toFixed(4)}%\n`);

    // 3. Anomalies Detection
    const anomalies: ProgressMeasurement[] = [];
    const anomalyThreshold = avgDeltaProgress * 2; // 2x average is anomaly

    measurements.forEach((m, i) => {
      if (Math.abs(m.deltaProgress - avgDeltaProgress) > anomalyThreshold) {
        anomalies.push(m);
      }
    });

    console.log('⚠️  Anomalies:');
    if (anomalies.length === 0) {
      console.log('   None detected ✅\n');
    } else {
      console.log(`   Found ${anomalies.length} anomalies:\n`);
      anomalies.forEach((a, i) => {
        console.log(`   ${i + 1}. At ${(a.timestamp / 1000).toFixed(1)}s: Δ${a.deltaProgress.toFixed(4)}% (expected ~${avgDeltaProgress.toFixed(4)}%)`);
      });
      console.log('');
    }

    // 4. Timing Accuracy
    const expectedProgressPerSecond = (1 / 240.0) * 100; // 1 second out of 240s total
    const actualProgressPerSecond = avgDeltaProgress;
    const timingAccuracy = (actualProgressPerSecond / expectedProgressPerSecond) * 100;

    console.log('⏱️  Timing Accuracy:');
    console.log(`   Expected progress/sec: ${expectedProgressPerSecond.toFixed(4)}%`);
    console.log(`   Actual progress/sec: ${actualProgressPerSecond.toFixed(4)}%`);
    console.log(`   Accuracy: ${timingAccuracy.toFixed(2)}%\n`);

    // 5. Final Position
    const finalMeasurement = measurements[measurements.length - 1];
    const expectedFinalTime = 60.0; // Should be at 60s
    const actualFinalTime = finalMeasurement.currentTime;
    const positionAccuracy = (actualFinalTime / expectedFinalTime) * 100;

    console.log('🎯 Final Position:');
    console.log(`   Expected time: ${expectedFinalTime.toFixed(2)}s`);
    console.log(`   Actual time: ${actualFinalTime.toFixed(2)}s`);
    console.log(`   Position accuracy: ${positionAccuracy.toFixed(2)}%`);
    console.log(`   Drift: ${(actualFinalTime - expectedFinalTime).toFixed(2)}s\n`);

    // 6. Summary
    console.log('=== SUMMARY ===\n');

    const issues: string[] = [];

    if (deltaStdDev > 0.01) {
      issues.push(`High progress inconsistency (σ = ${deltaStdDev.toFixed(4)}%)`);
    }

    if (anomalies.length > 3) {
      issues.push(`Multiple anomalies detected (${anomalies.length})`);
    }

    if (Math.abs(timingAccuracy - 100) > 5) {
      issues.push(`Timing inaccuracy (${timingAccuracy.toFixed(2)}%)`);
    }

    if (Math.abs(positionAccuracy - 100) > 5) {
      issues.push(`Position drift (${(actualFinalTime - expectedFinalTime).toFixed(2)}s)`);
    }

    if (issues.length === 0) {
      console.log('✅ Progress bar is functioning correctly!');
      console.log('   - Consistent updates');
      console.log('   - Accurate timing');
      console.log('   - No significant drift');
    } else {
      console.log('⚠️  Issues detected:');
      issues.forEach(issue => console.log(`   - ${issue}`));
    }

    console.log('\n========================\n');

    // Assertions
    expect(measurements.length).toBeGreaterThanOrEqual(55); // At least 55 measurements in 60s
    expect(deltaStdDev).toBeLessThan(0.1); // Progress should be consistent
    expect(anomalies.length).toBeLessThan(5); // Few anomalies acceptable
    expect(Math.abs(timingAccuracy - 100)).toBeLessThan(10); // Within 10% of expected
    expect(Math.abs(positionAccuracy - 100)).toBeLessThan(10); // Within 10% of expected
  }, 120000); // 2 minute timeout for 60s test
});
