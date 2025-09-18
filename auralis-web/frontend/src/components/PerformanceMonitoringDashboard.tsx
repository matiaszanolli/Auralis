import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  Grid,
  Card,
  CardContent,
  LinearProgress,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Switch,
  FormControlLabel,
  IconButton,
  Tooltip,
  Alert,
} from '@mui/material';
import {
  TrendingUp,
  TrendingDown,
  Warning,
  CheckCircle,
  Error,
  Speed,
  Memory,
  NetworkCheck,
  Timeline,
  GetApp,
} from '@mui/icons-material';

import { useAdvancedPerformanceOptimization } from '../utils/AdvancedPerformanceOptimizer';
import { useRealTimeAnalysisStream } from '../services/RealTimeAnalysisStream';
import { useSmoothAnimation } from '../utils/SmoothAnimationEngine';

interface PerformanceAlert {
  id: string;
  type: 'cpu' | 'memory' | 'network' | 'buffer' | 'quality';
  severity: 'low' | 'medium' | 'high' | 'critical';
  message: string;
  timestamp: number;
  resolved: boolean;
}

interface PerformanceMonitoringDashboardProps {
  className?: string;
  onAlert?: (alert: PerformanceAlert) => void;
  onExportReport?: () => void;
  real_time?: boolean;
}

export const PerformanceMonitoringDashboard: React.FC<PerformanceMonitoringDashboardProps> = ({
  className,
  onAlert,
  onExportReport,
  real_time = true,
}) => {
  const { metrics, profile, optimizer } = useAdvancedPerformanceOptimization();
  const { metrics: streamMetrics, isConnected } = useRealTimeAnalysisStream();
  const { animateAudioLevel, getFps } = useSmoothAnimation();

  // State
  const [alerts, setAlerts] = useState<PerformanceAlert[]>([]);
  const [showDetailedMetrics, setShowDetailedMetrics] = useState(false);
  const [performanceHistory, setPerformanceHistory] = useState<{
    fps: number[];
    cpu: number[];
    memory: number[];
    latency: number[];
    timestamps: number[];
  }>({
    fps: [],
    cpu: [],
    memory: [],
    latency: [],
    timestamps: [],
  });

  // Chart canvas ref
  const chartCanvasRef = useRef<HTMLCanvasElement>(null);

  // Performance thresholds
  const thresholds = {
    cpu: { warning: 70, critical: 90 },
    memory: { warning: 1024, critical: 2048 }, // MB
    fps: { warning: 30, critical: 15 },
    latency: { warning: 50, critical: 100 }, // ms
    bufferHealth: { warning: 0.8, critical: 0.9 },
  };

  // Update performance history
  useEffect(() => {
    if (!real_time) return;

    const interval = setInterval(() => {
      const now = Date.now();
      setPerformanceHistory(prev => {
        const maxHistory = 100; // Keep last 100 data points

        const newHistory = {
          fps: [...prev.fps, metrics.fps].slice(-maxHistory),
          cpu: [...prev.cpu, metrics.cpuUsage].slice(-maxHistory),
          memory: [...prev.memory, metrics.memoryUsage].slice(-maxHistory),
          latency: [...prev.latency, streamMetrics?.latency || 0].slice(-maxHistory),
          timestamps: [...prev.timestamps, now].slice(-maxHistory),
        };

        return newHistory;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [real_time, metrics, streamMetrics]);

  // Alert monitoring
  useEffect(() => {
    const checkAlerts = () => {
      const newAlerts: PerformanceAlert[] = [];

      // CPU alerts
      if (metrics.cpuUsage > thresholds.cpu.critical) {
        newAlerts.push({
          id: `cpu_critical_${Date.now()}`,
          type: 'cpu',
          severity: 'critical',
          message: `Critical CPU usage: ${metrics.cpuUsage.toFixed(1)}%`,
          timestamp: Date.now(),
          resolved: false,
        });
      } else if (metrics.cpuUsage > thresholds.cpu.warning) {
        newAlerts.push({
          id: `cpu_warning_${Date.now()}`,
          type: 'cpu',
          severity: 'medium',
          message: `High CPU usage: ${metrics.cpuUsage.toFixed(1)}%`,
          timestamp: Date.now(),
          resolved: false,
        });
      }

      // Memory alerts
      if (metrics.memoryUsage > thresholds.memory.critical) {
        newAlerts.push({
          id: `memory_critical_${Date.now()}`,
          type: 'memory',
          severity: 'critical',
          message: `Critical memory usage: ${metrics.memoryUsage.toFixed(1)}MB`,
          timestamp: Date.now(),
          resolved: false,
        });
      } else if (metrics.memoryUsage > thresholds.memory.warning) {
        newAlerts.push({
          id: `memory_warning_${Date.now()}`,
          type: 'memory',
          severity: 'medium',
          message: `High memory usage: ${metrics.memoryUsage.toFixed(1)}MB`,
          timestamp: Date.now(),
          resolved: false,
        });
      }

      // FPS alerts
      if (metrics.fps < thresholds.fps.critical) {
        newAlerts.push({
          id: `fps_critical_${Date.now()}`,
          type: 'quality',
          severity: 'critical',
          message: `Critical FPS drop: ${metrics.fps.toFixed(1)}fps`,
          timestamp: Date.now(),
          resolved: false,
        });
      } else if (metrics.fps < thresholds.fps.warning) {
        newAlerts.push({
          id: `fps_warning_${Date.now()}`,
          type: 'quality',
          severity: 'medium',
          message: `Low FPS: ${metrics.fps.toFixed(1)}fps`,
          timestamp: Date.now(),
          resolved: false,
        });
      }

      // Network/streaming alerts
      if (streamMetrics) {
        if (streamMetrics.packetsDropped > 10) {
          newAlerts.push({
            id: `network_drops_${Date.now()}`,
            type: 'network',
            severity: 'medium',
            message: `Packet drops detected: ${streamMetrics.packetsDropped}`,
            timestamp: Date.now(),
            resolved: false,
          });
        }

        if (streamMetrics.latency > thresholds.latency.critical) {
          newAlerts.push({
            id: `latency_critical_${Date.now()}`,
            type: 'network',
            severity: 'high',
            message: `High network latency: ${streamMetrics.latency.toFixed(1)}ms`,
            timestamp: Date.now(),
            resolved: false,
          });
        }
      }

      // Buffer health alerts
      if (metrics.bufferHealth > thresholds.bufferHealth.critical) {
        newAlerts.push({
          id: `buffer_critical_${Date.now()}`,
          type: 'buffer',
          severity: 'critical',
          message: `Buffer overflow risk: ${(metrics.bufferHealth * 100).toFixed(1)}%`,
          timestamp: Date.now(),
          resolved: false,
        });
      }

      // Add new alerts and notify
      if (newAlerts.length > 0) {
        setAlerts(prev => [...prev, ...newAlerts].slice(-20)); // Keep last 20 alerts
        newAlerts.forEach(alert => onAlert?.(alert));
      }
    };

    const interval = setInterval(checkAlerts, 2000);
    return () => clearInterval(interval);
  }, [metrics, streamMetrics, onAlert]);

  // Draw performance chart
  const drawPerformanceChart = useCallback(() => {
    const canvas = chartCanvasRef.current;
    if (!canvas || performanceHistory.fps.length < 2) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const { width, height } = canvas;
    ctx.clearRect(0, 0, width, height);

    // Chart settings
    const padding = 40;
    const chartWidth = width - padding * 2;
    const chartHeight = height - padding * 2;

    // Draw background
    ctx.fillStyle = '#0A0A0A';
    ctx.fillRect(0, 0, width, height);

    // Draw grid
    ctx.strokeStyle = '#333333';
    ctx.lineWidth = 1;
    ctx.setLineDash([2, 4]);

    // Horizontal grid lines
    for (let i = 0; i <= 5; i++) {
      const y = padding + (i / 5) * chartHeight;
      ctx.beginPath();
      ctx.moveTo(padding, y);
      ctx.lineTo(width - padding, y);
      ctx.stroke();
    }

    // Vertical grid lines
    for (let i = 0; i <= 10; i++) {
      const x = padding + (i / 10) * chartWidth;
      ctx.beginPath();
      ctx.moveTo(x, padding);
      ctx.lineTo(x, height - padding);
      ctx.stroke();
    }

    ctx.setLineDash([]);

    // Draw performance lines
    const drawLine = (data: number[], color: string, maxValue: number) => {
      if (data.length < 2) return;

      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.beginPath();

      data.forEach((value, index) => {
        const x = padding + (index / (data.length - 1)) * chartWidth;
        const y = height - padding - (value / maxValue) * chartHeight;

        if (index === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      });

      ctx.stroke();
    };

    // Draw lines for different metrics
    drawLine(performanceHistory.fps, '#4FC3F7', 60); // FPS (0-60)
    drawLine(performanceHistory.cpu, '#FF6B6B', 100); // CPU (0-100%)
    drawLine(performanceHistory.memory.map(m => m / 10), '#FFB74D', 100); // Memory (scaled)
    drawLine(performanceHistory.latency, '#34D399', 100); // Latency (0-100ms)

    // Draw legend
    ctx.fillStyle = '#FFFFFF';
    ctx.font = '12px sans-serif';
    const legends = [
      { text: 'FPS', color: '#4FC3F7' },
      { text: 'CPU%', color: '#FF6B6B' },
      { text: 'Memory/10', color: '#FFB74D' },
      { text: 'Latency', color: '#34D399' },
    ];

    legends.forEach((legend, index) => {
      const x = padding + index * 80;
      const y = 20;

      ctx.fillStyle = legend.color;
      ctx.fillRect(x, y - 5, 10, 10);
      ctx.fillStyle = '#FFFFFF';
      ctx.fillText(legend.text, x + 15, y + 5);
    });
  }, [performanceHistory]);

  // Update chart
  useEffect(() => {
    drawPerformanceChart();
  }, [drawPerformanceChart]);

  // Canvas setup
  useEffect(() => {
    const canvas = chartCanvasRef.current;
    if (!canvas) return;

    canvas.width = 600;
    canvas.height = 200;
  }, []);

  // Get status color
  const getStatusColor = (value: number, thresholds: { warning: number; critical: number }, inverse = false) => {
    if (inverse) {
      if (value < thresholds.critical) return 'error';
      if (value < thresholds.warning) return 'warning';
      return 'success';
    } else {
      if (value > thresholds.critical) return 'error';
      if (value > thresholds.warning) return 'warning';
      return 'success';
    }
  };

  // Get trend icon
  const getTrendIcon = (current: number, history: number[]) => {
    if (history.length < 2) return null;

    const previous = history[history.length - 2];
    const trend = current - previous;

    if (Math.abs(trend) < 0.1) return null;
    return trend > 0 ? <TrendingUp color="error" /> : <TrendingDown color="success" />;
  };

  const handleExportReport = () => {
    const report = {
      timestamp: new Date().toISOString(),
      currentMetrics: metrics,
      streamMetrics,
      profile: profile.name,
      performanceHistory,
      alerts: alerts.filter(a => !a.resolved),
      systemInfo: {
        userAgent: navigator.userAgent,
        platform: navigator.platform,
        memory: (navigator as any).deviceMemory,
        cores: navigator.hardwareConcurrency,
      },
    };

    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `auralis-performance-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);

    onExportReport?.();
  };

  // Active alerts
  const activeAlerts = alerts.filter(a => !a.resolved);
  const criticalAlerts = activeAlerts.filter(a => a.severity === 'critical');

  return (
    <Paper className={className} sx={{ p: 3, backgroundColor: '#1A1A1A' }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5" color="white">
          Performance Monitoring Dashboard
        </Typography>
        <Box display="flex" gap={1} alignItems="center">
          <Chip
            label={profile.name.toUpperCase()}
            color={profile.name === 'minimal' ? 'error' : profile.name === 'ultra' ? 'success' : 'warning'}
            size="small"
          />
          <Tooltip title="Export Performance Report">
            <IconButton onClick={handleExportReport} sx={{ color: 'white' }}>
              <GetApp />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Critical Alerts */}
      {criticalAlerts.length > 0 && (
        <Alert severity="error" sx={{ mb: 2 }}>
          <Typography variant="h6">Critical Performance Issues Detected!</Typography>
          {criticalAlerts.map(alert => (
            <Typography key={alert.id} variant="body2">
              • {alert.message}
            </Typography>
          ))}
        </Alert>
      )}

      {/* Key Metrics Grid */}
      <Grid container spacing={3} mb={3}>
        <Grid item xs={12} md={3}>
          <Card sx={{ backgroundColor: '#2A2A2A' }}>
            <CardContent>
              <Box display="flex" alignItems="center" justifyContent="space-between">
                <Box>
                  <Typography color="grey.400" variant="caption">
                    FPS
                  </Typography>
                  <Typography variant="h4" color="white">
                    {metrics.fps.toFixed(1)}
                  </Typography>
                </Box>
                <Box display="flex" alignItems="center">
                  {getTrendIcon(metrics.fps, performanceHistory.fps)}
                  <Speed color={getStatusColor(metrics.fps, thresholds.fps, true) as any} />
                </Box>
              </Box>
              <LinearProgress
                variant="determinate"
                value={(metrics.fps / 60) * 100}
                color={getStatusColor(metrics.fps, thresholds.fps, true) as any}
                sx={{ mt: 1 }}
              />
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card sx={{ backgroundColor: '#2A2A2A' }}>
            <CardContent>
              <Box display="flex" alignItems="center" justifyContent="space-between">
                <Box>
                  <Typography color="grey.400" variant="caption">
                    CPU Usage
                  </Typography>
                  <Typography variant="h4" color="white">
                    {metrics.cpuUsage.toFixed(1)}%
                  </Typography>
                </Box>
                <Box display="flex" alignItems="center">
                  {getTrendIcon(metrics.cpuUsage, performanceHistory.cpu)}
                  <Speed color={getStatusColor(metrics.cpuUsage, thresholds.cpu) as any} />
                </Box>
              </Box>
              <LinearProgress
                variant="determinate"
                value={metrics.cpuUsage}
                color={getStatusColor(metrics.cpuUsage, thresholds.cpu) as any}
                sx={{ mt: 1 }}
              />
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card sx={{ backgroundColor: '#2A2A2A' }}>
            <CardContent>
              <Box display="flex" alignItems="center" justifyContent="space-between">
                <Box>
                  <Typography color="grey.400" variant="caption">
                    Memory
                  </Typography>
                  <Typography variant="h4" color="white">
                    {metrics.memoryUsage.toFixed(0)}MB
                  </Typography>
                </Box>
                <Box display="flex" alignItems="center">
                  {getTrendIcon(metrics.memoryUsage, performanceHistory.memory)}
                  <Memory color={getStatusColor(metrics.memoryUsage, thresholds.memory) as any} />
                </Box>
              </Box>
              <LinearProgress
                variant="determinate"
                value={(metrics.memoryUsage / 2048) * 100}
                color={getStatusColor(metrics.memoryUsage, thresholds.memory) as any}
                sx={{ mt: 1 }}
              />
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={3}>
          <Card sx={{ backgroundColor: '#2A2A2A' }}>
            <CardContent>
              <Box display="flex" alignItems="center" justifyContent="space-between">
                <Box>
                  <Typography color="grey.400" variant="caption">
                    Network
                  </Typography>
                  <Typography variant="h4" color="white">
                    {streamMetrics?.latency.toFixed(0) || '0'}ms
                  </Typography>
                </Box>
                <Box display="flex" alignItems="center">
                  {isConnected ? <CheckCircle color="success" /> : <Error color="error" />}
                  <NetworkCheck color={isConnected ? 'success' : 'error'} />
                </Box>
              </Box>
              <LinearProgress
                variant="determinate"
                value={((streamMetrics?.latency || 0) / 100) * 100}
                color={getStatusColor(streamMetrics?.latency || 0, thresholds.latency) as any}
                sx={{ mt: 1 }}
              />
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Performance Chart */}
      <Paper sx={{ p: 2, backgroundColor: '#2A2A2A', mb: 3 }}>
        <Typography variant="h6" color="white" gutterBottom>
          Performance History
        </Typography>
        <canvas
          ref={chartCanvasRef}
          style={{
            width: '100%',
            height: 200,
            border: '1px solid #333',
          }}
        />
      </Paper>

      {/* Detailed Metrics Toggle */}
      <FormControlLabel
        control={
          <Switch
            checked={showDetailedMetrics}
            onChange={(e) => setShowDetailedMetrics(e.target.checked)}
            color="primary"
          />
        }
        label="Show Detailed Metrics"
        sx={{ color: 'white', mb: 2 }}
      />

      {/* Detailed Metrics */}
      {showDetailedMetrics && (
        <Grid container spacing={3}>
          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 2, backgroundColor: '#2A2A2A' }}>
              <Typography variant="h6" color="white" gutterBottom>
                Rendering Metrics
              </Typography>
              <TableContainer>
                <Table size="small">
                  <TableBody>
                    <TableRow>
                      <TableCell sx={{ color: 'grey.400' }}>Frame Time</TableCell>
                      <TableCell sx={{ color: 'white' }}>{metrics.frameTime.toFixed(2)}ms</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell sx={{ color: 'grey.400' }}>Render Time</TableCell>
                      <TableCell sx={{ color: 'white' }}>{metrics.renderTime.toFixed(2)}ms</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell sx={{ color: 'grey.400' }}>Dropped Frames</TableCell>
                      <TableCell sx={{ color: 'white' }}>{metrics.droppedFrames}</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell sx={{ color: 'grey.400' }}>Data Points</TableCell>
                      <TableCell sx={{ color: 'white' }}>{metrics.dataPoints}</TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell sx={{ color: 'grey.400' }}>Quality Level</TableCell>
                      <TableCell sx={{ color: 'white' }}>{(metrics.adaptiveQuality * 100).toFixed(0)}%</TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </TableContainer>
            </Paper>
          </Grid>

          <Grid item xs={12} md={6}>
            <Paper sx={{ p: 2, backgroundColor: '#2A2A2A' }}>
              <Typography variant="h6" color="white" gutterBottom>
                Stream Metrics
              </Typography>
              {streamMetrics ? (
                <TableContainer>
                  <Table size="small">
                    <TableBody>
                      <TableRow>
                        <TableCell sx={{ color: 'grey.400' }}>Packets Received</TableCell>
                        <TableCell sx={{ color: 'white' }}>{streamMetrics.packetsReceived}</TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell sx={{ color: 'grey.400' }}>Packets Dropped</TableCell>
                        <TableCell sx={{ color: 'white' }}>{streamMetrics.packetsDropped}</TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell sx={{ color: 'grey.400' }}>Jitter</TableCell>
                        <TableCell sx={{ color: 'white' }}>{streamMetrics.jitter.toFixed(2)}ms</TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell sx={{ color: 'grey.400' }}>Buffer Health</TableCell>
                        <TableCell sx={{ color: 'white' }}>{(streamMetrics.bufferHealth * 100).toFixed(1)}%</TableCell>
                      </TableRow>
                      <TableRow>
                        <TableCell sx={{ color: 'grey.400' }}>Data Rate</TableCell>
                        <TableCell sx={{ color: 'white' }}>{streamMetrics.dataRate.toFixed(1)} KB/s</TableCell>
                      </TableRow>
                    </TableBody>
                  </Table>
                </TableContainer>
              ) : (
                <Typography color="grey.400">No stream data available</Typography>
              )}
            </Paper>
          </Grid>
        </Grid>
      )}

      {/* Recent Alerts */}
      {activeAlerts.length > 0 && (
        <Paper sx={{ p: 2, backgroundColor: '#2A2A2A', mt: 3 }}>
          <Typography variant="h6" color="white" gutterBottom>
            Recent Alerts ({activeAlerts.length})
          </Typography>
          <Box display="flex" flexDirection="column" gap={1}>
            {activeAlerts.slice(-5).map(alert => (
              <Box
                key={alert.id}
                display="flex"
                alignItems="center"
                gap={1}
                p={1}
                sx={{
                  backgroundColor: alert.severity === 'critical' ? '#4A1A1A' : '#4A4A1A',
                  borderRadius: 1,
                }}
              >
                {alert.severity === 'critical' ? <Error color="error" /> : <Warning color="warning" />}
                <Typography variant="body2" color="white">
                  {alert.message}
                </Typography>
                <Typography variant="caption" color="grey.400" sx={{ ml: 'auto' }}>
                  {new Date(alert.timestamp).toLocaleTimeString()}
                </Typography>
              </Box>
            ))}
          </Box>
        </Paper>
      )}
    </Paper>
  );
};

export default PerformanceMonitoringDashboard;