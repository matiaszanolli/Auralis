/**
 * Outgoing WebSocket commands are a checked union (#6050): these specs hold the compile-time
 * contract, so `tsc` (pnpm run type-check) is what fails when a command shape drifts.
 */
import { describe, it, expect } from 'vitest';
import type { OutgoingCommand } from '../commands';

describe('OutgoingCommand', () => {
  it('accepts every command shape the backend handlers read', () => {
    const accepted: OutgoingCommand[] = [
      { type: 'play_enhanced', data: { track_id: 1, preset: 'adaptive', intensity: 0.5, force: true, start_position: 3 } },
      { type: 'play_normal', data: { track_id: 1, start_position: 3 } },
      { type: 'seek', data: { track_id: 1, position: 12.5 } },
      { type: 'pause' },
      { type: 'stop', data: {} },
      { type: 'buffer_full', data: {} },
      { type: 'buffer_ready', data: {} },
    ];
    expect(accepted.map((c) => c.type)).toEqual([
      'play_enhanced', 'play_normal', 'seek', 'pause', 'stop', 'buffer_full', 'buffer_ready',
    ]);
  });

  it('rejects a typo in the type, a misspelled field, a wrong field type and a missing required field', () => {
    const rejected: unknown[] = [
      // @ts-expect-error -- 'play_enhance' is not a command
      { type: 'play_enhance', data: { track_id: 1 } } satisfies OutgoingCommand,
      // @ts-expect-error -- the field is track_id, not trackId
      { type: 'play_normal', data: { trackId: 1 } } satisfies OutgoingCommand,
      // @ts-expect-error -- track_id is a number
      { type: 'seek', data: { track_id: '1', position: 2 } } satisfies OutgoingCommand,
      // @ts-expect-error -- seek needs its position
      { type: 'seek', data: { track_id: 1 } } satisfies OutgoingCommand,
      // @ts-expect-error -- play_normal takes no preset
      { type: 'play_normal', data: { track_id: 1, preset: 'adaptive' } } satisfies OutgoingCommand,
    ];
    expect(rejected).toHaveLength(5);
  });
});
