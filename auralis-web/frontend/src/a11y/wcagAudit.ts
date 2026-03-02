/**
 * WCAG 2.1 AA Compliance Audit Utilities
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tools for auditing and ensuring WCAG 2.1 AA accessibility compliance.
 * Provides automated and manual audit capabilities for web accessibility.
 *
 * WCAG 2.1 Levels:
 * - Level A: Basic accessibility
 * - Level AA: Enhanced accessibility (target for most sites)
 * - Level AAA: Advanced accessibility (optional)
 *
 * Features:
 * - Automated WCAG audit capabilities
 * - Color contrast verification
 * - Alt text validation
 * - ARIA attribute checking
 * - Keyboard navigation audit
 * - Focus management validation
 * - Heading hierarchy verification
 * - Form accessibility checks
 *
 * Phase C.4c: Accessibility & A11y
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

// ============================================================================
// Types & Interfaces
// ============================================================================

type WCAGLevel = 'A' | 'AA' | 'AAA';

interface WCAGCriterion {
  code: string; // e.g., "1.4.3"
  name: string;
  level: WCAGLevel;
  description: string;
  requirement: string;
}

interface AuditIssue {
  criterion: string;
  level: WCAGLevel;
  severity: 'error' | 'warning' | 'info';
  element?: HTMLElement;
  message: string;
  suggestion: string;
  selector?: string;
}

interface AuditResult {
  timestamp: number;
  level: WCAGLevel;
  totalIssues: number;
  errors: AuditIssue[];
  warnings: AuditIssue[];
  info: AuditIssue[];
  compliance: {
    A: boolean;
    AA: boolean;
    AAA: boolean;
  };
  report: string;
}

// ============================================================================
// WCAG Criteria Database
// ============================================================================

export const wcagCriteria: Record<string, WCAGCriterion> = {
  '1.1.1': {
    code: '1.1.1',
    name: 'Non-text Content',
    level: 'A',
    description: 'All non-text content has appropriate alternative text',
    requirement: 'Images must have alt attributes, videos must have captions',
  },
  '1.4.3': {
    code: '1.4.3',
    name: 'Contrast (Minimum)',
    level: 'AA',
    description: 'Text has minimum 4.5:1 contrast ratio',
    requirement: 'Foreground and background colors must have adequate contrast',
  },
  '2.1.1': {
    code: '2.1.1',
    name: 'Keyboard',
    level: 'A',
    description: 'All functionality available via keyboard',
    requirement: 'Users must be able to navigate and use all features via keyboard',
  },
  '2.4.3': {
    code: '2.4.3',
    name: 'Focus Order',
    level: 'A',
    description: 'Focus order is logical and meaningful',
    requirement: 'Tab order must follow logical visual flow',
  },
  '2.4.7': {
    code: '2.4.7',
    name: 'Focus Visible',
    level: 'AA',
    description: 'Keyboard focus indicator is visible',
    requirement: 'Users must be able to see which element has focus',
  },
  '3.2.4': {
    code: '3.2.4',
    name: 'Consistent Identification',
    level: 'AA',
    description: 'Components with same functionality are identified consistently',
    requirement: 'Similar UI components should look and behave the same way',
  },
  '4.1.2': {
    code: '4.1.2',
    name: 'Name, Role, Value',
    level: 'A',
    description: 'All UI components have accessible name, role, and state',
    requirement: 'Elements must have proper ARIA attributes',
  },
  '4.1.3': {
    code: '4.1.3',
    name: 'Status Messages',
    level: 'AA',
    description: 'Status messages are programmatically available',
    requirement: 'Alerts and errors must be announced to screen readers',
  },
};

// ============================================================================
// WCAG Audit Engine
// ============================================================================

export class WCAGAudit {
  private issues: AuditIssue[] = [];
  private targetLevel: WCAGLevel = 'AA';

  /**
   * Run comprehensive accessibility audit
   */
  audit(root: HTMLElement = document.body, level: WCAGLevel = 'AA'): AuditResult {
    this.issues = [];
    this.targetLevel = level;

    // Run all audit checks
    this.checkAltText(root);
    this.checkColorContrast(root);
    this.checkKeyboardNavigation(root);
    this.checkFocusManagement(root);
    this.checkARIA(root);
    this.checkHeadingHierarchy(root);
    this.checkFormLabels(root);
    this.checkLanguage(root);

    return this.generateResult();
  }

  /**
   * Check for alt text on images (1.1.1)
   */
  private checkAltText(root: HTMLElement): void {
    const images = root.querySelectorAll('img');

    for (const img of images) {
      if (!img.getAttribute('alt')) {
        this.addIssue({
          criterion: '1.1.1',
          level: 'A',
          severity: 'error',
          element: img,
          message: 'Image missing alt attribute',
          suggestion: 'Add descriptive alt text to image',
          selector: `img[src="${img.src}"]`,
        });
      }

      const alt = img.getAttribute('alt') || '';
      if (alt.length === 0) {
        this.addIssue({
          criterion: '1.1.1',
          level: 'A',
          severity: 'warning',
          element: img,
          message: 'Image has empty alt attribute',
          suggestion: 'Provide meaningful alt text or use alt="" if decorative',
          selector: `img[src="${img.src}"]`,
        });
      }
    }
  }

  /**
   * Check color contrast (1.4.3)
   */
  private checkColorContrast(root: HTMLElement): void {
    const elements = root.querySelectorAll('*');
    const minRatio = 4.5; // AA standard for normal text

    for (const element of elements) {
      const text = element.textContent?.trim();
      if (!text || text.length === 0) continue;

      const style = window.getComputedStyle(element);
      const color = style.color;
      const bgColor = style.backgroundColor;

      // Only check if element has actual color styling
      if (color && bgColor && color !== 'rgba(0, 0, 0, 0)') {
        const ratio = this.getContrastRatio(color, bgColor);

        if (ratio < minRatio) {
          this.addIssue({
            criterion: '1.4.3',
            level: 'AA',
            severity: 'error',
            element: element as HTMLElement,
            message: `Insufficient color contrast: ${ratio.toFixed(2)}:1 (need 4.5:1)`,
            suggestion:
              'Increase contrast by adjusting foreground or background color',
            selector: (element as HTMLElement).className,
          });
        }
      }
    }
  }

  /**
   * Check keyboard navigation (2.1.1)
   */
  private checkKeyboardNavigation(root: HTMLElement): void {
    // Check for keyboard accessible elements
    const interactiveElements = root.querySelectorAll(
      'button, a, input, select, textarea, [role="button"], [role="link"]'
    );

    for (const element of interactiveElements) {
      // Check if element is keyboard accessible
      const tabIndex = (element as HTMLElement).getAttribute('tabindex');

      // Button and input elements are naturally keyboard accessible
      if (element.tagName === 'BUTTON' || element.tagName === 'INPUT') {
        if ((element as HTMLElement).hasAttribute('disabled')) {
          continue; // Disabled elements don't need keyboard access
        }
      }

      // Links should have href or be focusable
      if (element.tagName === 'A') {
        const href = (element as HTMLAnchorElement).getAttribute('href');
        if (!href) {
          this.addIssue({
            criterion: '2.1.1',
            level: 'A',
            severity: 'warning',
            element: element as HTMLElement,
            message: 'Link element without href attribute',
            suggestion: 'Add href attribute or use button element',
          });
        }
      }

      // Divs with role="button" need keyboard support
      if ((element as HTMLElement).getAttribute('role') === 'button') {
        if (!tabIndex) {
          this.addIssue({
            criterion: '2.1.1',
            level: 'A',
            severity: 'error',
            element: element as HTMLElement,
            message: 'Button role element not keyboard focusable',
            suggestion: 'Add tabindex="0" to make element focusable',
          });
        }
      }
    }
  }

  /**
   * Check focus management (2.4.7)
   */
  private checkFocusManagement(root: HTMLElement): void {
    const focusableElements = root.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );

    // Check for focus visible styles
    const style = document.querySelector('style') || document.createElement('style');
    const styleText = style.textContent || '';

    if (!styleText.includes(':focus') && !styleText.includes(':focus-visible')) {
      this.addIssue({
        criterion: '2.4.7',
        level: 'AA',
        severity: 'warning',
        message: 'No visible focus indicator found in CSS',
        suggestion:
          'Add :focus or :focus-visible styles to show keyboard focus clearly',
      });
    }

    // Check that all focusable elements can be reached
    if (focusableElements.length === 0) {
      this.addIssue({
        criterion: '2.4.3',
        level: 'A',
        severity: 'info',
        message: 'No keyboard focusable elements found',
        suggestion: 'Ensure interactive elements are keyboard accessible',
      });
    }
  }

  /**
   * Check ARIA attributes (4.1.2)
   */
  private checkARIA(root: HTMLElement): void {
    // Check for custom roles without proper ARIA
    const customRoles = root.querySelectorAll('[role]');

    for (const element of customRoles) {
      const role = (element as HTMLElement).getAttribute('role');

      // Check for required ARIA attributes based on role
      if (role === 'button') {
        if (!this.hasAccessibleName(element as HTMLElement)) {
          this.addIssue({
            criterion: '4.1.2',
            level: 'A',
            severity: 'error',
            element: element as HTMLElement,
            message: `Element with role="${role}" has no accessible name`,
            suggestion:
              'Add aria-label, aria-labelledby, or visible text content',
          });
        }
      }

      if (role === 'dialog') {
        if (!this.hasAccessibleName(element as HTMLElement)) {
          this.addIssue({
            criterion: '4.1.2',
            level: 'A',
            severity: 'error',
            element: element as HTMLElement,
            message: 'Dialog element missing accessible name',
            suggestion:
              'Add aria-labelledby pointing to dialog title or aria-label',
          });
        }
      }
    }
  }

  /**
   * Check heading hierarchy (2.4.10)
   */
  private checkHeadingHierarchy(root: HTMLElement): void {
    const headings = root.querySelectorAll('h1, h2, h3, h4, h5, h6');
    let lastLevel = 0;

    for (const heading of headings) {
      const level = parseInt(heading.tagName[1]);

      // Check for skipped levels
      if (level - lastLevel > 1 && lastLevel > 0) {
        this.addIssue({
          criterion: '2.4.10',
          level: 'A',
          severity: 'warning',
          element: heading as HTMLElement,
          message: `Heading hierarchy skipped from H${lastLevel} to H${level}`,
          suggestion: 'Use sequential heading levels (H1, H2, H3, etc.)',
        });
      }

      // Check if heading has content
      if (!heading.textContent?.trim()) {
        this.addIssue({
          criterion: '2.4.10',
          level: 'A',
          severity: 'error',
          element: heading as HTMLElement,
          message: 'Empty heading element',
          suggestion: 'Provide meaningful heading text',
        });
      }

      lastLevel = level;
    }

    // Check for at least one H1
    if (!root.querySelector('h1')) {
      this.addIssue({
        criterion: '1.3.1',
        level: 'A',
        severity: 'warning',
        message: 'No H1 heading found on page',
        suggestion: 'Add exactly one H1 heading as main page title',
      });
    }
  }

  /**
   * Check form labels (1.3.1)
   */
  private checkFormLabels(root: HTMLElement): void {
    const inputs = root.querySelectorAll('input, select, textarea');

    for (const input of inputs) {
      const id = (input as HTMLElement).getAttribute('id');
      const ariaLabel = (input as HTMLElement).getAttribute('aria-label');
      const ariaLabelledBy = (input as HTMLElement).getAttribute(
        'aria-labelledby'
      );

      // Check for associated label
      let hasLabel = false;
      if (id) {
        const label = root.querySelector(`label[for="${id}"]`);
        hasLabel = !!label;
      }

      if (!hasLabel && !ariaLabel && !ariaLabelledBy) {
        this.addIssue({
          criterion: '1.3.1',
          level: 'A',
          severity: 'error',
          element: input as HTMLElement,
          message: 'Form input missing associated label',
          suggestion:
            'Add <label for="id"> or aria-label attribute to form input',
        });
      }
    }
  }

  /**
   * Check language specification (3.1.1)
   */
  private checkLanguage(_root: HTMLElement): void {
    const htmlElement = document.documentElement;
    if (!htmlElement.getAttribute('lang')) {
      this.addIssue({
        criterion: '3.1.1',
        level: 'A',
        severity: 'warning',
        message: 'HTML element missing lang attribute',
        suggestion: 'Add lang="en" (or appropriate language code) to <html>',
      });
    }
  }

  /**
   * Get contrast ratio between two colors
   */
  private getContrastRatio(color1: string, color2: string): number {
    const rgb1 = this.parseColor(color1);
    const rgb2 = this.parseColor(color2);

    if (!rgb1 || !rgb2) return 0;

    const lum1 = this.getRelativeLuminance(rgb1);
    const lum2 = this.getRelativeLuminance(rgb2);

    const lighter = Math.max(lum1, lum2);
    const darker = Math.min(lum1, lum2);

    return (lighter + 0.05) / (darker + 0.05);
  }

  /**
   * Calculate relative luminance
   */
  private getRelativeLuminance(rgb: [number, number, number]): number {
    const [r, g, b] = rgb.map((c) => {
      const c2 = c / 255;
      return c2 <= 0.03928 ? c2 / 12.92 : Math.pow((c2 + 0.055) / 1.055, 2.4);
    });

    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  }

  /**
   * Parse color string to RGB
   */
  private parseColor(color: string): [number, number, number] | null {
    // Parse rgb() format
    const rgbMatch = color.match(/\d+/g);
    if (rgbMatch && rgbMatch.length >= 3) {
      return [
        parseInt(rgbMatch[0]),
        parseInt(rgbMatch[1]),
        parseInt(rgbMatch[2]),
      ];
    }

    // Parse hex format
    const hexMatch = color.match(/#([A-Fa-f0-9]{6})/);
    if (hexMatch) {
      const hex = hexMatch[1];
      return [
        parseInt(hex.substr(0, 2), 16),
        parseInt(hex.substr(2, 2), 16),
        parseInt(hex.substr(4, 2), 16),
      ];
    }

    return null;
  }

  /**
   * Check if element has accessible name
   */
  private hasAccessibleName(element: HTMLElement): boolean {
    // Check for text content
    if (element.textContent?.trim()) return true;

    // Check for aria-label
    if (element.getAttribute('aria-label')) return true;

    // Check for aria-labelledby
    if (element.getAttribute('aria-labelledby')) return true;

    // Check for title attribute
    if (element.getAttribute('title')) return true;

    return false;
  }

  /**
   * Add an issue to the results
   */
  private addIssue(issue: AuditIssue): void {
    // Only include issues at or below target level
    const levels = ['A', 'AA', 'AAA'];
    const targetIndex = levels.indexOf(this.targetLevel);
    const issueIndex = levels.indexOf(issue.level);

    if (issueIndex <= targetIndex) {
      this.issues.push(issue);
    }
  }

  /**
   * Generate audit result report
   */
  private generateResult(): AuditResult {
    const errors = this.issues.filter((i) => i.severity === 'error');
    const warnings = this.issues.filter((i) => i.severity === 'warning');
    const info = this.issues.filter((i) => i.severity === 'info');

    const report = this.generateReport(errors, warnings, info);

    return {
      timestamp: Date.now(),
      level: this.targetLevel,
      totalIssues: this.issues.length,
      errors,
      warnings,
      info,
      compliance: {
        A: errors.length === 0,
        AA: errors.length === 0 && warnings.length === 0,
        AAA: this.issues.length === 0,
      },
      report,
    };
  }

  /**
   * Generate text report
   */
  private generateReport(
    errors: AuditIssue[],
    warnings: AuditIssue[],
    info: AuditIssue[]
  ): string {
    let report = '♿ WCAG 2.1 Accessibility Audit Report\n';
    report += '====================================\n\n';

    report += `Audit Level: WCAG 2.1 ${this.targetLevel}\n`;
    report += `Timestamp: ${new Date().toISOString()}\n\n`;

    report += 'Summary:\n';
    report += `  Errors: ${errors.length}\n`;
    report += `  Warnings: ${warnings.length}\n`;
    report += `  Info: ${info.length}\n`;
    report += `  Total Issues: ${errors.length + warnings.length + info.length}\n\n`;

    if (errors.length > 0) {
      report += '❌ ERRORS:\n';
      for (const error of errors) {
        report += `\n  [${error.criterion}] ${error.message}\n`;
        report += `  Suggestion: ${error.suggestion}\n`;
      }
      report += '\n';
    }

    if (warnings.length > 0) {
      report += '⚠️  WARNINGS:\n';
      for (const warning of warnings) {
        report += `\n  [${warning.criterion}] ${warning.message}\n`;
        report += `  Suggestion: ${warning.suggestion}\n`;
      }
      report += '\n';
    }

    if (info.length > 0) {
      report += 'ℹ️  INFORMATION:\n';
      for (const item of info) {
        report += `\n  [${item.criterion}] ${item.message}\n`;
        report += `  Suggestion: ${item.suggestion}\n`;
      }
      report += '\n';
    }

    const compliance = this.issues.length === 0;
    report += `\nCompliance Status: ${compliance ? '✅ PASS' : '❌ FAIL'}\n`;

    return report;
  }
}

// ============================================================================
// Global Instance
// ============================================================================

export const wcagAudit = new WCAGAudit();

export type { WCAGCriterion, AuditIssue, AuditResult, WCAGLevel };
