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
  describe('keys owned by the focused widget or an open dialog (#5656)', () => {
    let host: HTMLElement;

    beforeEach(() => {
      host = document.createElement('div');
      document.body.appendChild(host);
      service.startListening();
    });

    afterEach(() => {
      host.remove();
    });

    /** Fire a keydown at `target`; it bubbles to the window listener like a real one. */
    const press = (target: EventTarget, key: string, init: KeyboardEventInit = {}) => {
      const event = new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true, ...init });
      target.dispatchEvent(event);
      return event;
    };
    const add = (html: string) => {
      host.innerHTML = html;
      return host.firstElementChild as HTMLElement;
    };

    it.each(['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End'])(
      'leaves %s to a focused slider',
      (key) => {
        const handler = vi.fn();
        service.register(makeShortcut(key), handler);
        const slider = add('<div role="slider" tabindex="0"></div>');

        const event = press(slider, key);

        expect(handler).not.toHaveBeenCalled();
        expect(event.defaultPrevented).toBe(false);
      },
    );

    it.each([
      ['listbox option', '<div role="listbox"><div role="option" tabindex="0"></div></div>', '[role="option"]'],
      ['tab', '<div role="tablist"><button role="tab"></button></div>', '[role="tab"]'],
      ['menu item', '<ul role="menu"><li role="menuitem" tabindex="0"></li></ul>', '[role="menuitem"]'],
    ])('leaves the arrow keys to a focused %s', (_name, html, inner) => {
      const handler = vi.fn();
      service.register(makeShortcut('ArrowDown'), handler);
      add(html);

      press(host.querySelector(inner)!, 'ArrowDown');

      expect(handler).not.toHaveBeenCalled();
    });

    it('still fires an arrow shortcut when focus is on a plain element or the body', () => {
      const handler = vi.fn();
      service.register(makeShortcut('ArrowRight'), handler);

      press(add('<div tabindex="0"></div>'), 'ArrowRight');
      press(document.body, 'ArrowRight');

      expect(handler).toHaveBeenCalledTimes(2);
    });

    it.each([
      ['button', '<button>Play</button>'],
      ['link', '<a href="#x">x</a>'],
      ['tab', '<div role="tab" tabindex="0"></div>'],
      ['menu item', '<div role="menuitem" tabindex="0"></div>'],
    ])('does not hijack Space on a focused %s', (_name, html) => {
      const handler = vi.fn();
      service.register(makeShortcut(' '), handler);
      const control = add(html);

      const event = press(control, ' ');

      expect(handler).not.toHaveBeenCalled();
      // The control's own activation must not be cancelled.
      expect(event.defaultPrevented).toBe(false);
    });

    it('still toggles playback on Space from the body or the focused seek slider', () => {
      const handler = vi.fn();
      service.register(makeShortcut(' '), handler);

      press(document.body, ' ');
      press(add('<div role="slider" tabindex="0"></div>'), ' ');

      expect(handler).toHaveBeenCalledTimes(2);
    });

    it('does not run a shortcut the focused widget already handled', () => {
      const handler = vi.fn();
      service.register(makeShortcut('m'), handler);
      const el = add('<div tabindex="0"></div>');
      el.addEventListener('keydown', (e) => e.preventDefault());

      press(el, 'm');

      expect(handler).not.toHaveBeenCalled();
    });

    it.each([
      ['aria-modal dialog', '<div role="dialog" aria-modal="true"><button>OK</button></div>'],
      ['role=dialog', '<div role="dialog"><button>OK</button></div>'],
      ['alert dialog', '<div role="alertdialog"><button>OK</button></div>'],
      ['open menu', '<ul role="menu"><li>x</li></ul>'],
    ])('suspends every shortcut while a %s is open', (_name, html) => {
      const space = vi.fn();
      const mute = vi.fn();
      const escape = vi.fn();
      service.register(makeShortcut(' '), space);
      service.register(makeShortcut('m'), mute);
      service.register(makeShortcut('Escape'), escape);
      add(html);

      press(document.body, ' ');
      press(document.body, 'm');
      press(document.body, 'Escape');

      expect(space).not.toHaveBeenCalled();
      expect(mute).not.toHaveBeenCalled();
      expect(escape).not.toHaveBeenCalled();
    });

    it('resumes once the dialog is gone', () => {
      const handler = vi.fn();
      service.register(makeShortcut('m'), handler);
      add('<div role="dialog" aria-modal="true"></div>');
      press(document.body, 'm');
      expect(handler).not.toHaveBeenCalled();

      host.innerHTML = '';
      press(document.body, 'm');

      expect(handler).toHaveBeenCalledOnce();
    });
  });
});
