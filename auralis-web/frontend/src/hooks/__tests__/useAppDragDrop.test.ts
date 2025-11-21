import { renderHook, act } from '@testing-library/react';
import { useAppDragDrop } from '../useAppDragDrop';
import { DropResult } from '@hello-pangea/dnd';

// Mock fetch
global.fetch = vi.fn();

describe('useAppDragDrop', () => {
  const mockInfo = vi.fn();
  const mockSuccess = vi.fn();

  beforeEach(() => {
    mockInfo.mockClear();
    mockSuccess.mockClear();
    (global.fetch as any).mockClear();
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

      expect(global.fetch).not.toHaveBeenCalled();
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

      expect(global.fetch).not.toHaveBeenCalled();
    });
  });

  describe('add to queue', () => {
    it('adds track to queue on drop', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

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

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/player/queue/add-track',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: expect.stringContaining('track_id'),
        })
      );

      expect(mockSuccess).toHaveBeenCalledWith(
        expect.stringContaining('Added track to queue')
      );
    });

    it('handles queue add error', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
      });

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
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

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

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/playlists/5/tracks/add'),
        expect.any(Object)
      );

      expect(mockSuccess).toHaveBeenCalledWith(
        expect.stringContaining('Added track to playlist')
      );
    });

    it('handles playlist add error', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
      });

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
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

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

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/player/queue/move',
        expect.objectContaining({
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: expect.stringContaining('from_index'),
        })
      );

      expect(mockInfo).toHaveBeenCalledWith('Queue reordered');
    });

    it('handles queue reorder error', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
      });

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
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

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

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/playlists/5/tracks/reorder'),
        expect.any(Object)
      );

      expect(mockInfo).toHaveBeenCalledWith('Playlist reordered');
    });

    it('handles playlist reorder error', async () => {
      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
      });

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
      (global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      });

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
        (global.fetch as any).mock.calls[0][1].body
      );
      expect(callBody.track_id).toBe(999);
    });
  });

  describe('error handling', () => {
    it('handles network errors gracefully', async () => {
      (global.fetch as any).mockRejectedValueOnce(
        new Error('Network error')
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
      (global.fetch as any).mockRejectedValueOnce(
        new Error('Test error')
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
