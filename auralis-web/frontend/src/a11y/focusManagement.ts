/**
 * Focus Management Utilities
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tools for managing keyboard focus in accessible applications.
 * Provides utilities for focus restoration, focus indication, and focus management.
 *
 * Features:
 * - Focus restoration (save and restore focus state)
 * - Focus indication (visible focus styles)
 * - Focus visibility monitoring
 * - Focus lock for modals
 * - Focus notification to screen readers
 *
 * Phase C.4c: Accessibility & A11y
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

// ============================================================================
// Focus History Management
// ============================================================================

class FocusManager {
  private focusHistory: HTMLElement[] = [];
  private maxHistory: number = 50;

  /**
   * Save current focus
   */
  saveFocus(): HTMLElement | null {
    const focused = document.activeElement as HTMLElement;
    if (focused && focused !== document.body) {
      this.focusHistory.push(focused);

      if (this.focusHistory.length > this.maxHistory) {
        this.focusHistory.shift();
      }

      return focused;
    }
    return null;
  }

  /**
   * Restore previous focus
   */
  restoreFocus(): boolean {
    const previous = this.focusHistory.pop();
    if (previous && document.body.contains(previous)) {
      previous.focus();
      return true;
    }
    return false;
  }

  /**
   * Get focus history
   */
  getFocusHistory(): HTMLElement[] {
    return [...this.focusHistory];
  }

  /**
   * Clear focus history
   */
  clearHistory(): void {
    this.focusHistory = [];
  }

  /**
   * Get current focused element
   */
  getCurrentFocus(): HTMLElement | null {
    const element = document.activeElement;
    return element && element !== document.body ? (element as HTMLElement) : null;
  }

  /**
   * Check if element is focused
   */
  isFocused(element: HTMLElement): boolean {
    return document.activeElement === element;
  }

  /**
   * Focus element with optional scrolling
   */
  setFocus(element: HTMLElement, options: { scrollIntoView?: boolean } = {}): boolean {
    try {
      if (!element) return false;

      element.focus();

      if (options.scrollIntoView !== false) {
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }

      return true;
    } catch (error) {
      console.error('Error setting focus:', error);
      return false;
    }
  }

  /**
   * Focus trap for modal dialogs
   */
  createFocusTrap(
    container: HTMLElement,
    onEscape?: () => void
  ): () => void {
    const focusableElements = this.getFocusableElements(container);
    if (focusableElements.length === 0) {
      return () => {};
    }

    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && onEscape) {
        event.preventDefault();
        onEscape();
        return;
      }

      if (event.key !== 'Tab') return;

      if (event.shiftKey) {
        // Shift+Tab
        if (document.activeElement === firstElement) {
          event.preventDefault();
          lastElement.focus();
        }
      } else {
        // Tab
        if (document.activeElement === lastElement) {
          event.preventDefault();
          firstElement.focus();
        }
      }
    };

    container.addEventListener('keydown', handleKeyDown);

    // Focus first element
    firstElement.focus();

    // Return cleanup function
    return () => {
      container.removeEventListener('keydown', handleKeyDown);
    };
  }

  /**
   * Get all focusable elements in container
   */
  getFocusableElements(container: HTMLElement): HTMLElement[] {
    const focusableSelectors = [
      'button:not([disabled])',
      '[href]',
      'input:not([disabled])',
      'select:not([disabled])',
      'textarea:not([disabled])',
      '[tabindex]:not([tabindex="-1"])',
    ];

    const elements: HTMLElement[] = [];
    const selector = focusableSelectors.join(', ');

    container.querySelectorAll(selector).forEach((el) => {
      elements.push(el as HTMLElement);
    });

    return elements;
  }

  /**
   * Check if element can be focused
   */
  canBeFocused(element: HTMLElement): boolean {
    if (!element || !document.body.contains(element)) {
      return false;
    }

    const style = window.getComputedStyle(element);
    if (style.display === 'none' || style.visibility === 'hidden') {
      return false;
    }

    return true;
  }
}

export const focusManager = new FocusManager();

// ============================================================================
// Focus Indicator Management
// ============================================================================

/**
 * Inject focus indicator styles
 */
export function injectFocusStyles(): HTMLStyleElement {
  const existing = document.getElementById('focus-styles');
  if (existing) return existing as HTMLStyleElement;

  const style = document.createElement('style');
  style.id = 'focus-styles';
  style.textContent = `
    /* Visible focus indicator for keyboard users */
    *:focus-visible {
      outline: 3px solid #4A90E2;
      outline-offset: 2px;
    }

    /* Remove outline for mouse users */
    *:focus:not(:focus-visible) {
      outline: none;
    }

    /* Ensure focus is visible on interactive elements */
    button:focus-visible,
    a:focus-visible,
    input:focus-visible,
    select:focus-visible,
    textarea:focus-visible,
    [role="button"]:focus-visible {
      outline: 3px solid #4A90E2;
      outline-offset: 2px;
    }

    /* High contrast mode support */
    @media (prefers-contrast: more) {
      *:focus-visible {
        outline: 3px solid;
      }
    }

    /* Reduced motion support */
    @media (prefers-reduced-motion: reduce) {
      *:focus-visible {
        transition: none;
      }
    }
  `;

  document.head.appendChild(style);
  return style;
}

/**
 * Detect focus mode (keyboard vs mouse)
 */
export class FocusModeDetector {
  private isKeyboardMode: boolean = false;

  constructor() {
    this.initialize();
  }

  /**
   * Initialize focus mode detection
   */
  private initialize(): void {
    document.addEventListener('mousedown', () => {
      this.isKeyboardMode = false;
    });

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Tab') {
        this.isKeyboardMode = true;
      }
    });
  }

  /**
   * Check if currently in keyboard mode
   */
  isKeyboard(): boolean {
    return this.isKeyboardMode;
  }

  /**
   * Get current focus mode
   */
  getMode(): 'keyboard' | 'mouse' {
    return this.isKeyboardMode ? 'keyboard' : 'mouse';
  }
}

export const focusModeDetector = new FocusModeDetector();

// ============================================================================
// Focus Visibility Monitoring
// ============================================================================

class FocusVisibilityMonitor {
  private focusListeners: Set<(element: HTMLElement | null) => void> = new Set();
  private currentFocus: HTMLElement | null = null;

  constructor() {
    this.initialize();
  }

  /**
   * Initialize focus tracking
   */
  private initialize(): void {
    document.addEventListener('focusin', (event) => {
      const element = event.target as HTMLElement;
      this.currentFocus = element;
      this.notifyListeners(element);
    });

    document.addEventListener('focusout', () => {
      this.currentFocus = null;
      this.notifyListeners(null);
    });
  }

  /**
   * Subscribe to focus changes
   */
  onFocusChange(
    callback: (element: HTMLElement | null) => void
  ): () => void {
    this.focusListeners.add(callback);

    return () => {
      this.focusListeners.delete(callback);
    };
  }

  /**
   * Notify all listeners of focus change
   */
  private notifyListeners(element: HTMLElement | null): void {
    for (const listener of this.focusListeners) {
      listener(element);
    }
  }

  /**
   * Get currently focused element
   */
  getFocused(): HTMLElement | null {
    return this.currentFocus;
  }

  /**
   * Check if element is visible
   */
  isElementVisible(element: HTMLElement): boolean {
    const rect = element.getBoundingClientRect();
    const style = window.getComputedStyle(element);

    return (
      rect.width > 0 &&
      rect.height > 0 &&
      style.visibility !== 'hidden' &&
      style.display !== 'none'
    );
  }
}

export const focusVisibilityMonitor = new FocusVisibilityMonitor();

// ============================================================================
// Focus Announcement
// ============================================================================

/**
 * Announce focus change to screen readers
 */
export function announceFocus(element: HTMLElement, message: string): void {
  // Create temporary live region
  const announcement = document.createElement('div');
  announcement.setAttribute('aria-live', 'assertive');
  announcement.setAttribute('aria-atomic', 'true');
  announcement.style.position = 'absolute';
  announcement.style.left = '-10000px';
  announcement.textContent = message;

  document.body.appendChild(announcement);

  // Remove after announcement
  setTimeout(() => {
    announcement.remove();
  }, 1000);
}

/**
 * Get accessible name for element
 */
export function getAccessibleName(element: HTMLElement): string {
  // Check aria-label
  const ariaLabel = element.getAttribute('aria-label');
  if (ariaLabel) return ariaLabel;

  // Check aria-labelledby
  const ariaLabelledBy = element.getAttribute('aria-labelledby');
  if (ariaLabelledBy) {
    const labelElement = document.getElementById(ariaLabelledBy);
    if (labelElement) return labelElement.textContent || '';
  }

  // Check associated label
  if (element.tagName === 'INPUT' && (element as HTMLInputElement).id) {
    const label = document.querySelector(`label[for="${(element as HTMLInputElement).id}"]`);
    if (label) return label.textContent || '';
  }

  // Check placeholder
  if ((element as any).placeholder) {
    return (element as any).placeholder;
  }

  // Check title
  if (element.title) {
    return element.title;
  }

  // Check text content
  return element.textContent || '';
}

