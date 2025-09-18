import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Box, Paper, Typography, Switch, FormControlLabel, Grid, ToggleButton, ToggleButtonGroup, Chip } from '@mui/material';
import { useVisualizationOptimization } from '../hooks/useVisualizationOptimization';

// Types for processing activity data
interface ProcessingStageData {
  name: string;
  isActive: boolean;
  cpuUsage: number;
  latency: number; // ms
  bufferUsage: number; // 0-1
  inputLevel: number; // dB
  outputLevel: number; // dB
  gainReduction: number; // dB
  parameters: { [key: string]: number };
  alerts: string[];
  timestamp: number;
}

interface ProcessingActivityData {
  stages: ProcessingStageData[];
  globalCpuUsage: number;
  globalLatency: number;
  bufferUnderruns: number;
  sampleRate: number;
  bufferSize: number;
  isRealTime: boolean;
  processingLoad: number; // 0-1
  systemStats: {
    memoryUsage: number;
    diskIO: number;
    networkLatency?: number;
  };
}

interface ActivitySettings {
  displayMode: 'pipeline' | 'meters' | 'performance' | 'detailed';
  showLatency: boolean;
  showCpuUsage: boolean;
  showBufferStatus: boolean;
  showGainReduction: boolean;
  showParameters: boolean;
  showAlerts: boolean;
  timeSpan: number; // seconds
  updateRate: number; // Hz
  alertThresholds: {
    cpuWarning: number;
    cpuCritical: number;
    latencyWarning: number;
    latencyCritical: number;
    bufferWarning: number;
  };
  colorScheme: 'performance' | 'studio' | 'debug' | 'minimal';
}

interface EnhancedProcessingActivityViewProps {
  activityData?: ProcessingActivityData;
  width?: number;
  height?: number;
  showControls?: boolean;
  className?: string;
  real_time?: boolean;
  onStageClick?: (stageName: string) => void;
  onAlert?: (stage: string, alert: string, severity: 'low' | 'medium' | 'high') => void;
}

const defaultSettings: ActivitySettings = {
  displayMode: 'pipeline',
  showLatency: true,
  showCpuUsage: true,
  showBufferStatus: true,
  showGainReduction: true,
  showParameters: false,
  showAlerts: true,
  timeSpan: 10,
  updateRate: 20,
  alertThresholds: {
    cpuWarning: 70,
    cpuCritical: 90,
    latencyWarning: 10,
    latencyCritical: 20,
    bufferWarning: 0.8,
  },
  colorScheme: 'performance',
};

// Color schemes for different visualization modes
const colorSchemes = {
  performance: {
    background: '#0A0A0A',
    grid: '#333333',
    text: '#F0F0F0',
    stageActive: '#00FF7F',
    stageInactive: '#404040',
    cpuLow: '#00FF00',
    cpuMedium: '#FFFF00',
    cpuHigh: '#FF8000',
    cpuCritical: '#FF0000',
    latencyGood: '#00FF00',
    latencyWarning: '#FFAA00',
    latencyCritical: '#FF0000',
    bufferOk: '#00AA00',
    bufferWarning: '#FF8800',
    alert: '#FF4444',
  },
  studio: {
    background: '#1A1A1A',
    grid: '#444444',
    text: '#E0E0E0',
    stageActive: '#4FC3F7',
    stageInactive: '#666666',
    cpuLow: '#4CAF50',
    cpuMedium: '#FFC107',
    cpuHigh: '#FF9800',
    cpuCritical: '#F44336',
    latencyGood: '#4CAF50',
    latencyWarning: '#FF9800',
    latencyCritical: '#F44336',
    bufferOk: '#4CAF50',
    bufferWarning: '#FF9800',
    alert: '#F44336',
  },
  debug: {
    background: '#000000',
    grid: '#222222',
    text: '#00FF00',
    stageActive: '#00FFFF',
    stageInactive: '#404040',
    cpuLow: '#00FF00',
    cpuMedium: '#FFFF00',
    cpuHigh: '#FF8000',
    cpuCritical: '#FF0000',
    latencyGood: '#00FF00',
    latencyWarning: '#FFFF00',
    latencyCritical: '#FF0000',
    bufferOk: '#00FF00',
    bufferWarning: '#FFFF00',
    alert: '#FF0000',
  },
  minimal: {
    background: '#FAFAFA',
    grid: '#E0E0E0',
    text: '#333333',
    stageActive: '#2196F3',
    stageInactive: '#BDBDBD',
    cpuLow: '#4CAF50',
    cpuMedium: '#FF9800',
    cpuHigh: '#FF5722',
    cpuCritical: '#D32F2F',
    latencyGood: '#4CAF50',
    latencyWarning: '#FF9800',
    latencyCritical: '#D32F2F',
    bufferOk: '#4CAF50',
    bufferWarning: '#FF9800',
    alert: '#D32F2F',
  },
};

export const EnhancedProcessingActivityView: React.FC<EnhancedProcessingActivityViewProps> = ({
  activityData,
  width = 800,
  height = 500,
  showControls = true,
  className,
  real_time = true,
  onStageClick,
  onAlert,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationFrameRef = useRef<number>();
  const [settings, setSettings] = useState<ActivitySettings>(defaultSettings);
  const [selectedStage, setSelectedStage] = useState<string | null>(null);
  const [historyData, setHistoryData] = useState<{ [key: string]: number[] }>({});

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

  // Get color for CPU usage
  const getCpuColor = useCallback((usage: number): string => {
    const colors = colorSchemes[settings.colorScheme];
    if (usage < 30) return colors.cpuLow;
    if (usage < 60) return colors.cpuMedium;
    if (usage < settings.alertThresholds.cpuWarning) return colors.cpuHigh;
    return colors.cpuCritical;
  }, [settings]);

  // Get color for latency
  const getLatencyColor = useCallback((latency: number): string => {
    const colors = colorSchemes[settings.colorScheme];
    if (latency < settings.alertThresholds.latencyWarning) return colors.latencyGood;
    if (latency < settings.alertThresholds.latencyCritical) return colors.latencyWarning;
    return colors.latencyCritical;
  }, [settings]);

  // Get color for buffer usage
  const getBufferColor = useCallback((usage: number): string => {
    const colors = colorSchemes[settings.colorScheme];
    if (usage < settings.alertThresholds.bufferWarning) return colors.bufferOk;
    return colors.bufferWarning;
  }, [settings]);

  // Draw processing pipeline view
  const drawPipelineView = useCallback((ctx: CanvasRenderingContext2D, data: ProcessingActivityData) => {
    if (settings.displayMode !== 'pipeline') return;

    const colors = colorSchemes[settings.colorScheme];
    const stageWidth = 120;
    const stageHeight = 80;
    const spacing = 20;
    const startY = 50;

    data.stages.forEach((stage, index) => {
      const x = 20 + index * (stageWidth + spacing);
      const y = startY;

      // Stage box
      ctx.fillStyle = stage.isActive ? colors.stageActive : colors.stageInactive;
      ctx.globalAlpha = stage.isActive ? 0.8 : 0.4;
      ctx.fillRect(x, y, stageWidth, stageHeight);

      // Stage border
      ctx.strokeStyle = stage === selectedStage ? '#FFFFFF' : colors.grid;
      ctx.lineWidth = stage.name === selectedStage ? 3 : 1;
      ctx.globalAlpha = 1;
      ctx.strokeRect(x, y, stageWidth, stageHeight);

      // Stage name
      ctx.fillStyle = colors.text;
      ctx.font = 'bold 12px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(stage.name, x + stageWidth / 2, y + 15);

      // CPU usage
      if (settings.showCpuUsage) {
        ctx.fillStyle = getCpuColor(stage.cpuUsage);
        ctx.font = '10px sans-serif';
        ctx.fillText(`CPU: ${stage.cpuUsage.toFixed(1)}%`, x + stageWidth / 2, y + 30);
      }

      // Latency
      if (settings.showLatency) {
        ctx.fillStyle = getLatencyColor(stage.latency);
        ctx.font = '10px sans-serif';
        ctx.fillText(`Lat: ${stage.latency.toFixed(1)}ms`, x + stageWidth / 2, y + 45);
      }

      // Buffer usage
      if (settings.showBufferStatus) {
        ctx.fillStyle = getBufferColor(stage.bufferUsage);
        ctx.font = '10px sans-serif';
        ctx.fillText(`Buf: ${(stage.bufferUsage * 100).toFixed(0)}%`, x + stageWidth / 2, y + 60);
      }

      // Gain reduction (if applicable)
      if (settings.showGainReduction && stage.gainReduction > 0) {
        ctx.fillStyle = '#FFB74D';
        ctx.font = '10px sans-serif';
        ctx.fillText(`GR: -${stage.gainReduction.toFixed(1)}dB`, x + stageWidth / 2, y + 75);
      }

      // Alert indicator
      if (settings.showAlerts && stage.alerts.length > 0) {
        ctx.fillStyle = colors.alert;
        ctx.beginPath();
        ctx.arc(x + stageWidth - 10, y + 10, 5, 0, 2 * Math.PI);
        ctx.fill();
      }

      // Connection line to next stage
      if (index < data.stages.length - 1) {
        const connectionY = y + stageHeight / 2;
        ctx.strokeStyle = stage.isActive ? colors.stageActive : colors.stageInactive;
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(x + stageWidth, connectionY);
        ctx.lineTo(x + stageWidth + spacing, connectionY);
        ctx.stroke();

        // Arrow
        ctx.beginPath();
        ctx.moveTo(x + stageWidth + spacing - 5, connectionY - 3);
        ctx.lineTo(x + stageWidth + spacing, connectionY);
        ctx.lineTo(x + stageWidth + spacing - 5, connectionY + 3);
        ctx.stroke();
      }

      ctx.textAlign = 'left';
    });

    // Global stats
    ctx.fillStyle = colors.text;
    ctx.font = 'bold 14px sans-serif';
    ctx.fillText('Processing Pipeline', 20, 30);

    ctx.font = '12px sans-serif';
    const globalY = startY + stageHeight + 40;
    ctx.fillText(`Global CPU: ${data.globalCpuUsage.toFixed(1)}%`, 20, globalY);
    ctx.fillText(`Total Latency: ${data.globalLatency.toFixed(1)}ms`, 200, globalY);
    ctx.fillText(`Buffer Underruns: ${data.bufferUnderruns}`, 400, globalY);
    ctx.fillText(`Sample Rate: ${data.sampleRate}Hz`, 600, globalY);
  }, [settings, selectedStage, colorSchemes, getCpuColor, getLatencyColor, getBufferColor]);

  // Draw performance meters view
  const drawPerformanceView = useCallback((ctx: CanvasRenderingContext2D, data: ProcessingActivityData) => {
    if (settings.displayMode !== 'performance') return;

    const colors = colorSchemes[settings.colorScheme];
    const meterWidth = 40;
    const meterHeight = height - 120;
    const startX = 50;
    const startY = 50;

    // CPU usage meters for each stage
    data.stages.forEach((stage, index) => {
      const x = startX + index * (meterWidth + 20);

      // Meter background
      ctx.fillStyle = colors.background;
      ctx.fillRect(x, startY, meterWidth, meterHeight);
      ctx.strokeStyle = colors.grid;
      ctx.strokeRect(x, startY, meterWidth, meterHeight);

      // CPU usage fill
      const fillHeight = (stage.cpuUsage / 100) * meterHeight;
      const fillY = startY + meterHeight - fillHeight;

      ctx.fillStyle = getCpuColor(stage.cpuUsage);
      ctx.fillRect(x + 2, fillY, meterWidth - 4, fillHeight);

      // Stage label
      ctx.fillStyle = colors.text;
      ctx.font = '10px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(stage.name, x + meterWidth / 2, startY + meterHeight + 15);
      ctx.fillText(`${stage.cpuUsage.toFixed(1)}%`, x + meterWidth / 2, startY + meterHeight + 30);

      // Latency indicator
      if (settings.showLatency) {
        const latencyIndicatorY = startY + meterHeight - (stage.latency / 50) * meterHeight;
        ctx.fillStyle = getLatencyColor(stage.latency);
        ctx.fillRect(x - 5, latencyIndicatorY - 1, 5, 2);
      }

      ctx.textAlign = 'left';
    });

    // Performance history graph
    const graphX = startX + data.stages.length * (meterWidth + 20) + 50;
    const graphWidth = width - graphX - 50;
    const graphHeight = meterHeight / 2;

    ctx.strokeStyle = colors.grid;
    ctx.strokeRect(graphX, startY, graphWidth, graphHeight);

    // Draw CPU history
    const cpuHistory = historyData['globalCpu'] || [];
    if (cpuHistory.length > 1) {
      ctx.strokeStyle = colors.cpuMedium;
      ctx.lineWidth = 2;
      ctx.beginPath();

      cpuHistory.forEach((value, index) => {
        const x = graphX + (index / (cpuHistory.length - 1)) * graphWidth;
        const y = startY + graphHeight - (value / 100) * graphHeight;

        if (index === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      });
      ctx.stroke();
    }

    // Title
    ctx.fillStyle = colors.text;
    ctx.font = 'bold 14px sans-serif';
    ctx.fillText('Performance Monitoring', 20, 30);

    // Legend
    ctx.font = '12px sans-serif';
    ctx.fillText('CPU Usage', graphX, startY - 10);
    ctx.fillText('Latency →', startX - 40, startY + meterHeight / 2);
  }, [settings, height, width, colorSchemes, getCpuColor, getLatencyColor, historyData]);

  // Draw detailed view
  const drawDetailedView = useCallback((ctx: CanvasRenderingContext2D, data: ProcessingActivityData) => {
    if (settings.displayMode !== 'detailed' || !selectedStage) return;

    const stage = data.stages.find(s => s.name === selectedStage);
    if (!stage) return;

    const colors = colorSchemes[settings.colorScheme];

    // Background
    ctx.fillStyle = colors.background;
    ctx.fillRect(0, 0, width, height);

    // Title
    ctx.fillStyle = colors.text;
    ctx.font = 'bold 16px sans-serif';
    ctx.fillText(`${stage.name} - Detailed View`, 20, 30);

    // Parameters
    if (settings.showParameters && stage.parameters) {
      ctx.font = '14px sans-serif';
      ctx.fillText('Parameters:', 20, 60);

      let y = 80;
      Object.entries(stage.parameters).forEach(([param, value]) => {
        ctx.font = '12px sans-serif';
        ctx.fillText(`${param}: ${value.toFixed(2)}`, 20, y);
        y += 20;
      });
    }

    // Performance metrics
    const metricsX = 300;
    ctx.font = '14px sans-serif';
    ctx.fillStyle = colors.text;
    ctx.fillText('Performance:', metricsX, 60);

    const metrics = [
      { label: 'CPU Usage', value: `${stage.cpuUsage.toFixed(1)}%`, color: getCpuColor(stage.cpuUsage) },
      { label: 'Latency', value: `${stage.latency.toFixed(1)}ms`, color: getLatencyColor(stage.latency) },
      { label: 'Buffer Usage', value: `${(stage.bufferUsage * 100).toFixed(0)}%`, color: getBufferColor(stage.bufferUsage) },
      { label: 'Input Level', value: `${stage.inputLevel.toFixed(1)}dB`, color: colors.text },
      { label: 'Output Level', value: `${stage.outputLevel.toFixed(1)}dB`, color: colors.text },
    ];

    let y = 80;
    metrics.forEach(metric => {
      ctx.fillStyle = metric.color;
      ctx.font = '12px sans-serif';
      ctx.fillText(`${metric.label}: ${metric.value}`, metricsX, y);
      y += 20;
    });

    // Alerts
    if (settings.showAlerts && stage.alerts.length > 0) {
      ctx.fillStyle = colors.alert;
      ctx.font = '14px sans-serif';
      ctx.fillText('Alerts:', 20, height - 100);

      y = height - 80;
      stage.alerts.forEach(alert => {
        ctx.font = '12px sans-serif';
        ctx.fillText(`• ${alert}`, 20, y);
        y += 20;
      });
    }
  }, [settings, selectedStage, width, height, colorSchemes, getCpuColor, getLatencyColor, getBufferColor]);

  // Update history data
  const updateHistoryData = useCallback((data: ProcessingActivityData) => {
    const maxHistoryLength = settings.timeSpan * settings.updateRate;

    setHistoryData(prev => {
      const newHistory = { ...prev };

      // Global CPU history
      if (!newHistory['globalCpu']) newHistory['globalCpu'] = [];
      newHistory['globalCpu'].push(data.globalCpuUsage);
      if (newHistory['globalCpu'].length > maxHistoryLength) {
        newHistory['globalCpu'].shift();
      }

      // Per-stage histories
      data.stages.forEach(stage => {
        const key = `${stage.name}_cpu`;
        if (!newHistory[key]) newHistory[key] = [];
        newHistory[key].push(stage.cpuUsage);
        if (newHistory[key].length > maxHistoryLength) {
          newHistory[key].shift();
        }
      });

      return newHistory;
    });
  }, [settings.timeSpan, settings.updateRate]);

  // Check for alerts
  const checkAlerts = useCallback((data: ProcessingActivityData) => {
    if (!settings.showAlerts || !onAlert) return;

    data.stages.forEach(stage => {
      // CPU alerts
      if (stage.cpuUsage > settings.alertThresholds.cpuCritical) {
        onAlert(stage.name, 'Critical CPU usage', 'high');
      } else if (stage.cpuUsage > settings.alertThresholds.cpuWarning) {
        onAlert(stage.name, 'High CPU usage', 'medium');
      }

      // Latency alerts
      if (stage.latency > settings.alertThresholds.latencyCritical) {
        onAlert(stage.name, 'Critical latency', 'high');
      } else if (stage.latency > settings.alertThresholds.latencyWarning) {
        onAlert(stage.name, 'High latency', 'medium');
      }

      // Buffer alerts
      if (stage.bufferUsage > settings.alertThresholds.bufferWarning) {
        onAlert(stage.name, 'High buffer usage', 'medium');
      }
    });
  }, [settings, onAlert]);

  // Main render function
  const render = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !activityData) return;

    if (!shouldRender()) return;

    startRender();
    updateHistoryData(activityData);
    checkAlerts(activityData);

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
        case 'pipeline':
          drawPipelineView(ctx, activityData);
          break;
        case 'performance':
          drawPerformanceView(ctx, activityData);
          break;
        case 'detailed':
          drawDetailedView(ctx, activityData);
          break;
        default:
          drawPipelineView(ctx, activityData);
      }
    } catch (error) {
      console.error('Processing activity render error:', error);
    }

    endRender();
  }, [
    activityData, settings, width, height, colorSchemes,
    shouldRender, startRender, endRender, updateHistoryData, checkAlerts,
    drawPipelineView, drawPerformanceView, drawDetailedView
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

  // Canvas click handler
  const handleCanvasClick = useCallback((event: React.MouseEvent) => {
    if (!activityData || !onStageClick) return;

    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;

    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    // Check if click is on a stage (simplified)
    if (settings.displayMode === 'pipeline') {
      const stageWidth = 120;
      const spacing = 20;
      const startY = 50;
      const stageHeight = 80;

      activityData.stages.forEach((stage, index) => {
        const stageX = 20 + index * (stageWidth + spacing);
        if (x >= stageX && x <= stageX + stageWidth && y >= startY && y <= startY + stageHeight) {
          setSelectedStage(stage.name);
          onStageClick(stage.name);
        }
      });
    }
  }, [activityData, onStageClick, settings.displayMode]);

  return (
    <Paper className={className} sx={{ p: 2, backgroundColor: '#1A1A1A' }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h6" color="white">
          Processing Activity Monitor
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
          cursor: 'pointer',
          display: 'block',
          margin: '0 auto'
        }}
        onClick={handleCanvasClick}
      />

      {showControls && (
        <Box mt={2}>
          <Grid container spacing={2}>
            <Grid item xs={12} md={3}>
              <Typography gutterBottom>Display Mode</Typography>
              <ToggleButtonGroup
                value={settings.displayMode}
                exclusive
                onChange={(_, value) => value && setSettings(prev => ({ ...prev, displayMode: value }))}
                size="small"
                orientation="vertical"
              >
                <ToggleButton value="pipeline">Pipeline</ToggleButton>
                <ToggleButton value="performance">Performance</ToggleButton>
                <ToggleButton value="detailed">Detailed</ToggleButton>
              </ToggleButtonGroup>
            </Grid>

            <Grid item xs={12} md={3}>
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showCpuUsage}
                    onChange={(e) => setSettings(prev => ({ ...prev, showCpuUsage: e.target.checked }))}
                    color="primary"
                  />
                }
                label="CPU Usage"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showLatency}
                    onChange={(e) => setSettings(prev => ({ ...prev, showLatency: e.target.checked }))}
                    color="primary"
                  />
                }
                label="Latency"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showBufferStatus}
                    onChange={(e) => setSettings(prev => ({ ...prev, showBufferStatus: e.target.checked }))}
                    color="primary"
                  />
                }
                label="Buffer Status"
              />
            </Grid>

            <Grid item xs={12} md={3}>
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showGainReduction}
                    onChange={(e) => setSettings(prev => ({ ...prev, showGainReduction: e.target.checked }))}
                    color="primary"
                  />
                }
                label="Gain Reduction"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showParameters}
                    onChange={(e) => setSettings(prev => ({ ...prev, showParameters: e.target.checked }))}
                    color="primary"
                  />
                }
                label="Parameters"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showAlerts}
                    onChange={(e) => setSettings(prev => ({ ...prev, showAlerts: e.target.checked }))}
                    color="primary"
                  />
                }
                label="Alerts"
              />
            </Grid>

            <Grid item xs={12} md={3}>
              <Typography gutterBottom>Color Scheme</Typography>
              <ToggleButtonGroup
                value={settings.colorScheme}
                exclusive
                onChange={(_, value) => value && setSettings(prev => ({ ...prev, colorScheme: value }))}
                size="small"
              >
                <ToggleButton value="performance">Perf</ToggleButton>
                <ToggleButton value="studio">Studio</ToggleButton>
                <ToggleButton value="debug">Debug</ToggleButton>
              </ToggleButtonGroup>
            </Grid>
          </Grid>

          {activityData && (
            <Box mt={2}>
              <Typography variant="subtitle2" color="white" gutterBottom>
                System Status:
              </Typography>
              <Box display="flex" gap={1} flexWrap="wrap">
                <Chip
                  label={`CPU: ${activityData.globalCpuUsage.toFixed(1)}%`}
                  color={activityData.globalCpuUsage > 80 ? 'error' : activityData.globalCpuUsage > 60 ? 'warning' : 'success'}
                  size="small"
                />
                <Chip
                  label={`Latency: ${activityData.globalLatency.toFixed(1)}ms`}
                  color={activityData.globalLatency > 20 ? 'error' : activityData.globalLatency > 10 ? 'warning' : 'success'}
                  size="small"
                />
                <Chip
                  label={`Underruns: ${activityData.bufferUnderruns}`}
                  color={activityData.bufferUnderruns > 0 ? 'error' : 'success'}
                  size="small"
                />
                <Chip
                  label={`${activityData.sampleRate}Hz/${activityData.bufferSize}`}
                  color="info"
                  size="small"
                />
                <Chip
                  label={activityData.isRealTime ? 'Real-time' : 'Offline'}
                  color={activityData.isRealTime ? 'success' : 'info'}
                  size="small"
                />
              </Box>

              {selectedStage && (
                <Box mt={1}>
                  <Typography variant="caption" color="grey.400">
                    Selected: {selectedStage}
                  </Typography>
                </Box>
              )}
            </Box>
          )}
        </Box>
      )}
    </Paper>
  );
};

export default EnhancedProcessingActivityView;