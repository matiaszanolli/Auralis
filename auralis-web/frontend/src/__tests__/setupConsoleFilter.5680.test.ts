/**
 * The shared console.error filter is in effect inside a test (#5680)
 *
 * It was installed once at setup-file load; with `restoreMocks: true` that spy is restored before
 * the first test, so no test ever ran with the filter and its comment described a filter that was
 * not there. It is now installed in a beforeEach.
 */

import { describe, it, expect } from 'vitest';

describe('setup console.error filter', () => {
  it('is installed for the test body', () => {
    expect(vi.isMockFunction(console.error)).toBe(true);
  });

  it('swallows the known benign warnings and records them as calls', () => {
    console.error('Warning: React Router Future Flag Warning: v7_startTransition');
    console.error('Should not already be working.');

    expect(vi.mocked(console.error)).toHaveBeenCalledTimes(2);
  });

  it('is installed again for the next test (not a one-off)', () => {
    expect(vi.isMockFunction(console.error)).toBe(true);
    expect(vi.mocked(console.error)).not.toHaveBeenCalled();
  });
});
