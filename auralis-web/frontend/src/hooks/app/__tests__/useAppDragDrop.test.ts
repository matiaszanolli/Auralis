import { describe, it, expect, beforeEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useAppDragDrop } from '../useAppDragDrop';
import { DropResult } from '@hello-pangea/dnd';
import { server } from '@/test/mocks/server';
import { http, HttpResponse } from 'msw';

describe('useAppDragDrop', () => {
  const mockInfo = vi.fn();
  const mockSuccess = vi.fn();

  beforeEach(() => {
    mockInfo.mockClear();
    mockSuccess.mockClear();
    vi.clearAllMocks();

    // Set up MSW handlers for drag-drop endpoints
    server.use(
      // Add to playlist
      http.post('/api/playlists/:id/tracks/add', () => {
        return HttpResponse.json({ success: true });
      }),
      // Reorder queue
      http.put('/api/player/queue/move', () => {
        return HttpResponse.json({ success: true });
      }),
      // Add to queue
      http.post('/api/player/queue/add-track', () => {
        return HttpResponse.json({ success: true });
      })
    );
  });

  /** Record every drag-drop request the hook sends (method, path, JSON body). */
  const recordRequests = () => {
    const requests: { method: string; path: string; body: unknown }[] = [];
    const record = async ({ request }: { request: Request }) => {
      requests.push({
        method: request.method,
        path: new URL(request.url).pathname,
        body: await request.json(),
      });
      return HttpResponse.json({ success: true });
    };
    server.use(
      http.post('/api/player/queue/add-track', record),
      http.put('/api/player/queue/move', record),
      http.post('/api/playlists/:id/tracks/add', record),
      http.put('/api/playlists/:id/tracks/reorder', record)
    );
    return requests;
  };

  const createDropResult = (
    source: { droppableId: string; index: number },
    destination: { droppableId: string; index: number } | null,
    draggableId: string = 'track-1'
  ): DropResult => ({
    source,
    destination,
    draggableId,
    type: 'TRACK',
    reason: 'DROP',
    combine: null,
    mode: 'FLUID',
  });

  describe('initialization', () => {
    it('initializes with handleDragEnd function', () => {
      const { result } = renderHook(() =>
        useAppDragDrop({ info: mockInfo, success: mockSuccess })
      );

      expect(result.current.handleDragEnd).toBeDefined();
      expect(typeof result.current.handleDragEnd).toBe('function');
    });
  });

  describe('dropped outside valid area', () => {
    it('ignores drop with no destination', async () => {
      const requests = recordRequests();
      const { result } = renderHook(() =>
        useAppDragDrop({ info: mockInfo, success: mockSuccess })
      );

      await act(async () => {
        await result.current.handleDragEnd(
          createDropResult({ droppableId: 'library', index: 0 }, null)
        );
      });

      expect(requests).toEqual([]);
      expect(mockInfo).not.toHaveBeenCalled();
      expect(mockSuccess).not.toHaveBeenCalled();
    });
  });

  describe('dropped in same position', () => {
    it('ignores drop in same position', async () => {
      const requests = recordRequests();
      const { result } = renderHook(() =>
        useAppDragDrop({ info: mockInfo, success: mockSuccess })
      );

      await act(async () => {
        await result.current.handleDragEnd(
          createDropResult(
            { droppableId: 'queue', index: 0 },
            { droppableId: 'queue', index: 0 }
          )
        );
      });

      expect(requests).toEqual([]);
      expect(mockInfo).not.toHaveBeenCalled();
      expect(mockSuccess).not.toHaveBeenCalled();
    });
  });

  describe('add to queue', () => {
    it('adds track to queue on drop', async () => {
      const requests = recordRequests();
      const { result } = renderHook(() =>
        useAppDragDrop({ info: mockInfo, success: mockSuccess })
      );

      await act(async () => {
        await result.current.handleDragEnd(
          createDropResult(
            { droppableId: 'library', index: 0 },
            { droppableId: 'queue', index: 2 },
            'track-123'
          )
        );
      });

      expect(requests).toEqual([
        { method: 'POST', path: '/api/player/queue/add-track', body: { track_id: 123, position: 2 } },
      ]);
      expect(mockSuccess).toHaveBeenCalledWith('Added track to queue at position 3');
    });

    it('handles queue add error', async () => {
      server.use(
        http.post('/api/player/queue/add-track', () =>
          HttpResponse.json({}, { status: 500 })
        )
      );
      const { result } = renderHook(() =>
        useAppDragDrop({ info: mockInfo, success: mockSuccess })
      );
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      await act(async () => {
        await result.current.handleDragEnd(
          createDropResult(
            { droppableId: 'library', index: 0 },
            { droppableId: 'queue', index: 0 }
          )
        );
      });

      // A body-less 500 shows the handler's own message, and no success toast
      expect(mockInfo).toHaveBeenCalledWith('Failed to add track to queue');
      expect(mockSuccess).not.toHaveBeenCalled();
      consoleErrorSpy.mockRestore();
    });
  });

  describe('add to playlist', () => {
    it('adds track to playlist on drop', async () => {
      const requests = recordRequests();
      const { result } = renderHook(() =>
        useAppDragDrop({ info: mockInfo, success: mockSuccess })
      );

      await act(async () => {
        await result.current.handleDragEnd(
          createDropResult(
            { droppableId: 'library', index: 0 },
            { droppableId: 'playlist-5', index: 1 },
            'track-42'
          )
        );
      });

      expect(requests).toEqual([
        { method: 'POST', path: '/api/playlists/5/tracks/add', body: { track_id: 42, position: 1 } },
      ]);
      expect(mockSuccess).toHaveBeenCalledWith('Added track to playlist');
    });

    it('handles playlist add error', async () => {
      server.use(
        http.post('/api/playlists/:id/tracks/add', () =>
          HttpResponse.json({}, { status: 500 })
        )
      );
      const { result } = renderHook(() =>
        useAppDragDrop({ info: mockInfo, success: mockSuccess })
      );
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      await act(async () => {
        await result.current.handleDragEnd(
          createDropResult(
            { droppableId: 'library', index: 0 },
            { droppableId: 'playlist-5', index: 0 }
          )
        );
      });

      expect(mockInfo).toHaveBeenCalledWith('Failed to add track to playlist');
      expect(mockSuccess).not.toHaveBeenCalled();
      consoleErrorSpy.mockRestore();
    });
  });

  describe('track ID extraction', () => {
    it('extracts track ID from draggable ID', async () => {
      const requests = recordRequests();
      const { result } = renderHook(() =>
        useAppDragDrop({ info: mockInfo, success: mockSuccess })
      );

      await act(async () => {
        await result.current.handleDragEnd(
          createDropResult(
            { droppableId: 'library', index: 0 },
            { droppableId: 'queue', index: 0 },
            'track-999'
          )
        );
      });

      expect(requests[0].body).toEqual({ track_id: 999, position: 0 });
    });
  });

  describe('error handling', () => {
    it('handles network errors gracefully', async () => {
      server.use(
        http.post('/api/player/queue/add-track', () => {
          return HttpResponse.json({ error: 'Network error' }, { status: 500 });
        })
      );
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      const { result } = renderHook(() =>
        useAppDragDrop({ info: mockInfo, success: mockSuccess })
      );

      await act(async () => {
        await result.current.handleDragEnd(
          createDropResult(
            { droppableId: 'library', index: 0 },
            { droppableId: 'queue', index: 0 }
          )
        );
      });

      // The error is turned into a toast rather than thrown at the caller
      expect(mockInfo).toHaveBeenCalledWith('Failed to add track to queue');
      consoleErrorSpy.mockRestore();
    });

    it('logs errors to console', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      // Set up MSW handler for error case
      server.use(
        http.post('/api/player/queue/add-track', () => {
          return HttpResponse.json({ error: 'Test error' }, { status: 500 });
        })
      );

      const { result } = renderHook(() =>
        useAppDragDrop({ info: mockInfo, success: mockSuccess })
      );

      const dropResult = createDropResult(
        { droppableId: 'library', index: 0 },
        { droppableId: 'queue', index: 0 }
      );

      await act(async () => {
        await result.current.handleDragEnd(dropResult);
      });

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'Drag and drop error:',
        expect.any(Error)
      );

      consoleErrorSpy.mockRestore();
    });
  });

  describe('hung backend (#4694)', () => {
    // These handlers used bare fetch() with no signal and no timeout, so a
    // backend that accepted the connection and never answered left the drop
    // pending forever. Drag-drop has no loading indicator either, so the user
    // saw nothing at all. They now go through apiRequest's 30s timeout (#4442).
    //
    // Only the two *reachable* handlers are covered here. handleReorderQueue
    // and handleReorderPlaylist are unreachable at HEAD — see the routing test
    // below and #5189 — so a timeout test for them would assert nothing.

    const HUNG = () => new Promise<never>(() => {});

    it.each([
      ['add to queue', '/api/player/queue/add-track',
       { droppableId: 'library', index: 0 }, { droppableId: 'queue', index: 0 }],
      ['add to playlist', '/api/playlists/:id/tracks/add',
       { droppableId: 'library', index: 0 }, { droppableId: 'playlist-1', index: 0 }],
    ])('%s surfaces a timeout instead of hanging', async (_label, path, source, destination) => {
      server.use(http.post(path, HUNG));

      const { result } = renderHook(() =>
        useAppDragDrop({ info: mockInfo, success: mockSuccess })
      );

      vi.useFakeTimers();
      try {
        let settled = false;
        const pending = result.current
          .handleDragEnd(createDropResult(source, destination))
          .then(() => { settled = true; });

        // Before the timeout fires the drop is genuinely still pending —
        // this is the state the user used to be stuck in permanently.
        await vi.advanceTimersByTimeAsync(29_000);
        expect(settled).toBe(false);
        expect(mockInfo).not.toHaveBeenCalled();

        await vi.advanceTimersByTimeAsync(2_000);
        await pending;
        expect(settled).toBe(true);
      } finally {
        vi.useRealTimers();
      }

      // handleDragEnd swallows the error into a toast, so the toast text is
      // where the timeout is observable.
      expect(mockInfo).toHaveBeenCalledWith(expect.stringContaining('timed out'));
      expect(mockSuccess).not.toHaveBeenCalled();
    });
  });

  describe('reorder routing (#5189)', () => {
    // A drag within one list moves the track; only a drag from another list adds it. The
    // drop-target branches used to run first, so queue -> queue called the ADD endpoint and
    // duplicated the track.

    const recordEndpoint = (hits: string[]) => {
      server.use(
        http.post('/api/player/queue/add-track', () => {
          hits.push('POST add-track');
          return HttpResponse.json({ success: true });
        }),
        http.put('/api/player/queue/move', () => {
          hits.push('PUT move');
          return HttpResponse.json({ success: true });
        }),
        http.post('/api/playlists/:id/tracks/add', () => {
          hits.push('POST playlist-add');
          return HttpResponse.json({ success: true });
        }),
        http.put('/api/playlists/:id/tracks/reorder', () => {
          hits.push('PUT playlist-reorder');
          return HttpResponse.json({ success: true });
        })
      );
    };

    it('a queue reorder calls move, not add-track', async () => {
      const hits: string[] = [];
      recordEndpoint(hits);

      const { result } = renderHook(() =>
        useAppDragDrop({ info: mockInfo, success: mockSuccess })
      );

      await act(async () => {
        await result.current.handleDragEnd(
          createDropResult({ droppableId: 'queue', index: 1 }, { droppableId: 'queue', index: 3 })
        );
      });

      expect(hits).toEqual(['PUT move']);
    });

    it('a playlist reorder calls tracks/reorder, not tracks/add', async () => {
      const hits: string[] = [];
      recordEndpoint(hits);

      const { result } = renderHook(() =>
        useAppDragDrop({ info: mockInfo, success: mockSuccess })
      );

      await act(async () => {
        await result.current.handleDragEnd(
          createDropResult(
            { droppableId: 'playlist-1', index: 0 },
            { droppableId: 'playlist-1', index: 2 }
          )
        );
      });

      expect(hits).toEqual(['PUT playlist-reorder']);
    });

    it('a drag from the library into the queue still adds', async () => {
      const hits: string[] = [];
      recordEndpoint(hits);
      const { result } = renderHook(() => useAppDragDrop({ info: mockInfo, success: mockSuccess }));

      await act(async () => {
        await result.current.handleDragEnd(
          createDropResult({ droppableId: 'library', index: 4 }, { droppableId: 'queue', index: 0 })
        );
      });

      expect(hits).toEqual(['POST add-track']);
    });

    it('a drag from one playlist into another still adds', async () => {
      const hits: string[] = [];
      recordEndpoint(hits);
      const { result } = renderHook(() => useAppDragDrop({ info: mockInfo, success: mockSuccess }));

      await act(async () => {
        await result.current.handleDragEnd(
          createDropResult({ droppableId: 'playlist-1', index: 0 }, { droppableId: 'playlist-2', index: 0 })
        );
      });

      expect(hits).toEqual(['POST playlist-add']);
    });

    it('a reorder inside a list that is neither queue nor playlist does nothing', async () => {
      const hits: string[] = [];
      recordEndpoint(hits);
      const { result } = renderHook(() => useAppDragDrop({ info: mockInfo, success: mockSuccess }));

      await act(async () => {
        await result.current.handleDragEnd(
          createDropResult({ droppableId: 'library', index: 1 }, { droppableId: 'library', index: 3 })
        );
      });

      expect(hits).toEqual([]);
    });
  });
});
