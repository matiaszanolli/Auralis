/**
 * ThemeContext Tests
 *
 * Tests the theme context provider, state management, and localStorage persistence.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, act, waitFor } from '@/test/test-utils'
import { ReactNode } from 'react'
import { ThemeProvider, useTheme } from '../ThemeContext'

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}

  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value
    },
    removeItem: (key: string) => {
      delete store[key]
    },
    clear: () => {
      store = {}
    },
  }
})()

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
})

describe('ThemeContext', () => {
  beforeEach(() => {
    localStorageMock.clear()
    // Clear CSS custom properties
    document.documentElement.style.cssText = ''
  })

  afterEach(() => {
    localStorageMock.clear()
  })

  // ============================================================================
  // Basic Functionality Tests
  // ============================================================================

  it('provides theme context', () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <ThemeProvider>{children}</ThemeProvider>
    )

    const { result } = renderHook(() => useTheme(), { wrapper })

    expect(result.current).toBeDefined()
    expect(result.current.mode).toBeDefined()
    expect(result.current.toggleTheme).toBeDefined()
    expect(result.current.setTheme).toBeDefined()
    expect(result.current.colors).toBeDefined()
    expect(result.current.glassEffects).toBeDefined()
  })

  it('throws error when used outside ThemeProvider', () => {
    // Suppress console.error for this test
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    expect(() => {
      renderHook(() => useTheme())
    }).toThrow('useTheme must be used within a ThemeProvider')

    consoleSpy.mockRestore()
  })

  // ============================================================================
  // Default State Tests
  // ============================================================================

  it('defaults to dark mode when no localStorage value', () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <ThemeProvider>{children}</ThemeProvider>
    )

    const { result } = renderHook(() => useTheme(), { wrapper })

    expect(result.current.mode).toBe('dark')
  })

  it('uses localStorage value if available', () => {
    localStorageMock.setItem('auralis-theme', 'light')

    const wrapper = ({ children }: { children: ReactNode }) => (
      <ThemeProvider>{children}</ThemeProvider>
    )

    const { result } = renderHook(() => useTheme(), { wrapper })

    expect(result.current.mode).toBe('light')
  })

  // ============================================================================
  // Theme Toggle Tests
  // ============================================================================

  it('toggles from dark to light mode', () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <ThemeProvider>{children}</ThemeProvider>
    )

    const { result } = renderHook(() => useTheme(), { wrapper })

    expect(result.current.mode).toBe('dark')

    act(() => {
      result.current.toggleTheme()
    })

    expect(result.current.mode).toBe('light')
  })

  it('toggles from light to dark mode', () => {
    localStorageMock.setItem('auralis-theme', 'light')

    const wrapper = ({ children }: { children: ReactNode }) => (
      <ThemeProvider>{children}</ThemeProvider>
    )

    const { result } = renderHook(() => useTheme(), { wrapper })

    expect(result.current.mode).toBe('light')

    act(() => {
      result.current.toggleTheme()
    })

    expect(result.current.mode).toBe('dark')
  })

  it('can toggle multiple times', () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <ThemeProvider>{children}</ThemeProvider>
    )

    const { result } = renderHook(() => useTheme(), { wrapper })

    expect(result.current.mode).toBe('dark')

    act(() => {
      result.current.toggleTheme() // -> light
    })
    expect(result.current.mode).toBe('light')

    act(() => {
      result.current.toggleTheme() // -> dark
    })
    expect(result.current.mode).toBe('dark')

    act(() => {
      result.current.toggleTheme() // -> light
    })
    expect(result.current.mode).toBe('light')
  })

  // ============================================================================
  // SetTheme Tests
  // ============================================================================

  it('sets theme to dark mode explicitly', () => {
    localStorageMock.setItem('auralis-theme', 'light')

    const wrapper = ({ children }: { children: ReactNode }) => (
      <ThemeProvider>{children}</ThemeProvider>
    )

    const { result } = renderHook(() => useTheme(), { wrapper })

    expect(result.current.mode).toBe('light')

    act(() => {
      result.current.setTheme('dark')
    })

    expect(result.current.mode).toBe('dark')
  })

  it('sets theme to light mode explicitly', () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <ThemeProvider>{children}</ThemeProvider>
    )

    const { result } = renderHook(() => useTheme(), { wrapper })

    expect(result.current.mode).toBe('dark')

    act(() => {
      result.current.setTheme('light')
    })

    expect(result.current.mode).toBe('light')
  })

  // ============================================================================
  // LocalStorage Persistence Tests
  // ============================================================================

  it('saves theme preference to localStorage on toggle', () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <ThemeProvider>{children}</ThemeProvider>
    )

    const { result } = renderHook(() => useTheme(), { wrapper })

    act(() => {
      result.current.toggleTheme()
    })

    expect(localStorageMock.getItem('auralis-theme')).toBe('light')
  })

  it('saves theme preference to localStorage on setTheme', () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <ThemeProvider>{children}</ThemeProvider>
    )

    const { result } = renderHook(() => useTheme(), { wrapper })

    act(() => {
      result.current.setTheme('light')
    })

    expect(localStorageMock.getItem('auralis-theme')).toBe('light')
  })

  it('persists theme across re-initialization', () => {
    // First render
    const wrapper1 = ({ children }: { children: ReactNode }) => (
      <ThemeProvider>{children}</ThemeProvider>
    )
    const { result: result1 } = renderHook(() => useTheme(), { wrapper: wrapper1 })

    act(() => {
      result1.current.setTheme('light')
    })

    // Second render (simulating page refresh)
    const wrapper2 = ({ children }: { children: ReactNode }) => (
      <ThemeProvider>{children}</ThemeProvider>
    )
    const { result: result2 } = renderHook(() => useTheme(), { wrapper: wrapper2 })

    expect(result2.current.mode).toBe('light')
  })

  // ============================================================================
  // CSS Custom Properties Tests
  // ============================================================================

  it('sets CSS custom properties for dark mode', () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <ThemeProvider>{children}</ThemeProvider>
    )

    renderHook(() => useTheme(), { wrapper })

    const root = document.documentElement

    expect(root.style.getPropertyValue('--bg-primary')).toBe('#0A0E27')
    expect(root.style.getPropertyValue('--text-primary')).toBe('#ffffff')
  })

  it('sets CSS custom properties for light mode', () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <ThemeProvider>{children}</ThemeProvider>
    )

    const { result } = renderHook(() => useTheme(), { wrapper })

    act(() => {
      result.current.setTheme('light')
    })

    const root = document.documentElement

    expect(root.style.getPropertyValue('--bg-primary')).toBe('#f8f9fd')
    expect(root.style.getPropertyValue('--text-primary')).toBe('#1a1f3a')
  })

  it('updates CSS custom properties when theme changes', () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <ThemeProvider>{children}</ThemeProvider>
    )

    const { result } = renderHook(() => useTheme(), { wrapper })

    const root = document.documentElement

    // Dark mode
    expect(root.style.getPropertyValue('--bg-primary')).toBe('#0A0E27')

    // Switch to light
    act(() => {
      result.current.toggleTheme()
    })

    expect(root.style.getPropertyValue('--bg-primary')).toBe('#f8f9fd')

    // Switch back to dark
    act(() => {
      result.current.toggleTheme()
    })

    expect(root.style.getPropertyValue('--bg-primary')).toBe('#0A0E27')
  })

  // ============================================================================
  // Colors Object Tests
  // ============================================================================

  it('provides dark colors in dark mode', () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <ThemeProvider>{children}</ThemeProvider>
    )

    const { result } = renderHook(() => useTheme(), { wrapper })

    expect(result.current.colors.background.primary).toBe('#0A0E27')
    expect(result.current.colors.text.primary).toBe('#ffffff')
  })

  it('provides light colors in light mode', () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <ThemeProvider>{children}</ThemeProvider>
    )

    const { result } = renderHook(() => useTheme(), { wrapper })

    act(() => {
      result.current.setTheme('light')
    })

    expect(result.current.colors.background.primary).toBe('#f8f9fd')
    expect(result.current.colors.text.primary).toBe('#1a1f3a')
  })

  it('updates colors object when theme changes', () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <ThemeProvider>{children}</ThemeProvider>
    )

    const { result } = renderHook(() => useTheme(), { wrapper })

    const darkColors = result.current.colors

    act(() => {
      result.current.toggleTheme()
    })

    const lightColors = result.current.colors

    expect(darkColors).not.toEqual(lightColors)
    expect(lightColors.background.primary).toBe('#f8f9fd')
  })

  // ============================================================================
  // Glass Effects Tests
  // ============================================================================

  it('provides glassEffects utilities', () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <ThemeProvider>{children}</ThemeProvider>
    )

    const { result } = renderHook(() => useTheme(), { wrapper })

    expect(result.current.glassEffects).toBeDefined()
    expect(typeof result.current.glassEffects).toBe('object')
  })
})
