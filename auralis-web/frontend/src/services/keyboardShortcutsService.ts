/**
 * Keyboard Shortcuts Service
 *
 * Simple, framework-agnostic service for handling keyboard shortcuts.
 * Avoids React hook complexity and minification issues.
 *
 * Architecture: Plain TypeScript service pattern
 * - No React hooks or complex closures
 * - Direct event handlers
 * - Simple registry pattern
 */

export type ShortcutHandler = () => void;

export interface ShortcutDefinition {
  key: string;
  ctrl?: boolean;
  shift?: boolean;
  alt?: boolean;
  meta?: boolean;
  description: string;
  category: 'Playback' | 'Navigation' | 'Library' | 'Queue' | 'Global';
}

interface RegisteredShortcut extends ShortcutDefinition {
  handler: ShortcutHandler;
}

/**
 * Minimal shape of the User-Agent Client Hints API, which TypeScript's DOM lib
 * does not yet declare. Only the low-entropy `platform` hint is used, so no
 * permission prompt or async `getHighEntropyValues()` call is involved.
 */
interface NavigatorUAData {
  platform?: string;
}

/**
 * Whether we are running on macOS, which decides ⌘/⇧/⌥ vs Ctrl/Shift/Alt in
 * every shortcut label.
 *
 * Single source of truth (#4556). The expression
 * `navigator.platform.toUpperCase().indexOf('MAC') >= 0` was previously
 * duplicated across this service, `useKeyboardShortcuts` and
 * `useShortcutFormatting`, so any correction would have left the other copies
 * disagreeing — inconsistent glyphs within one session, which is worse than
 * being uniformly wrong.
 *
 * `Navigator.platform` is deprecated in the HTML Living Standard and is already
 * frozen (and eventually reduced) by Chromium's user-agent reduction, so the
 * modern `navigator.userAgentData.platform` hint is preferred where present.
 * Chromium is the only engine this Electron app runs on, so the remaining
 * fallbacks are belt-and-braces rather than load-bearing.
 */
export function isMacPlatform(): boolean {
  if (typeof navigator === 'undefined') return false;

  const uaData = (navigator as Navigator & { userAgentData?: NavigatorUAData }).userAgentData;
  if (uaData?.platform) {
    return uaData.platform.toUpperCase().includes('MAC');
  }

  if (typeof navigator.platform === 'string' && navigator.platform) {
    return navigator.platform.toUpperCase().includes('MAC');
  }

  return /Mac/i.test(navigator.userAgent ?? '');
}

class KeyboardShortcutsService {
  private shortcuts: Map<string, RegisteredShortcut> = new Map();
  private enabled: boolean = true;
  private listener: ((event: KeyboardEvent) => void) | null = null;

  /**
   * Generate unique key for shortcut matching
   */
  private generateKey(key: string, ctrl: boolean, shift: boolean, alt: boolean): string {
    const parts = [];
    if (ctrl) parts.push('ctrl');
    if (shift) parts.push('shift');
    if (alt) parts.push('alt');
    parts.push(key.toLowerCase());
    return parts.join('+');
  }

  /**
   * Check if element is an input that should block shortcuts
   */
  private isInputElement(target: EventTarget | null): boolean {
    if (!target || !(target instanceof HTMLElement)) return false;
    const tagName = target.tagName.toLowerCase();
    const isInput = ['input', 'textarea', 'select'].includes(tagName);
    const isContentEditable = target.contentEditable === 'true';
    return isInput || isContentEditable;
  }

  /**
   * Register a keyboard shortcut
   */
  register(definition: ShortcutDefinition, handler: ShortcutHandler): void {
    const key = this.generateKey(
      definition.key,
      definition.ctrl || definition.meta || false,
      definition.shift || false,
      definition.alt || false
    );

    this.shortcuts.set(key, {
      ...definition,
      handler
    });
  }

  /**
   * Unregister a keyboard shortcut
   */
  unregister(definition: ShortcutDefinition): void {
    const key = this.generateKey(
      definition.key,
      definition.ctrl || definition.meta || false,
      definition.shift || false,
      definition.alt || false
    );

    this.shortcuts.delete(key);
  }

  /**
   * Clear all registered shortcuts
   */
  clear(): void {
    this.shortcuts.clear();
  }

  /**
   * Get all registered shortcuts (for help display)
   */
  getShortcuts(): ShortcutDefinition[] {
    return Array.from(this.shortcuts.values()).map(({ handler, ...def }) => def);
  }

  /**
   * Enable shortcuts
   */
  enable(): void {
    this.enabled = true;
  }

  /**
   * Disable shortcuts
   */
  disable(): void {
    this.enabled = false;
  }

  /**
   * Check if shortcuts are enabled
   */
  isEnabled(): boolean {
    return this.enabled;
  }

  /**
   * Handle keyboard event
   */
  private handleKeyDown = (event: KeyboardEvent): void => {
    if (!this.enabled) return;

    // Allow "/" (focus search) to work even in input fields
    const isSearchKey = event.key === '/' && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey;
    if (!isSearchKey && this.isInputElement(event.target)) return;

    const key = this.generateKey(
      event.key,
      event.ctrlKey || event.metaKey,
      event.shiftKey,
      event.altKey
    );

    const shortcut = this.shortcuts.get(key);
    if (shortcut) {
      event.preventDefault();
      shortcut.handler();
    }
  };

  /**
   * Start listening for keyboard events
   */
  startListening(): void {
    if (this.listener) return; // Already listening

    this.listener = this.handleKeyDown;
    window.addEventListener('keydown', this.listener);
  }

  /**
   * Stop listening for keyboard events
   */
  stopListening(): void {
    if (this.listener) {
      window.removeEventListener('keydown', this.listener);
      this.listener = null;
    }
  }

  /**
   * Format shortcut for display
   */
  formatShortcut(definition: ShortcutDefinition): string {
    const parts: string[] = [];
    const isMac = isMacPlatform();

    if (definition.ctrl || definition.meta) {
      parts.push(isMac ? '⌘' : 'Ctrl');
    }
    if (definition.shift) {
      parts.push(isMac ? '⇧' : 'Shift');
    }
    if (definition.alt) {
      parts.push(isMac ? '⌥' : 'Alt');
    }

    // Format key display
    const keyMap: Record<string, string> = {
      ' ': 'Space',
      'ArrowUp': '↑',
      'ArrowDown': '↓',
      'ArrowLeft': '←',
      'ArrowRight': '→',
      'Enter': '↵',
      'Escape': 'Esc',
      'Delete': 'Del',
    };

    const keyDisplay = keyMap[definition.key] || definition.key.toUpperCase();
    parts.push(keyDisplay);

    return parts.join(isMac ? '' : '+');
  }
}

// Export singleton instance
export const keyboardShortcuts = new KeyboardShortcutsService();
