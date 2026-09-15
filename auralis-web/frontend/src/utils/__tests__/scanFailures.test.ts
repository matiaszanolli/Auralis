/**
 * scanFailures — shared scan-failure summary helpers (#4841, extracted #5466).
 */

import { describe, it, expect } from 'vitest';
import { describeFailures, baseName } from '../scanFailures';
import type { ScanFailure } from '@/types/ws/library';

describe('baseName', () => {
  it('returns the final path segment', () => {
    expect(baseName('/music/album/track.flac')).toBe('track.flac');
  });

  it('handles Windows-style separators', () => {
    expect(baseName('C:\\music\\album\\track.flac')).toBe('track.flac');
  });

  it('returns the input unchanged when there is no separator', () => {
    expect(baseName('track.flac')).toBe('track.flac');
  });
});

describe('describeFailures', () => {
  const failure = (filepath: string): ScanFailure => ({ filepath, reason: 'decode error' });

  it('returns an empty string when there are no failures', () => {
    expect(describeFailures(undefined, 0)).toBe('');
    expect(describeFailures([], 3)).toBe('');
  });

  it('lists all failed filenames when under the shown cap', () => {
    const failures = [failure('/a/one.flac'), failure('/a/two.mp3')];
    expect(describeFailures(failures, 2)).toBe('\none.flac, two.mp3');
  });

  it('caps the shown names and summarises the remainder', () => {
    const failures = [
      failure('/a/one.flac'),
      failure('/a/two.mp3'),
      failure('/a/three.wav'),
      failure('/a/four.ogg'),
      failure('/a/five.aac'),
    ];
    // MAX_FAILURES_SHOWN is 3 -- 2 more beyond that.
    expect(describeFailures(failures, 5)).toBe('\none.flac, two.mp3, three.wav and 2 more');
  });

  it('does not append "and N more" when the list is exactly the shown count', () => {
    const failures = [failure('/a/one.flac'), failure('/a/two.mp3'), failure('/a/three.wav')];
    expect(describeFailures(failures, 3)).toBe('\none.flac, two.mp3, three.wav');
  });
});
