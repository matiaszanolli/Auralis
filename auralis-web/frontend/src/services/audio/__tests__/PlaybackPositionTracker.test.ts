/**
 * PlaybackPositionTracker Tests (#4301)
 *
 * Isolated unit tests for the state machine + position/timing bookkeeping
 * extracted from AudioPlaybackEngine. No Web Audio API surface involved.
 */

import { describe, it, expect, vi } from 'vitest';
import { PlaybackPositionTracker } from '../PlaybackPositionTracker';

describe('PlaybackPositionTracker', () => {
  it('starts idle and not playing', () => {
    const tracker = new PlaybackPositionTracker();
    expect(tracker.getState()).toBe('idle');
    expect(tracker.isPlaying()).toBe(false);
  });

  describe('setState', () => {
    it('notifies the state-change callback on an actual transition', () => {
      const tracker = new PlaybackPositionTracker();
      const onStateChange = vi.fn();
      tracker.onStateChanged(onStateChange);

      tracker.setState('playing');

      expect(onStateChange).toHaveBeenCalledWith('playing');
      expect(tracker.isPlaying()).toBe(true);
    });

    it('does not notify when setting the same state again', () => {
      const tracker = new PlaybackPositionTracker();
      tracker.setState('playing');
      const onStateChange = vi.fn();
      tracker.onStateChanged(onStateChange);

      tracker.setState('playing');

      expect(onStateChange).not.toHaveBeenCalled();
    });

    it('unsubscribe stops further notifications', () => {
      const tracker = new PlaybackPositionTracker();
      const onStateChange = vi.fn();
      const unsubscribe = tracker.onStateChanged(onStateChange);

      unsubscribe();
      tracker.setState('playing');

      expect(onStateChange).not.toHaveBeenCalled();
    });
  });

  describe('getCurrentPlaybackTime', () => {
    const SAMPLE_RATE = 48000;

    it('returns 0 when idle', () => {
      const tracker = new PlaybackPositionTracker();
      expect(tracker.getCurrentPlaybackTime(SAMPLE_RATE)).toBe(0);
    });

    it('returns 0 when stopped', () => {
      const tracker = new PlaybackPositionTracker();
      tracker.setState('playing');
      tracker.setState('stopped');
      expect(tracker.getCurrentPlaybackTime(SAMPLE_RATE)).toBe(0);
    });

    it('returns the frozen pausedTime while paused, ignoring samplesPlayed', () => {
      const tracker = new PlaybackPositionTracker();
      tracker.setState('playing');
      tracker.setSamplesPlayed(SAMPLE_RATE * 10); // would be 10s if playing
      tracker.setPausedTime(3);
      tracker.setState('paused');

      expect(tracker.getCurrentPlaybackTime(SAMPLE_RATE)).toBe(3);
    });

    it('computes elapsed seconds from samplesPlayed while playing', () => {
      const tracker = new PlaybackPositionTracker();
      tracker.setState('playing');
      tracker.setSamplesPlayed(SAMPLE_RATE * 2);

      expect(tracker.getCurrentPlaybackTime(SAMPLE_RATE)).toBe(2);
    });

    it('adds the seek offset while playing', () => {
      const tracker = new PlaybackPositionTracker();
      tracker.setSeekOffset(30);
      tracker.setState('playing');

      expect(tracker.getCurrentPlaybackTime(SAMPLE_RATE)).toBe(30);
    });

    it('clamps a negative seek offset to 0', () => {
      const tracker = new PlaybackPositionTracker();
      tracker.setSeekOffset(-5);
      tracker.setState('playing');

      expect(tracker.getCurrentPlaybackTime(SAMPLE_RATE)).toBe(0);
    });
  });

  describe('samplesPlayed bookkeeping', () => {
    it('setSamplesPlayed sets an absolute value (worklet path)', () => {
      const tracker = new PlaybackPositionTracker();
      tracker.setSamplesPlayed(100);
      tracker.setSamplesPlayed(250);
      expect(tracker.getSamplesPlayed()).toBe(250);
    });

    it('addSamplesPlayed accumulates (script processor path)', () => {
      const tracker = new PlaybackPositionTracker();
      tracker.addSamplesPlayed(100);
      tracker.addSamplesPlayed(50);
      expect(tracker.getSamplesPlayed()).toBe(150);
    });
  });

  describe('reset', () => {
    it('clears pausedTime, samplesPlayed, and seekOffset', () => {
      const tracker = new PlaybackPositionTracker();
      tracker.setState('playing');
      tracker.setSamplesPlayed(1000);
      tracker.setSeekOffset(15);
      tracker.setPausedTime(7);

      tracker.reset();

      expect(tracker.getSamplesPlayed()).toBe(0);
      // With seekOffset and pausedTime cleared, playing time is back to 0.
      expect(tracker.getCurrentPlaybackTime(48000)).toBe(0);
    });

    it('does not itself change playback state', () => {
      const tracker = new PlaybackPositionTracker();
      tracker.setState('playing');

      tracker.reset();

      expect(tracker.getState()).toBe('playing');
    });
  });
});
