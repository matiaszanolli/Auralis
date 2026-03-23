import { keyboardShortcuts } from '../keyboardShortcutsService';
import type { ShortcutDefinition } from '../keyboardShortcutsService';

describe('KeyboardShortcutsService', () => {
  const service = keyboardShortcuts;

  beforeEach(() => {
    service.clear();
    service.enable();
  });

  afterEach(() => {
    service.stopListening();
  });

  const makeShortcut = (key: string, overrides?: Partial<ShortcutDefinition>): ShortcutDefinition => ({
    key,
    description: `Test ${key}`,
    category: 'Global',
    ...overrides,
  });

  it('registers and retrieves shortcuts', () => {
    const handler = vi.fn();
    service.register(makeShortcut('a'), handler);

    const shortcuts = service.getShortcuts();
    expect(shortcuts).toHaveLength(1);
    expect(shortcuts[0].key).toBe('a');
  });

  it('unregisters shortcuts', () => {
    const def = makeShortcut('b');
    service.register(def, vi.fn());
    expect(service.getShortcuts()).toHaveLength(1);

    service.unregister(def);
    expect(service.getShortcuts()).toHaveLength(0);
  });

  it('clears all shortcuts', () => {
    service.register(makeShortcut('x'), vi.fn());
    service.register(makeShortcut('y'), vi.fn());
    expect(service.getShortcuts()).toHaveLength(2);

    service.clear();
    expect(service.getShortcuts()).toHaveLength(0);
  });

  it('enable/disable toggles isEnabled', () => {
    expect(service.isEnabled()).toBe(true);
    service.disable();
    expect(service.isEnabled()).toBe(false);
    service.enable();
    expect(service.isEnabled()).toBe(true);
  });

  it('invokes handler on matching keydown event', () => {
    const handler = vi.fn();
    service.register(makeShortcut('a'), handler);
    service.startListening();

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'a' }));

    expect(handler).toHaveBeenCalledOnce();
  });

  it('does not invoke handler when disabled', () => {
    const handler = vi.fn();
    service.register(makeShortcut('a'), handler);
    service.startListening();
    service.disable();

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'a' }));

    expect(handler).not.toHaveBeenCalled();
  });

  it('matches ctrl modifier shortcuts', () => {
    const handler = vi.fn();
    service.register(makeShortcut('s', { ctrl: true }), handler);
    service.startListening();

    // Without ctrl — should not match
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 's' }));
    expect(handler).not.toHaveBeenCalled();

    // With ctrl — should match
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 's', ctrlKey: true }));
    expect(handler).toHaveBeenCalledOnce();
  });

  it('stopListening removes the event listener', () => {
    const handler = vi.fn();
    service.register(makeShortcut('a'), handler);
    service.startListening();
    service.stopListening();

    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'a' }));

    expect(handler).not.toHaveBeenCalled();
  });

  it('formatShortcut produces readable string', () => {
    const def = makeShortcut('s', { ctrl: true });
    const formatted = service.formatShortcut(def);
    expect(formatted).toContain('S');
    // Should have modifier
    expect(formatted.length).toBeGreaterThan(1);
  });
});
