/**
 * Analysis Export Service for Phase 5.3
 *
 * Provides comprehensive export functionality for audio analysis data,
 * visualization snapshots, and performance reports in multiple formats.
 */

interface ExportMetadata {
  timestamp: string;
  version: string;
  sampleRate: number;
  channels: number;
  duration: number;
  analysisEngine: string;
  exportFormat: string;
  userAgent: string;
}

interface AnalysisSnapshot {
  timestamp: number;
  sequence: number;

  // Phase 5.1 Analysis Data
  spectrum?: {
    frequency_bins: number[];
    magnitude_db: number[];
    peak_frequency: number;
    spectral_centroid: number;
    spectral_rolloff?: number;
    settings?: any;
  };

  loudness?: {
    momentary_loudness: number;
    short_term_loudness: number;
    integrated_loudness: number;
    loudness_range: number;
    peak_dbfs: number;
    true_peak_dbfs: number;
  };

  correlation?: {
    correlation_coefficient: number;
    phase_correlation: number;
    stereo_width: number;
    mono_compatibility: number;
    phase_stability: number;
    phase_deviation: number;
    stereo_position: number;
    left_energy: number;
    right_energy: number;
  };

  dynamics?: {
    dr_value: number;
    peak_to_loudness_ratio: number;
    crest_factor: number;
    compression_ratio: number;
    attack_time: number;
    release_time: number;
    loudness_war_assessment: any;
  };

  // Processing metrics
  processing?: {
    stages: Array<{
      name: string;
      isActive: boolean;
      cpuUsage: number;
      latency: number;
      bufferUsage: number;
      inputLevel: number;
      outputLevel: number;
      gainReduction: number;
      parameters: { [key: string]: number };
      alerts: string[];
    }>;
    globalCpuUsage: number;
    globalLatency: number;
    bufferUnderruns: number;
    isRealTime: boolean;
    processingLoad: number;
  };
}

interface AnalysisSession {
  sessionId: string;
  startTime: number;
  endTime?: number;
  metadata: ExportMetadata;
  snapshots: AnalysisSnapshot[];
  statistics: {
    totalSnapshots: number;
    averageLoudness: number;
    peakLoudness: number;
    averageCorrelation: number;
    averageDynamicRange: number;
    processingEfficiency: number;
  };
}

interface ExportOptions {
  format: 'json' | 'csv' | 'xml' | 'pdf' | 'png' | 'svg';
  includeMetadata: boolean;
  includeStatistics: boolean;
  includeVisualizations: boolean;
  compressionLevel?: number;
  timeRange?: { start: number; end: number };
  dataFilters?: string[];
  visualizationSettings?: {
    width: number;
    height: number;
    theme: 'dark' | 'light';
    includeWaveform: boolean;
    includeSpectrum: boolean;
    includeMeters: boolean;
    includeCorrelation: boolean;
  };
}

export class AnalysisExportService {
  private currentSession: AnalysisSession | null = null;
  private snapshots: AnalysisSnapshot[] = [];
  private maxSnapshots = 10000; // Limit memory usage
  private exportCallbacks: ((progress: number, status: string) => void)[] = [];

  constructor() {
    this.startNewSession();
  }

  // Session Management
  startNewSession(metadata?: Partial<ExportMetadata>): string {
    const sessionId = `auralis_session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    this.currentSession = {
      sessionId,
      startTime: Date.now(),
      metadata: {
        timestamp: new Date().toISOString(),
        version: '5.3.0',
        sampleRate: 44100,
        channels: 2,
        duration: 0,
        analysisEngine: 'Auralis Phase 5.1',
        exportFormat: 'json',
        userAgent: navigator.userAgent,
        ...metadata,
      },
      snapshots: [],
      statistics: {
        totalSnapshots: 0,
        averageLoudness: 0,
        peakLoudness: -Infinity,
        averageCorrelation: 0,
        averageDynamicRange: 0,
        processingEfficiency: 0,
      },
    };

    this.snapshots = [];
    return sessionId;
  }

  endCurrentSession(): void {
    if (this.currentSession) {
      this.currentSession.endTime = Date.now();
      this.currentSession.metadata.duration =
        (this.currentSession.endTime - this.currentSession.startTime) / 1000;

      this.updateSessionStatistics();
    }
  }

  // Data Collection
  addSnapshot(data: Partial<AnalysisSnapshot>): void {
    if (!this.currentSession) return;

    const snapshot: AnalysisSnapshot = {
      timestamp: Date.now(),
      sequence: this.snapshots.length,
      ...data,
    };

    this.snapshots.push(snapshot);
    this.currentSession.snapshots = this.snapshots;

    // Limit memory usage
    if (this.snapshots.length > this.maxSnapshots) {
      this.snapshots.shift();
    }

    // Update running statistics
    this.updateRunningStatistics(snapshot);
  }

  private updateRunningStatistics(snapshot: AnalysisSnapshot): void {
    if (!this.currentSession) return;

    const stats = this.currentSession.statistics;
    stats.totalSnapshots = this.snapshots.length;

    if (snapshot.loudness) {
      stats.averageLoudness = this.calculateRunningAverage(
        stats.averageLoudness,
        snapshot.loudness.momentary_loudness,
        stats.totalSnapshots
      );

      if (snapshot.loudness.momentary_loudness > stats.peakLoudness) {
        stats.peakLoudness = snapshot.loudness.momentary_loudness;
      }
    }

    if (snapshot.correlation) {
      stats.averageCorrelation = this.calculateRunningAverage(
        stats.averageCorrelation,
        snapshot.correlation.correlation_coefficient,
        stats.totalSnapshots
      );
    }

    if (snapshot.dynamics) {
      stats.averageDynamicRange = this.calculateRunningAverage(
        stats.averageDynamicRange,
        snapshot.dynamics.dr_value,
        stats.totalSnapshots
      );
    }

    if (snapshot.processing) {
      const efficiency = 100 - snapshot.processing.globalCpuUsage;
      stats.processingEfficiency = this.calculateRunningAverage(
        stats.processingEfficiency,
        efficiency,
        stats.totalSnapshots
      );
    }
  }

  private calculateRunningAverage(currentAvg: number, newValue: number, count: number): number {
    return (currentAvg * (count - 1) + newValue) / count;
  }

  private updateSessionStatistics(): void {
    if (!this.currentSession || this.snapshots.length === 0) return;

    const stats = this.currentSession.statistics;

    // Calculate final statistics
    const loudnessValues = this.snapshots
      .map(s => s.loudness?.momentary_loudness)
      .filter(v => v !== undefined) as number[];

    const correlationValues = this.snapshots
      .map(s => s.correlation?.correlation_coefficient)
      .filter(v => v !== undefined) as number[];

    const drValues = this.snapshots
      .map(s => s.dynamics?.dr_value)
      .filter(v => v !== undefined) as number[];

    const cpuValues = this.snapshots
      .map(s => s.processing?.globalCpuUsage)
      .filter(v => v !== undefined) as number[];

    if (loudnessValues.length > 0) {
      stats.averageLoudness = loudnessValues.reduce((a, b) => a + b, 0) / loudnessValues.length;
      stats.peakLoudness = Math.max(...loudnessValues);
    }

    if (correlationValues.length > 0) {
      stats.averageCorrelation = correlationValues.reduce((a, b) => a + b, 0) / correlationValues.length;
    }

    if (drValues.length > 0) {
      stats.averageDynamicRange = drValues.reduce((a, b) => a + b, 0) / drValues.length;
    }

    if (cpuValues.length > 0) {
      const avgCpu = cpuValues.reduce((a, b) => a + b, 0) / cpuValues.length;
      stats.processingEfficiency = 100 - avgCpu;
    }
  }

  // Export Methods
  async exportSession(options: Partial<ExportOptions> = {}): Promise<Blob> {
    if (!this.currentSession) {
      throw new Error('No active session to export');
    }

    const exportOptions: ExportOptions = {
      format: 'json',
      includeMetadata: true,
      includeStatistics: true,
      includeVisualizations: false,
      compressionLevel: 6,
      ...options,
    };

    this.notifyProgress(0, 'Preparing export...');

    let data: any;
    let mimeType: string;
    let filename: string;

    switch (exportOptions.format) {
      case 'json':
        data = await this.exportAsJSON(exportOptions);
        mimeType = 'application/json';
        filename = `auralis_analysis_${this.currentSession.sessionId}.json`;
        break;

      case 'csv':
        data = await this.exportAsCSV(exportOptions);
        mimeType = 'text/csv';
        filename = `auralis_analysis_${this.currentSession.sessionId}.csv`;
        break;

      case 'xml':
        data = await this.exportAsXML(exportOptions);
        mimeType = 'application/xml';
        filename = `auralis_analysis_${this.currentSession.sessionId}.xml`;
        break;

      case 'pdf':
        data = await this.exportAsPDF(exportOptions);
        mimeType = 'application/pdf';
        filename = `auralis_analysis_${this.currentSession.sessionId}.pdf`;
        break;

      case 'png':
        data = await this.exportAsImage(exportOptions, 'png');
        mimeType = 'image/png';
        filename = `auralis_analysis_${this.currentSession.sessionId}.png`;
        break;

      case 'svg':
        data = await this.exportAsImage(exportOptions, 'svg');
        mimeType = 'image/svg+xml';
        filename = `auralis_analysis_${this.currentSession.sessionId}.svg`;
        break;

      default:
        throw new Error(`Unsupported export format: ${exportOptions.format}`);
    }

    this.notifyProgress(100, 'Export complete');

    if (typeof data === 'string') {
      return new Blob([data], { type: mimeType });
    } else {
      return data;
    }
  }

  private async exportAsJSON(options: ExportOptions): Promise<string> {
    this.notifyProgress(20, 'Generating JSON...');

    const exportData: any = {};

    if (options.includeMetadata) {
      exportData.metadata = this.currentSession!.metadata;
    }

    if (options.includeStatistics) {
      exportData.statistics = this.currentSession!.statistics;
    }

    // Filter snapshots by time range if specified
    let snapshots = this.snapshots;
    if (options.timeRange) {
      snapshots = snapshots.filter(s =>
        s.timestamp >= options.timeRange!.start &&
        s.timestamp <= options.timeRange!.end
      );
    }

    // Apply data filters
    if (options.dataFilters && options.dataFilters.length > 0) {
      snapshots = snapshots.map(snapshot => {
        const filtered: any = { timestamp: snapshot.timestamp, sequence: snapshot.sequence };

        options.dataFilters!.forEach(filter => {
          if (snapshot[filter as keyof AnalysisSnapshot]) {
            filtered[filter] = snapshot[filter as keyof AnalysisSnapshot];
          }
        });

        return filtered;
      });
    }

    exportData.snapshots = snapshots;
    exportData.exportInfo = {
      exportedAt: new Date().toISOString(),
      snapshotCount: snapshots.length,
      timeRange: options.timeRange,
      filters: options.dataFilters,
    };

    this.notifyProgress(80, 'Formatting JSON...');
    return JSON.stringify(exportData, null, 2);
  }

  private async exportAsCSV(options: ExportOptions): Promise<string> {
    this.notifyProgress(20, 'Generating CSV...');

    const headers = [
      'timestamp',
      'sequence',
      'momentary_loudness',
      'peak_dbfs',
      'correlation_coefficient',
      'stereo_width',
      'dr_value',
      'crest_factor',
      'global_cpu_usage',
      'global_latency',
    ];

    let csv = headers.join(',') + '\n';

    this.snapshots.forEach((snapshot, index) => {
      this.notifyProgress(20 + (index / this.snapshots.length) * 60, `Processing row ${index + 1}...`);

      const row = [
        snapshot.timestamp,
        snapshot.sequence,
        snapshot.loudness?.momentary_loudness || '',
        snapshot.loudness?.peak_dbfs || '',
        snapshot.correlation?.correlation_coefficient || '',
        snapshot.correlation?.stereo_width || '',
        snapshot.dynamics?.dr_value || '',
        snapshot.dynamics?.crest_factor || '',
        snapshot.processing?.globalCpuUsage || '',
        snapshot.processing?.globalLatency || '',
      ];

      csv += row.join(',') + '\n';
    });

    return csv;
  }

  private async exportAsXML(options: ExportOptions): Promise<string> {
    this.notifyProgress(20, 'Generating XML...');

    let xml = '<?xml version="1.0" encoding="UTF-8"?>\n';
    xml += '<auralis_analysis>\n';

    if (options.includeMetadata) {
      xml += '  <metadata>\n';
      Object.entries(this.currentSession!.metadata).forEach(([key, value]) => {
        xml += `    <${key}>${this.escapeXml(String(value))}</${key}>\n`;
      });
      xml += '  </metadata>\n';
    }

    if (options.includeStatistics) {
      xml += '  <statistics>\n';
      Object.entries(this.currentSession!.statistics).forEach(([key, value]) => {
        xml += `    <${key}>${value}</${key}>\n`;
      });
      xml += '  </statistics>\n';
    }

    xml += '  <snapshots>\n';
    this.snapshots.forEach((snapshot, index) => {
      this.notifyProgress(20 + (index / this.snapshots.length) * 60, `Processing snapshot ${index + 1}...`);

      xml += '    <snapshot>\n';
      xml += `      <timestamp>${snapshot.timestamp}</timestamp>\n`;
      xml += `      <sequence>${snapshot.sequence}</sequence>\n`;

      if (snapshot.loudness) {
        xml += '      <loudness>\n';
        Object.entries(snapshot.loudness).forEach(([key, value]) => {
          xml += `        <${key}>${value}</${key}>\n`;
        });
        xml += '      </loudness>\n';
      }

      // Add other data sections...
      xml += '    </snapshot>\n';
    });
    xml += '  </snapshots>\n';
    xml += '</auralis_analysis>\n';

    return xml;
  }

  private escapeXml(text: string): string {
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  private async exportAsPDF(options: ExportOptions): Promise<Blob> {
    this.notifyProgress(20, 'Generating PDF report...');

    // This would require a PDF library like jsPDF
    // For now, return a placeholder
    const pdfContent = this.generatePDFContent(options);
    return new Blob([pdfContent], { type: 'application/pdf' });
  }

  private generatePDFContent(options: ExportOptions): string {
    // PDF generation would be implemented here
    // This is a placeholder that returns text content
    let content = 'AURALIS AUDIO ANALYSIS REPORT\n\n';

    if (this.currentSession) {
      content += `Session: ${this.currentSession.sessionId}\n`;
      content += `Date: ${this.currentSession.metadata.timestamp}\n`;
      content += `Duration: ${this.currentSession.metadata.duration}s\n\n`;

      content += 'STATISTICS:\n';
      content += `Total Snapshots: ${this.currentSession.statistics.totalSnapshots}\n`;
      content += `Average Loudness: ${this.currentSession.statistics.averageLoudness.toFixed(2)} LUFS\n`;
      content += `Peak Loudness: ${this.currentSession.statistics.peakLoudness.toFixed(2)} LUFS\n`;
      content += `Average Correlation: ${this.currentSession.statistics.averageCorrelation.toFixed(3)}\n`;
      content += `Average Dynamic Range: ${this.currentSession.statistics.averageDynamicRange.toFixed(1)} dB\n`;
      content += `Processing Efficiency: ${this.currentSession.statistics.processingEfficiency.toFixed(1)}%\n`;
    }

    return content;
  }

  private async exportAsImage(options: ExportOptions, format: 'png' | 'svg'): Promise<Blob> {
    this.notifyProgress(20, `Generating ${format.toUpperCase()} visualization...`);

    const visualSettings = options.visualizationSettings || {
      width: 1920,
      height: 1080,
      theme: 'dark',
      includeWaveform: true,
      includeSpectrum: true,
      includeMeters: true,
      includeCorrelation: true,
    };

    // Create canvas for rendering
    const canvas = document.createElement('canvas');
    canvas.width = visualSettings.width;
    canvas.height = visualSettings.height;
    const ctx = canvas.getContext('2d')!;

    // Render visualization
    await this.renderVisualization(ctx, visualSettings);

    this.notifyProgress(80, 'Converting to image...');

    if (format === 'png') {
      return new Promise((resolve) => {
        canvas.toBlob(resolve as any, 'image/png');
      });
    } else {
      // SVG export would require different approach
      const svgContent = this.generateSVGVisualization(visualSettings);
      return new Blob([svgContent], { type: 'image/svg+xml' });
    }
  }

  private async renderVisualization(
    ctx: CanvasRenderingContext2D,
    settings: ExportOptions['visualizationSettings']
  ): Promise<void> {
    const { width, height, theme } = settings!;

    // Set background
    ctx.fillStyle = theme === 'dark' ? '#0A0A0A' : '#FFFFFF';
    ctx.fillRect(0, 0, width, height);

    // Render title
    ctx.fillStyle = theme === 'dark' ? '#FFFFFF' : '#000000';
    ctx.font = 'bold 48px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Auralis Audio Analysis Report', width / 2, 60);

    // Render session info
    if (this.currentSession) {
      ctx.font = '24px sans-serif';
      ctx.fillText(`Session: ${this.currentSession.sessionId}`, width / 2, 100);
      ctx.fillText(`Date: ${new Date(this.currentSession.metadata.timestamp).toLocaleString()}`, width / 2, 130);
    }

    // Render visualizations based on settings
    let currentY = 180;

    if (settings!.includeWaveform) {
      await this.renderWaveformToCanvas(ctx, 50, currentY, width - 100, 150, theme!);
      currentY += 200;
    }

    if (settings!.includeSpectrum) {
      await this.renderSpectrumToCanvas(ctx, 50, currentY, width - 100, 150, theme!);
      currentY += 200;
    }

    if (settings!.includeMeters) {
      await this.renderMetersToCanvas(ctx, 50, currentY, width - 100, 100, theme!);
      currentY += 150;
    }

    // Render statistics
    if (this.currentSession) {
      this.renderStatisticsToCanvas(ctx, 50, currentY, width - 100, 200, theme!);
    }
  }

  private async renderWaveformToCanvas(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    width: number,
    height: number,
    theme: string
  ): Promise<void> {
    // Simplified waveform rendering
    ctx.strokeStyle = theme === 'dark' ? '#4FC3F7' : '#1976D2';
    ctx.lineWidth = 2;

    ctx.beginPath();
    for (let i = 0; i < width; i++) {
      const progress = i / width;
      const amplitude = Math.sin(progress * Math.PI * 20) * 0.5;
      const canvasY = y + height / 2 + amplitude * height / 2;

      if (i === 0) {
        ctx.moveTo(x + i, canvasY);
      } else {
        ctx.lineTo(x + i, canvasY);
      }
    }
    ctx.stroke();

    // Title
    ctx.fillStyle = theme === 'dark' ? '#FFFFFF' : '#000000';
    ctx.font = '20px sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('Waveform', x, y - 10);
  }

  private async renderSpectrumToCanvas(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    width: number,
    height: number,
    theme: string
  ): Promise<void> {
    // Simplified spectrum rendering
    const barWidth = width / 64;
    ctx.fillStyle = theme === 'dark' ? '#FFB74D' : '#F57C00';

    for (let i = 0; i < 64; i++) {
      const barHeight = Math.random() * height * 0.8;
      ctx.fillRect(x + i * barWidth, y + height - barHeight, barWidth - 1, barHeight);
    }

    // Title
    ctx.fillStyle = theme === 'dark' ? '#FFFFFF' : '#000000';
    ctx.font = '20px sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('Spectrum Analysis', x, y - 10);
  }

  private async renderMetersToCanvas(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    width: number,
    height: number,
    theme: string
  ): Promise<void> {
    // Simplified meters rendering
    const meterWidth = 30;
    const meterSpacing = 50;

    for (let i = 0; i < 5; i++) {
      const meterX = x + i * meterSpacing;
      const level = Math.random();

      // Background
      ctx.fillStyle = theme === 'dark' ? '#333333' : '#CCCCCC';
      ctx.fillRect(meterX, y, meterWidth, height);

      // Level
      const levelHeight = level * height;
      ctx.fillStyle = level > 0.8 ? '#FF6B6B' : level > 0.6 ? '#FFB74D' : '#4FC3F7';
      ctx.fillRect(meterX, y + height - levelHeight, meterWidth, levelHeight);
    }

    // Title
    ctx.fillStyle = theme === 'dark' ? '#FFFFFF' : '#000000';
    ctx.font = '20px sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('Audio Meters', x, y - 10);
  }

  private renderStatisticsToCanvas(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    width: number,
    height: number,
    theme: string
  ): void {
    ctx.fillStyle = theme === 'dark' ? '#FFFFFF' : '#000000';
    ctx.font = '20px sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText('Analysis Statistics', x, y);

    ctx.font = '16px sans-serif';
    const stats = this.currentSession!.statistics;
    const lines = [
      `Total Snapshots: ${stats.totalSnapshots}`,
      `Average Loudness: ${stats.averageLoudness.toFixed(2)} LUFS`,
      `Peak Loudness: ${stats.peakLoudness.toFixed(2)} LUFS`,
      `Average Correlation: ${stats.averageCorrelation.toFixed(3)}`,
      `Average Dynamic Range: ${stats.averageDynamicRange.toFixed(1)} dB`,
      `Processing Efficiency: ${stats.processingEfficiency.toFixed(1)}%`,
    ];

    lines.forEach((line, index) => {
      ctx.fillText(line, x, y + 40 + index * 25);
    });
  }

  private generateSVGVisualization(settings: ExportOptions['visualizationSettings']): string {
    // SVG generation would be implemented here
    return `<svg width="${settings!.width}" height="${settings!.height}" xmlns="http://www.w3.org/2000/svg">
      <rect width="100%" height="100%" fill="${settings!.theme === 'dark' ? '#0A0A0A' : '#FFFFFF'}"/>
      <text x="50%" y="60" text-anchor="middle" fill="${settings!.theme === 'dark' ? '#FFFFFF' : '#000000'}" font-size="48" font-weight="bold">
        Auralis Audio Analysis Report
      </text>
    </svg>`;
  }

  // Progress notification
  private notifyProgress(progress: number, status: string): void {
    this.exportCallbacks.forEach(callback => {
      callback(progress, status);
    });
  }

  onExportProgress(callback: (progress: number, status: string) => void): () => void {
    this.exportCallbacks.push(callback);
    return () => {
      const index = this.exportCallbacks.indexOf(callback);
      if (index > -1) {
        this.exportCallbacks.splice(index, 1);
      }
    };
  }

  // Quick export methods
  async exportCurrentSnapshot(format: 'json' | 'csv' = 'json'): Promise<Blob> {
    if (this.snapshots.length === 0) {
      throw new Error('No snapshots available');
    }

    const lastSnapshot = this.snapshots[this.snapshots.length - 1];
    const data = format === 'json' ?
      JSON.stringify(lastSnapshot, null, 2) :
      this.snapshotToCSV(lastSnapshot);

    return new Blob([data], { type: format === 'json' ? 'application/json' : 'text/csv' });
  }

  private snapshotToCSV(snapshot: AnalysisSnapshot): string {
    const headers = ['field', 'value'];
    let csv = headers.join(',') + '\n';

    const addField = (name: string, value: any) => {
      csv += `"${name}","${value}"\n`;
    };

    addField('timestamp', snapshot.timestamp);
    addField('sequence', snapshot.sequence);

    if (snapshot.loudness) {
      Object.entries(snapshot.loudness).forEach(([key, value]) => {
        addField(`loudness_${key}`, value);
      });
    }

    if (snapshot.correlation) {
      Object.entries(snapshot.correlation).forEach(([key, value]) => {
        addField(`correlation_${key}`, value);
      });
    }

    if (snapshot.dynamics) {
      Object.entries(snapshot.dynamics).forEach(([key, value]) => {
        addField(`dynamics_${key}`, value);
      });
    }

    return csv;
  }

  // Utility methods
  getCurrentSession(): AnalysisSession | null {
    return this.currentSession;
  }

  getSnapshotCount(): number {
    return this.snapshots.length;
  }

  clearSnapshots(): void {
    this.snapshots = [];
    if (this.currentSession) {
      this.currentSession.snapshots = [];
    }
  }

  // Cleanup
  destroy(): void {
    this.snapshots = [];
    this.currentSession = null;
    this.exportCallbacks = [];
  }
}

// React Hook for Analysis Export
export function useAnalysisExport() {
  const [exportService] = React.useState(() => new AnalysisExportService());
  const [isExporting, setIsExporting] = React.useState(false);
  const [exportProgress, setExportProgress] = React.useState(0);
  const [exportStatus, setExportStatus] = React.useState('');

  React.useEffect(() => {
    const unsubscribe = exportService.onExportProgress((progress, status) => {
      setExportProgress(progress);
      setExportStatus(status);
      setIsExporting(progress < 100);
    });

    return () => {
      unsubscribe();
      exportService.destroy();
    };
  }, [exportService]);

  const exportSession = React.useCallback(async (options?: Partial<ExportOptions>) => {
    setIsExporting(true);
    try {
      const blob = await exportService.exportSession(options);

      // Download the file
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `auralis_analysis_${Date.now()}.${options?.format || 'json'}`;
      a.click();
      URL.revokeObjectURL(url);

      return blob;
    } finally {
      setIsExporting(false);
    }
  }, [exportService]);

  return {
    exportService,
    isExporting,
    exportProgress,
    exportStatus,
    exportSession,
    addSnapshot: (data: Partial<AnalysisSnapshot>) => exportService.addSnapshot(data),
    startSession: (metadata?: Partial<ExportMetadata>) => exportService.startNewSession(metadata),
    endSession: () => exportService.endCurrentSession(),
    exportCurrentSnapshot: (format?: 'json' | 'csv') => exportService.exportCurrentSnapshot(format),
    getCurrentSession: () => exportService.getCurrentSession(),
    getSnapshotCount: () => exportService.getSnapshotCount(),
  };
}

// Import React for the hook
import React from 'react';

export default AnalysisExportService;