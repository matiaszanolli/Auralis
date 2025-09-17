import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Box, Paper, Typography, Grid, Switch, FormControlLabel, IconButton } from '@mui/material';
import { Settings, Fullscreen } from '@mui/icons-material';

interface MeterData {
  // Peak levels
  peakLevelL: number;
  peakLevelR: number;

  // RMS levels
  rmsLevelL: number;
  rmsLevelR: number;

  // LUFS measurements
  momentaryLUFS: number;
  shortTermLUFS: number;
  integratedLUFS: number;
  loudnessRange: number;

  // True peak
  truePeakL: number;
  truePeakR: number;

  // Phase correlation
  correlation: number;

  // Dynamic range
  dynamicRange: number;
  crestFactor: number;
}

interface MeterSettings {
  showPeakHold: boolean;
  showRMS: boolean;
  showLUFS: boolean;
  showPhaseCorrelation: boolean;
  showDynamicRange: boolean;
  peakHoldTime: number; // milliseconds
  meterDecayRate: number; // dB/s
  colorScheme: 'broadcast' | 'music' | 'mastering';
}

interface ProfessionalMeterBridgeProps {
  meterData?: MeterData;
  width?: number;
  height?: number;
  updateInterval?: number;
  className?: string;
}

const defaultSettings: MeterSettings = {
  showPeakHold: true,
  showRMS: true,
  showLUFS: true,
  showPhaseCorrelation: true,
  showDynamicRange: true,
  peakHoldTime: 3000,
  meterDecayRate: 20,
  colorScheme: 'mastering'
};

const defaultMeterData: MeterData = {
  peakLevelL: -60,
  peakLevelR: -60,
  rmsLevelL: -60,
  rmsLevelR: -60,
  momentaryLUFS: -23,
  shortTermLUFS: -23,
  integratedLUFS: -23,
  loudnessRange: 7,
  truePeakL: -60,
  truePeakR: -60,
  correlation: 0.5,
  dynamicRange: 12,
  crestFactor: 15
};

const getMeterColor = (level: number, type: 'peak' | 'rms' | 'lufs' | 'correlation', scheme: string): string => {
  switch (type) {
    case 'peak':
    case 'rms':
      if (level > -3) return '#FF1744'; // Red - clipping danger
      if (level > -6) return '#FF9800'; // Orange - hot
      if (level > -12) return '#FFEB3B'; // Yellow - good level
      if (level > -20) return '#4CAF50'; // Green - normal
      return '#2196F3'; // Blue - quiet

    case 'lufs':
      const target = scheme === 'broadcast' ? -23 : -16;
      const deviation = Math.abs(level - target);
      if (deviation < 1) return '#4CAF50'; // Green - perfect
      if (deviation < 3) return '#FFEB3B'; // Yellow - close
      if (deviation < 6) return '#FF9800'; // Orange - off
      return '#FF1744'; // Red - way off

    case 'correlation':
      if (level < -0.5) return '#FF1744'; // Red - phase issues
      if (level < 0) return '#FF9800'; // Orange - some issues
      if (level < 0.3) return '#FFEB3B'; // Yellow - narrow
      if (level < 0.8) return '#4CAF50'; // Green - good
      return '#2196F3'; // Blue - very wide

    default:
      return '#2196F3';
  }
};

export const ProfessionalMeterBridge: React.FC<ProfessionalMeterBridgeProps> = ({
  meterData = defaultMeterData,
  width = 400,
  height = 600,
  updateInterval = 50,
  className
}) => {
  const [settings, setSettings] = useState<MeterSettings>(defaultSettings);
  const [peakHoldL, setPeakHoldL] = useState(-60);
  const [peakHoldR, setPeakHoldR] = useState(-60);
  const [peakHoldTimestampL, setPeakHoldTimestampL] = useState(0);
  const [peakHoldTimestampR, setPeakHoldTimestampR] = useState(0);

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationFrameRef = useRef<number>();

  // Update peak hold values
  useEffect(() => {
    const now = Date.now();

    // Update left peak hold
    if (meterData.peakLevelL > peakHoldL) {
      setPeakHoldL(meterData.peakLevelL);
      setPeakHoldTimestampL(now);
    } else if (now - peakHoldTimestampL > settings.peakHoldTime) {
      // Decay peak hold
      const decayAmount = (now - peakHoldTimestampL - settings.peakHoldTime) / 1000 * settings.meterDecayRate;
      setPeakHoldL(Math.max(meterData.peakLevelL, peakHoldL - decayAmount));
    }

    // Update right peak hold
    if (meterData.peakLevelR > peakHoldR) {
      setPeakHoldR(meterData.peakLevelR);
      setPeakHoldTimestampR(now);
    } else if (now - peakHoldTimestampR > settings.peakHoldTime) {
      const decayAmount = (now - peakHoldTimestampR - settings.peakHoldTime) / 1000 * settings.meterDecayRate;
      setPeakHoldR(Math.max(meterData.peakLevelR, peakHoldR - decayAmount));
    }
  }, [meterData, peakHoldL, peakHoldR, peakHoldTimestampL, peakHoldTimestampR, settings]);

  const drawMeter = useCallback((
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    width: number,
    height: number,
    level: number,
    peakHold: number,
    label: string,
    type: 'peak' | 'rms' | 'lufs' | 'correlation'
  ) => {
    const meterRange = type === 'lufs' ? 60 : 60; // -60 to 0 dBFS or -60 to 0 LUFS
    const normalizedLevel = Math.max(0, (level + meterRange) / meterRange);
    const normalizedPeakHold = Math.max(0, (peakHold + meterRange) / meterRange);

    // Draw meter background
    ctx.fillStyle = '#1A1A1A';
    ctx.fillRect(x, y, width, height);

    // Draw meter segments
    const segmentHeight = 3;
    const segmentSpacing = 1;
    const totalSegmentHeight = segmentHeight + segmentSpacing;
    const numSegments = Math.floor(height / totalSegmentHeight);

    for (let i = 0; i < numSegments; i++) {
      const segmentY = y + height - (i + 1) * totalSegmentHeight;
      const segmentLevel = i / numSegments;

      if (segmentLevel <= normalizedLevel) {
        const segmentDbLevel = segmentLevel * meterRange - meterRange;
        ctx.fillStyle = getMeterColor(segmentDbLevel, type, settings.colorScheme);
        ctx.fillRect(x + 2, segmentY, width - 4, segmentHeight);
      }
    }

    // Draw peak hold indicator
    if (settings.showPeakHold && normalizedPeakHold > 0) {
      const peakY = y + height - (normalizedPeakHold * height);
      ctx.fillStyle = '#FFFFFF';
      ctx.fillRect(x, peakY - 1, width, 2);
    }

    // Draw meter border
    ctx.strokeStyle = '#555555';
    ctx.lineWidth = 1;
    ctx.strokeRect(x, y, width, height);

    // Draw scale markings
    const scaleMarks = type === 'lufs' ? [-60, -40, -23, -18, -12, -6, 0] : [-60, -40, -20, -12, -6, -3, 0];
    ctx.fillStyle = '#CCCCCC';
    ctx.font = '10px Arial';
    ctx.textAlign = 'left';

    for (const mark of scaleMarks) {
      const markY = y + height - ((mark + meterRange) / meterRange) * height;
      if (markY >= y && markY <= y + height) {
        ctx.fillText(mark.toString(), x + width + 5, markY + 3);
        // Scale tick
        ctx.fillRect(x + width, markY, 4, 1);
      }
    }

    // Draw label
    ctx.save();
    ctx.translate(x + width / 2, y + height + 20);
    ctx.fillStyle = '#FFFFFF';
    ctx.font = '12px Arial';
    ctx.textAlign = 'center';
    ctx.fillText(label, 0, 0);
    ctx.restore();

    // Draw current value
    ctx.fillStyle = '#FFFFFF';
    ctx.font = 'bold 14px Arial';
    ctx.textAlign = 'center';
    ctx.fillText(level.toFixed(1), x + width / 2, y - 10);
  }, [settings]);

  const drawPhaseScope = useCallback((
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    size: number,
    correlation: number
  ) => {
    const centerX = x + size / 2;
    const centerY = y + size / 2;
    const radius = size / 2 - 10;

    // Draw background circle
    ctx.fillStyle = '#1A1A1A';
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, 0, 2 * Math.PI);
    ctx.fill();

    // Draw grid
    ctx.strokeStyle = '#333333';
    ctx.lineWidth = 1;

    // Concentric circles
    for (let r = radius / 4; r <= radius; r += radius / 4) {
      ctx.beginPath();
      ctx.arc(centerX, centerY, r, 0, 2 * Math.PI);
      ctx.stroke();
    }

    // Cross lines
    ctx.beginPath();
    ctx.moveTo(centerX - radius, centerY);
    ctx.lineTo(centerX + radius, centerY);
    ctx.moveTo(centerX, centerY - radius);
    ctx.lineTo(centerX, centerY + radius);
    ctx.stroke();

    // Draw correlation indicator
    const corrColor = getMeterColor(correlation, 'correlation', settings.colorScheme);
    const indicatorRadius = Math.abs(correlation) * radius * 0.8;

    ctx.fillStyle = corrColor;
    ctx.beginPath();
    ctx.arc(centerX, centerY, Math.max(2, indicatorRadius), 0, 2 * Math.PI);
    ctx.fill();

    // Draw border
    ctx.strokeStyle = '#555555';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, 0, 2 * Math.PI);
    ctx.stroke();

    // Draw correlation value
    ctx.fillStyle = '#FFFFFF';
    ctx.font = 'bold 16px Arial';
    ctx.textAlign = 'center';
    ctx.fillText(correlation.toFixed(2), centerX, y + size + 20);
  }, [settings]);

  const render = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Clear canvas
    ctx.fillStyle = '#0D1B2A';
    ctx.fillRect(0, 0, width, height);

    const meterWidth = 40;
    const meterHeight = height * 0.6;
    const meterY = 50;

    // Draw peak meters
    if (settings.showRMS) {
      drawMeter(ctx, 20, meterY, meterWidth, meterHeight, meterData.peakLevelL, peakHoldL, 'L', 'peak');
      drawMeter(ctx, 80, meterY, meterWidth, meterHeight, meterData.peakLevelR, peakHoldR, 'R', 'peak');
    }

    // Draw RMS meters
    if (settings.showRMS) {
      drawMeter(ctx, 140, meterY, meterWidth, meterHeight, meterData.rmsLevelL, meterData.rmsLevelL, 'L RMS', 'rms');
      drawMeter(ctx, 200, meterY, meterWidth, meterHeight, meterData.rmsLevelR, meterData.rmsLevelR, 'R RMS', 'rms');
    }

    // Draw LUFS meters
    if (settings.showLUFS) {
      drawMeter(ctx, 260, meterY, meterWidth, meterHeight, meterData.momentaryLUFS, meterData.momentaryLUFS, 'M', 'lufs');
      drawMeter(ctx, 320, meterY, meterWidth, meterHeight, meterData.shortTermLUFS, meterData.shortTermLUFS, 'S', 'lufs');
    }

    // Draw phase correlation scope
    if (settings.showPhaseCorrelation) {
      const scopeSize = 80;
      const scopeX = width - scopeSize - 20;
      const scopeY = meterY + meterHeight - scopeSize;
      drawPhaseScope(ctx, scopeX, scopeY, scopeSize, meterData.correlation);
    }

    // Draw text information
    ctx.fillStyle = '#FFFFFF';
    ctx.font = '14px Arial';
    ctx.textAlign = 'left';

    let textY = meterY + meterHeight + 60;

    if (settings.showLUFS) {
      ctx.fillText(`Integrated: ${meterData.integratedLUFS.toFixed(1)} LUFS`, 20, textY);
      ctx.fillText(`Range: ${meterData.loudnessRange.toFixed(1)} LU`, 20, textY + 20);
      textY += 50;
    }

    if (settings.showDynamicRange) {
      ctx.fillText(`DR: ${meterData.dynamicRange.toFixed(1)} dB`, 20, textY);
      ctx.fillText(`Crest: ${meterData.crestFactor.toFixed(1)} dB`, 20, textY + 20);
      textY += 50;
    }

    ctx.fillText(`True Peak L: ${meterData.truePeakL.toFixed(1)} dBTP`, 20, textY);
    ctx.fillText(`True Peak R: ${meterData.truePeakR.toFixed(1)} dBTP`, 20, textY + 20);

  }, [width, height, settings, meterData, peakHoldL, peakHoldR, drawMeter, drawPhaseScope]);

  // Animation loop
  useEffect(() => {
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
  }, [render]);

  return (
    <Box className={className}>
      <Paper elevation={3} sx={{ p: 2, backgroundColor: '#1A1A1A' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h6" sx={{ color: 'white' }}>
            Professional Meter Bridge
          </Typography>
          <Box>
            <IconButton size="small" sx={{ color: 'white' }}>
              <Settings />
            </IconButton>
            <IconButton size="small" sx={{ color: 'white' }}>
              <Fullscreen />
            </IconButton>
          </Box>
        </Box>

        <canvas
          ref={canvasRef}
          width={width}
          height={height}
          style={{
            border: '1px solid #444',
            borderRadius: '4px',
            display: 'block',
            marginBottom: '16px'
          }}
        />

        <Grid container spacing={1}>
          <Grid item xs={6} sm={3}>
            <FormControlLabel
              control={
                <Switch
                  checked={settings.showPeakHold}
                  onChange={(e) => setSettings(prev => ({ ...prev, showPeakHold: e.target.checked }))}
                  size="small"
                />
              }
              label="Peak Hold"
              sx={{ color: 'white', fontSize: '0.875rem' }}
            />
          </Grid>
          <Grid item xs={6} sm={3}>
            <FormControlLabel
              control={
                <Switch
                  checked={settings.showRMS}
                  onChange={(e) => setSettings(prev => ({ ...prev, showRMS: e.target.checked }))}
                  size="small"
                />
              }
              label="RMS"
              sx={{ color: 'white', fontSize: '0.875rem' }}
            />
          </Grid>
          <Grid item xs={6} sm={3}>
            <FormControlLabel
              control={
                <Switch
                  checked={settings.showLUFS}
                  onChange={(e) => setSettings(prev => ({ ...prev, showLUFS: e.target.checked }))}
                  size="small"
                />
              }
              label="LUFS"
              sx={{ color: 'white', fontSize: '0.875rem' }}
            />
          </Grid>
          <Grid item xs={6} sm={3}>
            <FormControlLabel
              control={
                <Switch
                  checked={settings.showPhaseCorrelation}
                  onChange={(e) => setSettings(prev => ({ ...prev, showPhaseCorrelation: e.target.checked }))}
                  size="small"
                />
              }
              label="Phase"
              sx={{ color: 'white', fontSize: '0.875rem' }}
            />
          </Grid>
        </Grid>
      </Paper>
    </Box>
  );
};

export default ProfessionalMeterBridge;