import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Box, Paper, Typography, Switch, FormControlLabel, Slider, Grid, Button } from '@mui/material';
import { useVisualizationOptimization } from '../hooks/useVisualizationOptimization';

// Types for our Phase 5.1 analysis integration
interface AnalysisData {
  spectrum?: {
    frequency_bins: number[];
    magnitude_db: number[];
    peak_frequency: number;
    spectral_centroid: number;
  };
  loudness?: {
    momentary_loudness: number;
    peak_dbfs: number;
  };
  correlation?: {
    correlation_coefficient: number;
    stereo_width: number;
    mono_compatibility: number;
  };
  dynamics?: {
    dr_value: number;
    crest_factor: number;
    compression_ratio: number;
  };
}

interface WaveformData {
  peaks: number[];
  rms: number[];
  sampleRate: number;
  duration: number;
  channels: number;
  analysisData?: AnalysisData;
}

interface WaveformSettings {
  showRMS: boolean;
  showPeaks: boolean;
  showSpectralOverlay: boolean;
  showAnalysisOverlay: boolean;
  showLoudnessMarkers: boolean;
  showDynamicRangeMarkers: boolean;
  waveformColor: string;
  rmsColor: string;
  spectralColor: string;
  analysisColor: string;
  backgroundColor: string;
  gridColor: string;
  timeScale: number;
  amplitudeScale: number;
  showTimeGrid: boolean;
  showAmplitudeGrid: boolean;
  animatePlayhead: boolean;
}

interface AnalysisWaveformDisplayProps {
  waveformData?: WaveformData;
  width?: number;
  height?: number;
  currentTime?: number;
  isPlaying?: boolean;
  onSeek?: (time: number) => void;
  showControls?: boolean;
  className?: string;
  analysisMode?: 'off' | 'spectrum' | 'loudness' | 'correlation' | 'dynamics' | 'all';
  onAnalysisModeChange?: (mode: string) => void;
}

const defaultSettings: WaveformSettings = {
  showRMS: true,
  showPeaks: true,
  showSpectralOverlay: false,
  showAnalysisOverlay: true,
  showLoudnessMarkers: true,
  showDynamicRangeMarkers: true,
  waveformColor: '#4FC3F7',
  rmsColor: '#FFB74D',
  spectralColor: '#A78BFA',
  analysisColor: '#34D399',
  backgroundColor: '#1A1A1A',
  gridColor: '#333333',
  timeScale: 1.0,
  amplitudeScale: 1.0,
  showTimeGrid: true,
  showAmplitudeGrid: true,
  animatePlayhead: true,
};

export const AnalysisWaveformDisplay: React.FC<AnalysisWaveformDisplayProps> = ({
  waveformData,
  width = 800,
  height = 300,
  currentTime = 0,
  isPlaying = false,
  onSeek,
  showControls = true,
  className,
  analysisMode = 'all',
  onAnalysisModeChange,
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationFrameRef = useRef<number>();
  const [settings, setSettings] = useState<WaveformSettings>(defaultSettings);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);

  // Use our visualization optimization hook
  const {
    shouldRender,
    optimizeData,
    startRender,
    endRender,
    stats,
    qualityLevel
  } = useVisualizationOptimization({
    targetFPS: 60,
    adaptiveQuality: true,
    enableMonitoring: true
  });

  // Convert time to x coordinate
  const timeToX = useCallback((time: number): number => {
    if (!waveformData) return 0;
    return (time / waveformData.duration) * width * settings.timeScale;
  }, [waveformData, width, settings.timeScale]);

  // Convert x coordinate to time
  const xToTime = useCallback((x: number): number => {
    if (!waveformData) return 0;
    return (x / (width * settings.timeScale)) * waveformData.duration;
  }, [waveformData, width, settings.timeScale]);

  // Draw time grid
  const drawTimeGrid = useCallback((ctx: CanvasRenderingContext2D) => {
    if (!settings.showTimeGrid || !waveformData) return;

    ctx.strokeStyle = settings.gridColor;
    ctx.lineWidth = 1;
    ctx.setLineDash([2, 4]);

    const duration = waveformData.duration;
    const timeStep = duration > 60 ? 10 : duration > 10 ? 5 : 1; // Dynamic time steps

    for (let t = 0; t <= duration; t += timeStep) {
      const x = timeToX(t);
      if (x >= 0 && x <= width) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();

        // Time labels
        ctx.fillStyle = settings.gridColor;
        ctx.font = '10px sans-serif';
        ctx.fillText(`${t.toFixed(1)}s`, x + 2, 12);
      }
    }

    ctx.setLineDash([]);
  }, [settings, waveformData, timeToX, width, height]);

  // Draw amplitude grid
  const drawAmplitudeGrid = useCallback((ctx: CanvasRenderingContext2D) => {
    if (!settings.showAmplitudeGrid) return;

    ctx.strokeStyle = settings.gridColor;
    ctx.lineWidth = 1;
    ctx.setLineDash([1, 3]);

    const levels = [-60, -40, -20, -12, -6, -3, 0]; // dB levels
    const centerY = height / 2;

    levels.forEach(level => {
      const y = centerY - (level / 60) * centerY * settings.amplitudeScale;
      if (y >= 0 && y <= height) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();

        // Level labels
        ctx.fillStyle = settings.gridColor;
        ctx.font = '10px sans-serif';
        ctx.fillText(`${level}dB`, 2, y - 2);
      }
    });

    ctx.setLineDash([]);
  }, [settings, height, width]);

  // Draw waveform peaks
  const drawWaveform = useCallback((ctx: CanvasRenderingContext2D, data: WaveformData) => {
    if (!settings.showPeaks || !data.peaks.length) return;

    // Optimize data for current zoom level and quality
    const optimizedPeaks = optimizeData(data.peaks);

    ctx.strokeStyle = settings.waveformColor;
    ctx.lineWidth = 1;
    ctx.globalAlpha = 0.8;

    const centerY = height / 2;
    const samplesPerPixel = optimizedPeaks.length / width;

    ctx.beginPath();
    for (let x = 0; x < width; x++) {
      const startIdx = Math.floor(x * samplesPerPixel);
      const endIdx = Math.floor((x + 1) * samplesPerPixel);

      let max = -Infinity;
      let min = Infinity;

      for (let i = startIdx; i < Math.min(endIdx, optimizedPeaks.length); i++) {
        max = Math.max(max, optimizedPeaks[i]);
        min = Math.min(min, optimizedPeaks[i]);
      }

      if (max !== -Infinity) {
        const yMax = centerY - (max * centerY * settings.amplitudeScale);
        const yMin = centerY - (min * centerY * settings.amplitudeScale);

        ctx.moveTo(x, yMax);
        ctx.lineTo(x, yMin);
      }
    }
    ctx.stroke();
    ctx.globalAlpha = 1;
  }, [settings, height, width, optimizeData]);

  // Draw RMS overlay
  const drawRMS = useCallback((ctx: CanvasRenderingContext2D, data: WaveformData) => {
    if (!settings.showRMS || !data.rms.length) return;

    const optimizedRMS = optimizeData(data.rms);

    ctx.strokeStyle = settings.rmsColor;
    ctx.lineWidth = 2;
    ctx.globalAlpha = 0.7;

    const centerY = height / 2;
    const samplesPerPixel = optimizedRMS.length / width;

    ctx.beginPath();
    for (let x = 0; x < width; x++) {
      const idx = Math.floor(x * samplesPerPixel);
      if (idx < optimizedRMS.length) {
        const rms = optimizedRMS[idx];
        const y = centerY - (rms * centerY * settings.amplitudeScale);

        if (x === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      }
    }
    ctx.stroke();

    // Draw negative RMS
    ctx.beginPath();
    for (let x = 0; x < width; x++) {
      const idx = Math.floor(x * samplesPerPixel);
      if (idx < optimizedRMS.length) {
        const rms = optimizedRMS[idx];
        const y = centerY + (rms * centerY * settings.amplitudeScale);

        if (x === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      }
    }
    ctx.stroke();
    ctx.globalAlpha = 1;
  }, [settings, height, width, optimizeData]);

  // Draw analysis overlays
  const drawAnalysisOverlay = useCallback((ctx: CanvasRenderingContext2D, data: WaveformData) => {
    if (!settings.showAnalysisOverlay || !data.analysisData) return;

    const analysis = data.analysisData;

    // Draw loudness markers
    if (settings.showLoudnessMarkers && analysis.loudness && analysisMode !== 'off') {
      const loudness = analysis.loudness.momentary_loudness;
      const peak = analysis.loudness.peak_dbfs;

      // Loudness line
      ctx.strokeStyle = settings.analysisColor;
      ctx.lineWidth = 1;
      ctx.setLineDash([5, 5]);

      const loudnessY = height / 2 - (loudness / -60) * height / 2;
      ctx.beginPath();
      ctx.moveTo(0, loudnessY);
      ctx.lineTo(width, loudnessY);
      ctx.stroke();

      // Peak line
      ctx.strokeStyle = '#FF6B6B';
      const peakY = height / 2 - (peak / -60) * height / 2;
      ctx.beginPath();
      ctx.moveTo(0, peakY);
      ctx.lineTo(width, peakY);
      ctx.stroke();

      ctx.setLineDash([]);

      // Labels
      ctx.fillStyle = settings.analysisColor;
      ctx.font = '12px sans-serif';
      ctx.fillText(`LUFS: ${loudness.toFixed(1)}`, 10, loudnessY - 5);
      ctx.fillStyle = '#FF6B6B';
      ctx.fillText(`Peak: ${peak.toFixed(1)}dBFS`, 10, peakY - 5);
    }

    // Draw dynamic range markers
    if (settings.showDynamicRangeMarkers && analysis.dynamics && analysisMode !== 'off') {
      const dr = analysis.dynamics.dr_value;
      const crest = analysis.dynamics.crest_factor;

      ctx.fillStyle = settings.analysisColor;
      ctx.font = '12px sans-serif';
      ctx.fillText(`DR: ${dr.toFixed(1)}`, width - 100, 20);
      ctx.fillText(`Crest: ${crest.toFixed(1)}dB`, width - 100, 40);
    }

    // Draw correlation info
    if (analysis.correlation && analysisMode !== 'off') {
      const corr = analysis.correlation.correlation_coefficient;
      const width_val = analysis.correlation.stereo_width;

      ctx.fillStyle = settings.analysisColor;
      ctx.font = '12px sans-serif';
      ctx.fillText(`Correlation: ${corr.toFixed(2)}`, width - 150, height - 40);
      ctx.fillText(`Width: ${width_val.toFixed(2)}`, width - 150, height - 20);
    }
  }, [settings, analysisMode, height, width]);

  // Draw playhead
  const drawPlayhead = useCallback((ctx: CanvasRenderingContext2D) => {
    if (!waveformData) return;

    const x = timeToX(currentTime);

    ctx.strokeStyle = '#FF4444';
    ctx.lineWidth = 2;
    ctx.globalAlpha = settings.animatePlayhead && isPlaying ? 0.8 : 1;

    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
    ctx.stroke();

    // Playhead triangle
    ctx.fillStyle = '#FF4444';
    ctx.beginPath();
    ctx.moveTo(x - 5, 0);
    ctx.lineTo(x + 5, 0);
    ctx.lineTo(x, 10);
    ctx.closePath();
    ctx.fill();

    ctx.globalAlpha = 1;
  }, [waveformData, currentTime, timeToX, height, settings.animatePlayhead, isPlaying]);

  // Main render function
  const render = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !waveformData) return;

    if (!shouldRender()) return;

    startRender();

    const ctx = canvas.getContext('2d');
    if (!ctx) {
      endRender();
      return;
    }

    // Clear canvas
    ctx.fillStyle = settings.backgroundColor;
    ctx.fillRect(0, 0, width, height);

    try {
      // Draw grid
      drawTimeGrid(ctx);
      drawAmplitudeGrid(ctx);

      // Draw waveform components
      drawWaveform(ctx, waveformData);
      drawRMS(ctx, waveformData);
      drawAnalysisOverlay(ctx, waveformData);

      // Draw playhead last
      drawPlayhead(ctx);
    } catch (error) {
      console.error('Waveform render error:', error);
    }

    endRender();
  }, [
    waveformData, settings, width, height, shouldRender, startRender, endRender,
    drawTimeGrid, drawAmplitudeGrid, drawWaveform, drawRMS, drawAnalysisOverlay, drawPlayhead
  ]);

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

  // Canvas setup
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    canvas.width = width;
    canvas.height = height;
  }, [width, height]);

  // Mouse event handlers
  const handleMouseMove = useCallback((event: React.MouseEvent) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;

    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    setMousePos({ x, y });

    if (isDragging && onSeek) {
      const time = xToTime(x);
      onSeek(Math.max(0, Math.min(time, waveformData?.duration || 0)));
    }
  }, [isDragging, onSeek, xToTime, waveformData]);

  const handleMouseDown = useCallback((event: React.MouseEvent) => {
    setIsDragging(true);
    if (onSeek) {
      const rect = canvasRef.current?.getBoundingClientRect();
      if (rect) {
        const x = event.clientX - rect.left;
        const time = xToTime(x);
        onSeek(Math.max(0, Math.min(time, waveformData?.duration || 0)));
      }
    }
  }, [onSeek, xToTime, waveformData]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  return (
    <Paper className={className} sx={{ p: 2, backgroundColor: '#1A1A1A' }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h6" color="white">
          Analysis Waveform Display
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
          cursor: isDragging ? 'grabbing' : 'grab',
          display: 'block',
          margin: '0 auto'
        }}
        onMouseMove={handleMouseMove}
        onMouseDown={handleMouseDown}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      />

      {showControls && (
        <Box mt={2}>
          <Grid container spacing={2}>
            <Grid item xs={12} md={6}>
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showRMS}
                    onChange={(e) => setSettings(prev => ({ ...prev, showRMS: e.target.checked }))}
                    color="primary"
                  />
                }
                label="Show RMS"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showAnalysisOverlay}
                    onChange={(e) => setSettings(prev => ({ ...prev, showAnalysisOverlay: e.target.checked }))}
                    color="primary"
                  />
                }
                label="Analysis Overlay"
              />
            </Grid>
            <Grid item xs={12} md={6}>
              <Typography gutterBottom>Time Scale</Typography>
              <Slider
                value={settings.timeScale}
                onChange={(_, value) => setSettings(prev => ({ ...prev, timeScale: value as number }))}
                min={0.1}
                max={5}
                step={0.1}
                marks={[
                  { value: 0.5, label: '0.5x' },
                  { value: 1, label: '1x' },
                  { value: 2, label: '2x' },
                ]}
                valueLabelDisplay="auto"
              />
            </Grid>
          </Grid>

          {waveformData?.analysisData && (
            <Box mt={2}>
              <Typography variant="subtitle2" color="white" gutterBottom>
                Current Analysis Data:
              </Typography>
              <Box display="flex" gap={2} flexWrap="wrap">
                {waveformData.analysisData.loudness && (
                  <Typography variant="caption" color="grey.300">
                    Loudness: {waveformData.analysisData.loudness.momentary_loudness.toFixed(1)} LUFS
                  </Typography>
                )}
                {waveformData.analysisData.dynamics && (
                  <Typography variant="caption" color="grey.300">
                    DR: {waveformData.analysisData.dynamics.dr_value.toFixed(1)}
                  </Typography>
                )}
                {waveformData.analysisData.correlation && (
                  <Typography variant="caption" color="grey.300">
                    Correlation: {waveformData.analysisData.correlation.correlation_coefficient.toFixed(2)}
                  </Typography>
                )}
              </Box>
            </Box>
          )}
        </Box>
      )}
    </Paper>
  );
};

export default AnalysisWaveformDisplay;