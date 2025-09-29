import React, { useRef, useEffect, useState, useCallback } from 'react';
import { Box, Paper, Typography, Grid, FormControlLabel, Switch, Slider } from '@mui/material';

interface CorrelationData {
  correlation: number;
  phaseCorrelation: number;
  stereoWidth: number;
  monoCompatibility: number;
  leftLevel: number;
  rightLevel: number;
  midLevel: number;
  sideLevel: number;
  stereoCenter: number;
  stereoSpread: number;
  correlationHistory: number[];
  phaseHistory?: number[];
}

interface CorrelationDisplaySettings {
  showHistory: boolean;
  showVectorscope: boolean;
  showStereoField: boolean;
  showNumericValues: boolean;
  historyLength: number;
  updateRate: number;
  vectorscopeSize: number;
}

interface CorrelationDisplayProps {
  correlationData?: CorrelationData;
  width?: number;
  height?: number;
  className?: string;
}

const defaultSettings: CorrelationDisplaySettings = {
  showHistory: true,
  showVectorscope: true,
  showStereoField: true,
  showNumericValues: true,
  historyLength: 100,
  updateRate: 20,
  vectorscopeSize: 200
};

const defaultData: CorrelationData = {
  correlation: 0.5,
  phaseCorrelation: 0.8,
  stereoWidth: 0.6,
  monoCompatibility: 0.75,
  leftLevel: 0.5,
  rightLevel: 0.5,
  midLevel: 0.7,
  sideLevel: 0.3,
  stereoCenter: 0.0,
  stereoSpread: 0.5,
  correlationHistory: Array(100).fill(0.5),
  phaseHistory: Array(100).fill(0.8)
};

export const CorrelationDisplay: React.FC<CorrelationDisplayProps> = ({
  correlationData = defaultData,
  width = 800,
  height = 600,
  className
}) => {
  const [settings, setSettings] = useState<CorrelationDisplaySettings>(defaultSettings);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const historyCanvasRef = useRef<HTMLCanvasElement>(null);
  const vectorscopeCanvasRef = useRef<HTMLCanvasElement>(null);
  const animationFrameRef = useRef<number>();

  const getCorrelationColor = useCallback((correlation: number): string => {
    if (correlation < -0.5) return '#FF1744'; // Red - phase issues
    if (correlation < 0) return '#FF9800';    // Orange - some issues
    if (correlation < 0.3) return '#FFEB3B';  // Yellow - narrow
    if (correlation < 0.8) return '#4CAF50';  // Green - good
    return '#2196F3';                          // Blue - very wide
  }, []);

  const drawCorrelationMeter = useCallback((
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    width: number,
    height: number,
    value: number,
    label: string,
    range: { min: number; max: number } = { min: -1, max: 1 }
  ) => {
    // Draw background
    ctx.fillStyle = '#1A1A1A';
    ctx.fillRect(x, y, width, height);

    // Draw scale
    const normalizedValue = (value - range.min) / (range.max - range.min);
    const meterHeight = normalizedValue * height;

    // Color based on correlation value
    const color = label.toLowerCase().includes('correlation')
      ? getCorrelationColor(value)
      : value > 0.7 ? '#4CAF50' : value > 0.4 ? '#FFEB3B' : '#FF9800';

    ctx.fillStyle = color;
    ctx.fillRect(x + 2, y + height - meterHeight, width - 4, meterHeight);

    // Draw border
    ctx.strokeStyle = '#555555';
    ctx.lineWidth = 1;
    ctx.strokeRect(x, y, width, height);

    // Draw center line for correlation meters
    if (range.min < 0 && range.max > 0) {
      const centerY = y + height * (0 - range.min) / (range.max - range.min);
      ctx.strokeStyle = '#FFFFFF';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, centerY);
      ctx.lineTo(x + width, centerY);
      ctx.stroke();
    }

    // Draw scale marks
    ctx.fillStyle = '#CCCCCC';
    ctx.font = '10px Arial';
    ctx.textAlign = 'right';

    const marks = range.min < 0 ? [-1, -0.5, 0, 0.5, 1] : [0, 0.25, 0.5, 0.75, 1];
    for (const mark of marks) {
      if (mark >= range.min && mark <= range.max) {
        const markY = y + height * (1 - (mark - range.min) / (range.max - range.min));
        ctx.fillText(mark.toFixed(1), x - 5, markY + 3);

        ctx.fillStyle = '#555555';
        ctx.fillRect(x, markY, 4, 1);
        ctx.fillStyle = '#CCCCCC';
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

    // Draw value
    ctx.fillStyle = '#FFFFFF';
    ctx.font = 'bold 14px Arial';
    ctx.textAlign = 'center';
    ctx.fillText(value.toFixed(2), x + width / 2, y - 10);
  }, [getCorrelationColor]);

  const drawVectorscope = useCallback((
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    size: number,
    data: CorrelationData
  ) => {
    const centerX = x + size / 2;
    const centerY = y + size / 2;
    const radius = size / 2 - 20;

    // Clear background
    ctx.fillStyle = '#0A0A0A';
    ctx.fillRect(x, y, size, size);

    // Draw grid
    ctx.strokeStyle = '#333333';
    ctx.lineWidth = 1;

    // Concentric circles
    for (let r = radius / 4; r <= radius; r += radius / 4) {
      ctx.beginPath();
      ctx.arc(centerX, centerY, r, 0, 2 * Math.PI);
      ctx.stroke();
    }

    // Axes
    ctx.beginPath();
    ctx.moveTo(centerX - radius, centerY);
    ctx.lineTo(centerX + radius, centerY);
    ctx.moveTo(centerX, centerY - radius);
    ctx.lineTo(centerX, centerY + radius);
    ctx.stroke();

    // Diagonal lines for stereo field
    ctx.strokeStyle = '#555555';
    ctx.setLineDash([2, 2]);
    ctx.beginPath();
    ctx.moveTo(centerX - radius * 0.707, centerY - radius * 0.707);
    ctx.lineTo(centerX + radius * 0.707, centerY + radius * 0.707);
    ctx.moveTo(centerX - radius * 0.707, centerY + radius * 0.707);
    ctx.lineTo(centerX + radius * 0.707, centerY - radius * 0.707);
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw stereo vector
    const stereoX = data.stereoCenter * radius * 0.8;
    const stereoY = data.stereoSpread * radius * 0.8 * Math.sin(data.phaseCorrelation * Math.PI);

    // Draw trace (history of positions)
    if (data.correlationHistory && data.correlationHistory.length > 1) {
      ctx.strokeStyle = getCorrelationColor(data.correlation) + '40';
      ctx.lineWidth = 2;
      ctx.beginPath();

      for (let i = 1; i < data.correlationHistory.length; i++) {
        const histCorr = data.correlationHistory[i];
        const histPhase = data.phaseHistory?.[i] || data.phaseCorrelation;

        const hx = centerX + histCorr * radius * 0.6;
        const hy = centerY + histPhase * radius * 0.6;

        if (i === 1) {
          ctx.moveTo(hx, hy);
        } else {
          ctx.lineTo(hx, hy);
        }
      }
      ctx.stroke();
    }

    // Draw current position
    const currentX = centerX + stereoX;
    const currentY = centerY - stereoY;

    ctx.fillStyle = getCorrelationColor(data.correlation);
    ctx.beginPath();
    ctx.arc(currentX, currentY, 6, 0, 2 * Math.PI);
    ctx.fill();

    // Draw correlation indicator (line from center)
    ctx.strokeStyle = getCorrelationColor(data.correlation);
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(centerX, centerY);
    ctx.lineTo(currentX, currentY);
    ctx.stroke();

    // Draw border
    ctx.strokeStyle = '#555555';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, 0, 2 * Math.PI);
    ctx.stroke();

    // Labels
    ctx.fillStyle = '#CCCCCC';
    ctx.font = '12px Arial';
    ctx.textAlign = 'center';

    ctx.fillText('L', centerX - radius - 15, centerY + 4);
    ctx.fillText('R', centerX + radius + 15, centerY + 4);
    ctx.fillText('M', centerX, centerY - radius - 10);
    ctx.fillText('S', centerX, centerY + radius + 20);

    // Phase correlation value
    ctx.fillStyle = '#FFFFFF';
    ctx.font = 'bold 16px Arial';
    ctx.textAlign = 'center';
    ctx.fillText(`φ: ${data.phaseCorrelation.toFixed(2)}`, centerX, y + size + 20);
  }, [getCorrelationColor]);

  const drawCorrelationHistory = useCallback((
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    width: number,
    height: number,
    history: number[]
  ) => {
    if (!history || history.length < 2) return;

    // Clear background
    ctx.fillStyle = '#1A1A1A';
    ctx.fillRect(x, y, width, height);

    // Draw grid
    ctx.strokeStyle = '#333333';
    ctx.lineWidth = 1;

    // Horizontal lines
    for (let level = -1; level <= 1; level += 0.5) {
      const lineY = y + height / 2 - (level * height / 2);
      ctx.beginPath();
      ctx.moveTo(x, lineY);
      ctx.lineTo(x + width, lineY);
      ctx.stroke();
    }

    // Vertical time markers
    const timeInterval = Math.max(1, Math.floor(history.length / 10));
    for (let i = 0; i < history.length; i += timeInterval) {
      const lineX = x + (i / history.length) * width;
      ctx.beginPath();
      ctx.moveTo(lineX, y);
      ctx.lineTo(lineX, y + height);
      ctx.stroke();
    }

    // Draw correlation history
    ctx.strokeStyle = '#4FC3F7';
    ctx.lineWidth = 2;
    ctx.beginPath();

    for (let i = 0; i < history.length; i++) {
      const plotX = x + (i / history.length) * width;
      const plotY = y + height / 2 - (history[i] * height / 2);

      if (i === 0) {
        ctx.moveTo(plotX, plotY);
      } else {
        ctx.lineTo(plotX, plotY);
      }
    }
    ctx.stroke();

    // Draw border
    ctx.strokeStyle = '#555555';
    ctx.lineWidth = 1;
    ctx.strokeRect(x, y, width, height);

    // Scale labels
    ctx.fillStyle = '#CCCCCC';
    ctx.font = '10px Arial';
    ctx.textAlign = 'right';

    for (let level = -1; level <= 1; level += 0.5) {
      const labelY = y + height / 2 - (level * height / 2) + 3;
      ctx.fillText(level.toFixed(1), x - 5, labelY);
    }
  }, []);

  const drawStereoField = useCallback((
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    width: number,
    height: number,
    data: CorrelationData
  ) => {
    // Clear background
    ctx.fillStyle = '#1A1A1A';
    ctx.fillRect(x, y, width, height);

    // Draw stereo field visualization
    const centerX = x + width / 2;
    const fieldWidth = width * 0.8;

    // Background gradient representing stereo field
    const gradient = ctx.createLinearGradient(x, y, x + width, y);
    gradient.addColorStop(0, '#FF4444'); // Left
    gradient.addColorStop(0.5, '#44FF44'); // Center
    gradient.addColorStop(1, '#4444FF'); // Right

    ctx.fillStyle = gradient;
    ctx.globalAlpha = 0.3;
    ctx.fillRect(x + width * 0.1, y + height * 0.3, fieldWidth, height * 0.4);
    ctx.globalAlpha = 1.0;

    // Draw stereo position indicator
    const stereoPosition = (data.stereoCenter + 1) / 2; // -1 to 1 -> 0 to 1
    const positionX = x + width * 0.1 + stereoPosition * fieldWidth;

    ctx.fillStyle = '#FFFFFF';
    ctx.beginPath();
    ctx.arc(positionX, y + height / 2, 8, 0, 2 * Math.PI);
    ctx.fill();

    // Draw spread indicator
    const spreadWidth = data.stereoSpread * fieldWidth;
    ctx.fillStyle = '#FFFF00';
    ctx.globalAlpha = 0.5;
    ctx.fillRect(
      positionX - spreadWidth / 2,
      y + height * 0.4,
      spreadWidth,
      height * 0.2
    );
    ctx.globalAlpha = 1.0;

    // Labels
    ctx.fillStyle = '#CCCCCC';
    ctx.font = '12px Arial';
    ctx.textAlign = 'left';
    ctx.fillText('L', x + 5, y + height / 2);
    ctx.textAlign = 'right';
    ctx.fillText('R', x + width - 5, y + height / 2);
    ctx.textAlign = 'center';
    ctx.fillText('C', centerX, y + height / 2);

    // Border
    ctx.strokeStyle = '#555555';
    ctx.lineWidth = 1;
    ctx.strokeRect(x, y, width, height);
  }, []);

  const render = useCallback(() => {
    const canvas = canvasRef.current;
    const historyCanvas = historyCanvasRef.current;
    const vectorscopeCanvas = vectorscopeCanvasRef.current;

    if (!canvas || !historyCanvas || !vectorscopeCanvas) return;

    const ctx = canvas.getContext('2d');
    const historyCtx = historyCanvas.getContext('2d');
    const vectorscopeCtx = vectorscopeCanvas.getContext('2d');

    if (!ctx || !historyCtx || !vectorscopeCtx) return;

    // Main meters
    ctx.fillStyle = '#0D1B2A';
    ctx.fillRect(0, 0, width, height);

    const meterWidth = 50;
    const meterHeight = height * 0.6;
    const meterY = 40;

    // Draw correlation meters
    drawCorrelationMeter(ctx, 20, meterY, meterWidth, meterHeight,
      correlationData.correlation, 'Correlation');
    drawCorrelationMeter(ctx, 90, meterY, meterWidth, meterHeight,
      correlationData.phaseCorrelation, 'Phase Corr', { min: 0, max: 1 });
    drawCorrelationMeter(ctx, 160, meterY, meterWidth, meterHeight,
      correlationData.stereoWidth, 'Width', { min: 0, max: 1 });
    drawCorrelationMeter(ctx, 230, meterY, meterWidth, meterHeight,
      correlationData.monoCompatibility, 'Mono Compat', { min: 0, max: 1 });

    // Draw stereo field
    if (settings.showStereoField) {
      drawStereoField(ctx, 300, meterY, 200, 100, correlationData);
    }

    // Vectorscope
    if (settings.showVectorscope) {
      const vectorscopeSize = settings.vectorscopeSize;
      vectorscopeCtx.clearRect(0, 0, vectorscopeSize, vectorscopeSize);
      drawVectorscope(vectorscopeCtx, 0, 0, vectorscopeSize, correlationData);
    }

    // History graph
    if (settings.showHistory) {
      const historyWidth = width - 40;
      const historyHeight = 120;
      historyCtx.clearRect(0, 0, historyWidth, historyHeight);
      drawCorrelationHistory(historyCtx, 0, 0, historyWidth, historyHeight,
        correlationData.correlationHistory);
    }

  }, [width, height, settings, correlationData, drawCorrelationMeter,
      drawVectorscope, drawCorrelationHistory, drawStereoField]);

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
        <Typography variant="h6" gutterBottom sx={{ color: 'white' }}>
          Stereo Correlation & Phase Analysis
        </Typography>

        <Grid container spacing={2}>
          <Grid item xs={12} lg={8}>
            <canvas
              ref={canvasRef}
              width={width}
              height={height}
              style={{
                border: '1px solid #444',
                borderRadius: '4px',
                display: 'block',
                backgroundColor: '#0D1B2A'
              }}
            />

            {settings.showHistory && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="subtitle2" sx={{ color: 'white', mb: 1 }}>
                  Correlation History
                </Typography>
                <canvas
                  ref={historyCanvasRef}
                  width={width - 40}
                  height={120}
                  style={{
                    border: '1px solid #444',
                    borderRadius: '4px',
                    display: 'block'
                  }}
                />
              </Box>
            )}
          </Grid>

          <Grid item xs={12} lg={4}>
            {settings.showVectorscope && (
              <Box>
                <Typography variant="subtitle2" sx={{ color: 'white', mb: 1 }}>
                  Vectorscope
                </Typography>
                <canvas
                  ref={vectorscopeCanvasRef}
                  width={settings.vectorscopeSize}
                  height={settings.vectorscopeSize}
                  style={{
                    border: '1px solid #444',
                    borderRadius: '4px',
                    display: 'block',
                    marginBottom: '16px'
                  }}
                />
              </Box>
            )}

            {settings.showNumericValues && (
              <Box sx={{ color: 'white' }}>
                <Typography variant="subtitle2" gutterBottom>
                  Current Values
                </Typography>
                <Typography variant="body2">
                  Correlation: {correlationData.correlation.toFixed(3)}
                </Typography>
                <Typography variant="body2">
                  Phase Corr: {correlationData.phaseCorrelation.toFixed(3)}
                </Typography>
                <Typography variant="body2">
                  Stereo Width: {correlationData.stereoWidth.toFixed(3)}
                </Typography>
                <Typography variant="body2">
                  Mono Compat: {correlationData.monoCompatibility.toFixed(3)}
                </Typography>
                <Typography variant="body2">
                  Mid Level: {correlationData.midLevel.toFixed(3)}
                </Typography>
                <Typography variant="body2">
                  Side Level: {correlationData.sideLevel.toFixed(3)}
                </Typography>
              </Box>
            )}
          </Grid>
        </Grid>

        <Box sx={{ mt: 2 }}>
          <Grid container spacing={2}>
            <Grid item xs={6} sm={3}>
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showHistory}
                    onChange={(e) => setSettings(prev => ({ ...prev, showHistory: e.target.checked }))}
                    size="small"
                  />
                }
                label="History"
                sx={{ color: 'white' }}
              />
            </Grid>
            <Grid item xs={6} sm={3}>
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showVectorscope}
                    onChange={(e) => setSettings(prev => ({ ...prev, showVectorscope: e.target.checked }))}
                    size="small"
                  />
                }
                label="Vectorscope"
                sx={{ color: 'white' }}
              />
            </Grid>
            <Grid item xs={6} sm={3}>
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showStereoField}
                    onChange={(e) => setSettings(prev => ({ ...prev, showStereoField: e.target.checked }))}
                    size="small"
                  />
                }
                label="Stereo Field"
                sx={{ color: 'white' }}
              />
            </Grid>
            <Grid item xs={6} sm={3}>
              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showNumericValues}
                    onChange={(e) => setSettings(prev => ({ ...prev, showNumericValues: e.target.checked }))}
                    size="small"
                  />
                }
                label="Values"
                sx={{ color: 'white' }}
              />
            </Grid>
          </Grid>
        </Box>
      </Paper>
    </Box>
  );
};

export default CorrelationDisplay;