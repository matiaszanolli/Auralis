import { renderHook } from '@testing-library/react';
import { useCommitId, getVersionString } from '../useCommitId';

describe('useCommitId', () => {
  const originalEnv = import.meta.env.VITE_COMMIT_ID;

  afterEach(() => {
    // Vitest env is mutable via vi.stubEnv
    vi.unstubAllEnvs();
    if (originalEnv !== undefined) {
      vi.stubEnv('VITE_COMMIT_ID', originalEnv);
    }
  });

  it('returns the commit ID when VITE_COMMIT_ID is set', () => {
    vi.stubEnv('VITE_COMMIT_ID', 'abc1234');
    const { result } = renderHook(() => useCommitId());
    expect(result.current).toBe('abc1234');
  });

  it('returns "unknown" when VITE_COMMIT_ID is not set', () => {
    vi.stubEnv('VITE_COMMIT_ID', '');
    const { result } = renderHook(() => useCommitId());
    expect(result.current).toBe('unknown');
  });
});

describe('getVersionString', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('includes the commit ID in the version string', () => {
    vi.stubEnv('VITE_COMMIT_ID', 'abc1234');
    const result = getVersionString();
    expect(result).toContain('abc1234');
  });

  it('includes "unknown" when VITE_COMMIT_ID is not set', () => {
    vi.stubEnv('VITE_COMMIT_ID', '');
    const result = getVersionString();
    expect(result).toContain('unknown');
  });
});
