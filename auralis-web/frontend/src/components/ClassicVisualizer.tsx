import React, { useRef, useEffect, useState } from 'react';
import {
  Box,
  Paper,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
  Slider,
  FormControlLabel,
  Switch
} from '@mui/material';

type VisualizerType = 'bars' | 'oscilloscope' | 'spectrum' | 'classic';

interface ClassicVisualizerProps {
  isPlaying?: boolean;
  audioData?: Float32Array;
  width?: number;
  height?: number;
}

const ClassicVisualizer: React.FC<ClassicVisualizerProps> = ({
  isPlaying = false,
  audioData,
  width = 400,
  height = 200
}) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [visualizerType, setVisualizerType] = useState<VisualizerType>('bars');
  const [intensity, setIntensity] = useState(50);
  const [smoothing, setSmoothing] = useState(0.8);
  const [showParticles, setShowParticles] = useState(true);

  // Animation frame reference
  const animationRef = useRef<number>();

  // Particles for extra visual flair
  const particles = useRef<Array<{
    x: number;
    y: number;
    vx: number;
    vy: number;
    life: number;
    maxLife: number;
    size: number;
  }>>([]);

  // Generate mock audio data for demonstration
  const generateMockAudioData = (): Float32Array => {
    const data = new Float32Array(128);
    for (let i = 0; i < data.length; i++) {
      data[i] = Math.random() * (intensity / 100);
    }
    return data;
  };

  // Classic bar visualizer (WinAmp style)
  const drawBarsVisualizer = (ctx: CanvasRenderingContext2D, data: Float32Array) => {
    const barWidth = width / data.length;
    const gradient = ctx.createLinearGradient(0, height, 0, 0);

    // Classic green-to-red gradient
    gradient.addColorStop(0, '#00ff00');
    gradient.addColorStop(0.5, '#ffff00');
    gradient.addColorStop(1, '#ff0000');

    ctx.fillStyle = gradient;

    for (let i = 0; i < data.length; i++) {
      const barHeight = Math.max(2, data[i] * height * 0.8);
      const x = i * barWidth;
      const y = height - barHeight;

      // Draw bar with classic 3D effect
      ctx.fillRect(x + 1, y, barWidth - 2, barHeight);

      // Add highlight for 3D effect
      ctx.fillStyle = 'rgba(255, 255, 255, 0.3)';
      ctx.fillRect(x + 1, y, 2, barHeight);

      // Reset gradient
      ctx.fillStyle = gradient;
    }
  };

  // Classic oscilloscope (retro waveform)
  const drawOscilloscope = (ctx: CanvasRenderingContext2D, data: Float32Array) => {
    ctx.strokeStyle = '#00ff00';
    ctx.lineWidth = 2;
    ctx.beginPath();

    const sliceWidth = width / data.length;
    let x = 0;

    for (let i = 0; i < data.length; i++) {
      const v = data[i] * height * 0.5;
      const y = height / 2 + v;

      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }

      x += sliceWidth;
    }

    ctx.stroke();

    // Add glow effect
    ctx.shadowBlur = 10;
    ctx.shadowColor = '#00ff00';
    ctx.stroke();
    ctx.shadowBlur = 0;
  };

  // Spectrum analyzer (frequency-based)
  const drawSpectrum = (ctx: CanvasRenderingContext2D, data: Float32Array) => {
    const barWidth = width / data.length;

    for (let i = 0; i < data.length; i++) {
      const barHeight = data[i] * height;
      const hue = (i / data.length) * 360;

      ctx.fillStyle = `hsl(${hue}, 100%, 50%)`;
      ctx.fillRect(i * barWidth, height - barHeight, barWidth - 1, barHeight);

      // Add mirror effect
      const gradient = ctx.createLinearGradient(0, height, 0, height + barHeight * 0.5);
      gradient.addColorStop(0, `hsla(${hue}, 100%, 50%, 0.3)`);
      gradient.addColorStop(1, `hsla(${hue}, 100%, 50%, 0)`);

      ctx.fillStyle = gradient;
      ctx.fillRect(i * barWidth, height, barWidth - 1, barHeight * 0.5);
    }
  };

  // Classic WinAmp-style visualizer
  const drawClassicVisualizer = (ctx: CanvasRenderingContext2D, data: Float32Array) => {
    // Create classic pixel-style visualization
    const pixelSize = 4;
    const cols = Math.floor(width / pixelSize);
    const rows = Math.floor(height / pixelSize);

    for (let x = 0; x < cols; x++) {
      const dataIndex = Math.floor((x / cols) * data.length);
      const amplitude = data[dataIndex] || 0;
      const pixelHeight = Math.floor(amplitude * rows);

      for (let y = 0; y < pixelHeight; y++) {
        const intensity = y / pixelHeight;
        let color;

        if (intensity < 0.3) color = '#00ff00';
        else if (intensity < 0.7) color = '#ffff00';
        else color = '#ff0000';

        ctx.fillStyle = color;
        ctx.fillRect(
          x * pixelSize,
          height - (y + 1) * pixelSize,
          pixelSize - 1,
          pixelSize - 1
        );
      }
    }
  };

  // Update particles
  const updateParticles = (ctx: CanvasRenderingContext2D, data: Float32Array) => {
    if (!showParticles) return;

    // Add new particles based on audio intensity
    const avgAmplitude = data.reduce((sum, val) => sum + val, 0) / data.length;
    if (avgAmplitude > 0.1 && particles.current.length < 50) {
      particles.current.push({
        x: Math.random() * width,
        y: height,
        vx: (Math.random() - 0.5) * 4,
        vy: -Math.random() * 8 - 2,
        life: 0,
        maxLife: 60,
        size: Math.random() * 3 + 1
      });
    }

    // Update and draw particles
    ctx.save();
    particles.current = particles.current.filter(particle => {
      particle.x += particle.vx;
      particle.y += particle.vy;
      particle.vy += 0.1; // gravity
      particle.life++;

      const alpha = 1 - (particle.life / particle.maxLife);
      ctx.globalAlpha = alpha;
      ctx.fillStyle = '#ffffff';
      ctx.beginPath();
      ctx.arc(particle.x, particle.y, particle.size, 0, Math.PI * 2);
      ctx.fill();

      return particle.life < particle.maxLife && particle.y < height + 10;
    });
    ctx.restore();
  };

  // Main animation loop
  const animate = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Clear canvas with fade effect
    ctx.fillStyle = 'rgba(0, 0, 0, 0.1)';
    ctx.fillRect(0, 0, width, height);

    if (isPlaying) {
      const data = audioData || generateMockAudioData();

      // Apply smoothing
      for (let i = 0; i < data.length; i++) {
        data[i] = data[i] * (1 - smoothing) + (data[i - 1] || 0) * smoothing;
      }

      // Draw based on selected visualizer type
      switch (visualizerType) {
        case 'bars':
          drawBarsVisualizer(ctx, data);
          break;
        case 'oscilloscope':
          drawOscilloscope(ctx, data);
          break;
        case 'spectrum':
          drawSpectrum(ctx, data);
          break;
        case 'classic':
          drawClassicVisualizer(ctx, data);
          break;
      }

      // Update particles
      updateParticles(ctx, data);
    } else {
      // Show static pattern when not playing
      ctx.fillStyle = 'rgba(255, 255, 255, 0.1)';
      ctx.font = '16px monospace';
      ctx.textAlign = 'center';
      ctx.fillText('🎵 Play music to see the magic', width / 2, height / 2);
    }

    animationRef.current = requestAnimationFrame(animate);
  };

  useEffect(() => {
    animate();
    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [isPlaying, visualizerType, intensity, smoothing, showParticles]);

  return (
    <Paper
      elevation={3}
      sx={{
        p: 3,
        background: 'linear-gradient(135deg, #0a0a0a 0%, #1a1a1a 100%)',
        border: '2px solid #333',
        borderRadius: 2
      }}
    >
      {/* Header */}
      <Box sx={{ mb: 2, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Typography
          variant="h6"
          sx={{
            fontFamily: 'monospace',
            color: '#00ff00',
            textShadow: '0 0 10px #00ff00'
          }}
        >
          🎵 CLASSIC VISUALIZER
        </Typography>
        <Typography
          variant="caption"
          sx={{
            fontFamily: 'monospace',
            color: '#888',
            animation: isPlaying ? 'blink 1s infinite' : 'none',
            '@keyframes blink': {
              '0%, 50%': { opacity: 1 },
              '51%, 100%': { opacity: 0.3 }
            }
          }}
        >
          {isPlaying ? '● REC' : '○ STOP'}
        </Typography>
      </Box>

      {/* Canvas */}
      <Box
        sx={{
          mb: 2,
          border: '1px solid #333',
          borderRadius: 1,
          overflow: 'hidden',
          background: '#000'
        }}
      >
        <canvas
          ref={canvasRef}
          width={width}
          height={height}
          style={{ display: 'block', width: '100%', height: 'auto' }}
        />
      </Box>

      {/* Controls */}
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        {/* Visualizer Type */}
        <Box>
          <Typography variant="caption" sx={{ color: '#888', mb: 1, display: 'block' }}>
            MODE
          </Typography>
          <ToggleButtonGroup
            value={visualizerType}
            exclusive
            onChange={(_, value) => value && setVisualizerType(value)}
            size="small"
            sx={{
              '& .MuiToggleButton-root': {
                color: '#888',
                borderColor: '#333',
                fontFamily: 'monospace',
                fontSize: '10px',
                '&.Mui-selected': {
                  background: '#00ff00',
                  color: '#000',
                  '&:hover': {
                    background: '#00dd00'
                  }
                }
              }
            }}
          >
            <ToggleButton value="bars">BARS</ToggleButton>
            <ToggleButton value="oscilloscope">SCOPE</ToggleButton>
            <ToggleButton value="spectrum">SPECTRUM</ToggleButton>
            <ToggleButton value="classic">RETRO</ToggleButton>
          </ToggleButtonGroup>
        </Box>

        {/* Settings */}
        <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
          {/* Intensity */}
          <Box sx={{ minWidth: 120 }}>
            <Typography variant="caption" sx={{ color: '#888' }}>
              GAIN: {intensity}%
            </Typography>
            <Slider
              value={intensity}
              onChange={(_, value) => setIntensity(value as number)}
              min={10}
              max={100}
              size="small"
              sx={{
                color: '#00ff00',
                '& .MuiSlider-thumb': {
                  background: '#00ff00',
                  boxShadow: '0 0 10px #00ff00'
                }
              }}
            />
          </Box>

          {/* Smoothing */}
          <Box sx={{ minWidth: 120 }}>
            <Typography variant="caption" sx={{ color: '#888' }}>
              SMOOTH: {Math.round(smoothing * 100)}%
            </Typography>
            <Slider
              value={smoothing}
              onChange={(_, value) => setSmoothing(value as number)}
              min={0}
              max={0.95}
              step={0.05}
              size="small"
              sx={{
                color: '#ffff00',
                '& .MuiSlider-thumb': {
                  background: '#ffff00',
                  boxShadow: '0 0 10px #ffff00'
                }
              }}
            />
          </Box>
        </Box>

        {/* Particles Toggle */}
        <FormControlLabel
          control={
            <Switch
              checked={showParticles}
              onChange={(e) => setShowParticles(e.target.checked)}
              size="small"
              sx={{
                '& .MuiSwitch-switchBase.Mui-checked': {
                  color: '#00ff00'
                },
                '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                  backgroundColor: '#006600'
                }
              }}
            />
          }
          label={
            <Typography variant="caption" sx={{ color: '#888', fontFamily: 'monospace' }}>
              PARTICLES
            </Typography>
          }
        />
      </Box>
    </Paper>
  );
};

export default ClassicVisualizer;