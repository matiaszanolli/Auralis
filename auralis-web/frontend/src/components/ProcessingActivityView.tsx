import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Box,
  Paper,
  Typography,
  Grid,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Chip,
  LinearProgress,
  IconButton,
  Collapse,
  Card,
  CardContent
} from '@mui/material';
import {
  PlayArrow,
  Pause,
  Stop,
  Settings,
  ExpandMore,
  ExpandLess,
  MusicNote,
  TrendingUp,
  Equalizer,
  Waves,
  Timeline
} from '@mui/icons-material';

interface ProcessingStep {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  progress: number;
  startTime?: number;
  endTime?: number;
  duration?: number;
  parameters?: Record<string, any>;
  metrics?: Record<string, number>;
  icon?: React.ReactNode;
}

interface ProcessingChain {
  id: string;
  name: string;
  steps: ProcessingStep[];
  status: 'idle' | 'running' | 'completed' | 'error';
  totalProgress: number;
  startTime?: number;
  endTime?: number;
}

interface ProcessingMetrics {
  cpuUsage: number;
  memoryUsage: number;
  bufferHealth: number;
  latency: number;
  throughput: number;
  droppedSamples: number;
}

interface ProcessingActivityViewProps {
  processingChains?: ProcessingChain[];
  currentMetrics?: ProcessingMetrics;
  realTimeMode?: boolean;
  onStepClick?: (chainId: string, stepId: string) => void;
  onChainControl?: (chainId: string, action: 'start' | 'pause' | 'stop') => void;
  className?: string;
}

const defaultMetrics: ProcessingMetrics = {
  cpuUsage: 45,
  memoryUsage: 60,
  bufferHealth: 85,
  latency: 12.5,
  throughput: 44100,
  droppedSamples: 0
};

const sampleChains: ProcessingChain[] = [
  {
    id: 'mastering-chain',
    name: 'Mastering Chain',
    status: 'running',
    totalProgress: 65,
    startTime: Date.now() - 30000,
    steps: [
      {
        id: 'analysis',
        name: 'Audio Analysis',
        status: 'completed',
        progress: 100,
        startTime: Date.now() - 30000,
        endTime: Date.now() - 25000,
        duration: 5000,
        icon: <TrendingUp />,
        metrics: { lufs: -16.2, dr: 8.5, thd: 0.02 }
      },
      {
        id: 'eq',
        name: 'Spectral EQ',
        status: 'running',
        progress: 75,
        startTime: Date.now() - 20000,
        icon: <Equalizer />,
        parameters: { highShelf: 2.1, lowCut: 40, presence: 1.5 }
      },
      {
        id: 'compression',
        name: 'Multiband Compression',
        status: 'pending',
        progress: 0,
        icon: <Waves />,
        parameters: { ratio: 3.0, attack: 10, release: 100 }
      },
      {
        id: 'limiting',
        name: 'Peak Limiting',
        status: 'pending',
        progress: 0,
        icon: <Timeline />,
        parameters: { ceiling: -0.1, release: 50 }
      }
    ]
  },
  {
    id: 'reference-match',
    name: 'Reference Matching',
    status: 'idle',
    totalProgress: 0,
    steps: [
      {
        id: 'reference-analysis',
        name: 'Reference Analysis',
        status: 'pending',
        progress: 0,
        icon: <MusicNote />
      },
      {
        id: 'spectral-match',
        name: 'Spectral Matching',
        status: 'pending',
        progress: 0,
        icon: <Equalizer />
      },
      {
        id: 'dynamics-match',
        name: 'Dynamics Matching',
        status: 'pending',
        progress: 0,
        icon: <Waves />
      }
    ]
  }
];

const getStatusColor = (status: string): string => {
  switch (status) {
    case 'completed': return '#4CAF50';
    case 'running': return '#2196F3';
    case 'error': return '#F44336';
    case 'pending': return '#9E9E9E';
    default: return '#9E9E9E';
  }
};

const formatDuration = (milliseconds: number): string => {
  const seconds = milliseconds / 1000;
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}m ${remainingSeconds.toFixed(0)}s`;
};

export const ProcessingActivityView: React.FC<ProcessingActivityViewProps> = ({
  processingChains = sampleChains,
  currentMetrics = defaultMetrics,
  realTimeMode = true,
  onStepClick,
  onChainControl,
  className
}) => {
  const [expandedChains, setExpandedChains] = useState<Set<string>>(new Set(['mastering-chain']));
  const [metricsHistory, setMetricsHistory] = useState<ProcessingMetrics[]>([]);
  const metricsCanvasRef = useRef<HTMLCanvasElement>(null);

  // Update metrics history for real-time monitoring
  useEffect(() => {
    if (!realTimeMode) return;

    const interval = setInterval(() => {
      setMetricsHistory(prev => {
        const newHistory = [...prev, currentMetrics].slice(-100); // Keep last 100 points
        return newHistory;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [realTimeMode, currentMetrics]);

  const drawMetricsGraph = useCallback(() => {
    const canvas = metricsCanvasRef.current;
    if (!canvas || metricsHistory.length < 2) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    // Clear canvas
    ctx.fillStyle = '#1A1A1A';
    ctx.fillRect(0, 0, width, height);

    // Draw grid
    ctx.strokeStyle = '#333333';
    ctx.lineWidth = 1;

    for (let i = 0; i <= 10; i++) {
      const y = (i / 10) * height;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    // Draw metrics
    const metrics = ['cpuUsage', 'memoryUsage', 'bufferHealth'];
    const colors = ['#FF5722', '#4CAF50', '#2196F3'];

    metrics.forEach((metric, index) => {
      ctx.strokeStyle = colors[index];
      ctx.lineWidth = 2;
      ctx.beginPath();

      metricsHistory.forEach((data, i) => {
        const x = (i / (metricsHistory.length - 1)) * width;
        const value = (data as any)[metric];
        const y = height - (value / 100) * height;

        if (i === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      });

      ctx.stroke();
    });

    // Draw legend
    ctx.fillStyle = '#FFFFFF';
    ctx.font = '12px Arial';
    metrics.forEach((metric, index) => {
      ctx.fillStyle = colors[index];
      const y = 20 + index * 20;
      ctx.fillRect(10, y - 10, 15, 10);
      ctx.fillStyle = '#FFFFFF';
      ctx.fillText(metric, 30, y);
    });
  }, [metricsHistory]);

  useEffect(() => {
    drawMetricsGraph();
  }, [drawMetricsGraph]);

  const toggleChainExpansion = (chainId: string) => {
    setExpandedChains(prev => {
      const newSet = new Set(prev);
      if (newSet.has(chainId)) {
        newSet.delete(chainId);
      } else {
        newSet.add(chainId);
      }
      return newSet;
    });
  };

  const handleChainControl = (chainId: string, action: 'start' | 'pause' | 'stop') => {
    onChainControl?.(chainId, action);
  };

  return (
    <Box className={className}>
      <Paper elevation={2} sx={{ p: 2, backgroundColor: '#2A2A2A' }}>
        <Typography variant="h6" gutterBottom sx={{ color: 'white' }}>
          Processing Activity Monitor
        </Typography>

        <Grid container spacing={3}>
          {/* Real-time Metrics */}
          <Grid item xs={12} lg={6}>
            <Card sx={{ backgroundColor: '#1A1A1A', color: 'white' }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  System Metrics
                </Typography>

                <Grid container spacing={2}>
                  <Grid item xs={6}>
                    <Typography variant="body2" gutterBottom>
                      CPU Usage
                    </Typography>
                    <LinearProgress
                      variant="determinate"
                      value={currentMetrics.cpuUsage}
                      sx={{
                        backgroundColor: '#333333',
                        '& .MuiLinearProgress-bar': {
                          backgroundColor: currentMetrics.cpuUsage > 80 ? '#FF5722' : '#4CAF50'
                        }
                      }}
                    />
                    <Typography variant="caption">
                      {currentMetrics.cpuUsage.toFixed(1)}%
                    </Typography>
                  </Grid>

                  <Grid item xs={6}>
                    <Typography variant="body2" gutterBottom>
                      Memory Usage
                    </Typography>
                    <LinearProgress
                      variant="determinate"
                      value={currentMetrics.memoryUsage}
                      sx={{
                        backgroundColor: '#333333',
                        '& .MuiLinearProgress-bar': {
                          backgroundColor: currentMetrics.memoryUsage > 80 ? '#FF5722' : '#4CAF50'
                        }
                      }}
                    />
                    <Typography variant="caption">
                      {currentMetrics.memoryUsage.toFixed(1)}%
                    </Typography>
                  </Grid>

                  <Grid item xs={6}>
                    <Typography variant="body2" gutterBottom>
                      Buffer Health
                    </Typography>
                    <LinearProgress
                      variant="determinate"
                      value={currentMetrics.bufferHealth}
                      sx={{
                        backgroundColor: '#333333',
                        '& .MuiLinearProgress-bar': {
                          backgroundColor: currentMetrics.bufferHealth < 50 ? '#FF5722' : '#4CAF50'
                        }
                      }}
                    />
                    <Typography variant="caption">
                      {currentMetrics.bufferHealth.toFixed(1)}%
                    </Typography>
                  </Grid>

                  <Grid item xs={6}>
                    <Typography variant="body2" gutterBottom>
                      Latency: {currentMetrics.latency.toFixed(1)}ms
                    </Typography>
                    <Typography variant="body2" gutterBottom>
                      Throughput: {(currentMetrics.throughput / 1000).toFixed(1)}kHz
                    </Typography>
                    <Typography variant="body2">
                      Dropped: {currentMetrics.droppedSamples}
                    </Typography>
                  </Grid>
                </Grid>

                {realTimeMode && (
                  <Box sx={{ mt: 2 }}>
                    <Typography variant="subtitle2" gutterBottom>
                      Metrics History
                    </Typography>
                    <canvas
                      ref={metricsCanvasRef}
                      width={300}
                      height={150}
                      style={{
                        border: '1px solid #444',
                        borderRadius: '4px',
                        width: '100%',
                        maxWidth: '300px'
                      }}
                    />
                  </Box>
                )}
              </CardContent>
            </Card>
          </Grid>

          {/* Processing Chains */}
          <Grid item xs={12} lg={6}>
            <Card sx={{ backgroundColor: '#1A1A1A', color: 'white' }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Processing Chains
                </Typography>

                {processingChains.map((chain) => (
                  <Box key={chain.id} sx={{ mb: 2 }}>
                    <Box
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        p: 1,
                        backgroundColor: '#333333',
                        borderRadius: 1,
                        cursor: 'pointer'
                      }}
                      onClick={() => toggleChainExpansion(chain.id)}
                    >
                      <Box sx={{ display: 'flex', alignItems: 'center', flex: 1 }}>
                        <Typography variant="subtitle1" sx={{ mr: 2 }}>
                          {chain.name}
                        </Typography>
                        <Chip
                          label={chain.status}
                          size="small"
                          sx={{
                            backgroundColor: getStatusColor(chain.status),
                            color: 'white',
                            mr: 2
                          }}
                        />
                        {chain.status === 'running' && (
                          <LinearProgress
                            variant="determinate"
                            value={chain.totalProgress}
                            sx={{
                              flex: 1,
                              mr: 2,
                              backgroundColor: '#555555',
                              '& .MuiLinearProgress-bar': {
                                backgroundColor: '#2196F3'
                              }
                            }}
                          />
                        )}
                        {chain.endTime && chain.startTime && (
                          <Typography variant="caption">
                            {formatDuration(chain.endTime - chain.startTime)}
                          </Typography>
                        )}
                      </Box>

                      <Box sx={{ display: 'flex', alignItems: 'center' }}>
                        {chain.status !== 'idle' && (
                          <>
                            <IconButton
                              size="small"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleChainControl(chain.id, chain.status === 'running' ? 'pause' : 'start');
                              }}
                              sx={{ color: 'white', mr: 1 }}
                            >
                              {chain.status === 'running' ? <Pause /> : <PlayArrow />}
                            </IconButton>
                            <IconButton
                              size="small"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleChainControl(chain.id, 'stop');
                              }}
                              sx={{ color: 'white', mr: 1 }}
                            >
                              <Stop />
                            </IconButton>
                          </>
                        )}
                        <IconButton size="small" sx={{ color: 'white' }}>
                          {expandedChains.has(chain.id) ? <ExpandLess /> : <ExpandMore />}
                        </IconButton>
                      </Box>
                    </Box>

                    <Collapse in={expandedChains.has(chain.id)}>
                      <List dense sx={{ pl: 2 }}>
                        {chain.steps.map((step) => (
                          <ListItem
                            key={step.id}
                            button={!!onStepClick}
                            onClick={() => onStepClick?.(chain.id, step.id)}
                            sx={{
                              borderLeft: `3px solid ${getStatusColor(step.status)}`,
                              mb: 1,
                              backgroundColor: '#2A2A2A',
                              borderRadius: 1
                            }}
                          >
                            <ListItemIcon sx={{ color: getStatusColor(step.status) }}>
                              {step.icon || <Settings />}
                            </ListItemIcon>
                            <ListItemText
                              primary={
                                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                  <Typography variant="body2">{step.name}</Typography>
                                  <Box sx={{ display: 'flex', alignItems: 'center' }}>
                                    <Chip
                                      label={step.status}
                                      size="small"
                                      sx={{
                                        backgroundColor: getStatusColor(step.status),
                                        color: 'white',
                                        mr: 1,
                                        fontSize: '0.7rem'
                                      }}
                                    />
                                    {step.duration && (
                                      <Typography variant="caption">
                                        {formatDuration(step.duration)}
                                      </Typography>
                                    )}
                                  </Box>
                                </Box>
                              }
                              secondary={
                                <Box>
                                  {step.status === 'running' && (
                                    <LinearProgress
                                      variant="determinate"
                                      value={step.progress}
                                      size="small"
                                      sx={{
                                        mt: 1,
                                        backgroundColor: '#555555',
                                        '& .MuiLinearProgress-bar': {
                                          backgroundColor: '#2196F3'
                                        }
                                      }}
                                    />
                                  )}
                                  {step.parameters && (
                                    <Box sx={{ mt: 1 }}>
                                      {Object.entries(step.parameters).map(([key, value]) => (
                                        <Typography key={key} variant="caption" sx={{ mr: 2, color: '#CCCCCC' }}>
                                          {key}: {typeof value === 'number' ? value.toFixed(1) : value}
                                        </Typography>
                                      ))}
                                    </Box>
                                  )}
                                  {step.metrics && (
                                    <Box sx={{ mt: 1 }}>
                                      {Object.entries(step.metrics).map(([key, value]) => (
                                        <Typography key={key} variant="caption" sx={{ mr: 2, color: '#4CAF50' }}>
                                          {key}: {value.toFixed(2)}
                                        </Typography>
                                      ))}
                                    </Box>
                                  )}
                                </Box>
                              }
                            />
                          </ListItem>
                        ))}
                      </List>
                    </Collapse>
                  </Box>
                ))}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </Paper>
    </Box>
  );
};

export default ProcessingActivityView;