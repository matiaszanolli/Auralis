/**
 * ThemeContext Tests
 *
 * Tests the theme context provider, state management, and localStorage persistence.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, act } from '@/test/test-utils'
import { ReactNode } from 'react'
import { ThemeProvider, useTheme } from '../ThemeContext'
import { getSemanticTheme } from '@/theme/semanticTheme'

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
    // #4584: `colors` / `glassEffects` were retired from the context — they
    // were a second colour API competing with themeVars, and `colors` always
    // resolved against the dark palette regardless of the active mode.
    expect('colors' in result.current).toBe(false)
    expect('glassEffects' in result.current).toBe(false)
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
    const darkTheme = getSemanticTheme('dark')

    expect(root.dataset.theme).toBe('dark')
    expect(root.style.getPropertyValue('--app-canvas')).toBe(darkTheme.canvas)
    expect(root.style.getPropertyValue('--app-surface-raised')).toBe(darkTheme.surfaceRaised)
    expect(root.style.getPropertyValue('--app-text-primary')).toBe(darkTheme.textPrimary)
    expect(root.style.getPropertyValue('--app-on-accent')).toBe(darkTheme.onAccent)
    expect(root.style.getPropertyValue('--app-on-error')).toBe(darkTheme.onError)
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
    const lightTheme = getSemanticTheme('light')

    expect(root.dataset.theme).toBe('light')
    expect(root.style.getPropertyValue('--app-canvas')).toBe(lightTheme.canvas)
    expect(root.style.getPropertyValue('--app-surface-raised')).toBe(lightTheme.surfaceRaised)
    expect(root.style.getPropertyValue('--app-text-primary')).toBe(lightTheme.textPrimary)
    expect(root.style.getPropertyValue('--app-on-accent')).toBe(lightTheme.onAccent)
    expect(root.style.getPropertyValue('--app-on-error')).toBe(lightTheme.onError)
  })

  it('updates CSS custom properties when theme changes', () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <ThemeProvider>{children}</ThemeProvider>
    )

    const { result } = renderHook(() => useTheme(), { wrapper })

    const root = document.documentElement
    const darkTheme = getSemanticTheme('dark')
    const lightTheme = getSemanticTheme('light')

    // Dark mode
    expect(root.style.getPropertyValue('--app-canvas')).toBe(darkTheme.canvas)

    // Switch to light
    act(() => {
      result.current.toggleTheme()
    })

    expect(root.style.getPropertyValue('--app-canvas')).toBe(lightTheme.canvas)

    // Switch back to dark
    act(() => {
      result.current.toggleTheme()
    })

    expect(root.style.getPropertyValue('--app-canvas')).toBe(darkTheme.canvas)
  })

  // ============================================================================
  // Semantic Colour Contract Tests (#4584)
  // ============================================================================

  it('publishes dark semantic CSS variables in dark mode', () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <ThemeProvider>{children}</ThemeProvider>
    )

    renderHook(() => useTheme(), { wrapper })

    const root = document.documentElement
    expect(root.dataset.theme).toBe('dark')
    expect(root.style.getPropertyValue('--app-canvas')).toBe(getSemanticTheme('dark').canvas)
    expect(root.style.getPropertyValue('--app-text-primary')).toBe(
      getSemanticTheme('dark').textPrimary
    )
  })

  it('republishes semantic CSS variables when the theme changes', () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <ThemeProvider>{children}</ThemeProvider>
    )

    const { result } = renderHook(() => useTheme(), { wrapper })
    const root = document.documentElement

    act(() => {
      result.current.setTheme('light')
    })

    expect(root.dataset.theme).toBe('light')
    expect(root.style.getPropertyValue('--app-canvas')).toBe(getSemanticTheme('light').canvas)
    expect(root.style.getPropertyValue('--app-text-primary')).toBe(
      getSemanticTheme('light').textPrimary
    )
  })

  it('changes context value identity on toggle so consumers re-render', () => {
    // The memo dep array shrank when colors/glassEffects were removed (#4584);
    // `mode` must still drive a fresh object or consumers would freeze.
    const wrapper = ({ children }: { children: ReactNode }) => (
      <ThemeProvider>{children}</ThemeProvider>
    )

    const { result } = renderHook(() => useTheme(), { wrapper })
    const before = result.current

    act(() => {
      result.current.toggleTheme()
    })

    expect(result.current).not.toBe(before)
    expect(result.current.mode).not.toBe(before.mode)
  })

  it('drops the dead compatibility CSS aliases', () => {
    // The `--bg-*` / `--text-*` / `--glass-border` alias block had zero
    // consumers and was deleted with the rest of the second API (#4584).
    const wrapper = ({ children }: { children: ReactNode }) => (
      <ThemeProvider>{children}</ThemeProvider>
    )

    renderHook(() => useTheme(), { wrapper })

    const root = document.documentElement
    for (const dead of ['--bg-primary', '--bg-surface', '--text-primary', '--glass-border']) {
      expect(root.style.getPropertyValue(dead)).toBe('')
    }
  })
})
