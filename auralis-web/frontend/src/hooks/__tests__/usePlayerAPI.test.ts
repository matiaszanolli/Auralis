/**
 * Tests for usePlayerAPI hook
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { usePlayerAPI } from '../usePlayerAPI'
import { mockFetch, mockApiEndpoint, mockTrack, mockPlayerState, resetFetchMock } from '@/test/mocks/api'

describe('usePlayerAPI', () => {
  beforeEach(() => {
    mockFetch()
  })

  afterEach(() => {
    resetFetchMock()
  })

  it('initializes with default state', () => {
    mockApiEndpoint('/api/player/status', {})

    const { result } = renderHook(() => usePlayerAPI())

    expect(result.current.currentTrack).toBeNull()
    expect(result.current.isPlaying).toBe(false)
    expect(result.current.currentTime).toBe(0)
    expect(result.current.duration).toBe(0)
    expect(result.current.volume).toBe(80)
    expect(result.current.queue).toEqual([])
  })

  it('fetches player status on mount', async () => {
    mockApiEndpoint('/api/player/status', mockPlayerState)

    const { result } = renderHook(() => usePlayerAPI())

    await waitFor(() => {
      expect(result.current.currentTrack).toEqual(mockPlayerState.currentTrack)
      expect(result.current.isPlaying).toBe(mockPlayerState.isPlaying)
    })
  })

  it('plays a track', async () => {
    mockApiEndpoint('/api/player/status', mockPlayerState)
    mockApiEndpoint('/api/player/play', { success: true })

    const { result } = renderHook(() => usePlayerAPI())

    await waitFor(() => {
      expect(result.current.play).toBeDefined()
    })

    await result.current.play(mockTrack)

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/player/play'),
      expect.objectContaining({
        method: 'POST',
        body: expect.stringContaining(String(mockTrack.id)),
      })
    )
  })

  it('pauses playback', async () => {
    mockApiEndpoint('/api/player/status', { ...mockPlayerState, isPlaying: true })
    mockApiEndpoint('/api/player/pause', { success: true })

    const { result } = renderHook(() => usePlayerAPI())

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
    mockApiEndpoint('/api/player/resume', { success: true })

    const { result } = renderHook(() => usePlayerAPI())

    await waitFor(() => {
      expect(result.current.resume).toBeDefined()
    })

    await result.current.resume()

    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/api/player/resume'),
      expect.objectContaining({
        method: 'POST',
      })
    )
  })

  it('skips to next track', async () => {
    mockApiEndpoint('/api/player/status', mockPlayerState)
    mockApiEndpoint('/api/player/next', { success: true })

    const { result } = renderHook(() => usePlayerAPI())

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

    const { result } = renderHook(() => usePlayerAPI())

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

    const { result } = renderHook(() => usePlayerAPI())

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

    const { result } = renderHook(() => usePlayerAPI())

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
    mockApiEndpoint('/api/player/status', { error: 'Failed to fetch' }, { status: 500 })

    const { result } = renderHook(() => usePlayerAPI())

    await waitFor(() => {
      expect(result.current.error).toBeTruthy()
    })
  })

  it('sets loading state during API calls', async () => {
    mockApiEndpoint('/api/player/status', mockPlayerState, { delay: 100 })
    mockApiEndpoint('/api/player/play', { success: true }, { delay: 100 })

    const { result } = renderHook(() => usePlayerAPI())

    await waitFor(() => {
      expect(result.current.play).toBeDefined()
    })

    result.current.play(mockTrack)

    // Loading should be true immediately after calling play
    expect(result.current.loading).toBe(true)

    // Wait for API call to complete
    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })
  })
})
