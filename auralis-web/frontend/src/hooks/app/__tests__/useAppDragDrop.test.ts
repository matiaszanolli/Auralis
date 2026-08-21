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
      const { result } = renderHook(() =>
        useAppDragDrop({ info: mockInfo, success: mockSuccess })
      );

      const dropResult = createDropResult(
        { droppableId: 'library', index: 0 },
        null // No destination
      );

      await act(async () => {
        await result.current.handleDragEnd(dropResult);
      });

      // MSW will not handle the request, but that's OK - the hook should still work
    });
  });

  describe('dropped in same position', () => {
    it('ignores drop in same position', async () => {
      const { result } = renderHook(() =>
        useAppDragDrop({ info: mockInfo, success: mockSuccess })
      );

      const dropResult = createDropResult(
        { droppableId: 'queue', index: 0 },
        { droppableId: 'queue', index: 0 } // Same position
      );

      await act(async () => {
        await result.current.handleDragEnd(dropResult);
      });

      // MSW will not handle the request, but that's OK - the hook should still work
    });
  });

  describe('add to queue', () => {
    it('adds track to queue on drop', async () => {
      // MSW handlers are set up in beforeEach

      const { result } = renderHook(() =>
        useAppDragDrop({ info: mockInfo, success: mockSuccess })
      );

      const dropResult = createDropResult(
        { droppableId: 'library', index: 0 },
        { droppableId: 'queue', index: 2 },
        'track-123'
      );

      await act(async () => {
        await result.current.handleDragEnd(dropResult);
      });

      // MSW intercepts the fetch, so we just verify the success callback was called

      // Hook executes drag end without crashing
      expect(result.current.handleDragEnd).toBeDefined();
    });

    it('handles queue add error', async () => {
      // MSW handler will return error when configured for error case

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

      // Hook handles error gracefully without throwing
      expect(result.current).toBeDefined();
    });
  });

  describe('add to playlist', () => {
    it('adds track to playlist on drop', async () => {
      // MSW handlers are set up in beforeEach

      const { result } = renderHook(() =>
        useAppDragDrop({ info: mockInfo, success: mockSuccess })
      );

      const dropResult = createDropResult(
        { droppableId: 'library', index: 0 },
        { droppableId: 'playlist-5', index: 1 },
        'track-42'
      );

      await act(async () => {
        await result.current.handleDragEnd(dropResult);
      });

      // MSW intercepts the fetch, so we just verify the success callback was called

      // Hook executes without crashing
      expect(result.current).toBeDefined();
    });

    it('handles playlist add error', async () => {
      // MSW handler will return error when configured for error case

      const { result } = renderHook(() =>
        useAppDragDrop({ info: mockInfo, success: mockSuccess })
      );

      const dropResult = createDropResult(
        { droppableId: 'library', index: 0 },
        { droppableId: 'playlist-5', index: 0 }
      );

      await act(async () => {
        await result.current.handleDragEnd(dropResult);
      });

      // Hook handles error gracefully without throwing
      expect(result.current).toBeDefined();
    });
  });

  describe('reorder queue', () => {
    it('reorders tracks in queue', async () => {
      // MSW handlers are set up in beforeEach

      const { result } = renderHook(() =>
        useAppDragDrop({ info: mockInfo, success: mockSuccess })
      );

      const dropResult = createDropResult(
        { droppableId: 'queue', index: 1 },
        { droppableId: 'queue', index: 3 }
      );

      await act(async () => {
        await result.current.handleDragEnd(dropResult);
      });

      // MSW intercepts the fetch, so we just verify the info callback was called

      // Hook executes queue reorder without throwing
      expect(result.current).toBeDefined();
    });

    it('handles queue reorder error', async () => {
      // MSW handler will return error when configured for error case

      const { result } = renderHook(() =>
        useAppDragDrop({ info: mockInfo, success: mockSuccess })
      );

      const dropResult = createDropResult(
        { droppableId: 'queue', index: 0 },
        { droppableId: 'queue', index: 1 }
      );

      await act(async () => {
        await result.current.handleDragEnd(dropResult);
      });

      // Hook handles error gracefully without throwing
      expect(result.current).toBeDefined();
    });
  });

  describe('reorder playlist', () => {
    it('reorders tracks in playlist', async () => {
      // MSW handlers are set up in beforeEach

      const { result } = renderHook(() =>
        useAppDragDrop({ info: mockInfo, success: mockSuccess })
      );

      const dropResult = createDropResult(
        { droppableId: 'playlist-5', index: 0 },
        { droppableId: 'playlist-5', index: 2 }
      );

      await act(async () => {
        await result.current.handleDragEnd(dropResult);
      });

      // MSW handles the API call, just verify the UI callback was called
      // Hook executes playlist reorder without throwing
      expect(result.current).toBeDefined();
    });

    it('handles playlist reorder error', async () => {
      // MSW handler will return error when configured for error case

      const { result } = renderHook(() =>
        useAppDragDrop({ info: mockInfo, success: mockSuccess })
      );

      const dropResult = createDropResult(
        { droppableId: 'playlist-5', index: 0 },
        { droppableId: 'playlist-5', index: 1 }
      );

      await act(async () => {
        await result.current.handleDragEnd(dropResult);
      });

      // Hook handles error gracefully without throwing
      expect(result.current).toBeDefined();
    });
  });

  describe('track ID extraction', () => {
    it('extracts track ID from draggable ID', async () => {
      // MSW handlers are set up in beforeEach

      const { result } = renderHook(() =>
        useAppDragDrop({ info: mockInfo, success: mockSuccess })
      );

      const dropResult = createDropResult(
        { droppableId: 'library', index: 0 },
        { droppableId: 'queue', index: 0 },
        'track-999'
      );

      await act(async () => {
        await result.current.handleDragEnd(dropResult);
      });

      // Verify the API call was made successfully (MSW handles it)
      // Adding to queue calls success callback, not info
      expect(mockSuccess).toHaveBeenCalled();
    });
  });

  describe('error handling', () => {
    it('handles network errors gracefully', async () => {
      // Set up MSW handler for error case
      server.use(
        http.post('/api/player/queue/add-track', () => {
          return HttpResponse.json({ error: 'Network error' }, { status: 500 });
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

      // Hook handles error gracefully without throwing
      expect(result.current).toBeDefined();
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

  describe('reorder routing is broken (#5189)', () => {
    // Characterization, not desired behaviour. handleDragEnd tests
    // `destination.droppableId === 'queue'` before it tests
    // `destination.droppableId === source.droppableId`, so a within-list drag
    // never reaches handleReorderQueue / handleReorderPlaylist — it calls the
    // ADD endpoint instead, duplicating the track rather than moving it.
    //
    // The pre-existing 'reorders tracks in queue' / 'reorders tracks in
    // playlist' tests above assert only `expect(result.current).toBeDefined()`,
    // which is why this went unnoticed. Pinned here so the gap is visible;
    // when #5189 fixes the routing these expectations flip to the move/reorder
    // endpoints.

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

    it('a queue reorder calls add-track, not move', async () => {
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

      expect(hits).toEqual(['POST add-track']);   // should be ['PUT move']
    });

    it('a playlist reorder calls tracks/add, not tracks/reorder', async () => {
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

      expect(hits).toEqual(['POST playlist-add']); // should be ['PUT playlist-reorder']
    });
  });
});
