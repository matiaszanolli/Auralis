/**
 * RepeatMode and StreamType each have one definition (#6048)
 *
 * They were re-typed as literals at ~15 and ~9 sites (two exported `StreamType`s among them), so
 * adding a member compiled with a miss. `expectTypeOf` fails `pnpm run type-check` if any of
 * these re-exports stops being the same type.
 */

import { describe, it, expectTypeOf } from 'vitest';
import type { RepeatMode, StreamType } from '@/types/domain';
import type { RepeatMode as SliceRepeatMode } from '@/store/slices/queueSlice';
import type { StreamType as SliceStreamType } from '@/store/slices/playerSlice';
import type { StreamType as CoreStreamType } from '@/hooks/enhancement/streamingCoreTypes';
import type { PlaybackWireType } from '@/hooks/enhancement/useEnhancedPlayCommand';
import type { QueueState } from '@/hooks/player/usePlaybackQueue';

describe('closed unions are single-sourced (#6048)', () => {
  it('RepeatMode is the same type everywhere it is re-exported or consumed', () => {
    expectTypeOf<SliceRepeatMode>().toEqualTypeOf<RepeatMode>();
    expectTypeOf<QueueState['repeatMode']>().toEqualTypeOf<RepeatMode>();
  });

  it('StreamType is one type, and the play_* wire type is that type', () => {
    expectTypeOf<SliceStreamType>().toEqualTypeOf<StreamType>();
    expectTypeOf<CoreStreamType>().toEqualTypeOf<StreamType>();
    expectTypeOf<PlaybackWireType>().toEqualTypeOf<StreamType>();
  });
});
