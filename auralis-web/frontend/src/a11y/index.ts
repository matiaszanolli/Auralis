/**
 * Accessibility (A11y) Module Index
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Central export point for all accessibility utilities and tools.
 * Import accessibility tools from '@/a11y' for convenience.
 *
 * Phase C.4c: Accessibility & A11y
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

// ============================================================================
// Internal Imports (for functions below)
// ============================================================================

import { wcagAudit, type AuditIssue } from './wcagAudit';
import { contrastAuditor } from './contrastChecker';
import { focusManager, injectFocusStyles, focusVisibilityMonitor } from './focusManagement';
import { liveRegionManager } from './ariaUtilities';

// ============================================================================
// WCAG Audit
// ============================================================================

export { wcagAudit, WCAGAudit } from './wcagAudit';
export type { WCAGCriterion, AuditIssue, AuditResult, WCAGLevel } from './wcagAudit';

// ============================================================================
// Keyboard Navigation
// ============================================================================

export {
  useKeyboardShortcuts,
  useFocusTrap,
  useArrowKeyNavigation,
  useEscapeKey,
  matchesShortcut,
  isArrowKey,
  getArrowDirection,
  canFocus,
  getFocusableElements,
  focusNext,
  focusPrevious,
  focusFirst,
  focusLast,
} from './useKeyboardNavigation';

export type {
  KeyboardShortcut,
  FocusTrapOptions,
  ArrowNavigationOptions,
  KeyModifier,
  ArrowDirection,
} from './useKeyboardNavigation';

// ============================================================================
// ARIA Utilities
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
} from './ariaUtilities';

export type { AriaRole, LiveRegionPoliteness } from './ariaUtilities';

// ============================================================================
// Focus Management
// ============================================================================

export {
  focusManager,
  focusModeDetector,
  focusVisibilityMonitor,
  injectFocusStyles,
  announceFocus,
  getAccessibleName,
} from './focusManagement';

// ============================================================================
// Color Contrast
// ============================================================================

export {
  parseColor,
  rgbToHex,
  hexToRgb,
  invertColor,
  getRelativeLuminance,
  getContrastRatio,
  checkContrast,
  contrastAuditor,
  accessiblePalette,
} from './contrastChecker';

export type { RGB, ContrastCheck, ColorIssue } from './contrastChecker';

// ============================================================================
// Accessibility Monitoring
// ============================================================================

/**
 * Run a complete accessibility audit
 */
export function runA11yAudit(root: HTMLElement = document.body) {
  return wcagAudit.audit(root, 'AA');
}

/**
 * Get comprehensive accessibility report
 */
export function getA11yReport(): string {
  let report = '♿ Comprehensive Accessibility Report\n';
  report += '====================================\n\n';

  // WCAG audit
  const wcagResult = wcagAudit.audit(document.body, 'AA');
  report += wcagResult.report;
  report += '\n\n';

  // Color contrast
  report += contrastAuditor.generateReport(document.body);
  report += '\n\n';

  // Focus management
  const focusable = focusManager.getFocusableElements(document.body);
  report += `Focusable Elements: ${focusable.length}\n`;

  return report;
}

/**
 * Enable all accessibility monitoring
 */
export function enableA11yMonitoring(): void {
  // Inject focus styles
  injectFocusStyles();

  // Start focus visibility monitoring
  focusVisibilityMonitor.onFocusChange((element: HTMLElement | null) => {
    if (element && process.env.NODE_ENV === 'development') {
      console.debug('[A11y] Focus moved to:', element);
    }
  });

  // Log to window for DevTools access
  if (typeof window !== 'undefined') {
    (window as any).__A11Y__ = {
      audit: wcagAudit,
      focus: focusManager,
      contrast: contrastAuditor,
      liveRegions: liveRegionManager,
    };
  }
}

/**
 * Check accessibility compliance
 */
export function checkA11yCompliance(): {
  passed: boolean;
  errors: string[];
  warnings: string[];
} {
  const audit = wcagAudit.audit(document.body, 'AA');

  return {
    passed: audit.compliance.AA,
    errors: audit.errors.map((e: AuditIssue) => e.message),
    warnings: audit.warnings.map((w: AuditIssue) => w.message),
  };
}

// ============================================================================
// Module Documentation
// ============================================================================

/**
 * Accessibility (A11y) Module
 *
 * Complete accessibility toolkit for WCAG 2.1 AA compliance:
 *
 * 1. **WCAG Audit** - Automated compliance checking
 *    - Image alt text validation
 *    - Heading hierarchy verification
 *    - Form label requirements
 *    - Color contrast checking
 *    - ARIA attribute validation
 *
 * 2. **Keyboard Navigation** - Full keyboard support
 *    - Arrow key navigation
 *    - Tab order management
 *    - Focus traps for modals
 *    - Keyboard shortcuts
 *    - Escape key handling
 *
 * 3. **ARIA Utilities** - Screen reader support
 *    - ARIA attribute generators
 *    - Live region management
 *    - Role-specific helpers
 *    - Announcement utilities
 *    - ARIA validation
 *
 * 4. **Focus Management** - Focus handling
 *    - Focus history/restoration
 *    - Focus visibility
 *    - Focus mode detection
 *    - Accessible naming
 *    - Focus indication styles
 *
 * 5. **Color Contrast** - Visual accessibility
 *    - WCAG AA/AAA compliance
 *    - Contrast calculation
 *    - Color suggestions
 *    - Accessible palette
 *
 * Usage:
 * ```typescript
 * import {
 *   wcagAudit,
 *   focusManager,
 *   liveRegionManager,
 *   runA11yAudit,
 *   enableA11yMonitoring,
 * } from '@/a11y';
 *
 * // Enable all monitoring
 * enableA11yMonitoring();
 *
 * // Run audit
 * const result = runA11yAudit();
 *
 * // Announce to screen readers
 * liveRegionManager.announce('Item added to cart');
 *
 * // Manage focus
 * focusManager.saveFocus();
 * // ... do something ...
 * focusManager.restoreFocus();
 * ```
 */
