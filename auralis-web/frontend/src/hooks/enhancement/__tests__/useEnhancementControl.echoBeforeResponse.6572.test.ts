/**
 * The confirmation broadcast can beat the POST response (#6572).
 *
 * The server awaits its `enhancement_settings_changed` broadcast before it returns the toggle's HTTP
 * response, so the WebSocket frame can arrive first. The local-command mark used to be set only
 * after the POST resolved, so that early echo read as an external (Settings) change and re-issued
 * the stream - and then the toggle's own apply re-issued it a second time.
 */
import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useEnhancementControl } from '@/hooks/enhancement/useEnhancementControl';
import { useRestAPI } from '@/hooks/api/useRestAPI';
import { useWebSocketMessages } from '@/hooks/websocket/useWebSocketMessages';
import * as WebSocketContextModule from '@/contexts/WebSocketContext';
import { LOCAL_COMMAND_SUPPRESS_MS } from '@/hooks/enhancement/enhancementBroadcastReissue';

vi.mock('@/hooks/api/useRestAPI');
vi.mock('@/hooks/websocket/useWebSocketMessages');

const disabledBroadcast = () => ({
  type: 'enhancement_settings_changed',
  data: { enabled: false, preset: 'adaptive', intensity: 0.8 },
});

describe('enhancement echo that arrives before the POST response (#6572)', () => {
  // The suppression window is module state: start each test past the previous one's window.
  const realNow = Date.now.bind(Date);
  let clockOffset = 0;
  let clock: ReturnType<typeof vi.spyOn> | undefined;
  beforeEach(() => {
    vi.clearAllMocks();
    clockOffset += LOCAL_COMMAND_SUPPRESS_MS * 10;
    clock = vi.spyOn(Date, 'now').mockImplementation(() => realNow() + clockOffset);
  });
  afterEach(() => clock?.mockRestore());

  function setup(post: ReturnType<typeof vi.fn>) {
    const reissue = vi.fn().mockReturnValue(false);
    vi.spyOn(WebSocketContextModule, 'useWebSocketContext').mockReturnValue({
      reissueActiveStreamAs: reissue,
    } as unknown as ReturnType<typeof WebSocketContextModule.useWebSocketContext>);
    vi.mocked(useRestAPI).mockReturnValue({
      get: vi.fn().mockResolvedValue({ enabled: true, preset: 'adaptive', intensity: 0.8 }),
      post, put: vi.fn(), patch: vi.fn(), delete: vi.fn(),
    } as unknown as ReturnType<typeof useRestAPI>);
    let handler: ((m: unknown) => void) | undefined;
    vi.mocked(useWebSocketMessages).mockImplementation(((types: string[], fn: (m: unknown) => void) => {
      if (types.includes('enhancement_settings_changed')) handler = fn;
    }) as unknown as typeof useWebSocketMessages);
    return { reissue, deliver: (m: unknown) => handler!(m) };
  }

  it('re-issues exactly once when the broadcast precedes the response', async () => {
    let respond!: () => void;
    const post = vi.fn(() => new Promise<void>((resolve) => { respond = resolve; }));
    const { reissue, deliver } = setup(post);
    const { result } = renderHook(() => useEnhancementControl());
    await act(async () => {}); // initial fetch: enabled

    let toggled!: Promise<void>;
    act(() => { toggled = result.current.toggleEnabled(); });
    act(() => { deliver(disabledBroadcast()); }); // the server's echo wins the race
    await act(async () => { respond(); await toggled; });

    expect(reissue).toHaveBeenCalledTimes(1);
    expect(reissue).toHaveBeenCalledWith('play_normal');
  });

  it('honours a genuine external change right after a failed local command', async () => {
    const post = vi.fn().mockRejectedValue(new Error('server down'));
    const { reissue, deliver } = setup(post);
    const { result } = renderHook(() => useEnhancementControl());
    await act(async () => {});

    await act(async () => { await result.current.toggleEnabled().catch(() => undefined); });
    expect(reissue).not.toHaveBeenCalled();

    act(() => { deliver(disabledBroadcast()); }); // e.g. the Settings dialog disabled it
    await act(async () => {});

    expect(reissue).toHaveBeenCalledTimes(1);
    expect(reissue).toHaveBeenCalledWith('play_normal');
  });
});
