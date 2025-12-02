/**
 * Keyboard Navigation Utilities
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Hooks and utilities for implementing comprehensive keyboard navigation.
 * Provides focus management, arrow key navigation, and keyboard shortcuts.
 *
 * Features:
 * - Focus trap implementation
 * - Arrow key navigation (lists, grids, menus)
 * - Keyboard shortcut handling
 * - Focus restoration
 * - Escape key handling
 * - Tab key management
 *
 * Phase C.4c: Accessibility & A11y
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { useEffect, useRef, useCallback } from 'react';

// ============================================================================
// Types
// ============================================================================

type KeyModifier = 'ctrl' | 'shift' | 'alt' | 'meta';
type ArrowDirection = 'up' | 'down' | 'left' | 'right';

interface KeyboardShortcut {
  key: string;
  modifiers?: KeyModifier[];
  handler: (event: KeyboardEvent) => void;
  description?: string;
}

interface FocusTrapOptions {
  initialFocus?: HTMLElement;
  restoreFocus?: boolean;
  clickOutsideDeactivates?: boolean;
}

interface ArrowNavigationOptions {
  direction?: 'vertical' | 'horizontal' | 'grid';
  wrap?: boolean;
  onNavigate?: (element: HTMLElement, direction: ArrowDirection) => void;
}

// ============================================================================
// Keyboard Event Utilities
// ============================================================================

/**
 * Check if a keyboard event matches a shortcut
 */
export function matchesShortcut(
  event: KeyboardEvent,
  shortcut: KeyboardShortcut
): boolean {
  if (event.key.toLowerCase() !== shortcut.key.toLowerCase()) {
    return false;
  }

  const modifiers = shortcut.modifiers || [];

  // Check ctrl/cmd
  const hasCtrl = event.ctrlKey || event.metaKey;
  const expectCtrl = modifiers.includes('ctrl') || modifiers.includes('meta');

  if (hasCtrl !== expectCtrl) {
    return false;
  }

  // Check shift
  if (event.shiftKey !== modifiers.includes('shift')) {
    return false;
  }

  // Check alt
  if (event.altKey !== modifiers.includes('alt')) {
    return false;
  }

  return true;
}

/**
 * Check if key is an arrow key
 */
export function isArrowKey(key: string): key is ArrowDirection {
  return ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(key);
}

/**
 * Get arrow direction from key
 */
export function getArrowDirection(key: string): ArrowDirection | null {
  const directions: Record<string, ArrowDirection> = {
    ArrowUp: 'up',
    ArrowDown: 'down',
    ArrowLeft: 'left',
    ArrowRight: 'right',
  };
  return directions[key] || null;
}

/**
 * Check if element can receive keyboard focus
 */
export function canFocus(element: HTMLElement): boolean {
  // Naturally focusable elements
  if (
    ['BUTTON', 'INPUT', 'SELECT', 'TEXTAREA', 'A'].includes(element.tagName)
  ) {
    return !(element as HTMLElement).hasAttribute('disabled');
  }

  // Elements with tabindex
  const tabIndex = element.getAttribute('tabindex');
  if (tabIndex !== null) {
    const index = parseInt(tabIndex);
    return index >= 0;
  }

  // Elements with click handlers
  if (element.hasAttribute('onclick')) {
    return true;
  }

  // Elements with specific roles
  const role = element.getAttribute('role');
  if (['button', 'link', 'menuitem', 'tab'].includes(role)) {
    return true;
  }

  return false;
}

// ============================================================================
// Focus Management
// ============================================================================

/**
 * Get all focusable elements within a container
 */
export function getFocusableElements(
  container: HTMLElement
): HTMLElement[] {
  const focusableSelectors = [
    'button:not([disabled])',
    '[href]',
    'input:not([disabled])',
    'select:not([disabled])',
    'textarea:not([disabled])',
    '[tabindex]:not([tabindex="-1"])',
    '[role="button"]',
    '[role="link"]',
    '[role="menuitem"]',
    '[role="tab"]',
  ];

  const elements: HTMLElement[] = [];
  const selector = focusableSelectors.join(', ');

  container.querySelectorAll(selector).forEach((el) => {
    if (canFocus(el as HTMLElement)) {
      elements.push(el as HTMLElement);
    }
  });

  return elements;
}

/**
 * Move focus to next focusable element
 */
export function focusNext(
  container: HTMLElement,
  wrap: boolean = true
): boolean {
  const current = document.activeElement as HTMLElement;
  const focusable = getFocusableElements(container);

  if (focusable.length === 0) return false;

  const currentIndex = focusable.indexOf(current);
  const nextIndex = wrap
    ? (currentIndex + 1) % focusable.length
    : Math.min(currentIndex + 1, focusable.length - 1);

  focusable[nextIndex].focus();
  return true;
}

/**
 * Move focus to previous focusable element
 */
export function focusPrevious(
  container: HTMLElement,
  wrap: boolean = true
): boolean {
  const current = document.activeElement as HTMLElement;
  const focusable = getFocusableElements(container);

  if (focusable.length === 0) return false;

  const currentIndex = focusable.indexOf(current);
  const prevIndex = wrap
    ? (currentIndex - 1 + focusable.length) % focusable.length
    : Math.max(currentIndex - 1, 0);

  focusable[prevIndex].focus();
  return true;
}

/**
 * Set focus to first focusable element
 */
export function focusFirst(container: HTMLElement): boolean {
  const focusable = getFocusableElements(container);
  if (focusable.length === 0) return false;

  focusable[0].focus();
  return true;
}

/**
 * Set focus to last focusable element
 */
export function focusLast(container: HTMLElement): boolean {
  const focusable = getFocusableElements(container);
  if (focusable.length === 0) return false;

  focusable[focusable.length - 1].focus();
  return true;
}

// ============================================================================
// Hooks
// ============================================================================

/**
 * Hook for keyboard shortcut handling
 */
export function useKeyboardShortcuts(shortcuts: KeyboardShortcut[]) {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      for (const shortcut of shortcuts) {
        if (matchesShortcut(event, shortcut)) {
          event.preventDefault();
          shortcut.handler(event);
          break;
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [shortcuts]);
}

/**
 * Hook for focus trap (modal behavior)
 */
export function useFocusTrap(
  containerRef: React.RefObject<HTMLElement>,
  options: FocusTrapOptions = {}
) {
  const previousActiveRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // Store previous focus
    previousActiveRef.current = document.activeElement as HTMLElement;

    // Set initial focus
    if (options.initialFocus) {
      options.initialFocus.focus();
    } else {
      const firstFocusable = getFocusableElements(container)[0];
      if (firstFocusable) {
        firstFocusable.focus();
      }
    }

    // Handle Tab key within trap
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Tab') return;

      const focusable = getFocusableElements(container);
      if (focusable.length === 0) return;

      const current = document.activeElement;
      const currentIndex = focusable.indexOf(current as HTMLElement);

      if (event.shiftKey) {
        // Shift+Tab
        if (currentIndex === 0) {
          event.preventDefault();
          focusable[focusable.length - 1].focus();
        }
      } else {
        // Tab
        if (currentIndex === focusable.length - 1) {
          event.preventDefault();
          focusable[0].focus();
        }
      }
    };

    // Handle click outside (deactivate trap)
    const handleClickOutside = (event: MouseEvent) => {
      if (options.clickOutsideDeactivates) {
        if (!container.contains(event.target as Node)) {
          // Deactivate trap
        }
      }
    };

    container.addEventListener('keydown', handleKeyDown);
    if (options.clickOutsideDeactivates) {
      document.addEventListener('click', handleClickOutside);
    }

    return () => {
      container.removeEventListener('keydown', handleKeyDown);
      if (options.clickOutsideDeactivates) {
        document.removeEventListener('click', handleClickOutside);
      }

      // Restore focus if enabled
      if (options.restoreFocus && previousActiveRef.current) {
        previousActiveRef.current.focus();
      }
    };
  }, [containerRef, options]);
}

/**
 * Hook for arrow key navigation
 */
export function useArrowKeyNavigation(
  containerRef: React.RefObject<HTMLElement>,
  options: ArrowNavigationOptions = {}
) {
  const handleArrowKey = useCallback(
    (event: KeyboardEvent) => {
      const container = containerRef.current;
      if (!container) return;

      const direction = getArrowDirection(event.key);
      if (!direction) return;

      event.preventDefault();

      const focusable = getFocusableElements(container);
      if (focusable.length === 0) return;

      const current = document.activeElement as HTMLElement;
      const currentIndex = focusable.indexOf(current);

      let nextIndex = currentIndex;

      if (options.direction === 'vertical') {
        if (direction === 'down') {
          nextIndex = options.wrap
            ? (currentIndex + 1) % focusable.length
            : Math.min(currentIndex + 1, focusable.length - 1);
        } else if (direction === 'up') {
          nextIndex = options.wrap
            ? (currentIndex - 1 + focusable.length) % focusable.length
            : Math.max(currentIndex - 1, 0);
        }
      } else if (options.direction === 'horizontal') {
        if (direction === 'right') {
          nextIndex = options.wrap
            ? (currentIndex + 1) % focusable.length
            : Math.min(currentIndex + 1, focusable.length - 1);
        } else if (direction === 'left') {
          nextIndex = options.wrap
            ? (currentIndex - 1 + focusable.length) % focusable.length
            : Math.max(currentIndex - 1, 0);
        }
      }

      const nextElement = focusable[nextIndex];
      nextElement.focus();

      options.onNavigate?.(nextElement, direction);
    },
    [containerRef, options]
  );

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    container.addEventListener('keydown', handleArrowKey);
    return () => container.removeEventListener('keydown', handleArrowKey);
  }, [handleArrowKey, containerRef]);
}

/**
 * Hook for Escape key handling
 */
export function useEscapeKey(
  onEscape: () => void,
  enabled: boolean = true
) {
  useEffect(() => {
    if (!enabled) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onEscape();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onEscape, enabled]);
}

export type {
  KeyboardShortcut,
  FocusTrapOptions,
  ArrowNavigationOptions,
  KeyModifier,
  ArrowDirection,
};
