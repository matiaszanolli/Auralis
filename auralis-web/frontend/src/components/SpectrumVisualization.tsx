import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Box, Paper, Typography, Switch, FormControlLabel, Slider, Grid, ToggleButton, ToggleButtonGroup } from '@mui/material';
import { useVisualizationOptimization } from '../hooks/useVisualizationOptimization';

// Types matching our Phase 5.1 spectrum analyzer
interface SpectrumData {
  frequency_bins: number[];
  magnitude_db: number[];
  peak_frequency: number;
  spectral_centroid: number;
  spectral_rolloff?: number;
  spectral_flux?: number;
  settings?: {
    fft_size: number;
    frequency_bands: number;
    weighting: string;
  };
}

interface SpectrumSettings {
  displayMode: 'magnitude' | 'power' | 'phase';
  frequencyScale: 'linear' | 'log';
  amplitudeScale: 'linear' | 'log';
  smoothing: number;
  showPeakMarkers: boolean;
  showCentroidMarker: boolean;
  showRolloffMarker: boolean;
  showFrequencyGrid: boolean;
  showAmplitudeGrid: boolean;
  showWeightingCurve: boolean;
  colorScheme: 'spectrum' | 'heatmap' | 'classic' | 'neon';
  backgroundColor: string;
  gridColor: string;
  spectrumColor: string;
  peakColor: string;
  centroidColor: string;
  animateSpectrum: boolean;
  showAnalysisText: boolean;
}

interface SpectrumVisualizationProps {
  spectrumData?: SpectrumData;
  width?: number;
  height?: number;
  showControls?: boolean;
  className?: string;
  onFrequencyClick?: (frequency: number) => void;
  real_time?: boolean;
  analysisMode?: 'basic' | 'detailed' | 'professional';
}

const defaultSettings: SpectrumSettings = {
  displayMode: 'magnitude',
  frequencyScale: 'log',
  amplitudeScale: 'linear',
  smoothing: 0.7,
  showPeakMarkers: true,
  showCentroidMarker: true,
  showRolloffMarker: false,
  showFrequencyGrid: true,
  showAmplitudeGrid: true,
  showWeightingCurve: false,
  colorScheme: 'spectrum',
  backgroundColor: '#0A0A0A',
  gridColor: '#333333',
  spectrumColor: '#4FC3F7',
  peakColor: '#FF6B6B',
  centroidColor: '#34D399',
  animateSpectrum: true,
  showAnalysisText: true,
};

// Color schemes for different visualization modes
const colorSchemes = {
  spectrum: {
    primary: '#4FC3F7',
    secondary: '#81C784',
    accent: '#FFB74D',
    peak: '#FF6B6B',
  },
  heatmap: {
    primary: '#FF5722',
    secondary: '#FF9800',
    accent: '#FFC107',
    peak: '#F44336',
  },
  classic: {
    primary: '#00FF00',
    secondary: '#FFFF00',
    accent: '#FF0000',
    peak: '#FFFFFF',
  },
  neon: {
    primary: '#00FFFF',
    secondary: '#FF00FF',
    accent: '#FFFF00',
    peak: '#FF0080',
  },
};

export const SpectrumVisualization: React.FC<SpectrumVisualizationProps> = ({
  spectrumData,
  width = 800,
  height = 400,
  showControls = true,
  className,
  onFrequencyClick,
  real_time = false,
  analysisMode = 'basic',
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationFrameRef = useRef<number>();
  const [settings, setSettings] = useState<SpectrumSettings>(defaultSettings);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [hoveredFrequency, setHoveredFrequency] = useState<number | null>(null);
  const [smoothedSpectrum, setSmoothedSpectrum] = useState<number[]>([]);

  // Use visualization optimization
  const {
    shouldRender,
    optimizeData,
    startRender,
    endRender,
    stats,
    qualityLevel
  } = useVisualizationOptimization({
    targetFPS: real_time ? 60 : 30,
    adaptiveQuality: true,
    enableMonitoring: true
  });

  // Frequency scaling functions
  const linearToLog = useCallback((freq: number, minFreq: number, maxFreq: number): number => {
    if (freq <= 0) return 0;
    return Math.log10(freq / minFreq) / Math.log10(maxFreq / minFreq);
  }, []);

  const logToLinear = useCallback((ratio: number, minFreq: number, maxFreq: number): number => {
    return minFreq * Math.pow(maxFreq / minFreq, ratio);
  }, []);

  // Convert frequency to x coordinate
  const frequencyToX = useCallback((frequency: number): number => {
    if (!spectrumData || spectrumData.frequency_bins.length === 0) return 0;

    const minFreq = Math.max(spectrumData.frequency_bins[0], 20);
    const maxFreq = spectrumData.frequency_bins[spectrumData.frequency_bins.length - 1];

    if (settings.frequencyScale === 'log') {
      return linearToLog(frequency, minFreq, maxFreq) * width;
    } else {
      return ((frequency - minFreq) / (maxFreq - minFreq)) * width;
    }
  }, [spectrumData, width, settings.frequencyScale, linearToLog]);

  // Convert x coordinate to frequency
  const xToFrequency = useCallback((x: number): number => {
    if (!spectrumData || spectrumData.frequency_bins.length === 0) return 0;

    const ratio = x / width;
    const minFreq = Math.max(spectrumData.frequency_bins[0], 20);
    const maxFreq = spectrumData.frequency_bins[spectrumData.frequency_bins.length - 1];

    if (settings.frequencyScale === 'log') {
      return logToLinear(ratio, minFreq, maxFreq);
    } else {
      return minFreq + ratio * (maxFreq - minFreq);
    }
  }, [spectrumData, width, settings.frequencyScale, logToLinear]);

  // Convert magnitude to y coordinate
  const magnitudeToY = useCallback((magnitude: number): number => {
    const minDb = -120;
    const maxDb = 0;

    if (settings.amplitudeScale === 'log') {
      // Linear dB scale
      const ratio = (magnitude - minDb) / (maxDb - minDb);
      return height - (ratio * height);
    } else {
      // Linear amplitude scale
      const amplitude = Math.pow(10, magnitude / 20);
      return height - (amplitude * height);
    }
  }, [height, settings.amplitudeScale]);

  // Draw frequency grid
  const drawFrequencyGrid = useCallback((ctx: CanvasRenderingContext2D) => {
    if (!settings.showFrequencyGrid || !spectrumData) return;

    ctx.strokeStyle = settings.gridColor;
    ctx.lineWidth = 1;
    ctx.setLineDash([1, 3]);

    const frequencies = settings.frequencyScale === 'log'
      ? [31.5, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000]
      : [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000];

    frequencies.forEach(freq => {
      const x = frequencyToX(freq);
      if (x >= 0 && x <= width) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
        ctx.stroke();

        // Frequency labels
        ctx.fillStyle = settings.gridColor;
        ctx.font = '10px sans-serif';
        const label = freq >= 1000 ? `${freq / 1000}k` : `${freq}`;
        ctx.fillText(label, x + 2, height - 5);
      }
    });

    ctx.setLineDash([]);
  }, [settings, spectrumData, frequencyToX, width, height]);

  // Draw amplitude grid
  const drawAmplitudeGrid = useCallback((ctx: CanvasRenderingContext2D) => {
    if (!settings.showAmplitudeGrid) return;

    ctx.strokeStyle = settings.gridColor;
    ctx.lineWidth = 1;
    ctx.setLineDash([1, 3]);

    const levels = [-80, -60, -40, -20, -12, -6, -3, 0];

    levels.forEach(level => {
      const y = magnitudeToY(level);
      if (y >= 0 && y <= height) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();

        // Level labels
        ctx.fillStyle = settings.gridColor;
        ctx.font = '10px sans-serif';
        ctx.fillText(`${level}dB`, 5, y - 2);
      }
    });

    ctx.setLineDash([]);
  }, [settings, magnitudeToY, height, width]);

  // Draw spectrum bars/curve
  const drawSpectrum = useCallback((ctx: CanvasRenderingContext2D, data: SpectrumData) => {
    if (!data.magnitude_db.length || !data.frequency_bins.length) return;

    // Apply smoothing
    const currentSpectrum = settings.smoothing > 0 && smoothedSpectrum.length > 0
      ? data.magnitude_db.map((mag, i) =>
          smoothedSpectrum[i] * settings.smoothing + mag * (1 - settings.smoothing)
        )
      : data.magnitude_db;

    // Optimize data for current quality level
    const optimizedMagnitudes = optimizeData(currentSpectrum);
    const optimizedFrequencies = optimizeData(data.frequency_bins);

    // Get color scheme
    const colors = colorSchemes[settings.colorScheme];

    // Draw spectrum curve
    ctx.strokeStyle = colors.primary;
    ctx.lineWidth = 2;
    ctx.globalAlpha = 0.8;

    ctx.beginPath();
    for (let i = 0; i < optimizedFrequencies.length; i++) {
      const x = frequencyToX(optimizedFrequencies[i]);
      const y = magnitudeToY(optimizedMagnitudes[i]);

      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }
    ctx.stroke();

    // Fill under curve with gradient
    if (settings.colorScheme === 'heatmap' || settings.colorScheme === 'spectrum') {
      const gradient = ctx.createLinearGradient(0, 0, 0, height);
      gradient.addColorStop(0, colors.primary + '80');
      gradient.addColorStop(0.5, colors.secondary + '40');
      gradient.addColorStop(1, colors.accent + '10');

      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.moveTo(frequencyToX(optimizedFrequencies[0]), height);

      for (let i = 0; i < optimizedFrequencies.length; i++) {
        const x = frequencyToX(optimizedFrequencies[i]);
        const y = magnitudeToY(optimizedMagnitudes[i]);
        ctx.lineTo(x, y);
      }

      ctx.lineTo(frequencyToX(optimizedFrequencies[optimizedFrequencies.length - 1]), height);
      ctx.closePath();
      ctx.fill();
    }

    ctx.globalAlpha = 1;

    // Update smoothed spectrum for next frame
    if (settings.smoothing > 0) {
      setSmoothedSpectrum(currentSpectrum);
    }
  }, [settings, smoothedSpectrum, optimizeData, frequencyToX, magnitudeToY, height]);

  // Draw analysis markers
  const drawAnalysisMarkers = useCallback((ctx: CanvasRenderingContext2D, data: SpectrumData) => {
    const colors = colorSchemes[settings.colorScheme];

    // Peak frequency marker
    if (settings.showPeakMarkers && data.peak_frequency) {
      const x = frequencyToX(data.peak_frequency);

      ctx.strokeStyle = colors.peak;
      ctx.lineWidth = 2;
      ctx.setLineDash([5, 5]);

      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();

      // Peak frequency label
      ctx.fillStyle = colors.peak;
      ctx.font = 'bold 12px sans-serif';
      ctx.fillText(`Peak: ${data.peak_frequency.toFixed(0)}Hz`, x + 5, 20);

      ctx.setLineDash([]);
    }

    // Spectral centroid marker
    if (settings.showCentroidMarker && data.spectral_centroid) {
      const x = frequencyToX(data.spectral_centroid);

      ctx.strokeStyle = settings.centroidColor;
      ctx.lineWidth = 2;
      ctx.setLineDash([3, 3]);

      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();

      // Centroid label
      ctx.fillStyle = settings.centroidColor;
      ctx.font = '12px sans-serif';
      ctx.fillText(`Centroid: ${data.spectral_centroid.toFixed(0)}Hz`, x + 5, 40);

      ctx.setLineDash([]);
    }

    // Spectral rolloff marker
    if (settings.showRolloffMarker && data.spectral_rolloff) {
      const x = frequencyToX(data.spectral_rolloff);

      ctx.strokeStyle = colors.accent;
      ctx.lineWidth = 1;
      ctx.setLineDash([2, 2]);

      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();

      ctx.fillStyle = colors.accent;
      ctx.font = '12px sans-serif';
      ctx.fillText(`Rolloff: ${data.spectral_rolloff.toFixed(0)}Hz`, x + 5, 60);

      ctx.setLineDash([]);
    }
  }, [settings, frequencyToX, height]);

  // Draw hover cursor
  const drawHoverCursor = useCallback((ctx: CanvasRenderingContext2D) => {
    if (hoveredFrequency === null) return;

    const x = mousePos.x;

    ctx.strokeStyle = '#FFFFFF80';
    ctx.lineWidth = 1;
    ctx.setLineDash([2, 2]);

    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
    ctx.stroke();

    // Frequency display
    ctx.fillStyle = '#FFFFFF';
    ctx.font = '12px sans-serif';
    ctx.fillRect(x + 5, mousePos.y - 10, 80, 20);
    ctx.fillStyle = '#000000';
    ctx.fillText(`${hoveredFrequency.toFixed(0)}Hz`, x + 10, mousePos.y + 5);

    ctx.setLineDash([]);
  }, [hoveredFrequency, mousePos, height]);

  // Main render function
  const render = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas || !spectrumData) return;

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
      drawFrequencyGrid(ctx);
      drawAmplitudeGrid(ctx);

      // Draw spectrum
      drawSpectrum(ctx, spectrumData);

      // Draw analysis markers
      if (analysisMode !== 'basic') {
        drawAnalysisMarkers(ctx, spectrumData);
      }

      // Draw hover cursor
      drawHoverCursor(ctx);
    } catch (error) {
      console.error('Spectrum render error:', error);
    }

    endRender();
  }, [
    spectrumData, settings, width, height, analysisMode,
    shouldRender, startRender, endRender,
    drawFrequencyGrid, drawAmplitudeGrid, drawSpectrum, drawAnalysisMarkers, drawHoverCursor
  ]);

  // Animation loop
  useEffect(() => {
    if (!settings.animateSpectrum && !real_time) {
      render();
      return;
    }

    const animate = () => {
      render();
      if (settings.animateSpectrum || real_time) {
        animationFrameRef.current = requestAnimationFrame(animate);
      }
    };

    animationFrameRef.current = requestAnimationFrame(animate);

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [render, settings.animateSpectrum, real_time]);

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

    const frequency = xToFrequency(x);
    setHoveredFrequency(frequency);
  }, [xToFrequency]);

  const handleMouseLeave = useCallback(() => {
    setHoveredFrequency(null);
  }, []);

  const handleClick = useCallback((event: React.MouseEvent) => {
    if (!onFrequencyClick) return;

    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;

    const x = event.clientX - rect.left;
    const frequency = xToFrequency(x);
    onFrequencyClick(frequency);
  }, [onFrequencyClick, xToFrequency]);

  return (
    <Paper className={className} sx={{ p: 2, backgroundColor: '#1A1A1A' }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h6" color="white">
          Spectrum Analysis
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
          cursor: 'crosshair',
          display: 'block',
          margin: '0 auto'
        }}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
        onClick={handleClick}
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
              >
                <ToggleButton value="magnitude">Magnitude</ToggleButton>
                <ToggleButton value="power">Power</ToggleButton>
                <ToggleButton value="phase">Phase</ToggleButton>
              </ToggleButtonGroup>
            </Grid>

            <Grid item xs={12} md={3}>
              <Typography gutterBottom>Frequency Scale</Typography>
              <ToggleButtonGroup
                value={settings.frequencyScale}
                exclusive
                onChange={(_, value) => value && setSettings(prev => ({ ...prev, frequencyScale: value }))}
                size="small"
              >
                <ToggleButton value="linear">Linear</ToggleButton>
                <ToggleButton value="log">Log</ToggleButton>
              </ToggleButtonGroup>
            </Grid>

            <Grid item xs={12} md={3}>
              <Typography gutterBottom>Color Scheme</Typography>
              <ToggleButtonGroup
                value={settings.colorScheme}
                exclusive
                onChange={(_, value) => value && setSettings(prev => ({ ...prev, colorScheme: value }))}
                size="small"
              >
                <ToggleButton value="spectrum">Spectrum</ToggleButton>
                <ToggleButton value="heatmap">Heat</ToggleButton>
                <ToggleButton value="classic">Classic</ToggleButton>
              </ToggleButtonGroup>
            </Grid>

            <Grid item xs={12} md={3}>
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showPeakMarkers}
                    onChange={(e) => setSettings(prev => ({ ...prev, showPeakMarkers: e.target.checked }))}
                    color="primary"
                  />
                }
                label="Peak Markers"
              />
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showCentroidMarker}
                    onChange={(e) => setSettings(prev => ({ ...prev, showCentroidMarker: e.target.checked }))}
                    color="primary"
                  />
                }
                label="Centroid"
              />
            </Grid>

            <Grid item xs={12} md={6}>
              <Typography gutterBottom>Smoothing</Typography>
              <Slider
                value={settings.smoothing}
                onChange={(_, value) => setSettings(prev => ({ ...prev, smoothing: value as number }))}
                min={0}
                max={0.95}
                step={0.05}
                marks={[
                  { value: 0, label: 'None' },
                  { value: 0.5, label: 'Medium' },
                  { value: 0.9, label: 'High' },
                ]}
                valueLabelDisplay="auto"
              />
            </Grid>
          </Grid>

          {settings.showAnalysisText && spectrumData && (
            <Box mt={2}>
              <Typography variant="subtitle2" color="white" gutterBottom>
                Analysis Results:
              </Typography>
              <Box display="flex" gap={2} flexWrap="wrap">
                <Typography variant="caption" color="grey.300">
                  Peak: {spectrumData.peak_frequency?.toFixed(0) || 'N/A'}Hz
                </Typography>
                <Typography variant="caption" color="grey.300">
                  Centroid: {spectrumData.spectral_centroid?.toFixed(0) || 'N/A'}Hz
                </Typography>
                {spectrumData.settings && (
                  <>
                    <Typography variant="caption" color="grey.300">
                      FFT: {spectrumData.settings.fft_size}
                    </Typography>
                    <Typography variant="caption" color="grey.300">
                      Weighting: {spectrumData.settings.weighting}
                    </Typography>
                  </>
                )}
              </Box>
            </Box>
          )}
        </Box>
      )}
    </Paper>
  );
};

export default SpectrumVisualization;