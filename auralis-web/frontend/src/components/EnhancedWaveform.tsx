import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Box, Paper, Typography, Switch, FormControlLabel, Slider, Grid } from '@mui/material';

interface WaveformData {
  peaks: number[];
  rms: number[];
  sampleRate: number;
  duration: number;
  channels: number;
}

interface WaveformSettings {
  showRMS: boolean;
  showPeaks: boolean;
  showSpectralOverlay: boolean;
  waveformColor: string;
  rmsColor: string;
  backgroundColor: string;
  gridColor: string;
  timeScale: number; // Zoom factor
  amplitudeScale: number;
  showTimeGrid: boolean;
  showAmplitudeGrid: boolean;
}

interface EnhancedWaveformProps {
  waveformData?: WaveformData;
  width?: number;
  height?: number;
  currentTime?: number;
  isPlaying?: boolean;
  onSeek?: (time: number) => void;
  showControls?: boolean;
  className?: string;
}

const defaultSettings: WaveformSettings = {
  showRMS: true,
  showPeaks: true,
  showSpectralOverlay: false,
  waveformColor: '#4FC3F7',
  rmsColor: '#FFB74D',
  backgroundColor: '#1A1A1A',
  gridColor: '#333333',
  timeScale: 1.0,
  amplitudeScale: 1.0,
  showTimeGrid: true,
  showAmplitudeGrid: true,
};

export const EnhancedWaveform: React.FC<EnhancedWaveformProps> = ({
  waveformData,
  width = 800,
  height = 200,
  currentTime = 0,
  isPlaying = false,
  onSeek,
  showControls = true,
  className
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [settings, setSettings] = useState<WaveformSettings>(defaultSettings);
  const [isDragging, setIsDragging] = useState(false);
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });

  // Animation frame for smooth playback cursor
  const animationFrameRef = useRef<number>();

  const drawGrid = useCallback((ctx: CanvasRenderingContext2D, width: number, height: number) => {
    if (!settings.showTimeGrid && !settings.showAmplitudeGrid) return;

    ctx.strokeStyle = settings.gridColor;
    ctx.lineWidth = 0.5;
    ctx.globalAlpha = 0.3;

    // Time grid (vertical lines)
    if (settings.showTimeGrid && waveformData) {
      const timeInterval = Math.max(1, Math.floor(waveformData.duration / 10));
      const pixelsPerSecond = width / waveformData.duration;

      for (let t = 0; t <= waveformData.duration; t += timeInterval) {
        const x = t * pixelsPerSecond;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();
      }
    }

    // Amplitude grid (horizontal lines)
    if (settings.showAmplitudeGrid) {
      const amplitudeLines = [-1, -0.5, 0, 0.5, 1];
      for (const amp of amplitudeLines) {
        const y = height / 2 + (amp * height / 2) / settings.amplitudeScale;
        if (y >= 0 && y <= height) {
          ctx.beginPath();
          ctx.moveTo(0, y);
          ctx.lineTo(width, y);
          ctx.stroke();
        }
      }
    }

    ctx.globalAlpha = 1.0;
  }, [settings, waveformData]);

  const drawWaveform = useCallback((ctx: CanvasRenderingContext2D, width: number, height: number) => {
    if (!waveformData || !waveformData.peaks.length) return;

    const { peaks, rms } = waveformData;
    const samplesPerPixel = peaks.length / width;
    const centerY = height / 2;

    // Draw RMS envelope first (if enabled)
    if (settings.showRMS && rms.length > 0) {
      ctx.fillStyle = settings.rmsColor + '40'; // 25% opacity
      ctx.beginPath();

      for (let x = 0; x < width; x++) {
        const sampleIndex = Math.floor(x * samplesPerPixel);
        if (sampleIndex < rms.length) {
          const rmsValue = rms[sampleIndex] * settings.amplitudeScale;
          const rmsHeight = Math.min(rmsValue * centerY, centerY);

          if (x === 0) {
            ctx.moveTo(x, centerY - rmsHeight);
          } else {
            ctx.lineTo(x, centerY - rmsHeight);
          }
        }
      }

      // Complete the envelope
      for (let x = width - 1; x >= 0; x--) {
        const sampleIndex = Math.floor(x * samplesPerPixel);
        if (sampleIndex < rms.length) {
          const rmsValue = rms[sampleIndex] * settings.amplitudeScale;
          const rmsHeight = Math.min(rmsValue * centerY, centerY);
          ctx.lineTo(x, centerY + rmsHeight);
        }
      }

      ctx.closePath();
      ctx.fill();
    }

    // Draw peak waveform
    if (settings.showPeaks) {
      ctx.strokeStyle = settings.waveformColor;
      ctx.lineWidth = 1;
      ctx.beginPath();

      for (let x = 0; x < width; x++) {
        const sampleIndex = Math.floor(x * samplesPerPixel);
        if (sampleIndex < peaks.length) {
          const peakValue = peaks[sampleIndex] * settings.amplitudeScale;
          const y = centerY - (peakValue * centerY);

          if (x === 0) {
            ctx.moveTo(x, y);
          } else {
            ctx.lineTo(x, y);
          }
        }
      }

      ctx.stroke();
    }
  }, [waveformData, settings]);

  const drawPlaybackCursor = useCallback((ctx: CanvasRenderingContext2D, width: number, height: number) => {
    if (!waveformData || currentTime < 0) return;

    const x = (currentTime / waveformData.duration) * width;

    // Draw playback cursor
    ctx.strokeStyle = '#FF5722';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
    ctx.stroke();

    // Draw time indicator
    ctx.fillStyle = '#FF5722';
    ctx.font = '12px Arial';
    ctx.textAlign = 'center';
    const timeText = `${currentTime.toFixed(2)}s`;
    ctx.fillText(timeText, x, 15);
  }, [currentTime, waveformData]);

  const drawMouseCursor = useCallback((ctx: CanvasRenderingContext2D, width: number, height: number) => {
    if (!waveformData || mousePosition.x < 0 || mousePosition.x > width) return;

    const time = (mousePosition.x / width) * waveformData.duration;

    // Draw mouse cursor
    ctx.strokeStyle = '#FFC107';
    ctx.lineWidth = 1;
    ctx.setLineDash([5, 5]);
    ctx.beginPath();
    ctx.moveTo(mousePosition.x, 0);
    ctx.lineTo(mousePosition.x, height);
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw time indicator
    ctx.fillStyle = '#FFC107';
    ctx.font = '11px Arial';
    ctx.textAlign = 'center';
    const timeText = `${time.toFixed(2)}s`;
    ctx.fillText(timeText, mousePosition.x, height - 5);
  }, [mousePosition, waveformData]);

  const render = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Clear canvas
    ctx.fillStyle = settings.backgroundColor;
    ctx.fillRect(0, 0, width, height);

    // Draw components
    drawGrid(ctx, width, height);
    drawWaveform(ctx, width, height);
    drawMouseCursor(ctx, width, height);
    drawPlaybackCursor(ctx, width, height);
  }, [width, height, settings, drawGrid, drawWaveform, drawMouseCursor, drawPlaybackCursor]);

  // Render on changes
  useEffect(() => {
    render();
  }, [render]);

  // Animation loop for smooth playback cursor
  useEffect(() => {
    if (isPlaying) {
      const animate = () => {
        render();
        animationFrameRef.current = requestAnimationFrame(animate);
      };
      animationFrameRef.current = requestAnimationFrame(animate);
    } else {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    }

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [isPlaying, render]);

  // Mouse event handlers
  const handleMouseMove = useCallback((event: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    setMousePosition({ x, y });

    if (isDragging && onSeek && waveformData) {
      const time = (x / width) * waveformData.duration;
      onSeek(Math.max(0, Math.min(time, waveformData.duration)));
    }
  }, [isDragging, onSeek, waveformData, width]);

  const handleMouseDown = useCallback((event: React.MouseEvent<HTMLCanvasElement>) => {
    if (!onSeek || !waveformData) return;

    setIsDragging(true);

    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const time = (x / width) * waveformData.duration;
    onSeek(Math.max(0, Math.min(time, waveformData.duration)));
  }, [onSeek, waveformData, width]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleMouseLeave = useCallback(() => {
    setIsDragging(false);
    setMousePosition({ x: -1, y: -1 });
  }, []);

  return (
    <Box className={className}>
      <Paper elevation={2} sx={{ p: 2, backgroundColor: '#2A2A2A' }}>
        <Typography variant="h6" gutterBottom sx={{ color: 'white' }}>
          Enhanced Waveform Display
        </Typography>

        <canvas
          ref={canvasRef}
          width={width}
          height={height}
          style={{
            border: '1px solid #444',
            borderRadius: '4px',
            cursor: onSeek ? 'pointer' : 'default',
            display: 'block',
            marginBottom: showControls ? '16px' : '0'
          }}
          onMouseMove={handleMouseMove}
          onMouseDown={handleMouseDown}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseLeave}
        />

        {showControls && (
          <Grid container spacing={2}>
            <Grid item xs={12} md={6}>
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showPeaks}
                    onChange={(e) => setSettings(prev => ({ ...prev, showPeaks: e.target.checked }))}
                  />
                }
                label="Show Peaks"
                sx={{ color: 'white' }}
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showRMS}
                    onChange={(e) => setSettings(prev => ({ ...prev, showRMS: e.target.checked }))}
                  />
                }
                label="Show RMS"
                sx={{ color: 'white', ml: 2 }}
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showTimeGrid}
                    onChange={(e) => setSettings(prev => ({ ...prev, showTimeGrid: e.target.checked }))}
                  />
                }
                label="Time Grid"
                sx={{ color: 'white' }}
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showAmplitudeGrid}
                    onChange={(e) => setSettings(prev => ({ ...prev, showAmplitudeGrid: e.target.checked }))}
                  />
                }
                label="Amplitude Grid"
                sx={{ color: 'white', ml: 2 }}
              />
            </Grid>

            <Grid item xs={6}>
              <Typography variant="body2" sx={{ color: 'white', mb: 1 }}>
                Amplitude Scale
              </Typography>
              <Slider
                value={settings.amplitudeScale}
                onChange={(_, value) => setSettings(prev => ({ ...prev, amplitudeScale: value as number }))}
                min={0.1}
                max={5.0}
                step={0.1}
                valueLabelDisplay="auto"
                sx={{ color: '#4FC3F7' }}
              />
            </Grid>

            <Grid item xs={6}>
              <Typography variant="body2" sx={{ color: 'white', mb: 1 }}>
                Time Scale
              </Typography>
              <Slider
                value={settings.timeScale}
                onChange={(_, value) => setSettings(prev => ({ ...prev, timeScale: value as number }))}
                min={0.1}
                max={10.0}
                step={0.1}
                valueLabelDisplay="auto"
                sx={{ color: '#4FC3F7' }}
              />
            </Grid>
          </Grid>
        )}

        {waveformData && (
          <Box sx={{ mt: 2, color: 'white', fontSize: '0.875rem' }}>
            <Typography variant="body2">
              Duration: {waveformData.duration.toFixed(2)}s |
              Sample Rate: {waveformData.sampleRate}Hz |
              Channels: {waveformData.channels} |
              Samples: {waveformData.peaks.length.toLocaleString()}
            </Typography>
          </Box>
        )}
      </Paper>
    </Box>
  );
};

export default EnhancedWaveform;