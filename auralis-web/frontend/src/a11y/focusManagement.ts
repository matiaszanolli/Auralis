/**
 * Focus Management Utilities
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tools for managing keyboard focus in accessible applications: focus
 * restoration (save/restore) and a focus trap for modals, consumed by
 * useDialogAccessibility.ts.
 *
 * #4392 deleted injectFocusStyles/FocusModeDetector/FocusVisibilityMonitor/
 * announceFocus/getAccessibleName from this file — dead a11y tooling with
 * zero call sites anywhere, never wired into app bootstrap.
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
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && onEscape) {
        event.preventDefault();
        onEscape();
        return;
      }

      if (event.key !== 'Tab') return;

      // Re-query on each Tab so dynamically added elements are included
      const focusableElements = this.getFocusableElements(container);
      if (focusableElements.length === 0) return;

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];

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

    // Focus first element if available
    const initialElements = this.getFocusableElements(container);
    if (initialElements.length > 0) {
      initialElements[0].focus();
    }

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
