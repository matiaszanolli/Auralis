/**
 * WebSocket subscribe handlers are typed per message (#5636)
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * `subscribe()` used to type every handler as
 * `(AnyWebSocketMessage | WebSocketMessage) => void`; the generic
 * `WebSocketMessage` member absorbed every specific interface, so `message`
 * could never narrow and ~20 consumers re-asserted its shape with hand-written
 * casts the compiler could not check against `types/ws/*`.
 *
 * These are compile-time assertions: `tsc` (pnpm run type-check) is the test,
 * and each `@ts-expect-error` fails the build if the line STOPS being an error.
 * The runtime body only keeps vitest from reporting an empty file.
 */

import { describe, it, expect } from 'vitest';
import type {
  MessageOf,
  TypedMessageHandler,
} from '@/contexts/WebSocketContext';
import type {
  PositionChangedMessage,
  TrackChangedMessage,
  VolumeChangedMessage,
  WebSocketMessageType,
} from '@/types/websocket';
import type { MessageHandlers } from '@/hooks/websocket/useWebSocketMessages';

type Equal<A, B> = (<T>() => T extends A ? 1 : 2) extends <T>() => T extends B ? 1 : 2 ? true : false;
const assertType = <_T extends true>(): void => {};

describe('subscribe handler typing (#5636)', () => {
  it('narrows the handler message to the subscribed type, with no cast', () => {
    assertType<Equal<MessageOf<'position_changed'>, PositionChangedMessage>>();
    assertType<Equal<MessageOf<'volume_changed'>, VolumeChangedMessage>>();
    assertType<Equal<MessageOf<'track_changed'>, TrackChangedMessage>>();

    // The issue's acceptance case: `m.data.position` compiles on the narrowed type.
    const onPosition: TypedMessageHandler<'position_changed'> = (m) => m.data.position;
    expect(typeof onPosition).toBe('function');
  });

  it('rejects reading a field the subscribed message does not have', () => {
    const bad: TypedMessageHandler<'position_changed'> = (m) => {
      // @ts-expect-error — `volume` belongs to volume_changed, not position_changed
      return m.data.volume;
    };
    expect(typeof bad).toBe('function');
  });

  it('rejects a handler written for a different message type', () => {
    // @ts-expect-error — a volume_changed handler cannot be registered for position_changed
    const mismatched: TypedMessageHandler<'position_changed'> = (m: VolumeChangedMessage) => m.data.volume;
    expect(typeof mismatched).toBe('function');
  });

  it('MessageHandlers maps each key to that key\'s narrowed handler', () => {
    const handlers: MessageHandlers = {
      volume_changed: (m) => m.data.volume,
      // @ts-expect-error — position_changed's handler receives PositionChangedMessage
      position_changed: (m: VolumeChangedMessage) => m.data.volume,
    };
    expect(Object.keys(handlers)).toHaveLength(2);
  });

  it('every message-type literal resolves to a message interface (none collapse to never)', () => {
    type Unresolved = {
      [K in WebSocketMessageType]: [MessageOf<K>] extends [never] ? K : never;
    }[WebSocketMessageType];
    assertType<Equal<Unresolved, never>>();
    expect(true).toBe(true);
  });
});
