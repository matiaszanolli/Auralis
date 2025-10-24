/**
 * Tests for usePlayerAPI hook
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { usePlayerAPI } from '../usePlayerAPI'
import { mockFetch, mockApiEndpoint, mockTrack, mockPlayerState, resetFetchMock } from '@/test/mocks/api'
import { TestProviders } from '@/test/utils/TestProviders'

describe('usePlayerAPI', () => {
  beforeEach(() => {
    mockFetch()
  })

  afterEach(() => {
    resetFetchMock()
  })

  it('initializes with default state', () => {
    mockApiEndpoint('/api/player/status', {})

    const { result } = renderHook(() => usePlayerAPI(), { wrapper: TestProviders })

    expect(result.current.currentTrack).toBeNull()
    expect(result.current.isPlaying).toBe(false)
    expect(result.current.currentTime).toBe(0)
    expect(result.current.duration).toBe(0)
    expect(result.current.volume).toBe(80)
    expect(result.current.queue).toEqual([])
  })

  it('fetches player status on mount', async () => {
    mockApiEndpoint('/api/player/status', mockPlayerState)

    const { result } = renderHook(() => usePlayerAPI(), { wrapper: TestProviders })

    await waitFor(() => {
      expect(result.current.currentTrack).toEqual(mockPlayerState.current_track)
      expect(result.current.isPlaying).toBe(mockPlayerState.is_playing)
    })
  })

  it('plays a track', async () => {
    mockApiEndpoint('/api/player/status', mockPlayerState)
    mockApiEndpoint('/api/player/queue', { success: true, queue: [mockTrack], queue_index: 0 })

    const { result } = renderHook(() => usePlayerAPI(), { wrapper: TestProviders })

    await waitFor(() => {
      expect(result.current.playTrack).toBeDefined()
    })

    await result.current.playTrack(mockTrack)

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/player/queue'),
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining(String(mockTrack.id)),
      })
    )
  })

  it('pauses playback', async () => {
    mockApiEndpoint('/api/player/status', { ...mockPlayerState, is_playing: true })
    mockApiEndpoint('/api/player/pause', { success: true })

    const { result } = renderHook(() => usePlayerAPI(), { wrapper: TestProviders })

    await waitFor(() => {
      expect(result.current.pause).toBeDefined()
    })

    await result.current.pause()

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/player/pause'),
      expect.objectContaining({
        method: 'POST',
      })
    )
  })

  it('resumes playback', async () => {
    mockApiEndpoint('/api/player/status', mockPlayerState)
    mockApiEndpoint('/api/player/play', { success: true })

    const { result } = renderHook(() => usePlayerAPI(), { wrapper: TestProviders })

    await waitFor(() => {
      expect(result.current.play).toBeDefined()
    })

    await result.current.play()

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/player/play'),
      expect.objectContaining({
        method: 'POST',
      })
    )
  })

  it('skips to next track', async () => {
    mockApiEndpoint('/api/player/status', mockPlayerState)
    mockApiEndpoint('/api/player/next', { success: true })

    const { result } = renderHook(() => usePlayerAPI(), { wrapper: TestProviders })

    await waitFor(() => {
      expect(result.current.next).toBeDefined()
    })

    await result.current.next()

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/player/next'),
      expect.objectContaining({
        method: 'POST',
      })
    )
  })

  it('goes to previous track', async () => {
    mockApiEndpoint('/api/player/status', mockPlayerState)
    mockApiEndpoint('/api/player/previous', { success: true })

    const { result } = renderHook(() => usePlayerAPI(), { wrapper: TestProviders })

    await waitFor(() => {
      expect(result.current.previous).toBeDefined()
    })

    await result.current.previous()

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/player/previous'),
      expect.objectContaining({
        method: 'POST',
      })
    )
  })

  it('seeks to position', async () => {
    mockApiEndpoint('/api/player/status', mockPlayerState)
    mockApiEndpoint('/api/player/seek', { success: true })

    const { result } = renderHook(() => usePlayerAPI(), { wrapper: TestProviders })

    await waitFor(() => {
      expect(result.current.seek).toBeDefined()
    })

    const seekPosition = 60
    await result.current.seek(seekPosition)

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/player/seek'),
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining(String(seekPosition)),
      })
    )
  })

  it('sets volume', async () => {
    mockApiEndpoint('/api/player/status', mockPlayerState)
    mockApiEndpoint('/api/player/volume', { success: true })

    const { result } = renderHook(() => usePlayerAPI(), { wrapper: TestProviders })

    await waitFor(() => {
      expect(result.current.setVolume).toBeDefined()
    })

    const newVolume = 50
    await result.current.setVolume(newVolume)

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/player/volume'),
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining(String(newVolume)),
      })
    )
  })

  it('handles API errors gracefully', async () => {
    // Mock a successful status call first, then an error on play
    mockApiEndpoint('/api/player/status', mockPlayerState)
    mockApiEndpoint('/api/player/play', { detail: 'Playback failed' }, { status: 500 })

    const { result } = renderHook(() => usePlayerAPI(), { wrapper: TestProviders })

    await waitFor(() => {
      expect(result.current.play).toBeDefined()
    })

    // Call play which should fail and set error state
    await result.current.play()

    await waitFor(() => {
      expect(result.current.error).toBeTruthy()
      expect(result.current.error).toContain('Playback failed')
    })
  })

  it('sets loading state during API calls', async () => {
    mockApiEndpoint('/api/player/status', mockPlayerState, { delay: 100 })
    mockApiEndpoint('/api/player/queue', { success: true, queue: [mockTrack], queue_index: 0 }, { delay: 100 })

    const { result } = renderHook(() => usePlayerAPI(), { wrapper: TestProviders })

    await waitFor(() => {
      expect(result.current.playTrack).toBeDefined()
    })

    // Call playTrack without awaiting to check loading state
    const playPromise = result.current.playTrack(mockTrack)

    // Loading should be true immediately after calling playTrack
    await waitFor(() => {
      expect(result.current.loading).toBe(true)
    })

    // Wait for API call to complete
    await playPromise
    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })
  })
})
