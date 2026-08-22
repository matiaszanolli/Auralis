/**
 * MockWebSocket.send() WHATWG semantics (#4491)
 *
 * Per https://websockets.spec.whatwg.org/#dom-websocket-send, send() throws
 * only while CONNECTING; while CLOSING/CLOSED it's a silent no-op. The mock
 * used to throw for any non-OPEN state, misrepresenting real behavior.
 */

import { describe, expect, it } from 'vitest';
import { MockWebSocket, CONNECTING, OPEN, CLOSING, CLOSED } from '@/test/mocks/websocket';

describe('MockWebSocket.send()', () => {
  it('throws while CONNECTING', () => {
    const ws = new MockWebSocket('ws://localhost/ws');
    expect(ws.readyState).toBe(CONNECTING);
    expect(() => ws.send('hello')).toThrow();
  });

  it('sends without throwing while OPEN', () => {
    const ws = new MockWebSocket('ws://localhost/ws');
    ws.readyState = OPEN;
    expect(() => ws.send('hello')).not.toThrow();
  });

  it('is a silent no-op while CLOSING', () => {
    const ws = new MockWebSocket('ws://localhost/ws');
    ws.readyState = CLOSING;
    expect(() => ws.send('hello')).not.toThrow();
  });

  it('is a silent no-op while CLOSED', () => {
    const ws = new MockWebSocket('ws://localhost/ws');
    ws.readyState = CLOSED;
    expect(() => ws.send('hello')).not.toThrow();
  });
});
