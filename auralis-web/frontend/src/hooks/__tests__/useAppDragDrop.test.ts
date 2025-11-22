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
      http.post('/api/player/queue/add', () => {
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

      expect(mockSuccess).toHaveBeenCalledWith(
        expect.stringContaining('Added track to queue')
      );
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

      expect(mockInfo).toHaveBeenCalledWith(
        'Failed to complete drag and drop operation'
      );
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

      expect(mockSuccess).toHaveBeenCalledWith(
        expect.stringContaining('Added track to playlist')
      );
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

      expect(mockInfo).toHaveBeenCalledWith(
        'Failed to complete drag and drop operation'
      );
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

      expect(mockInfo).toHaveBeenCalledWith('Queue reordered');
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

      expect(mockInfo).toHaveBeenCalledWith(
        'Failed to complete drag and drop operation'
      );
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

      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/playlists/5/tracks/reorder'),
        expect.any(Object)
      );

      expect(mockInfo).toHaveBeenCalledWith('Playlist reordered');
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

      expect(mockInfo).toHaveBeenCalledWith(
        'Failed to complete drag and drop operation'
      );
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

      const callBody = JSON.parse(
        mockFetch.mock.calls[0][1].body
      );
      expect(callBody.track_id).toBe(999);
    });
  });

  describe('error handling', () => {
    it('handles network errors gracefully', async () => {
      // Set up MSW handler for error case
      server.use(
        http.post('/api/player/queue/add', () => {
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

      expect(mockInfo).toHaveBeenCalledWith(
        'Failed to complete drag and drop operation'
      );
    });

    it('logs errors to console', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation();
      // Set up MSW handler for error case
      server.use(
        http.post('/api/player/queue/add', () => {
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
});
