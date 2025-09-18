import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Box, Paper, Typography, Switch, FormControlLabel, Grid, Slider } from '@mui/material';
import { useVisualizationOptimization } from '../hooks/useVisualizationOptimization';

// Types for meter data that matches our Phase 5.1 analysis
interface MeterData {
  // Loudness metering (LUFS)
  momentary_loudness: number;
  short_term_loudness: number;
  integrated_loudness: number;
  loudness_range: number;

  // Peak metering
  peak_dbfs: number;
  true_peak_dbfs: number;

  // RMS levels
  rms_left: number;
  rms_right: number;

  // Phase and correlation
  correlation_coefficient: number;
  phase_coherence: number;
  stereo_width: number;

  // Dynamic range
  crest_factor: number;
  dynamic_range: number;

  // Clipping detection
  clipping_detected: boolean;
  clip_count: number;

  // Analysis settings
  sample_rate?: number;
  channels?: number;
}

interface MeterSettings {
  showLUFS: boolean;
  showPeaks: boolean;
  showRMS: boolean;
  showCorrelation: boolean;
  showDynamics: boolean;
  showClipping: boolean;
  enablePeakHold: boolean;
  peakHoldTime: number; // seconds
  enableOverloadWarning: boolean;
  meterOrientation: 'vertical' | 'horizontal';
  colorScheme: 'broadcast' | 'music' | 'mastering' | 'vintage';
  updateRate: number; // Hz
  ballistics: 'fast' | 'medium' | 'slow';
}

interface MeterBridgeProps {
  meterData?: MeterData;
  width?: number;
  height?: number;
  showControls?: boolean;
  className?: string;
  real_time?: boolean;
  onOverload?: (channel: string, level: number) => void;
  onCorrelationAlert?: (correlation: number) => void;
}

const defaultSettings: MeterSettings = {
  showLUFS: true,
  showPeaks: true,
  showRMS: true,
  showCorrelation: true,
  showDynamics: false,
  showClipping: true,
  enablePeakHold: true,
  peakHoldTime: 2.0,
  enableOverloadWarning: true,
  meterOrientation: 'vertical',
  colorScheme: 'broadcast',
  updateRate: 30,
  ballistics: 'medium',
};

// Color schemes for different meter types
const colorSchemes = {
  broadcast: {
    safe: '#00FF00',      // Green: -20dB and below
    caution: '#FFFF00',   // Yellow: -20dB to -10dB
    warning: '#FF8000',   // Orange: -10dB to -3dB
    danger: '#FF0000',    // Red: -3dB and above
    background: '#1A1A1A',
    grid: '#333333',
    text: '#FFFFFF',
  },
  music: {
    safe: '#4CAF50',
    caution: '#FFC107',
    warning: '#FF9800',
    danger: '#F44336',
    background: '#0D1117',
    grid: '#30363D',
    text: '#F0F6FC',
  },
  mastering: {
    safe: '#00C851',
    caution: '#FFB700',
    warning: '#FF6900',
    danger: '#FF0039',
    background: '#000000',
    grid: '#444444',
    text: '#FFFFFF',
  },
  vintage: {
    safe: '#00FF7F',
    caution: '#FFFF32',
    warning: '#FF7F00',
    danger: '#FF3232',
    background: '#2F2F2F',
    grid: '#5F5F5F',
    text: '#E0E0E0',
  },
};

export const MeterBridge: React.FC<MeterBridgeProps> = ({
  meterData,
  width = 600,
  height = 300,
  showControls = true,
  className,
  real_time = true,
  onOverload,
  onCorrelationAlert,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationFrameRef = useRef<number>();
  const [settings, setSettings] = useState<MeterSettings>(defaultSettings);
  const [peakHolds, setPeakHolds] = useState<{ [key: string]: { value: number; timestamp: number } }>({});
  const [alertState, setAlertState] = useState<{ overload: boolean; correlation: boolean }>({
    overload: false,
    correlation: false,
  });

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

  // Convert dB to meter position (0-1)
  const dbToMeterPos = useCallback((db: number, range: { min: number; max: number } = { min: -60, max: 0 }): number => {
    return Math.max(0, Math.min(1, (db - range.min) / (range.max - range.min)));
  }, []);

  // Get color for dB level
  const getColorForLevel = useCallback((db: number): string => {
    const colors = colorSchemes[settings.colorScheme];

    if (db <= -20) return colors.safe;
    if (db <= -10) return colors.caution;
    if (db <= -3) return colors.warning;
    return colors.danger;
  }, [settings.colorScheme]);

  // Draw vertical meter
  const drawVerticalMeter = useCallback((
    ctx: CanvasRenderingContext2D,
    x: number,
    width: number,
    value: number,
    label: string,
    range: { min: number; max: number } = { min: -60, max: 0 }
  ) => {
    const meterHeight = height - 60; // Leave space for labels
    const meterY = 30;

    // Background
    ctx.fillStyle = colorSchemes[settings.colorScheme].background;
    ctx.fillRect(x, meterY, width, meterHeight);

    // Grid lines
    ctx.strokeStyle = colorSchemes[settings.colorScheme].grid;
    ctx.lineWidth = 1;
    const gridSteps = [-60, -40, -20, -12, -6, -3, 0];

    gridSteps.forEach(step => {
      const y = meterY + meterHeight - (dbToMeterPos(step, range) * meterHeight);
      ctx.beginPath();
      ctx.moveTo(x, y);
      ctx.lineTo(x + width, y);
      ctx.stroke();

      // Grid labels
      ctx.fillStyle = colorSchemes[settings.colorScheme].text;
      ctx.font = '8px sans-serif';
      ctx.fillText(`${step}`, x + width + 2, y + 3);
    });

    // Meter fill
    const fillHeight = dbToMeterPos(value, range) * meterHeight;
    const fillY = meterY + meterHeight - fillHeight;

    // Create gradient fill
    const gradient = ctx.createLinearGradient(0, meterY + meterHeight, 0, meterY);
    gradient.addColorStop(0, getColorForLevel(-60));
    gradient.addColorStop(0.3, getColorForLevel(-20));
    gradient.addColorStop(0.7, getColorForLevel(-10));
    gradient.addColorStop(0.9, getColorForLevel(-3));
    gradient.addColorStop(1, getColorForLevel(0));

    ctx.fillStyle = gradient;
    ctx.fillRect(x + 1, fillY, width - 2, fillHeight);

    // Peak hold
    if (settings.enablePeakHold) {
      const peakHold = peakHolds[label];
      if (peakHold) {
        const peakY = meterY + meterHeight - (dbToMeterPos(peakHold.value, range) * meterHeight);
        ctx.fillStyle = '#FFFFFF';
        ctx.fillRect(x, peakY - 1, width, 2);
      }
    }

    // Overload indicator
    if (value >= -0.1 && settings.enableOverloadWarning) {
      ctx.fillStyle = '#FF0000';
      ctx.fillRect(x, meterY - 10, width, 8);

      if (onOverload) {
        onOverload(label, value);
      }
    }

    // Label
    ctx.fillStyle = colorSchemes[settings.colorScheme].text;
    ctx.font = '12px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(label, x + width / 2, height - 5);

    // Value display
    ctx.font = '10px sans-serif';
    ctx.fillText(`${value.toFixed(1)}`, x + width / 2, height - 20);

    ctx.textAlign = 'left';
  }, [height, settings, colorSchemes, dbToMeterPos, getColorForLevel, peakHolds, onOverload]);

  // Draw LUFS meter
  const drawLUFSMeter = useCallback((ctx: CanvasRenderingContext2D, data: MeterData) => {
    if (!settings.showLUFS) return;

    const startX = 20;
    const meterWidth = 30;
    const spacing = 40;

    // Momentary LUFS
    drawVerticalMeter(ctx, startX, meterWidth, data.momentary_loudness, 'M-LUFS', { min: -60, max: 0 });

    // Short-term LUFS
    drawVerticalMeter(ctx, startX + spacing, meterWidth, data.short_term_loudness, 'S-LUFS', { min: -60, max: 0 });

    // Integrated LUFS
    drawVerticalMeter(ctx, startX + spacing * 2, meterWidth, data.integrated_loudness, 'I-LUFS', { min: -60, max: 0 });

    // Loudness Range
    ctx.fillStyle = colorSchemes[settings.colorScheme].text;
    ctx.font = '12px sans-serif';
    ctx.fillText(`LRA: ${data.loudness_range.toFixed(1)} LU`, startX + spacing * 3, 25);
  }, [settings.showLUFS, drawVerticalMeter, colorSchemes, settings.colorScheme]);

  // Draw peak meters
  const drawPeakMeters = useCallback((ctx: CanvasRenderingContext2D, data: MeterData) => {
    if (!settings.showPeaks) return;

    const startX = 200;
    const meterWidth = 30;
    const spacing = 40;

    // Peak dBFS
    drawVerticalMeter(ctx, startX, meterWidth, data.peak_dbfs, 'Peak', { min: -60, max: 6 });

    // True Peak dBFS
    drawVerticalMeter(ctx, startX + spacing, meterWidth, data.true_peak_dbfs, 'TP', { min: -60, max: 6 });
  }, [settings.showPeaks, drawVerticalMeter]);

  // Draw RMS meters
  const drawRMSMeters = useCallback((ctx: CanvasRenderingContext2D, data: MeterData) => {
    if (!settings.showRMS) return;

    const startX = 320;
    const meterWidth = 25;
    const spacing = 35;

    // Left RMS
    drawVerticalMeter(ctx, startX, meterWidth, data.rms_left, 'L-RMS', { min: -60, max: 0 });

    // Right RMS
    drawVerticalMeter(ctx, startX + spacing, meterWidth, data.rms_right, 'R-RMS', { min: -60, max: 0 });
  }, [settings.showRMS, drawVerticalMeter]);

  // Draw correlation display
  const drawCorrelationDisplay = useCallback((ctx: CanvasRenderingContext2D, data: MeterData) => {
    if (!settings.showCorrelation) return;

    const startX = 420;
    const displayWidth = 100;
    const displayHeight = 60;
    const centerY = height / 2;

    // Background
    ctx.fillStyle = colorSchemes[settings.colorScheme].background;
    ctx.fillRect(startX, centerY - displayHeight / 2, displayWidth, displayHeight);
    ctx.strokeStyle = colorSchemes[settings.colorScheme].grid;
    ctx.strokeRect(startX, centerY - displayHeight / 2, displayWidth, displayHeight);

    // Correlation meter (horizontal)
    const corrPos = (data.correlation_coefficient + 1) / 2; // Convert -1:1 to 0:1
    const corrX = startX + corrPos * displayWidth;

    // Correlation background gradient
    const gradient = ctx.createLinearGradient(startX, 0, startX + displayWidth, 0);
    gradient.addColorStop(0, '#FF0000'); // Anti-phase
    gradient.addColorStop(0.5, '#FFFF00'); // Uncorrelated
    gradient.addColorStop(1, '#00FF00'); // In-phase

    ctx.fillStyle = gradient;
    ctx.fillRect(startX + 2, centerY - 5, displayWidth - 4, 10);

    // Correlation indicator
    ctx.fillStyle = '#FFFFFF';
    ctx.fillRect(corrX - 2, centerY - 15, 4, 30);

    // Labels
    ctx.fillStyle = colorSchemes[settings.colorScheme].text;
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('Correlation', startX + displayWidth / 2, centerY - 25);
    ctx.fillText(data.correlation_coefficient.toFixed(2), startX + displayWidth / 2, centerY + 25);

    // Stereo width display
    ctx.fillText(`Width: ${data.stereo_width.toFixed(2)}`, startX + displayWidth / 2, centerY + 40);

    ctx.textAlign = 'left';

    // Correlation alert
    if (Math.abs(data.correlation_coefficient) < 0.5 && onCorrelationAlert) {
      onCorrelationAlert(data.correlation_coefficient);
    }
  }, [settings.showCorrelation, height, colorSchemes, settings.colorScheme, onCorrelationAlert]);

  // Draw dynamics display
  const drawDynamicsDisplay = useCallback((ctx: CanvasRenderingContext2D, data: MeterData) => {
    if (!settings.showDynamics) return;

    const startX = 540;

    ctx.fillStyle = colorSchemes[settings.colorScheme].text;
    ctx.font = '12px sans-serif';
    ctx.fillText(`DR: ${data.dynamic_range.toFixed(1)}`, startX, 30);
    ctx.fillText(`Crest: ${data.crest_factor.toFixed(1)}dB`, startX, 50);

    // Clipping indicator
    if (data.clipping_detected) {
      ctx.fillStyle = '#FF0000';
      ctx.fillText('CLIP!', startX, 70);
      ctx.fillText(`Count: ${data.clip_count}`, startX, 90);
    }
  }, [settings.showDynamics, colorSchemes, settings.colorScheme]);

  // Update peak holds
  const updatePeakHolds = useCallback((data: MeterData) => {
    if (!settings.enablePeakHold) return;

    const now = Date.now();
    const channels = ['Peak', 'TP', 'L-RMS', 'R-RMS', 'M-LUFS', 'S-LUFS', 'I-LUFS'];
    const values = [
      data.peak_dbfs,
      data.true_peak_dbfs,
      data.rms_left,
      data.rms_right,
      data.momentary_loudness,
      data.short_term_loudness,
      data.integrated_loudness,
    ];

    const newPeakHolds = { ...peakHolds };

    channels.forEach((channel, index) => {
      const value = values[index];
      const existing = newPeakHolds[channel];

      if (!existing || value > existing.value) {
        newPeakHolds[channel] = { value, timestamp: now };
      } else if (now - existing.timestamp > settings.peakHoldTime * 1000) {
        delete newPeakHolds[channel];
      }
    });

    setPeakHolds(newPeakHolds);
  }, [settings.enablePeakHold, settings.peakHoldTime, peakHolds]);

  // Main render function
  const render = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !meterData) return;

    if (!shouldRender()) return;

    startRender();
    updatePeakHolds(meterData);

    const ctx = canvas.getContext('2d');
    if (!ctx) {
      endRender();
      return;
    }

    // Clear canvas
    ctx.fillStyle = colorSchemes[settings.colorScheme].background;
    ctx.fillRect(0, 0, width, height);

    try {
      // Draw all meter components
      drawLUFSMeter(ctx, meterData);
      drawPeakMeters(ctx, meterData);
      drawRMSMeters(ctx, meterData);
      drawCorrelationDisplay(ctx, meterData);
      drawDynamicsDisplay(ctx, meterData);

      // Draw title
      ctx.fillStyle = colorSchemes[settings.colorScheme].text;
      ctx.font = 'bold 14px sans-serif';
      ctx.fillText('Audio Meter Bridge', 10, 15);
    } catch (error) {
      console.error('Meter render error:', error);
    }

    endRender();
  }, [
    meterData, settings, width, height, colorSchemes,
    shouldRender, startRender, endRender, updatePeakHolds,
    drawLUFSMeter, drawPeakMeters, drawRMSMeters, drawCorrelationDisplay, drawDynamicsDisplay
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
          Professional Meter Bridge
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
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showLUFS}
                    onChange={(e) => setSettings(prev => ({ ...prev, showLUFS: e.target.checked }))}
                    color="primary"
                  />
                }
                label="LUFS Meters"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showPeaks}
                    onChange={(e) => setSettings(prev => ({ ...prev, showPeaks: e.target.checked }))}
                    color="primary"
                  />
                }
                label="Peak Meters"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showRMS}
                    onChange={(e) => setSettings(prev => ({ ...prev, showRMS: e.target.checked }))}
                    color="primary"
                  />
                }
                label="RMS Meters"
              />
            </Grid>

            <Grid item xs={12} md={4}>
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showCorrelation}
                    onChange={(e) => setSettings(prev => ({ ...prev, showCorrelation: e.target.checked }))}
                    color="primary"
                  />
                }
                label="Correlation"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.enablePeakHold}
                    onChange={(e) => setSettings(prev => ({ ...prev, enablePeakHold: e.target.checked }))}
                    color="primary"
                  />
                }
                label="Peak Hold"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.enableOverloadWarning}
                    onChange={(e) => setSettings(prev => ({ ...prev, enableOverloadWarning: e.target.checked }))}
                    color="primary"
                  />
                }
                label="Overload Warning"
              />
            </Grid>

            <Grid item xs={12} md={4}>
              <Typography gutterBottom>Peak Hold Time</Typography>
              <Slider
                value={settings.peakHoldTime}
                onChange={(_, value) => setSettings(prev => ({ ...prev, peakHoldTime: value as number }))}
                min={0.5}
                max={10}
                step={0.5}
                marks={[
                  { value: 1, label: '1s' },
                  { value: 3, label: '3s' },
                  { value: 5, label: '5s' },
                ]}
                valueLabelDisplay="auto"
              />
            </Grid>
          </Grid>

          {meterData && (
            <Box mt={2}>
              <Typography variant="subtitle2" color="white" gutterBottom>
                Current Levels:
              </Typography>
              <Box display="flex" gap={2} flexWrap="wrap">
                <Typography variant="caption" color="grey.300">
                  Peak: {meterData.peak_dbfs.toFixed(1)}dBFS
                </Typography>
                <Typography variant="caption" color="grey.300">
                  LUFS: {meterData.momentary_loudness.toFixed(1)}
                </Typography>
                <Typography variant="caption" color="grey.300">
                  Correlation: {meterData.correlation_coefficient.toFixed(2)}
                </Typography>
                <Typography variant="caption" color="grey.300">
                  DR: {meterData.dynamic_range.toFixed(1)}
                </Typography>
              </Box>
            </Box>
          )}
        </Box>
      )}
    </Paper>
  );
};

export default MeterBridge;