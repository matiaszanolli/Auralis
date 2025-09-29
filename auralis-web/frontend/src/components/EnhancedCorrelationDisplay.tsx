import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Box, Paper, Typography, Switch, FormControlLabel, Grid, ToggleButton, ToggleButtonGroup } from '@mui/material';
import { useVisualizationOptimization } from '../hooks/useVisualizationOptimization';

// Types for correlation analysis matching our Phase 5.1 backend
interface CorrelationData {
  correlation_coefficient: number;
  phase_correlation: number;
  stereo_width: number;
  mono_compatibility: number;
  phase_stability: number;
  phase_deviation: number;
  stereo_position: number;
  left_energy: number;
  right_energy: number;
  mid_energy?: number;
  side_energy?: number;
  correlation_history?: number[];
  phase_history?: number[];
  timestamp?: number;
}

interface CorrelationSettings {
  displayMode: 'goniometer' | 'correlation' | 'balance' | 'history';
  showGrid: boolean;
  showLabels: boolean;
  showHistory: boolean;
  showMidSide: boolean;
  showWarnings: boolean;
  traceLength: number;
  sensitivity: number;
  colorScheme: 'classic' | 'modern' | 'broadcast' | 'mastering';
  backgroundColor: string;
  traceColor: string;
  gridColor: string;
  warningColor: string;
  updateRate: number;
}

interface EnhancedCorrelationDisplayProps {
  correlationData?: CorrelationData;
  width?: number;
  height?: number;
  showControls?: boolean;
  className?: string;
  real_time?: boolean;
  onPhaseAlert?: (issue: string, severity: 'low' | 'medium' | 'high') => void;
  onMonoCompatibilityAlert?: (compatibility: number) => void;
}

const defaultSettings: CorrelationSettings = {
  displayMode: 'goniometer',
  showGrid: true,
  showLabels: true,
  showHistory: true,
  showMidSide: false,
  showWarnings: true,
  traceLength: 100,
  sensitivity: 1.0,
  colorScheme: 'modern',
  backgroundColor: '#0A0A0A',
  traceColor: '#00FF7F',
  gridColor: '#333333',
  warningColor: '#FF4444',
  updateRate: 30,
};

// Color schemes for different display modes
const colorSchemes = {
  classic: {
    trace: '#00FF00',
    grid: '#444444',
    warning: '#FF0000',
    background: '#000000',
    text: '#FFFFFF',
    accent: '#FFFF00',
  },
  modern: {
    trace: '#00FF7F',
    grid: '#333333',
    warning: '#FF4444',
    background: '#0A0A0A',
    text: '#F0F0F0',
    accent: '#4FC3F7',
  },
  broadcast: {
    trace: '#00FF00',
    grid: '#666666',
    warning: '#FF0000',
    background: '#1A1A1A',
    text: '#E0E0E0',
    accent: '#FFAA00',
  },
  mastering: {
    trace: '#40E0D0',
    grid: '#2F2F2F',
    warning: '#FF3030',
    background: '#000000',
    text: '#FFFFFF',
    accent: '#FFD700',
  },
};

export const EnhancedCorrelationDisplay: React.FC<EnhancedCorrelationDisplayProps> = ({
  correlationData,
  width = 400,
  height = 400,
  showControls = true,
  className,
  real_time = true,
  onPhaseAlert,
  onMonoCompatibilityAlert,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationFrameRef = useRef<number>();
  const [settings, setSettings] = useState<CorrelationSettings>(defaultSettings);
  const [traceHistory, setTraceHistory] = useState<Array<{ x: number; y: number; timestamp: number }>>([]);
  const [alertState, setAlertState] = useState<{ [key: string]: boolean }>({});

  // Use visualization optimization
  const {
    shouldRender,
    startRender,
    endRender,
    stats,
    qualityLevel
  } = useVisualizationOptimization({
    targetFPS: settings.updateRate,
    adaptiveQuality: true,
    enableMonitoring: true
  });

  // Convert correlation values to goniometer coordinates
  const correlationToGoniometer = useCallback((left: number, right: number): { x: number; y: number } => {
    // Goniometer: X = L+R (sum), Y = L-R (difference)
    const sum = (left + right) / 2;
    const diff = (left - right) / 2;

    // Convert to canvas coordinates
    const centerX = width / 2;
    const centerY = height / 2;
    const scale = Math.min(width, height) / 2 * 0.8;

    return {
      x: centerX + sum * scale,
      y: centerY - diff * scale, // Invert Y for proper display
    };
  }, [width, height]);

  // Draw grid for goniometer
  const drawGoniometerGrid = useCallback((ctx: CanvasRenderingContext2D) => {
    if (!settings.showGrid) return;

    const colors = colorSchemes[settings.colorScheme];
    const centerX = width / 2;
    const centerY = height / 2;
    const scale = Math.min(width, height) / 2 * 0.8;

    ctx.strokeStyle = colors.grid;
    ctx.lineWidth = 1;
    ctx.setLineDash([2, 4]);

    // Outer circle (100%)
    ctx.beginPath();
    ctx.arc(centerX, centerY, scale, 0, 2 * Math.PI);
    ctx.stroke();

    // Inner circles (50%, 25%)
    [0.5, 0.25].forEach(ratio => {
      ctx.beginPath();
      ctx.arc(centerX, centerY, scale * ratio, 0, 2 * Math.PI);
      ctx.stroke();
    });

    // Center axes
    ctx.setLineDash([]);
    ctx.lineWidth = 2;

    // Horizontal axis (L-R = 0, mono content)
    ctx.beginPath();
    ctx.moveTo(centerX - scale, centerY);
    ctx.lineTo(centerX + scale, centerY);
    ctx.stroke();

    // Vertical axis (L+R = 0, no signal)
    ctx.beginPath();
    ctx.moveTo(centerX, centerY - scale);
    ctx.lineTo(centerX, centerY + scale);
    ctx.stroke();

    // Diagonal lines for phase reference
    ctx.strokeStyle = colors.grid;
    ctx.lineWidth = 1;
    ctx.setLineDash([1, 2]);

    // 45-degree lines (in-phase and anti-phase)
    const diagOffset = scale * 0.7;

    // In-phase line (lower-left to upper-right)
    ctx.beginPath();
    ctx.moveTo(centerX - diagOffset, centerY + diagOffset);
    ctx.lineTo(centerX + diagOffset, centerY - diagOffset);
    ctx.stroke();

    // Anti-phase line (upper-left to lower-right)
    ctx.beginPath();
    ctx.moveTo(centerX - diagOffset, centerY - diagOffset);
    ctx.lineTo(centerX + diagOffset, centerY + diagOffset);
    ctx.stroke();

    ctx.setLineDash([]);

    // Labels
    if (settings.showLabels) {
      ctx.fillStyle = colors.text;
      ctx.font = '12px sans-serif';
      ctx.textAlign = 'center';

      // Axis labels
      ctx.fillText('L+R', centerX, 15);
      ctx.fillText('L-R', width - 15, centerY + 5);
      ctx.fillText('Mono', centerX, height - 5);
      ctx.fillText('Stereo', 15, centerY + 5);

      // Phase labels
      ctx.font = '10px sans-serif';
      ctx.fillText('In-Phase', centerX + diagOffset * 0.7, centerY - diagOffset * 0.7);
      ctx.fillText('Anti-Phase', centerX + diagOffset * 0.7, centerY + diagOffset * 0.7);

      ctx.textAlign = 'left';
    }
  }, [settings, width, height, colorSchemes]);

  // Draw goniometer trace
  const drawGoniometerTrace = useCallback((ctx: CanvasRenderingContext2D, data: CorrelationData) => {
    if (settings.displayMode !== 'goniometer') return;

    const colors = colorSchemes[settings.colorScheme];

    // Simulate stereo audio for goniometer display
    // In real implementation, this would come from actual L/R audio samples
    const correlation = data.correlation_coefficient;
    const width_val = data.stereo_width;

    // Generate simulated stereo signal points
    const numPoints = 50;
    const points: { x: number; y: number }[] = [];

    for (let i = 0; i < numPoints; i++) {
      // Simulate based on correlation and width
      const angle = (i / numPoints) * 2 * Math.PI;
      const left = Math.sin(angle) * (1 - width_val * 0.5);
      const right = Math.sin(angle + Math.PI * (1 - correlation)) * (1 - width_val * 0.5);

      points.push(correlationToGoniometer(left, right));
    }

    // Draw trace points
    ctx.fillStyle = colors.trace;
    ctx.globalAlpha = 0.7;

    points.forEach((point, index) => {
      const alpha = (index / points.length) * 0.5 + 0.5; // Fade older points
      ctx.globalAlpha = alpha * 0.7;

      ctx.beginPath();
      ctx.arc(point.x, point.y, 2, 0, 2 * Math.PI);
      ctx.fill();
    });

    ctx.globalAlpha = 1;

    // Add to trace history for animated trail
    if (points.length > 0) {
      const now = Date.now();
      setTraceHistory(prev => {
        const newHistory = [...prev, { ...points[points.length - 1], timestamp: now }];
        // Keep only recent points
        return newHistory.filter(point => now - point.timestamp < settings.traceLength * 50);
      });
    }

    // Draw trace history trail
    if (settings.showHistory && traceHistory.length > 1) {
      ctx.strokeStyle = colors.trace;
      ctx.lineWidth = 1;
      ctx.globalAlpha = 0.3;

      ctx.beginPath();
      traceHistory.forEach((point, index) => {
        if (index === 0) {
          ctx.moveTo(point.x, point.y);
        } else {
          ctx.lineTo(point.x, point.y);
        }
      });
      ctx.stroke();

      ctx.globalAlpha = 1;
    }
  }, [settings, colorSchemes, correlationToGoniometer, traceHistory]);

  // Draw correlation meter
  const drawCorrelationMeter = useCallback((ctx: CanvasRenderingContext2D, data: CorrelationData) => {
    if (settings.displayMode !== 'correlation') return;

    const colors = colorSchemes[settings.colorScheme];
    const meterWidth = width * 0.8;
    const meterHeight = 40;
    const startX = (width - meterWidth) / 2;
    const startY = height / 2 - 100;

    // Background
    ctx.fillStyle = colors.background;
    ctx.fillRect(startX, startY, meterWidth, meterHeight);
    ctx.strokeStyle = colors.grid;
    ctx.strokeRect(startX, startY, meterWidth, meterHeight);

    // Correlation scale (-1 to +1)
    const correlation = data.correlation_coefficient;
    const corrPos = (correlation + 1) / 2; // Convert -1:1 to 0:1

    // Color gradient background
    const gradient = ctx.createLinearGradient(startX, 0, startX + meterWidth, 0);
    gradient.addColorStop(0, '#FF0000');     // Anti-phase
    gradient.addColorStop(0.5, '#FFFF00');  // Uncorrelated
    gradient.addColorStop(1, '#00FF00');    // In-phase

    ctx.fillStyle = gradient;
    ctx.fillRect(startX + 2, startY + 2, meterWidth - 4, meterHeight - 4);

    // Correlation indicator
    const indicatorX = startX + corrPos * meterWidth;
    ctx.fillStyle = '#FFFFFF';
    ctx.fillRect(indicatorX - 2, startY, 4, meterHeight);

    // Scale markings
    const markings = [-1, -0.5, 0, 0.5, 1];
    ctx.fillStyle = colors.text;
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'center';

    markings.forEach(mark => {
      const x = startX + ((mark + 1) / 2) * meterWidth;
      ctx.fillText(mark.toString(), x, startY + meterHeight + 15);
    });

    // Value display
    ctx.font = 'bold 14px sans-serif';
    ctx.fillText(`Correlation: ${correlation.toFixed(3)}`, width / 2, startY - 10);

    // Additional metrics
    const metrics = [
      { label: 'Stereo Width', value: data.stereo_width.toFixed(2) },
      { label: 'Mono Compatibility', value: (data.mono_compatibility * 100).toFixed(1) + '%' },
      { label: 'Phase Stability', value: (data.phase_stability * 100).toFixed(1) + '%' },
    ];

    ctx.font = '12px sans-serif';
    metrics.forEach((metric, index) => {
      const y = startY + 80 + index * 25;
      ctx.fillText(`${metric.label}: ${metric.value}`, startX, y);
    });

    ctx.textAlign = 'left';
  }, [settings, width, height, colorSchemes]);

  // Draw stereo balance display
  const drawStereoBalance = useCallback((ctx: CanvasRenderingContext2D, data: CorrelationData) => {
    if (settings.displayMode !== 'balance') return;

    const colors = colorSchemes[settings.colorScheme];
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = Math.min(width, height) / 3;

    // Draw balance circle
    ctx.strokeStyle = colors.grid;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, 0, 2 * Math.PI);
    ctx.stroke();

    // Draw center point
    ctx.fillStyle = colors.grid;
    ctx.beginPath();
    ctx.arc(centerX, centerY, 3, 0, 2 * Math.PI);
    ctx.fill();

    // Calculate stereo position
    const position = data.stereo_position || 0; // -1 (left) to +1 (right)
    const leftEnergy = data.left_energy || 0.5;
    const rightEnergy = data.right_energy || 0.5;

    // Position indicator
    const posX = centerX + position * radius * 0.8;
    const posY = centerY;

    ctx.fillStyle = colors.trace;
    ctx.beginPath();
    ctx.arc(posX, posY, 8, 0, 2 * Math.PI);
    ctx.fill();

    // Energy bars
    const barWidth = 20;
    const barMaxHeight = radius * 0.8;

    // Left channel bar
    const leftBarHeight = leftEnergy * barMaxHeight;
    ctx.fillStyle = leftEnergy > 0.9 ? colors.warning : colors.trace;
    ctx.fillRect(centerX - radius - barWidth - 10, centerY + radius - leftBarHeight, barWidth, leftBarHeight);

    // Right channel bar
    const rightBarHeight = rightEnergy * barMaxHeight;
    ctx.fillStyle = rightEnergy > 0.9 ? colors.warning : colors.trace;
    ctx.fillRect(centerX + radius + 10, centerY + radius - rightBarHeight, barWidth, rightBarHeight);

    // Labels
    ctx.fillStyle = colors.text;
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'center';

    ctx.fillText('L', centerX - radius - 10, centerY + radius + 20);
    ctx.fillText('R', centerX + radius + 10, centerY + radius + 20);
    ctx.fillText(`Position: ${(position * 100).toFixed(0)}%`, centerX, centerY + radius + 40);

    // Energy values
    ctx.font = '10px sans-serif';
    ctx.fillText(leftEnergy.toFixed(2), centerX - radius - 10, centerY + radius + 35);
    ctx.fillText(rightEnergy.toFixed(2), centerX + radius + 10, centerY + radius + 35);

    ctx.textAlign = 'left';
  }, [settings, width, height, colorSchemes]);

  // Draw correlation history
  const drawCorrelationHistory = useCallback((ctx: CanvasRenderingContext2D, data: CorrelationData) => {
    if (settings.displayMode !== 'history' || !data.correlation_history) return;

    const colors = colorSchemes[settings.colorScheme];
    const graphWidth = width * 0.9;
    const graphHeight = height * 0.6;
    const startX = (width - graphWidth) / 2;
    const startY = (height - graphHeight) / 2;

    // Background
    ctx.fillStyle = colors.background;
    ctx.fillRect(startX, startY, graphWidth, graphHeight);
    ctx.strokeStyle = colors.grid;
    ctx.strokeRect(startX, startY, graphWidth, graphHeight);

    // Grid lines
    ctx.setLineDash([2, 2]);
    ctx.lineWidth = 1;

    // Horizontal grid lines
    for (let i = 0; i <= 4; i++) {
      const y = startY + (i / 4) * graphHeight;
      ctx.beginPath();
      ctx.moveTo(startX, y);
      ctx.lineTo(startX + graphWidth, y);
      ctx.stroke();

      // Labels
      const value = 1 - (i / 4) * 2; // 1 to -1
      ctx.fillStyle = colors.text;
      ctx.font = '10px sans-serif';
      ctx.fillText(value.toFixed(1), startX - 20, y + 3);
    }

    ctx.setLineDash([]);

    // Draw correlation history curve
    const history = data.correlation_history;
    if (history.length > 1) {
      ctx.strokeStyle = colors.trace;
      ctx.lineWidth = 2;

      ctx.beginPath();
      history.forEach((value, index) => {
        const x = startX + (index / (history.length - 1)) * graphWidth;
        const y = startY + ((1 - value) / 2) * graphHeight; // Convert -1:1 to graph coords

        if (index === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      });
      ctx.stroke();
    }

    // Current value indicator
    const currentCorr = data.correlation_coefficient;
    const currentY = startY + ((1 - currentCorr) / 2) * graphHeight;

    ctx.fillStyle = colors.accent;
    ctx.beginPath();
    ctx.arc(startX + graphWidth, currentY, 4, 0, 2 * Math.PI);
    ctx.fill();

    // Title
    ctx.fillStyle = colors.text;
    ctx.font = 'bold 14px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Correlation History', width / 2, startY - 10);
    ctx.textAlign = 'left';
  }, [settings, width, height, colorSchemes]);

  // Check for alerts
  const checkAlerts = useCallback((data: CorrelationData) => {
    if (!settings.showWarnings) return;

    // Phase correlation alerts
    if (Math.abs(data.correlation_coefficient) < 0.3) {
      if (onPhaseAlert) {
        onPhaseAlert('Poor phase correlation detected', 'high');
      }
    } else if (Math.abs(data.correlation_coefficient) < 0.6) {
      if (onPhaseAlert) {
        onPhaseAlert('Moderate phase issues', 'medium');
      }
    }

    // Mono compatibility alerts
    if (data.mono_compatibility < 0.7) {
      if (onMonoCompatibilityAlert) {
        onMonoCompatibilityAlert(data.mono_compatibility);
      }
    }
  }, [settings.showWarnings, onPhaseAlert, onMonoCompatibilityAlert]);

  // Main render function
  const render = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !correlationData) return;

    if (!shouldRender()) return;

    startRender();
    checkAlerts(correlationData);

    const ctx = canvas.getContext('2d');
    if (!ctx) {
      endRender();
      return;
    }

    // Clear canvas
    const colors = colorSchemes[settings.colorScheme];
    ctx.fillStyle = colors.background;
    ctx.fillRect(0, 0, width, height);

    try {
      // Draw based on display mode
      switch (settings.displayMode) {
        case 'goniometer':
          drawGoniometerGrid(ctx);
          drawGoniometerTrace(ctx, correlationData);
          break;
        case 'correlation':
          drawCorrelationMeter(ctx, correlationData);
          break;
        case 'balance':
          drawStereoBalance(ctx, correlationData);
          break;
        case 'history':
          drawCorrelationHistory(ctx, correlationData);
          break;
      }
    } catch (error) {
      console.error('Correlation display render error:', error);
    }

    endRender();
  }, [
    correlationData, settings, width, height, colorSchemes,
    shouldRender, startRender, endRender, checkAlerts,
    drawGoniometerGrid, drawGoniometerTrace, drawCorrelationMeter,
    drawStereoBalance, drawCorrelationHistory
  ]);

  // Animation loop
  useEffect(() => {
    if (!real_time) {
      render();
      return;
    }

    const animate = () => {
      render();
      animationFrameRef.current = requestAnimationFrame(animate);
    };

    animationFrameRef.current = requestAnimationFrame(animate);

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [render, real_time]);

  // Canvas setup
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    canvas.width = width;
    canvas.height = height;
  }, [width, height]);

  return (
    <Paper className={className} sx={{ p: 2, backgroundColor: '#1A1A1A' }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h6" color="white">
          Phase & Correlation Analysis
        </Typography>
        <Box display="flex" gap={1}>
          <Typography variant="caption" color="grey.400">
            FPS: {stats.fps.toFixed(1)} | Quality: {(qualityLevel * 100).toFixed(0)}%
          </Typography>
        </Box>
      </Box>

      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        style={{
          border: '1px solid #333',
          display: 'block',
          margin: '0 auto'
        }}
      />

      {showControls && (
        <Box mt={2}>
          <Grid container spacing={2}>
            <Grid item xs={12} md={4}>
              <Typography gutterBottom>Display Mode</Typography>
              <ToggleButtonGroup
                value={settings.displayMode}
                exclusive
                onChange={(_, value) => value && setSettings(prev => ({ ...prev, displayMode: value }))}
                size="small"
                orientation="vertical"
              >
                <ToggleButton value="goniometer">Goniometer</ToggleButton>
                <ToggleButton value="correlation">Correlation</ToggleButton>
                <ToggleButton value="balance">Balance</ToggleButton>
                <ToggleButton value="history">History</ToggleButton>
              </ToggleButtonGroup>
            </Grid>

            <Grid item xs={12} md={4}>
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showGrid}
                    onChange={(e) => setSettings(prev => ({ ...prev, showGrid: e.target.checked }))}
                    color="primary"
                  />
                }
                label="Show Grid"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showLabels}
                    onChange={(e) => setSettings(prev => ({ ...prev, showLabels: e.target.checked }))}
                    color="primary"
                  />
                }
                label="Show Labels"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showHistory}
                    onChange={(e) => setSettings(prev => ({ ...prev, showHistory: e.target.checked }))}
                    color="primary"
                  />
                }
                label="Trace History"
              />
            </Grid>

            <Grid item xs={12} md={4}>
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showWarnings}
                    onChange={(e) => setSettings(prev => ({ ...prev, showWarnings: e.target.checked }))}
                    color="primary"
                  />
                }
                label="Phase Warnings"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showMidSide}
                    onChange={(e) => setSettings(prev => ({ ...prev, showMidSide: e.target.checked }))}
                    color="primary"
                  />
                }
                label="Mid-Side Info"
              />
            </Grid>
          </Grid>

          {correlationData && (
            <Box mt={2}>
              <Typography variant="subtitle2" color="white" gutterBottom>
                Current Analysis:
              </Typography>
              <Box display="flex" gap={2} flexWrap="wrap">
                <Typography variant="caption" color="grey.300">
                  Correlation: {correlationData.correlation_coefficient.toFixed(3)}
                </Typography>
                <Typography variant="caption" color="grey.300">
                  Width: {correlationData.stereo_width.toFixed(2)}
                </Typography>
                <Typography variant="caption" color="grey.300">
                  Mono Compat: {(correlationData.mono_compatibility * 100).toFixed(0)}%
                </Typography>
                <Typography variant="caption" color="grey.300">
                  Phase Stability: {(correlationData.phase_stability * 100).toFixed(0)}%
                </Typography>
              </Box>
            </Box>
          )}
        </Box>
      )}
    </Paper>
  );
};

export default EnhancedCorrelationDisplay;