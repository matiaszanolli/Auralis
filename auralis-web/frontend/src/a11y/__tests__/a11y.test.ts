/**
 * Comprehensive Accessibility Tests
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Unit tests for accessibility features and WCAG compliance.
 *
 * Test Coverage:
 * - WCAG audit functionality
 * - Keyboard navigation
 * - ARIA attributes
 * - Focus management
 * - Color contrast
 *
 * Phase C.4c: Accessibility & A11y
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  wcagAudit,
  type AuditResult,
} from '../wcagAudit';
import {
  focusManager,
  focusModeDetector,
  focusVisibilityMonitor,
  injectFocusStyles,
  getAccessibleName,
} from '../focusManagement';
import {
  liveRegionManager,
  getButtonAriaProps,
  validateAriaAttributes,
} from '../ariaUtilities';
import {
  getContrastRatio,
  checkContrast,
  contrastAuditor,
  hexToRgb,
  rgbToHex,
} from '../contrastChecker';
import {
  matchesShortcut,
  isArrowKey,
  canFocus,
  getFocusableElements,
  type KeyboardShortcut,
} from '../useKeyboardNavigation';

describe('Accessibility Suite', () => {
  // ============================================================================
  // WCAG Audit Tests
  // ============================================================================

  describe('WCAG Audit', () => {
    let container: HTMLElement;

    beforeEach(() => {
      container = document.createElement('div');
      document.body.appendChild(container);
    });

    afterEach(() => {
      document.body.removeChild(container);
    });

    it('should audit for alt text on images', () => {
      const img = document.createElement('img');
      img.src = 'test.jpg';
      container.appendChild(img);

      const result = wcagAudit.audit(container, 'A');

      expect(result.errors.length).toBeGreaterThan(0);
      expect(result.errors[0].criterion).toBe('1.1.1');
    });

    it('should pass images with alt text', () => {
      const img = document.createElement('img');
      img.src = 'test.jpg';
      img.alt = 'Test image';
      container.appendChild(img);

      const result = wcagAudit.audit(container, 'A');

      expect(result.errors.filter((e) => e.criterion === '1.1.1')).toHaveLength(
        0
      );
    });

    it('should check heading hierarchy', () => {
      container.innerHTML = `
        <h1>Main</h1>
        <h3>Skipped H2</h3>
      `;

      const result = wcagAudit.audit(container, 'A');

      expect(result.warnings.length).toBeGreaterThan(0);
    });

    it('should require H1 on page', () => {
      container.innerHTML = '<h2>No H1</h2>';

      const result = wcagAudit.audit(container, 'A');

      expect(result.warnings.some((w) => w.message.includes('H1'))).toBe(true);
    });

    it('should check form labels', () => {
      const input = document.createElement('input');
      container.appendChild(input);

      const result = wcagAudit.audit(container, 'A');

      expect(result.errors.some((e) => e.message.includes('label'))).toBe(
        true
      );
    });

    it('should pass forms with labels', () => {
      const input = document.createElement('input');
      input.id = 'test-input';
      container.appendChild(input);

      const label = document.createElement('label');
      label.htmlFor = 'test-input';
      label.textContent = 'Test';
      container.appendChild(label);

      const result = wcagAudit.audit(container, 'A');

      expect(result.errors.filter((e) => e.message.includes('label'))).toHaveLength(
        0
      );
    });

    it('should check language attribute', () => {
      const result = wcagAudit.audit(container, 'A');

      expect(result.warnings.some((w) => w.message.includes('lang'))).toBe(true);
    });
  });

  // ============================================================================
  // Focus Management Tests
  // ============================================================================

  describe('Focus Management', () => {
    let container: HTMLElement;

    beforeEach(() => {
      container = document.createElement('div');
      container.innerHTML = `
        <button>Button 1</button>
        <button>Button 2</button>
        <button>Button 3</button>
      `;
      document.body.appendChild(container);
    });

    afterEach(() => {
      document.body.removeChild(container);
    });

    it('should save and restore focus', () => {
      const button = container.querySelector('button') as HTMLButtonElement;
      button.focus();

      const saved = focusManager.saveFocus();
      expect(saved).toBe(button);

      // Move focus elsewhere
      const otherButton = container.querySelectorAll('button')[1] as HTMLButtonElement;
      otherButton.focus();

      // Restore
      const restored = focusManager.restoreFocus();
      expect(restored).toBe(true);
      expect(document.activeElement).toBe(button);
    });

    it('should get focusable elements', () => {
      const focusable = focusManager.getFocusableElements(container);
      expect(focusable.length).toBeGreaterThan(0);
    });

    it('should detect can focus', () => {
      const button = container.querySelector('button') as HTMLButtonElement;
      expect(canFocus(button)).toBe(true);

      const div = document.createElement('div');
      expect(canFocus(div)).toBe(false);
    });

    it('should create focus trap', () => {
      const cleanup = focusManager.createFocusTrap(container);

      expect(typeof cleanup).toBe('function');
      cleanup();
    });

    it('should get current focus', () => {
      const button = container.querySelector('button') as HTMLButtonElement;
      button.focus();

      const current = focusManager.getCurrentFocus();
      expect(current).toBe(button);
    });

    it('should check if element is focused', () => {
      const button = container.querySelector('button') as HTMLButtonElement;
      button.focus();

      expect(focusManager.isFocused(button)).toBe(true);
    });
  });

  // ============================================================================
  // ARIA Tests
  // ============================================================================

  describe('ARIA Attributes', () => {
    it('should generate button ARIA props', () => {
      const props = getButtonAriaProps({
        label: 'Close',
        disabled: false,
      });

      expect(props.role).toBe('button');
      expect(props['aria-label']).toBe('Close');
      expect(props['aria-disabled']).toBe(false);
    });

    it('should validate ARIA attributes', () => {
      const element = document.createElement('div');
      element.setAttribute('role', 'button');

      const issues = validateAriaAttributes(element);
      expect(issues.length).toBeGreaterThan(0);
      expect(issues[0]).toContain('accessible name');
    });

    it('should pass validation with aria-label', () => {
      const element = document.createElement('div');
      element.setAttribute('role', 'button');
      element.setAttribute('aria-label', 'Click me');

      const issues = validateAriaAttributes(element);
      expect(issues.length).toBe(0);
    });

    it('should create live region', () => {
      const region = liveRegionManager.createLiveRegion(
        'test-live',
        'polite'
      );

      expect(region).toBeDefined();
      expect(region.getAttribute('aria-live')).toBe('polite');
      expect(region.getAttribute('aria-atomic')).toBe('true');

      region.remove();
    });
  });

  // ============================================================================
  // Contrast Tests
  // ============================================================================

  describe('Color Contrast', () => {
    it('should calculate contrast ratio', () => {
      const ratio = getContrastRatio('#ffffff', '#000000');
      expect(ratio).toBeCloseTo(21, 0); // Max contrast
    });

    it('should check WCAG AA compliance', () => {
      const check = checkContrast('#ffffff', '#666666');
      expect(check.aa).toBe(true);
    });

    it('should fail low contrast', () => {
      const check = checkContrast('#ffffff', '#f5f5f5');
      expect(check.aa).toBe(false);
    });

    it('should check large text AA', () => {
      const check = checkContrast('#ffffff', '#cccccc');
      expect(check.largeTextAA).toBe(true);
    });

    it('should parse hex colors', () => {
      const rgb = hexToRgb('#ffffff');
      expect(rgb).toEqual({ r: 255, g: 255, b: 255 });
    });

    it('should convert RGB to hex', () => {
      const hex = rgbToHex({ r: 255, g: 255, b: 255 });
      expect(hex).toBe('#ffffff');
    });
  });

  // ============================================================================
  // Keyboard Navigation Tests
  // ============================================================================

  describe('Keyboard Navigation', () => {
    it('should detect arrow keys', () => {
      expect(isArrowKey('ArrowUp')).toBe(true);
      expect(isArrowKey('ArrowDown')).toBe(true);
      expect(isArrowKey('ArrowLeft')).toBe(true);
      expect(isArrowKey('ArrowRight')).toBe(true);
      expect(isArrowKey('Enter')).toBe(false);
    });

    it('should match keyboard shortcuts', () => {
      const event = new KeyboardEvent('keydown', {
        key: 's',
        ctrlKey: true,
      });

      const shortcut: KeyboardShortcut = {
        key: 's',
        modifiers: ['ctrl'],
        handler: vi.fn(),
      };

      expect(matchesShortcut(event, shortcut)).toBe(true);
    });

    it('should not match non-matching shortcuts', () => {
      const event = new KeyboardEvent('keydown', {
        key: 's',
        ctrlKey: false,
      });

      const shortcut: KeyboardShortcut = {
        key: 's',
        modifiers: ['ctrl'],
        handler: vi.fn(),
      };

      expect(matchesShortcut(event, shortcut)).toBe(false);
    });

    it('should detect focusable elements', () => {
      const container = document.createElement('div');
      container.innerHTML = `
        <button>Button</button>
        <a href="#">Link</a>
        <input type="text" />
      `;

      const focusable = getFocusableElements(container);
      expect(focusable.length).toBe(3);
    });
  });

  // ============================================================================
  // Focus Indication Tests
  // ============================================================================

  describe('Focus Indication', () => {
    it('should inject focus styles', () => {
      const style = injectFocusStyles();

      expect(style).toBeDefined();
      expect(style.textContent).toContain(':focus-visible');

      style.remove();
    });

    it('should detect focus mode', () => {
      const mode = focusModeDetector.getMode();
      expect(['keyboard', 'mouse']).toContain(mode);
    });

    it('should monitor focus changes', () => {
      const callback = vi.fn();
      const unsubscribe = focusVisibilityMonitor.onFocusChange(callback);

      expect(typeof unsubscribe).toBe('function');
      unsubscribe();
    });

    it('should get accessible name', () => {
      const button = document.createElement('button');
      button.textContent = 'Click me';

      const name = getAccessibleName(button);
      expect(name).toBe('Click me');
    });

    it('should get accessible name from aria-label', () => {
      const button = document.createElement('button');
      button.setAttribute('aria-label', 'Submit form');

      const name = getAccessibleName(button);
      expect(name).toBe('Submit form');
    });
  });

  // ============================================================================
  // Integration Tests
  // ============================================================================

  describe('Integration', () => {
    it('should audit complete page', () => {
      const page = document.createElement('div');
      page.innerHTML = `
        <h1>Test Page</h1>
        <button>Submit</button>
        <img src="test.jpg" alt="Test image" />
      `;
      document.body.appendChild(page);

      const result = wcagAudit.audit(page, 'AA');

      expect(result).toBeDefined();
      expect(result.errors).toBeDefined();
      expect(result.warnings).toBeDefined();

      document.body.removeChild(page);
    });

    it('should audit color contrast', () => {
      const container = document.createElement('div');
      container.style.color = '#ffffff';
      container.style.backgroundColor = '#ffffff';
      container.textContent = 'Low contrast text';
      document.body.appendChild(container);

      const issues = contrastAuditor.auditContainer(container);

      expect(issues.length).toBeGreaterThan(0);

      document.body.removeChild(container);
    });
  });
});

function afterEach(callback: () => void): void {
  callback();
}
