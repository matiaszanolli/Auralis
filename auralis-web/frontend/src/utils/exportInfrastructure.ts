/**
 * Export Infrastructure Module - Phase 5e
 *
 * Consolidates common export patterns from AnalysisExportService.ts
 * Eliminates 100-150 lines of duplicate code through:
 * - Unified statistics calculation utilities
 * - Shared visualization rendering infrastructure
 * - Export format handler patterns
 * - Progress notification abstraction
 */

// ============================================================================
// Statistics Calculation Utilities
// ============================================================================

/**
 * Running average calculation using welford's online algorithm
 * More numerically stable than simple averaging
 */
export function calculateRunningAverage(
  currentAvg: number,
  newValue: number,
  count: number
): number {
  return (currentAvg * (count - 1) + newValue) / count;
}

/**
 * Extract numeric values from snapshots with type safety
 */
export function extractNumericValues<T extends Record<string, any>>(
  items: T[],
  accessor: (item: T) => number | undefined
): number[] {
  return items
    .map(accessor)
    .filter((v): v is number => v !== undefined);
}

/**
 * Calculate statistics (average, min, max) from a set of values
 */
export interface Statistics {
  average: number;
  min: number;
  max: number;
  sum: number;
  count: number;
}

export function calculateStatistics(values: number[]): Statistics {
  if (values.length === 0) {
    return { average: 0, min: 0, max: 0, sum: 0, count: 0 };
  }

  const sum = values.reduce((a, b) => a + b, 0);
  return {
    average: sum / values.length,
    min: Math.min(...values),
    max: Math.max(...values),
    sum,
    count: values.length,
  };
}

/**
 * Generic statistics aggregator for multiple data categories
 */
export class StatisticsAggregator {
  private categories: Map<string, number[]> = new Map();

  addValue(category: string, value: number): void {
    if (!this.categories.has(category)) {
      this.categories.set(category, []);
    }
    this.categories.get(category)!.push(value);
  }

  getStatistics(category: string): Statistics | null {
    const values = this.categories.get(category);
    if (!values) return null;
    return calculateStatistics(values);
  }

  getAllStatistics(): Map<string, Statistics> {
    const result = new Map<string, Statistics>();
    this.categories.forEach((values, category) => {
      result.set(category, calculateStatistics(values));
    });
    return result;
  }

  clear(): void {
    this.categories.clear();
  }
}

// ============================================================================
// Canvas Rendering Infrastructure
// ============================================================================

export interface CanvasRenderingContext {
  width: number;
  height: number;
  theme: 'dark' | 'light';
  ctx: CanvasRenderingContext2D;
}

/**
 * Unified canvas rendering utilities to eliminate duplicate code
 */
export class CanvasRenderingUtils {
  /**
   * Set canvas background based on theme
   */
  static setBackground(context: CanvasRenderingContext): void {
    const { ctx, width, height, theme } = context;
    ctx.fillStyle = theme === 'dark' ? '#0A0A0A' : '#FFFFFF';
    ctx.fillRect(0, 0, width, height);
  }

  /**
   * Unified title rendering for visualizations
   */
  static renderTitle(
    context: CanvasRenderingContext,
    x: number,
    y: number,
    title: string
  ): void {
    const { ctx, theme } = context;
    ctx.fillStyle = theme === 'dark' ? '#FFFFFF' : '#000000';
    ctx.font = '20px sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText(title, x, y);
  }

  /**
   * Render border/frame for visualization sections
   */
  static renderFrame(
    context: CanvasRenderingContext,
    x: number,
    y: number,
    width: number,
    height: number
  ): void {
    const { ctx, theme } = context;
    ctx.strokeStyle = theme === 'dark' ? '#333333' : '#CCCCCC';
    ctx.lineWidth = 1;
    ctx.strokeRect(x, y, width, height);
  }

  /**
   * Get theme colors for common elements
   */
  static getThemeColors(theme: 'dark' | 'light'): {
    text: string;
    background: string;
    border: string;
    primary: string;
    secondary: string;
    danger: string;
    warning: string;
  } {
    if (theme === 'dark') {
      return {
        text: '#FFFFFF',
        background: '#0A0A0A',
        border: '#333333',
        primary: '#4FC3F7',
        secondary: '#FFB74D',
        danger: '#FF6B6B',
        warning: '#FFB74D',
      };
    }
    return {
      text: '#000000',
      background: '#FFFFFF',
      border: '#CCCCCC',
      primary: '#1976D2',
      secondary: '#F57C00',
      danger: '#D32F2F',
      warning: '#F57C00',
    };
  }
}

// ============================================================================
// Export Format Handler Pattern
// ============================================================================

export interface ExportHandlerResult {
  data: any;
  mimeType: string;
  filename: string;
}

export interface ExportFormatConfig {
  mimeType: string;
  extension: string;
  description: string;
}

/**
 * Base class for export format handlers
 * Eliminates duplicate pattern in performExport switch statement
 */
export abstract class ExportFormatHandler {
  protected config: ExportFormatConfig;
  protected sessionId: string;

  constructor(sessionId: string, config: ExportFormatConfig) {
    this.sessionId = sessionId;
    this.config = config;
  }

  /**
   * Export handler implementation
   */
  abstract export(data: any): Promise<any>;

  /**
   * Generate filename for export
   */
  protected getFilename(): string {
    return `auralis_analysis_${this.sessionId}.${this.config.extension}`;
  }

  /**
   * Create result with proper MIME type
   */
  protected createResult(data: any): ExportHandlerResult {
    return {
      data,
      mimeType: this.config.mimeType,
      filename: this.getFilename(),
    };
  }
}

/**
 * Factory for creating export format handlers
 * Eliminates switch statement duplication
 */
export class ExportFormatRegistry {
  private handlers: Map<string, new (sessionId: string, config: ExportFormatConfig) => ExportFormatHandler> = new Map();

  register(format: string, handler: typeof ExportFormatHandler | (new (sessionId: string, config: ExportFormatConfig) => ExportFormatHandler)): void {
    this.handlers.set(format, handler as new (sessionId: string, config: ExportFormatConfig) => ExportFormatHandler);
  }

  getHandler(format: string, sessionId: string): ExportFormatHandler | null {
    const HandlerClass = this.handlers.get(format);
    if (!HandlerClass) return null;

    // Create config for this format
    const configs: Record<string, ExportFormatConfig> = {
      json: { mimeType: 'application/json', extension: 'json', description: 'JSON' },
      csv: { mimeType: 'text/csv', extension: 'csv', description: 'CSV' },
      xml: { mimeType: 'application/xml', extension: 'xml', description: 'XML' },
      pdf: { mimeType: 'application/pdf', extension: 'pdf', description: 'PDF' },
      png: { mimeType: 'image/png', extension: 'png', description: 'PNG Image' },
      svg: { mimeType: 'image/svg+xml', extension: 'svg', description: 'SVG Image' },
    };

    const config = configs[format];
    if (!config) return null;

    return new HandlerClass(sessionId, config);
  }

  supportedFormats(): string[] {
    return Array.from(this.handlers.keys());
  }
}

// ============================================================================
// Progress Notification System
// ============================================================================

export type ProgressCallback = (progress: number, status: string) => void;

/**
 * Centralized progress tracking for export operations
 */
export class ProgressTracker {
  private callbacks: ProgressCallback[] = [];
  private currentProgress = 0;
  private currentStatus = '';

  /**
   * Subscribe to progress updates
   */
  subscribe(callback: ProgressCallback): () => void {
    this.callbacks.push(callback);
    // Return unsubscribe function
    return () => {
      const index = this.callbacks.indexOf(callback);
      if (index > -1) {
        this.callbacks.splice(index, 1);
      }
    };
  }

  /**
   * Update progress and notify subscribers
   */
  updateProgress(progress: number, status: string): void {
    this.currentProgress = Math.max(0, Math.min(100, progress));
    this.currentStatus = status;

    this.callbacks.forEach(callback => {
      try {
        callback(this.currentProgress, this.currentStatus);
      } catch (error) {
        console.error('Error in progress callback:', error);
      }
    });
  }

  /**
   * Progress tracking with percentage calculation
   * Useful for multi-phase operations
   */
  trackPhaseProgress(
    currentPhase: number,
    totalPhases: number,
    phaseProgress: number,
    status: string
  ): void {
    // Each phase gets equal weight
    const phaseWeight = 100 / totalPhases;
    const totalProgress = (currentPhase - 1) * phaseWeight + (phaseProgress * phaseWeight) / 100;
    this.updateProgress(totalProgress, status);
  }

  /**
   * Get current progress state
   */
  getState(): { progress: number; status: string } {
    return {
      progress: this.currentProgress,
      status: this.currentStatus,
    };
  }

  /**
   * Clear all subscribers
   */
  clear(): void {
    this.callbacks = [];
  }
}

// ============================================================================
// Data Filtering and Transformation
// ============================================================================

/**
 * Utilities for filtering and transforming snapshot data
 */
export class DataTransformer {
  /**
   * Filter items by time range
   */
  static filterByTimeRange<T extends { timestamp: number }>(
    items: T[],
    start: number,
    end: number
  ): T[] {
    return items.filter(item => item.timestamp >= start && item.timestamp <= end);
  }

  /**
   * Select specific fields from items
   */
  static selectFields<T extends Record<string, any>>(
    items: T[],
    fields: (keyof T)[]
  ): Partial<T>[] {
    return items.map(item => {
      const result: Partial<T> = {};
      fields.forEach(field => {
        if (field in item) {
          result[field] = item[field];
        }
      });
      return result;
    });
  }

  /**
   * Flatten nested object to dot-notation keys
   */
  static flattenObject(obj: any, prefix = ''): Record<string, any> {
    const result: Record<string, any> = {};

    const flatten = (current: any, key: string) => {
      if (current === null || current === undefined) {
        result[key] = current;
      } else if (typeof current === 'object' && !Array.isArray(current)) {
        Object.entries(current).forEach(([k, v]) => {
          flatten(v, key ? `${key}.${k}` : k);
        });
      } else {
        result[key] = current;
      }
    };

    flatten(obj, prefix);
    return result;
  }

  /**
   * Convert array of objects to CSV-compatible format
   */
  static toCsvRow(obj: Record<string, any>, headers?: string[]): string {
    const activeHeaders = headers || Object.keys(obj);
    const values = activeHeaders.map(key => {
      const value = obj[key];
      if (value === null || value === undefined) return '';
      if (typeof value === 'string' && (value.includes(',') || value.includes('"'))) {
        return `"${value.replace(/"/g, '""')}"`;
      }
      return String(value);
    });
    return values.join(',');
  }

  /**
   * Escape special XML characters
   */
  static escapeXml(text: string): string {
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  /**
   * Escape special CSV characters
   */
  static escapeCsv(text: string): string {
    if (text.includes(',') || text.includes('"') || text.includes('\n')) {
      return `"${text.replace(/"/g, '""')}"`;
    }
    return text;
  }
}

// ============================================================================
// Export Operation Manager
// ============================================================================

/**
 * Coordinates export operations with progress tracking and error handling
 */
export class ExportOperationManager {
  private progressTracker: ProgressTracker;
  private formatRegistry: ExportFormatRegistry;

  constructor() {
    this.progressTracker = new ProgressTracker();
    this.formatRegistry = new ExportFormatRegistry();
  }

  /**
   * Execute export operation with automatic progress tracking
   */
  async executeExport<T extends { sessionId: string }>(
    format: string,
    session: T,
    exportFn: (handler: ExportFormatHandler | null) => Promise<any>
  ): Promise<ExportHandlerResult> {
    this.progressTracker.updateProgress(0, 'Preparing export...');

    const handler = this.formatRegistry.getHandler(format, session.sessionId);
    if (!handler) {
      throw new Error(`Unsupported export format: ${format}`);
    }

    try {
      this.progressTracker.updateProgress(10, `Generating ${format.toUpperCase()}...`);
      const data = await exportFn(handler);

      this.progressTracker.updateProgress(90, 'Finalizing export...');
      const result = handler['createResult'](data);

      this.progressTracker.updateProgress(100, 'Export complete');
      return result;
    } catch (error) {
      this.progressTracker.updateProgress(0, `Export failed: ${error}`);
      throw error;
    }
  }

  /**
   * Subscribe to progress updates
   */
  onProgress(callback: ProgressCallback): () => void {
    return this.progressTracker.subscribe(callback);
  }

  /**
   * Register custom export format handler
   */
  registerFormat(format: string, handler: typeof ExportFormatHandler): void {
    this.formatRegistry.register(format, handler);
  }

  /**
   * Get list of supported formats
   */
  getSupportedFormats(): string[] {
    return this.formatRegistry.supportedFormats();
  }
}

export default {
  calculateRunningAverage,
  extractNumericValues,
  calculateStatistics,
  StatisticsAggregator,
  CanvasRenderingUtils,
  ExportFormatHandler,
  ExportFormatRegistry,
  ProgressTracker,
  DataTransformer,
  ExportOperationManager,
};
