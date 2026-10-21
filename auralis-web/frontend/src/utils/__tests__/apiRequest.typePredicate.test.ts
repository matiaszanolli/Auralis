/**
 * `validate` ↔ `T` predicate linkage (#5637)
 *
 * The bulk of the transport's contract is compile-time, so this spec's
 * assertions are mostly type-level: the `@ts-expect-error` lines are only
 * satisfied while `RequestOptions.validate` stays a predicate tied to the
 * call's `T`. Sever that link (revert `validate` to `(v: unknown) => boolean`,
 * or loosen it to accept any boolean guard) and `pnpm run type-check` fails
 * here — an "unused @ts-expect-error" — which is the regression signal.
 */

import { describe, it, expect } from 'vitest';
import { get } from '@/utils/apiRequest';
import { isQueueResponseShape, isTracksListShape } from '@/api/responseGuards';
import type { QueueResponse } from '@/services/queueService';
import type { TracksApiResponse } from '@/api/transformers';

/** Never invoked — this helper exists so its body gets type-checked. */
function compileTimePairings(): Promise<QueueResponse> {
  // A guard paired with a `T` of a different shape must not compile.
  // @ts-expect-error isTracksListShape asserts TracksApiResponse, not QueueResponse
  get<QueueResponse>('/api/library/tracks', { validate: isTracksListShape });

  // @ts-expect-error isQueueResponseShape asserts QueueResponse, not TracksApiResponse
  get<TracksApiResponse>('/api/player/queue', { validate: isQueueResponseShape });

  // The matching pairing compiles, and the declared type flows through.
  return get<QueueResponse>('/api/player/queue', { validate: isQueueResponseShape });
}

describe('validate predicate ↔ T linkage (#5637)', () => {
  it('type-checks the guard/T pairings above', () => {
    // The real assertions are the @ts-expect-error lines in the helper,
    // enforced by `pnpm run type-check` (gated in CI, #5640). This run-time
    // body only proves the file executes.
    expect(typeof compileTimePairings).toBe('function');
  });
});
