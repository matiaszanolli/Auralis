import React, { useEffect, useRef, useState } from 'react';
import { Box, Card, CardContent, Typography, FormControlLabel, Switch, Slider } from '@mui/material';

interface AudioVisualizerProps {
  websocket: WebSocket | null;
  width?: number;
  height?: number;
}

interface AudioAnalysis {
  peak_level: number;
  rms_level: number;
  frequency_spectrum: number[];
}

const RealtimeAudioVisualizer: React.FC<AudioVisualizerProps> = ({
  websocket,
  width = 800,
  height = 300
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationFrameRef = useRef<number>();
  const [analysisData, setAnalysisData] = useState<AudioAnalysis | null>(null);
  const [visualizerEnabled, setVisualizerEnabled] = useState(true);
  const [sensitivity, setSensitivity] = useState(50);

  // Generate mock spectrum data for visualization
  const generateMockSpectrum = (baseLevel: number = 0.3): number[] => {
    const spectrum = [];
    for (let i = 0; i < 64; i++) {
      // Create some variation based on frequency bands
      const frequencyFactor = Math.sin(i * 0.1) * 0.3 + 0.7;
      const randomVariation = (Math.random() - 0.5) * 0.4;
      const value = Math.max(0, Math.min(1, baseLevel * frequencyFactor + randomVariation));
      spectrum.push(value);
    }
    return spectrum;
  };

  // WebSocket message handler for real-time data
  useEffect(() => {
    if (!websocket) return;

    const handleMessage = (event: MessageEvent) => {
      try {
        const message = JSON.parse(event.data);

        if (message.type === 'audio_analysis' && message.data) {
          setAnalysisData(message.data);
        }
      } catch (err) {
        console.error('Error parsing WebSocket audio data:', err);
      }
    };

    websocket.addEventListener('message', handleMessage);
    return () => websocket.removeEventListener('message', handleMessage);
  }, [websocket]);

  // Animation loop for the visualizer
  useEffect(() => {
    if (!visualizerEnabled) return;

    const animate = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;

      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      // Clear canvas
      ctx.fillStyle = 'rgba(0, 0, 0, 0.1)';
      ctx.fillRect(0, 0, width, height);

      // Use real data if available, otherwise generate mock data
      const spectrum = analysisData?.frequency_spectrum || generateMockSpectrum(0.2 + Math.random() * 0.3);
      const peakLevel = analysisData?.peak_level || Math.random() * 0.8;
      const rmsLevel = analysisData?.rms_level || Math.random() * 0.5;

      // Draw frequency spectrum bars
      const barWidth = width / spectrum.length;
      const sensitivityFactor = sensitivity / 50;

      spectrum.forEach((value, index) => {
        const barHeight = value * height * 0.7 * sensitivityFactor;
        const x = index * barWidth;
        const y = height - barHeight;

        // Create gradient for bars
        const gradient = ctx.createLinearGradient(0, y, 0, height);
        const hue = (index / spectrum.length) * 360;
        gradient.addColorStop(0, `hsla(${hue}, 70%, 60%, 0.9)`);
        gradient.addColorStop(1, `hsla(${hue}, 70%, 40%, 0.6)`);

        ctx.fillStyle = gradient;
        ctx.fillRect(x, y, barWidth - 1, barHeight);

        // Add glow effect for high values
        if (value > 0.7) {
          ctx.shadowColor = `hsla(${hue}, 70%, 50%, 0.8)`;
          ctx.shadowBlur = 10;
          ctx.fillRect(x, y, barWidth - 1, barHeight);
          ctx.shadowBlur = 0;
        }
      });

      // Draw peak level indicator
      const peakY = height - (peakLevel * height * 0.9);
      ctx.strokeStyle = '#ff4444';
      ctx.lineWidth = 2;
      ctx.setLineDash([5, 5]);
      ctx.beginPath();
      ctx.moveTo(0, peakY);
      ctx.lineTo(width, peakY);
      ctx.stroke();
      ctx.setLineDash([]);

      // Draw RMS level indicator
      const rmsY = height - (rmsLevel * height * 0.9);
      ctx.strokeStyle = '#44ff44';
      ctx.lineWidth = 2;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(0, rmsY);
      ctx.lineTo(width, rmsY);
      ctx.stroke();
      ctx.setLineDash([]);

      // Draw level text
      ctx.fillStyle = 'rgba(255, 255, 255, 0.9)';
      ctx.font = '12px monospace';
      ctx.fillText(`Peak: ${(peakLevel * 100).toFixed(1)}%`, 10, 20);
      ctx.fillText(`RMS: ${(rmsLevel * 100).toFixed(1)}%`, 10, 35);

      // Draw frequency labels
      ctx.fillStyle = 'rgba(255, 255, 255, 0.6)';
      ctx.font = '10px monospace';
      const labels = ['60Hz', '250Hz', '1kHz', '4kHz', '16kHz'];
      labels.forEach((label, index) => {
        const x = (index / (labels.length - 1)) * (width - 40) + 20;
        ctx.fillText(label, x, height - 5);
      });

      animationFrameRef.current = requestAnimationFrame(animate);
    };

    animationFrameRef.current = requestAnimationFrame(animate);

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [analysisData, visualizerEnabled, sensitivity, width, height]);

  return (
    <Card
      elevation={3}
      sx={{
        background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
        color: 'white',
        borderRadius: 3
      }}
    >
      <CardContent>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
          <Typography variant="h6">
            🎚️ Real-time Audio Visualizer
          </Typography>

          <Box display="flex" alignItems="center" gap={2}>
            <FormControlLabel
              control={
                <Switch
                  checked={visualizerEnabled}
                  onChange={(e) => setVisualizerEnabled(e.target.checked)}
                  sx={{
                    '& .MuiSwitch-switchBase.Mui-checked': {
                      color: 'white',
                    },
                    '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                      backgroundColor: 'rgba(255,255,255,0.5)',
                    },
                  }}
                />
              }
              label="Enable"
              sx={{ color: 'white', m: 0 }}
            />
          </Box>
        </Box>

        {/* Sensitivity Control */}
        <Box mb={2}>
          <Typography variant="caption" gutterBottom>
            Sensitivity: {sensitivity}%
          </Typography>
          <Slider
            value={sensitivity}
            onChange={(_, value) => setSensitivity(value as number)}
            min={10}
            max={200}
            sx={{
              color: 'rgba(255,255,255,0.8)',
              '& .MuiSlider-thumb': {
                backgroundColor: 'white',
              }
            }}
          />
        </Box>

        {/* Canvas for visualization */}
        <Box
          sx={{
            border: '1px solid rgba(255,255,255,0.2)',
            borderRadius: 2,
            overflow: 'hidden',
            background: 'rgba(0,0,0,0.3)'
          }}
        >
          <canvas
            ref={canvasRef}
            width={width}
            height={height}
            style={{
              display: 'block',
              width: '100%',
              height: 'auto'
            }}
          />
        </Box>

        {/* Analysis Info */}
        {analysisData && (
          <Box mt={2}>
            <Typography variant="caption" color="rgba(255,255,255,0.7)">
              Live audio data • Peak: {(analysisData.peak_level * 100).toFixed(1)}% •
              RMS: {(analysisData.rms_level * 100).toFixed(1)}% •
              Spectrum bands: {analysisData.frequency_spectrum.length}
            </Typography>
          </Box>
        )}

        {!analysisData && (
          <Box mt={2}>
            <Typography variant="caption" color="rgba(255,255,255,0.7)">
              Simulation mode • Connect audio player for live data
            </Typography>
          </Box>
        )}
      </CardContent>
    </Card>
  );
};

export default RealtimeAudioVisualizer;