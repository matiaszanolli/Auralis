/**
 * WebSocketManager reconnect / heartbeat / close, against the REAL class (#5670).
 *
 * Every other spec mocks WebSocketManager wholesale, so its retry scheduler had
 * no assertions at all and the double-scheduling bug (#5602) shipped: a refused
 * connection fires `error` then `close`, and both used to schedule a retry.
 * Only the browser `WebSocket` is faked here.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { WebSocketManager } from '../errorHandling';

class FakeWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;
  static instances: FakeWebSocket[] = [];
  static throwOnConstruct = false;

  readyState = FakeWebSocket.CONNECTING;
  binaryType = 'blob';
  onopen: (() => void) | null = null;
  onclose: ((e: { code: number }) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  sent: unknown[] = [];

  constructor(public url: string) {
    if (FakeWebSocket.throwOnConstruct) throw new Error('SyntaxError: bad url');
    FakeWebSocket.instances.push(this);
  }

  send(data: unknown): void {
    this.sent.push(data);
  }

  close(): void {
    this.readyState = FakeWebSocket.CLOSED;
  }

  /** A refused connection: the browser fires `error`, then `close`. */
  fail(): void {
    this.readyState = FakeWebSocket.CLOSED;
    this.onerror?.(new Event('error'));
    this.onclose?.({ code: 1006 });
  }

  open(): void {
    this.readyState = FakeWebSocket.OPEN;
    this.onopen?.();
  }

  /** The server went away after a successful connection. */
  drop(): void {
    this.readyState = FakeWebSocket.CLOSED;
    this.onclose?.({ code: 1006 });
  }

  /** The server rejected this connection by policy (e.g. untrusted Origin). */
  rejectPolicy(): void {
    this.readyState = FakeWebSocket.CLOSED;
    this.onerror?.(new Event('error'));
    this.onclose?.({ code: 1008 });
  }
}

const sockets = () => FakeWebSocket.instances;
const openSockets = () => sockets().filter(s => s.readyState === FakeWebSocket.OPEN);

function makeManager(over: Partial<ConstructorParameters<typeof WebSocketManager>[1]> = {}) {
  const onMax = vi.fn();
  const onAttempt = vi.fn();
  const manager = new WebSocketManager('ws://test/ws', {
    maxReconnectAttempts: 3,
    initialReconnectDelayMs: 100,
    backoffMultiplier: 1,
    maxReconnectDelayMs: 100,
    onMaxAttemptsExceeded: onMax,
    onReconnectAttempt: onAttempt,
    ...over,
  });
  return { manager, onMax, onAttempt };
}

/**
 * Fail socket `i` and let promise callbacks run. A refused connection rejects
 * connect()'s promise from `error` and fires `close` — the retry scheduler that
 * hangs off the rejection runs as a microtask, so a synchronous test would
 * never see a second scheduler (#5602).
 */
async function failSocket(i: number): Promise<void> {
  sockets()[i].fail();
  await Promise.resolve();
  await Promise.resolve();
}

/** Start connecting and swallow the rejection a failed attempt reports. */
function startConnect(manager: WebSocketManager): Promise<void> {
  const p = manager.connect();
  p.catch(() => undefined);
  return p;
}

describe('WebSocketManager (real class)', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    FakeWebSocket.instances = [];
    FakeWebSocket.throwOnConstruct = false;
    vi.stubGlobal('WebSocket', FakeWebSocket);
    vi.spyOn(console, 'log').mockImplementation(() => undefined);
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  describe('reconnect scheduling (#5602)', () => {
    it('consumes exactly one attempt and one timer per failed connection', async () => {
      const { manager, onAttempt } = makeManager();
      startConnect(manager);

      await failSocket(0); // error + close

      expect(onAttempt).toHaveBeenCalledTimes(1);
      expect(vi.getTimerCount()).toBe(1);
    });

    it('gives up after maxReconnectAttempts real retries and reports it once', async () => {
      const { manager, onMax, onAttempt } = makeManager();
      startConnect(manager);
      await failSocket(0);

      for (let retry = 1; retry <= 3; retry++) {
        vi.advanceTimersByTime(100);
        expect(sockets()).toHaveLength(retry + 1);
        await failSocket(retry);
      }

      expect(onAttempt).toHaveBeenCalledTimes(3);
      expect(onMax).toHaveBeenCalledTimes(1);
      expect(vi.getTimerCount()).toBe(0);
      expect(sockets()).toHaveLength(4);
    });

    it('applies exponential backoff between attempts', async () => {
      const { manager, onAttempt } = makeManager({
        maxReconnectAttempts: 10,
        initialReconnectDelayMs: 100,
        backoffMultiplier: 2,
        maxReconnectDelayMs: 350,
      });
      startConnect(manager);
      await failSocket(0);
      vi.advanceTimersByTime(100);
      await failSocket(1);
      vi.advanceTimersByTime(200);
      await failSocket(2);
      vi.advanceTimersByTime(350); // 100*2^2 = 400, capped at 350

      expect(onAttempt.mock.calls.map(c => c[1])).toEqual([100, 200, 350]);
      expect(sockets()).toHaveLength(4);
    });

    it('retries when the socket cannot even be constructed', () => {
      const { manager, onAttempt } = makeManager();
      FakeWebSocket.throwOnConstruct = true;

      const p = startConnect(manager);

      expect(onAttempt).toHaveBeenCalledTimes(1);
      expect(vi.getTimerCount()).toBe(1);
      return expect(p).rejects.toThrow('bad url');
    });

    it('ends with one live socket, one onOpen and one heartbeat when the server returns', async () => {
      const onOpen = vi.fn();
      const { manager } = makeManager({ maxReconnectAttempts: 10 });
      manager.on('open', onOpen);
      startConnect(manager);

      await failSocket(0);
      vi.advanceTimersByTime(100);
      await failSocket(1);
      vi.advanceTimersByTime(100);
      sockets()[2].open();

      expect(openSockets()).toHaveLength(1);
      expect(onOpen).toHaveBeenCalledTimes(1);
      // Only the heartbeat interval remains — no stray retry timers.
      expect(vi.getTimerCount()).toBe(1);
      expect(sockets()).toHaveLength(3);
    });

    it('reconnects after an established connection drops and resets the budget on success', () => {
      const { manager, onAttempt } = makeManager();
      startConnect(manager);
      sockets()[0].open();

      sockets()[0].drop();
      expect(onAttempt).toHaveBeenLastCalledWith(1, 100);

      vi.advanceTimersByTime(100);
      sockets()[1].open();
      sockets()[1].drop();

      // Budget was reset by the successful reopen, so this is attempt 1 again.
      expect(onAttempt).toHaveBeenLastCalledWith(1, 100);
    });
  });

  describe('close-code handling (#5469)', () => {
    it('gives up immediately on a 1008 policy rejection without spending a retry', async () => {
      const { manager, onMax, onAttempt } = makeManager();
      startConnect(manager);

      sockets()[0].rejectPolicy();
      await Promise.resolve();
      await Promise.resolve();

      expect(onMax).toHaveBeenCalledTimes(1);
      expect(onAttempt).not.toHaveBeenCalled();
      expect(vi.getTimerCount()).toBe(0);
      vi.advanceTimersByTime(60_000);
      expect(sockets()).toHaveLength(1);
    });

    it('keeps retrying a transient abnormal (1006) closure', async () => {
      const { manager, onMax, onAttempt } = makeManager();
      startConnect(manager);

      await failSocket(0);

      expect(onMax).not.toHaveBeenCalled();
      expect(onAttempt).toHaveBeenCalledTimes(1);
      expect(vi.getTimerCount()).toBe(1);
    });
  });

  describe('close()', () => {
    it('cancels the pending retry so no socket opens afterwards', async () => {
      const { manager } = makeManager();
      startConnect(manager);
      await failSocket(0);
      expect(vi.getTimerCount()).toBe(1);

      manager.close();

      expect(vi.getTimerCount()).toBe(0);
      vi.advanceTimersByTime(10_000);
      expect(sockets()).toHaveLength(1);
    });

    it('does not reconnect when the intentionally closed socket fires close', () => {
      const { manager, onAttempt } = makeManager();
      startConnect(manager);
      const ws = sockets()[0];
      ws.open();

      manager.close();
      ws.onclose?.({ code: 1000 }); // a late close event, if the handler were still attached

      expect(onAttempt).not.toHaveBeenCalled();
      expect(vi.getTimerCount()).toBe(0);
    });

    it('stops the heartbeat', () => {
      const { manager } = makeManager();
      startConnect(manager);
      sockets()[0].open();
      expect(vi.getTimerCount()).toBe(1);

      manager.close();

      expect(vi.getTimerCount()).toBe(0);
    });
  });

  describe('replacing a socket', () => {
    it('detaches the previous socket so it cannot dispatch or schedule retries', () => {
      const onMessage = vi.fn();
      const { manager, onAttempt } = makeManager();
      manager.on('message', onMessage);
      startConnect(manager);
      const first = sockets()[0];
      first.open();

      startConnect(manager); // explicit second connect() while the first is live
      const second = sockets()[1];

      expect(first.readyState).toBe(FakeWebSocket.CLOSED);
      expect(first.onmessage).toBeNull();
      expect(first.onclose).toBeNull();
      second.open();
      second.onmessage?.(new MessageEvent('message', { data: 'x' }));
      expect(onMessage).toHaveBeenCalledTimes(1);
      expect(onAttempt).not.toHaveBeenCalled();
    });

    it('never runs two heartbeat intervals at once', () => {
      const { manager } = makeManager();
      startConnect(manager);
      sockets()[0].open();
      startConnect(manager);
      sockets()[1].open();

      expect(vi.getTimerCount()).toBe(1);
      vi.advanceTimersByTime(30_000);
      expect(sockets()[1].sent).toEqual([JSON.stringify({ type: 'heartbeat' })]);
      expect(sockets()[0].sent).toEqual([]);
    });
  });

  describe('send / isConnected', () => {
    it('only sends while the socket is open', () => {
      const { manager } = makeManager();
      startConnect(manager);
      expect(manager.send('a')).toBe(false);
      expect(manager.isConnected()).toBe(false);

      sockets()[0].open();
      expect(manager.send('b')).toBe(true);
      expect(manager.isConnected()).toBe(true);
      expect(sockets()[0].sent).toContain('b');
    });
  });
});
