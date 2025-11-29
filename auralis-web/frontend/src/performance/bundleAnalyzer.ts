/**
 * Bundle Size Analysis Tools
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Tools for analyzing and tracking bundle size metrics.
 * Helps identify large dependencies and code splitting opportunities.
 *
 * Features:
 * - Module size tracking
 * - Dependency analysis
 * - Code splitting recommendations
 * - Historical size comparisons
 * - Size budget enforcement
 *
 * Phase C.4b: Performance Optimization
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3, see LICENSE for more details
 */

// ============================================================================
// Types
// ============================================================================

interface ModuleMetrics {
  name: string;
  size: number;
  gzipSize: number;
  isDuplicate: boolean;
  dependents: string[];
  dependencies: string[];
  isChunk: boolean;
  chunkName?: string;
}

interface BundleMetrics {
  totalSize: number;
  totalGzipSize: number;
  moduleCount: number;
  chunkCount: number;
  modules: ModuleMetrics[];
  chunks: Map<string, number>;
  timestamp: number;
}

interface SizeBudget {
  total?: number; // Total bundle size limit in KB
  gzip?: number; // Gzipped bundle limit in KB
  chunk?: number; // Individual chunk limit in KB
  module?: number; // Individual module limit in KB
}

interface SizeAnalysis {
  metrics: BundleMetrics;
  warnings: string[];
  violations: string[];
  opportunities: string[];
  recommendations: string[];
}

// ============================================================================
// Bundle Analyzer Class
// ============================================================================

class BundleAnalyzer {
  private history: BundleMetrics[] = [];
  private budgets: SizeBudget = {};
  private maxHistorySize: number = 100;

  /**
   * Record bundle metrics
   */
  recordMetrics(
    modules: ModuleMetrics[],
    chunks: Map<string, number> = new Map()
  ): void {
    const totalSize = modules.reduce((sum, m) => sum + m.size, 0);
    const totalGzipSize = modules.reduce((sum, m) => sum + m.gzipSize, 0);

    const metrics: BundleMetrics = {
      totalSize,
      totalGzipSize,
      moduleCount: modules.length,
      chunkCount: chunks.size,
      modules,
      chunks,
      timestamp: Date.now(),
    };

    this.history.push(metrics);

    // Keep only recent history
    if (this.history.length > this.maxHistorySize) {
      this.history.shift();
    }
  }

  /**
   * Set size budgets
   */
  setSizeBudget(budget: SizeBudget): void {
    this.budgets = budget;
  }

  /**
   * Get current bundle metrics
   */
  getCurrentMetrics(): BundleMetrics | null {
    return this.history.length > 0 ? this.history[this.history.length - 1] : null;
  }

  /**
   * Get bundle history
   */
  getHistory(): BundleMetrics[] {
    return [...this.history];
  }

  /**
   * Get size change from previous measurement
   */
  getSizeChange(): { size: number; gzip: number; percent: number } | null {
    if (this.history.length < 2) return null;

    const current = this.history[this.history.length - 1];
    const previous = this.history[this.history.length - 2];

    return {
      size: current.totalSize - previous.totalSize,
      gzip: current.totalGzipSize - previous.totalGzipSize,
      percent: ((current.totalSize - previous.totalSize) / previous.totalSize) * 100,
    };
  }

  /**
   * Find largest modules
   */
  getLargestModules(limit: number = 10): ModuleMetrics[] {
    const metrics = this.getCurrentMetrics();
    if (!metrics) return [];

    return [...metrics.modules]
      .sort((a, b) => b.gzipSize - a.gzipSize)
      .slice(0, limit);
  }

  /**
   * Find duplicate modules
   */
  getDuplicateModules(): ModuleMetrics[] {
    const metrics = this.getCurrentMetrics();
    if (!metrics) return [];

    return metrics.modules.filter((m) => m.isDuplicate);
  }

  /**
   * Analyze bundle against budgets
   */
  analyzeBundle(): SizeAnalysis {
    const metrics = this.getCurrentMetrics();
    if (!metrics) {
      return {
        metrics: {
          totalSize: 0,
          totalGzipSize: 0,
          moduleCount: 0,
          chunkCount: 0,
          modules: [],
          chunks: new Map(),
          timestamp: 0,
        },
        warnings: [],
        violations: [],
        opportunities: [],
        recommendations: [],
      };
    }

    const warnings: string[] = [];
    const violations: string[] = [];
    const opportunities: string[] = [];
    const recommendations: string[] = [];

    // Check total size budget
    if (
      this.budgets.total &&
      metrics.totalSize > this.budgets.total * 1024
    ) {
      violations.push(
        `Total bundle size ${(metrics.totalSize / 1024).toFixed(1)}KB exceeds budget of ${this.budgets.total}KB`
      );
    }

    // Check gzip budget
    if (
      this.budgets.gzip &&
      metrics.totalGzipSize > this.budgets.gzip * 1024
    ) {
      violations.push(
        `Gzipped bundle size ${(metrics.totalGzipSize / 1024).toFixed(1)}KB exceeds budget of ${this.budgets.gzip}KB`
      );
    }

    // Check individual chunk budgets
    for (const [chunkName, size] of metrics.chunks) {
      if (this.budgets.chunk && size > this.budgets.chunk * 1024) {
        violations.push(
          `Chunk "${chunkName}" size ${(size / 1024).toFixed(1)}KB exceeds budget of ${this.budgets.chunk}KB`
        );
      }
    }

    // Check individual module budgets
    for (const module of metrics.modules) {
      if (this.budgets.module && module.gzipSize > this.budgets.module * 1024) {
        warnings.push(
          `Module "${module.name}" size ${(module.gzipSize / 1024).toFixed(
            1
          )}KB exceeds budget of ${this.budgets.module}KB`
        );
      }
    }

    // Find optimization opportunities
    const largestModules = this.getLargestModules(5);
    for (const module of largestModules) {
      const sizeKB = (module.gzipSize / 1024).toFixed(1);
      if (module.dependents.length === 1) {
        opportunities.push(
          `Consider lazy-loading "${module.name}" (${sizeKB}KB) - only used by "${module.dependents[0]}"`
        );
      } else if (module.dependents.length > 3) {
        opportunities.push(
          `Consider code-splitting "${module.name}" (${sizeKB}KB) - used by ${module.dependents.length} components`
        );
      }
    }

    // Check for duplicates
    const duplicates = this.getDuplicateModules();
    if (duplicates.length > 0) {
      const totalDupSize = (
        duplicates.reduce((sum, m) => sum + m.gzipSize, 0) / 1024
      ).toFixed(1);
      opportunities.push(
        `Found ${duplicates.length} duplicate modules totaling ${totalDupSize}KB - consider deduplication`
      );
    }

    // Generate recommendations
    if (violations.length > 0) {
      recommendations.push(
        'Review bundle budgets - implement code splitting for large chunks'
      );
      recommendations.push('Analyze dependencies - remove unused packages');
      recommendations.push('Enable tree-shaking in build configuration');
    }

    if (opportunities.length > 0) {
      recommendations.push(
        'Review opportunities for lazy loading and code splitting'
      );
    }

    // Check size trends
    const sizeChange = this.getSizeChange();
    if (sizeChange && sizeChange.percent > 5) {
      warnings.push(
        `Bundle size increased by ${sizeChange.percent.toFixed(1)}% since last build`
      );
      recommendations.push('Review recent dependency additions');
    }

    return {
      metrics,
      warnings,
      violations,
      opportunities,
      recommendations,
    };
  }

  /**
   * Generate analysis report
   */
  generateReport(): string {
    const analysis = this.analyzeBundle();
    const metrics = analysis.metrics;

    let report = '📦 Bundle Analysis Report\n';
    report += '========================\n\n';

    report += 'Bundle Size:\n';
    report += `  Total: ${(metrics.totalSize / 1024).toFixed(1)}KB\n`;
    report += `  Gzipped: ${(metrics.totalGzipSize / 1024).toFixed(1)}KB\n`;
    report += `  Modules: ${metrics.moduleCount}\n`;
    report += `  Chunks: ${metrics.chunkCount}\n\n`;

    const largestModules = this.getLargestModules(5);
    if (largestModules.length > 0) {
      report += 'Top 5 Largest Modules:\n';
      for (const module of largestModules) {
        report += `  - ${module.name}: ${(module.gzipSize / 1024).toFixed(1)}KB\n`;
      }
      report += '\n';
    }

    if (analysis.violations.length > 0) {
      report += '❌ Budget Violations:\n';
      for (const violation of analysis.violations) {
        report += `  - ${violation}\n`;
      }
      report += '\n';
    }

    if (analysis.warnings.length > 0) {
      report += '⚠️  Warnings:\n';
      for (const warning of analysis.warnings) {
        report += `  - ${warning}\n`;
      }
      report += '\n';
    }

    if (analysis.opportunities.length > 0) {
      report += '💡 Optimization Opportunities:\n';
      for (const opportunity of analysis.opportunities) {
        report += `  - ${opportunity}\n`;
      }
      report += '\n';
    }

    if (analysis.recommendations.length > 0) {
      report += '✅ Recommendations:\n';
      for (const recommendation of analysis.recommendations) {
        report += `  - ${recommendation}\n`;
      }
    }

    return report;
  }

  /**
   * Reset analysis
   */
  reset(): void {
    this.history = [];
  }
}

// ============================================================================
// Global Instance
// ============================================================================

export const bundleAnalyzer = new BundleAnalyzer();

// ============================================================================
// Vite Plugin Integration
// ============================================================================

/**
 * Extract module sizes from Vite build output
 * This would be used with a Vite plugin in the build configuration
 */
export function extractModuleSizes(rollupOutput: any[]): ModuleMetrics[] {
  const modules: ModuleMetrics[] = [];

  for (const output of rollupOutput) {
    if (output.type === 'asset') {
      modules.push({
        name: output.fileName,
        size: output.source.length,
        gzipSize: output.source.length, // Would need actual gzip compression
        isDuplicate: false,
        dependents: [],
        dependencies: [],
        isChunk: false,
      });
    } else if (output.type === 'chunk') {
      modules.push({
        name: output.fileName,
        size: output.code.length,
        gzipSize: output.code.length,
        isDuplicate: false,
        dependents: Object.keys(output.modules || {}),
        dependencies: [],
        isChunk: true,
        chunkName: output.name,
      });
    }
  }

  return modules;
}

// ============================================================================
// Exports
// ============================================================================

export { BundleAnalyzer, bundleAnalyzer };
export type {
  ModuleMetrics,
  BundleMetrics,
  SizeBudget,
  SizeAnalysis,
};
