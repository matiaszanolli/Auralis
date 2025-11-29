/**
 * ARIA Utilities for Screen Reader Support
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Utilities for implementing ARIA attributes and roles.
 * Provides helpers for creating accessible interactive components.
 *
 * ARIA Roles: button, link, menuitem, tab, dialog, alert, region, etc.
 * ARIA Properties: aria-label, aria-describedby, aria-expanded, etc.
 * ARIA States: aria-checked, aria-disabled, aria-selected, etc.
 *
 * Features:
 * - ARIA attribute generators
 * - Live region management
 * - Announcement utilities
 * - Role-specific helpers
 * - Validation utilities
 *
 * Phase C.4c: Accessibility & A11y
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

// ============================================================================
// Types
// ============================================================================

type AriaRole =
  | 'button'
  | 'link'
  | 'menuitem'
  | 'tab'
  | 'dialog'
  | 'alert'
  | 'region'
  | 'main'
  | 'navigation'
  | 'banner'
  | 'complementary'
  | 'contentinfo';

type LiveRegionPoliteness = 'polite' | 'assertive' | 'off';

interface AriaButtonProps {
  'aria-label': string;
  'aria-pressed'?: boolean;
  'aria-disabled'?: boolean;
  role: 'button';
  tabIndex: number;
}

interface AriaDialogProps {
  role: 'dialog';
  'aria-modal': boolean;
  'aria-labelledby'?: string;
  'aria-describedby'?: string;
}

interface AriaMenuProps {
  role: 'menu' | 'menubar';
  'aria-orientation'?: 'vertical' | 'horizontal';
}

// ============================================================================
// Live Region Management
// ============================================================================

class LiveRegionManager {
  private regions: Map<string, HTMLElement> = new Map();

  /**
   * Create a live region for announcements
   */
  createLiveRegion(
    id: string,
    politeness: LiveRegionPoliteness = 'polite'
  ): HTMLElement {
    const existing = this.regions.get(id);
    if (existing) return existing;

    const region = document.createElement('div');
    region.id = id;
    region.setAttribute('aria-live', politeness);
    region.setAttribute('aria-atomic', 'true');
    region.style.position = 'absolute';
    region.style.left = '-10000px';
    region.style.width = '1px';
    region.style.height = '1px';
    region.style.overflow = 'hidden';

    document.body.appendChild(region);
    this.regions.set(id, region);

    return region;
  }

  /**
   * Announce text to screen readers
   */
  announce(text: string, politeness: LiveRegionPoliteness = 'polite'): void {
    const region = this.createLiveRegion('aria-announcer', politeness);
    region.textContent = text;

    // Clear after announcement
    setTimeout(() => {
      region.textContent = '';
    }, 1000);
  }

  /**
   * Announce with delay
   */
  announceAsync(
    text: string,
    delay: number = 100,
    politeness: LiveRegionPoliteness = 'polite'
  ): void {
    setTimeout(() => {
      this.announce(text, politeness);
    }, delay);
  }

  /**
   * Cleanup live regions
   */
  cleanup(): void {
    for (const region of this.regions.values()) {
      region.remove();
    }
    this.regions.clear();
  }
}

export const liveRegionManager = new LiveRegionManager();

// ============================================================================
// ARIA Attribute Generators
// ============================================================================

/**
 * Generate ARIA attributes for a button
 */
export function getButtonAriaProps(options: {
  label: string;
  pressed?: boolean;
  disabled?: boolean;
}): AriaButtonProps {
  return {
    role: 'button',
    'aria-label': options.label,
    'aria-pressed': options.pressed,
    'aria-disabled': options.disabled,
    tabIndex: options.disabled ? -1 : 0,
  };
}

/**
 * Generate ARIA attributes for a dialog
 */
export function getDialogAriaProps(options: {
  titleId?: string;
  descriptionId?: string;
  modal?: boolean;
}): AriaDialogProps {
  return {
    role: 'dialog',
    'aria-modal': options.modal ?? true,
    'aria-labelledby': options.titleId,
    'aria-describedby': options.descriptionId,
  };
}

/**
 * Generate ARIA attributes for a menu
 */
export function getMenuAriaProps(options: {
  orientation?: 'vertical' | 'horizontal';
  isMenubar?: boolean;
}): AriaMenuProps {
  return {
    role: options.isMenubar ? 'menubar' : 'menu',
    'aria-orientation': options.orientation || 'vertical',
  };
}

/**
 * Generate ARIA attributes for a tab
 */
export function getTabAriaProps(options: {
  id: string;
  panelId: string;
  selected?: boolean;
}): Record<string, any> {
  return {
    role: 'tab',
    'aria-selected': options.selected ?? false,
    'aria-controls': options.panelId,
    id: options.id,
    tabIndex: options.selected ? 0 : -1,
  };
}

/**
 * Generate ARIA attributes for a tab panel
 */
export function getTabPanelAriaProps(options: {
  id: string;
  tabId: string;
  labelledBy?: string;
}): Record<string, any> {
  return {
    role: 'tabpanel',
    id: options.id,
    'aria-labelledby': options.labelledBy || options.tabId,
    hidden: false,
  };
}

/**
 * Generate ARIA attributes for a combobox
 */
export function getComboboxAriaProps(options: {
  expanded?: boolean;
  listboxId: string;
  activeDescendant?: string;
}): Record<string, any> {
  return {
    role: 'combobox',
    'aria-expanded': options.expanded ?? false,
    'aria-controls': options.listboxId,
    'aria-activedescendant': options.activeDescendant,
  };
}

/**
 * Generate ARIA attributes for a listbox
 */
export function getListboxAriaProps(options: {
  id: string;
  orientation?: 'vertical' | 'horizontal';
  multiselectable?: boolean;
}): Record<string, any> {
  return {
    role: 'listbox',
    id: options.id,
    'aria-orientation': options.orientation || 'vertical',
    'aria-multiselectable': options.multiselectable ?? false,
  };
}

/**
 * Generate ARIA attributes for a list option
 */
export function getOptionAriaProps(options: {
  id: string;
  selected?: boolean;
  disabled?: boolean;
}): Record<string, any> {
  return {
    role: 'option',
    id: options.id,
    'aria-selected': options.selected ?? false,
    'aria-disabled': options.disabled ?? false,
  };
}

// ============================================================================
// Accessible Label Helpers
// ============================================================================

/**
 * Generate unique ID
 */
export function generateId(prefix: string = 'id'): string {
  return `${prefix}-${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Link label to input
 */
export function createLabelForInput(
  inputElement: HTMLInputElement,
  labelText: string
): HTMLLabelElement {
  const id = inputElement.id || generateId('input');
  inputElement.id = id;

  const label = document.createElement('label');
  label.htmlFor = id;
  label.textContent = labelText;

  return label;
}

/**
 * Create screen reader only text
 */
export function createSROnlyText(text: string): HTMLElement {
  const span = document.createElement('span');
  span.className = 'sr-only';
  span.textContent = text;

  // Apply sr-only styles
  Object.assign(span.style, {
    position: 'absolute',
    width: '1px',
    height: '1px',
    padding: '0',
    margin: '-1px',
    overflow: 'hidden',
    clip: 'rect(0, 0, 0, 0)',
    whiteSpace: 'nowrap',
    borderWidth: '0',
  });

  return span;
}

// ============================================================================
// Validation Utilities
// ============================================================================

/**
 * Validate ARIA attributes
 */
export function validateAriaAttributes(element: HTMLElement): string[] {
  const issues: string[] = [];

  // Check for aria-label or aria-labelledby
  const hasAriaLabel = element.hasAttribute('aria-label');
  const hasAriaLabelledBy = element.hasAttribute('aria-labelledby');
  const hasTextContent = (element.textContent || '').trim().length > 0;

  if (!hasAriaLabel && !hasAriaLabelledBy && !hasTextContent) {
    issues.push('Element missing accessible name');
  }

  // Check for aria-describedby
  const ariaDescribedBy = element.getAttribute('aria-describedby');
  if (ariaDescribedBy) {
    const describedById = ariaDescribedBy.split(' ')[0];
    if (!document.getElementById(describedById)) {
      issues.push(`aria-describedby references non-existent element: ${describedById}`);
    }
  }

  // Check for aria-labelledby
  const ariaLabelledBy = element.getAttribute('aria-labelledby');
  if (ariaLabelledBy) {
    const labelledById = ariaLabelledBy.split(' ')[0];
    if (!document.getElementById(labelledById)) {
      issues.push(`aria-labelledby references non-existent element: ${labelledById}`);
    }
  }

  // Check role attribute
  const role = element.getAttribute('role');
  if (role) {
    const validRoles: AriaRole[] = [
      'button',
      'link',
      'menuitem',
      'tab',
      'dialog',
      'alert',
      'region',
      'main',
      'navigation',
      'banner',
      'complementary',
      'contentinfo',
    ];

    if (!validRoles.includes(role as AriaRole)) {
      issues.push(`Invalid ARIA role: ${role}`);
    }
  }

  return issues;
}

/**
 * Validate all ARIA in container
 */
export function validateContainerAria(container: HTMLElement): Map<HTMLElement, string[]> {
  const results = new Map<HTMLElement, string[]>();

  const elementsWithAria = container.querySelectorAll('[aria-*], [role]');
  for (const element of elementsWithAria) {
    const issues = validateAriaAttributes(element as HTMLElement);
    if (issues.length > 0) {
      results.set(element as HTMLElement, issues);
    }
  }

  return results;
}

// ============================================================================
// Exports
// ============================================================================

export {
  liveRegionManager,
  getButtonAriaProps,
  getDialogAriaProps,
  getMenuAriaProps,
  getTabAriaProps,
  getTabPanelAriaProps,
  getComboboxAriaProps,
  getListboxAriaProps,
  getOptionAriaProps,
  generateId,
  createLabelForInput,
  createSROnlyText,
  validateAriaAttributes,
  validateContainerAria,
};

export type { AriaRole, LiveRegionPoliteness };
