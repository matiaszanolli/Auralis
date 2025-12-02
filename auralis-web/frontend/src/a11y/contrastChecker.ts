/**
 * Color Contrast Checking Utilities
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tools for checking and ensuring WCAG color contrast requirements.
 * Validates color combinations meet accessibility standards.
 *
 * WCAG Standards:
 * - AA: 4.5:1 for normal text, 3:1 for large text
 * - AAA: 7:1 for normal text, 4.5:1 for large text
 *
 * Features:
 * - Color contrast calculation
 * - WCAG AA/AAA compliance checking
 * - Contrast audit tools
 * - Color suggestion for improvements
 *
 * Phase C.4c: Accessibility & A11y
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

// ============================================================================
// Types
// ============================================================================

interface RGB {
  r: number;
  g: number;
  b: number;
}

interface ContrastCheck {
  foreground: string;
  background: string;
  ratio: number;
  aa: boolean;
  aaa: boolean;
  largeTextAA: boolean;
  largeTextAAA: boolean;
}

interface ColorIssue {
  element: HTMLElement;
  foreground: string;
  background: string;
  ratio: number;
  requiredRatio: number;
  suggestion?: string;
}

// ============================================================================
// Color Parsing & Conversion
// ============================================================================

/**
 * Parse color string to RGB
 */
export function parseColor(color: string): RGB | null {
  // Remove whitespace
  color = color.trim();

  // Handle named colors
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 1;
  const ctx = canvas.getContext('2d');
  if (!ctx) return null;

  ctx.fillStyle = color;
  ctx.fillRect(0, 0, 1, 1);
  const imageData = ctx.getImageData(0, 0, 1, 1);
  const [r, g, b] = imageData.data;

  return { r, g, b };
}

/**
 * Convert RGB to hex
 */
export function rgbToHex(rgb: RGB): string {
  const toHex = (n: number) => {
    const hex = n.toString(16);
    return hex.length === 1 ? '0' + hex : hex;
  };

  return `#${toHex(rgb.r)}${toHex(rgb.g)}${toHex(rgb.b)}`;
}

/**
 * Parse hex color to RGB
 */
export function hexToRgb(hex: string): RGB | null {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result
    ? {
        r: parseInt(result[1], 16),
        g: parseInt(result[2], 16),
        b: parseInt(result[3], 16),
      }
    : null;
}

/**
 * Invert color (for suggestions)
 */
export function invertColor(color: string): string {
  const rgb = parseColor(color);
  if (!rgb) return color;

  return rgbToHex({
    r: 255 - rgb.r,
    g: 255 - rgb.g,
    b: 255 - rgb.b,
  });
}

// ============================================================================
// Contrast Calculation
// ============================================================================

/**
 * Calculate relative luminance
 */
export function getRelativeLuminance(rgb: RGB): number {
  const [r, g, b] = [rgb.r, rgb.g, rgb.b].map((c) => {
    const sRGB = c / 255;
    return sRGB <= 0.03928 ? sRGB / 12.92 : Math.pow((sRGB + 0.055) / 1.055, 2.4);
  });

  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/**
 * Calculate contrast ratio
 */
export function getContrastRatio(color1: string, color2: string): number {
  const rgb1 = parseColor(color1);
  const rgb2 = parseColor(color2);

  if (!rgb1 || !rgb2) return 0;

  const lum1 = getRelativeLuminance(rgb1);
  const lum2 = getRelativeLuminance(rgb2);

  const lighter = Math.max(lum1, lum2);
  const darker = Math.min(lum1, lum2);

  return (lighter + 0.05) / (darker + 0.05);
}

/**
 * Check WCAG compliance
 */
export function checkContrast(
  foreground: string,
  background: string
): ContrastCheck {
  const ratio = getContrastRatio(foreground, background);

  return {
    foreground,
    background,
    ratio: Math.round(ratio * 100) / 100,
    aa: ratio >= 4.5,
    aaa: ratio >= 7,
    largeTextAA: ratio >= 3,
    largeTextAAA: ratio >= 4.5,
  };
}

// ============================================================================
// Contrast Audit
// ============================================================================

class ContrastAuditor {
  /**
   * Audit all colors in a container
   */
  auditContainer(container: HTMLElement): ColorIssue[] {
    const issues: ColorIssue[] = [];
    const elements = container.querySelectorAll('*');

    for (const element of elements) {
      const text = element.textContent?.trim();
      if (!text || text.length === 0) continue;

      const style = window.getComputedStyle(element);
      const foreground = style.color;
      const background = style.backgroundColor;

      if (!foreground || !background) continue;

      const check = checkContrast(foreground, background);

      if (!check.aa) {
        issues.push({
          element: element as HTMLElement,
          foreground,
          background,
          ratio: check.ratio,
          requiredRatio: 4.5,
          suggestion: this.suggestColor(foreground, background),
        });
      }
    }

    return issues;
  }

  /**
   * Suggest improved color combination
   */
  private suggestColor(foreground: string, background: string): string {
    const fgRgb = parseColor(foreground);
    const bgRgb = parseColor(background);

    if (!fgRgb || !bgRgb) return 'Unable to determine suggestion';

    // Try darkening/lightening foreground
    const darkerFg = this.adjustBrightness(fgRgb, -20);
    const lighterFg = this.adjustBrightness(fgRgb, 20);

    const darkerRatio = getContrastRatio(
      rgbToHex(darkerFg),
      background
    );
    const lighterRatio = getContrastRatio(
      rgbToHex(lighterFg),
      background
    );

    if (darkerRatio >= 4.5) {
      return `Try darker ${rgbToHex(darkerFg)} (ratio: ${darkerRatio.toFixed(2)}:1)`;
    }

    if (lighterRatio >= 4.5) {
      return `Try lighter ${rgbToHex(lighterFg)} (ratio: ${lighterRatio.toFixed(2)}:1)`;
    }

    return 'Consider adjusting colors for better contrast';
  }

  /**
   * Adjust brightness of color
   */
  private adjustBrightness(rgb: RGB, percent: number): RGB {
    const factor = 1 + percent / 100;

    return {
      r: Math.min(255, Math.max(0, Math.round(rgb.r * factor))),
      g: Math.min(255, Math.max(0, Math.round(rgb.g * factor))),
      b: Math.min(255, Math.max(0, Math.round(rgb.b * factor))),
    };
  }

  /**
   * Generate audit report
   */
  generateReport(container: HTMLElement): string {
    const issues = this.auditContainer(container);

    let report = '🎨 Color Contrast Audit Report\n';
    report += '==============================\n\n';

    if (issues.length === 0) {
      report += '✅ All colors meet WCAG AA contrast requirements\n';
      return report;
    }

    report += `Found ${issues.length} contrast issues:\n\n`;

    for (let i = 0; i < Math.min(issues.length, 10); i++) {
      const issue = issues[i];
      report += `${i + 1}. Contrast ratio: ${issue.ratio}:1 (need 4.5:1)\n`;
      report += `   Foreground: ${issue.foreground}\n`;
      report += `   Background: ${issue.background}\n`;
      if (issue.suggestion) {
        report += `   ${issue.suggestion}\n`;
      }
      report += '\n';
    }

    if (issues.length > 10) {
      report += `...and ${issues.length - 10} more issues\n`;
    }

    return report;
  }
}

export const contrastAuditor = new ContrastAuditor();

// ============================================================================
// Pre-defined Color Combinations
// ============================================================================

/**
 * Accessible color palette
 */
export const accessiblePalette = {
  // Dark text on light backgrounds
  darkText: '#1a1a1a',
  lightBg: '#ffffff',

  // Light text on dark backgrounds
  lightText: '#ffffff',
  darkBg: '#1a1a1a',

  // Accent colors with good contrast
  primary: '#0066cc',
  success: '#00a050',
  warning: '#ff8c00',
  error: '#e81b23',
  info: '#0066cc',

  // Hover states
  primaryHover: '#0052a3',
  successHover: '#008040',
  warningHover: '#cc7000',
  errorHover: '#cc1519',

  // Disabled states
  disabled: '#999999',
  disabledBg: '#f5f5f5',
};

export type { RGB, ContrastCheck, ColorIssue };
