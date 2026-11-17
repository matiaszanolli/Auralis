/**
 * The MSW harness fails a spec that makes a REST call nothing answers (#5681).
 *
 * Unanswered /api calls used to become network failures that most hooks swallow, so specs passed
 * against a backend that never replied. setup.ts now records them and fails the test in afterEach.
 */

import { afterEach, describe, expect, it } from 'vitest';
import { unhandledApiRequests } from '../unhandledRequests';

afterEach(() => {
  unhandledApiRequests.length = 0; // this spec triggers one on purpose
});

describe('unhandled REST requests', () => {
  it('records an /api call with no handler, which setup.ts then fails the test for', async () => {
    await fetch('http://localhost:8765/api/no-such-endpoint-5681').catch(() => undefined);

    expect(unhandledApiRequests).toEqual(['GET /api/no-such-endpoint-5681']);
  });

  it.each([
    ['/api/player/enhancement/status', 'enabled'],
    ['/api/player/queue', 'queue'],
    ['/api/library/scan/status', 'is_scanning'],
    ['/api/library/fingerprints/status', 'total_tracks'],
    ['/api/cache/stats', 'tier1'],
    ['/api/settings', 'scan_folders'],
    ['/api/artists', 'artists'],
  ])('answers the initial-state read %s by default', async (path, field) => {
    const response = await fetch(`http://localhost:8765${path}`);

    expect(response.ok).toBe(true);
    expect(await response.json()).toHaveProperty(field);
    expect(unhandledApiRequests).toEqual([]);
  });
});
