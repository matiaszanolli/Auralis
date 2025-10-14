import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Card,
  CardMedia,
  Typography,
  IconButton,
  Slider,
  Switch,
  FormControlLabel,
  Paper,
  Container,
  Chip,
  Fade,
  Zoom
} from '@mui/material';
import {
  PlayArrow,
  Pause,
  SkipNext,
  SkipPrevious,
  VolumeUp,
  Shuffle,
  Repeat,
  FavoriteOutlined,
  Favorite,
  AutoAwesome
} from '@mui/icons-material';

interface Track {
  id: number;
  title: string;
  artist: string;
  album: string;
  duration: number;
  albumArt?: string;
  isEnhanced?: boolean;
}

interface MagicalMusicPlayerProps {
  currentTrack?: Track;
  isPlaying?: boolean;
  onPlayPause?: () => void;
  onNext?: () => void;
  onPrevious?: () => void;
  onEnhancementToggle?: (enabled: boolean) => void;
}

const MagicalMusicPlayer: React.FC<MagicalMusicPlayerProps> = ({
  currentTrack,
  isPlaying = false,
  onPlayPause,
  onNext,
  onPrevious,
  onEnhancementToggle
}) => {
  const [currentTime, setCurrentTime] = useState(0);
  const [volume, setVolume] = useState(80);
  const [isLoved, setIsLoved] = useState(false);
  const [isEnhanced, setIsEnhanced] = useState(true);
  const [showEnhancementGlow, setShowEnhancementGlow] = useState(false);

  // Audio visualization canvas ref
  const visualizerRef = useRef<HTMLCanvasElement>(null);

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const handleEnhancementToggle = () => {
    const newState = !isEnhanced;
    setIsEnhanced(newState);
    setShowEnhancementGlow(newState);
    onEnhancementToggle?.(newState);

    // Hide glow after animation
    if (newState) {
      setTimeout(() => setShowEnhancementGlow(false), 2000);
    }
  };

  // Classic audio visualizer effect
  useEffect(() => {
    if (!visualizerRef.current || !isPlaying) return;

    const canvas = visualizerRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationId: number;

    const draw = () => {
      const width = canvas.width;
      const height = canvas.height;

      // Clear canvas
      ctx.fillStyle = 'rgba(18, 18, 18, 0.3)';
      ctx.fillRect(0, 0, width, height);

      // Create classic bar visualizer
      const barWidth = width / 32;
      const gradient = ctx.createLinearGradient(0, height, 0, 0);
      gradient.addColorStop(0, '#06B6D4'); // Aurora Cyan
      gradient.addColorStop(0.5, '#7C3AED'); // Aurora Violet
      gradient.addColorStop(1, '#F472B6'); // Aurora Pink

      ctx.fillStyle = gradient;

      // Animate bars (simulate audio data)
      for (let i = 0; i < 32; i++) {
        const barHeight = Math.random() * height * 0.8;
        const x = i * barWidth;
        const y = height - barHeight;

        ctx.fillRect(x, y, barWidth - 2, barHeight);
      }

      animationId = requestAnimationFrame(draw);
    };

    draw();

    return () => {
      cancelAnimationFrame(animationId);
    };
  }, [isPlaying]);

  if (!currentTrack) {
    return (
      <Paper
        elevation={0}
        sx={{
          p: 4,
          textAlign: 'center',
          background: 'var(--charcoal)',
          color: 'var(--silver)'
        }}
      >
        <Typography
          variant="h6"
          sx={{
            fontFamily: 'var(--font-body)',
            color: 'var(--silver)',
            opacity: 0.7
          }}
        >
          🎵 Select a track to begin your magical music journey
        </Typography>
      </Paper>
    );
  }

  return (
    <Container maxWidth="md" sx={{ py: 4 }}>
      <Card
        elevation={12}
        sx={{
          background: 'var(--charcoal)',
          color: 'var(--silver)',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid rgba(226, 232, 240, 0.1)',
          overflow: 'hidden',
          position: 'relative'
        }}
      >
        {/* Enhancement Glow Effect */}
        {showEnhancementGlow && (
          <Box
            sx={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              background: 'radial-gradient(circle, rgba(124, 58, 237, 0.3) 0%, transparent 70%)',
              zIndex: 1,
              pointerEvents: 'none'
            }}
          />
        )}

        <Box sx={{ display: 'flex', p: 3, position: 'relative', zIndex: 2 }}>
          {/* Album Art Section */}
          <Box sx={{ position: 'relative', mr: 3 }}>
            <CardMedia
              component="img"
              sx={{
                width: 200,
                height: 200,
                borderRadius: 2,
                boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
                transition: 'transform 0.3s ease',
                transform: isPlaying ? 'scale(1.02)' : 'scale(1)',
              }}
              image={currentTrack.albumArt || '/placeholder-album.jpg'}
              alt={currentTrack.album}
            />

            {/* Enhancement Badge */}
            <Zoom in={isEnhanced}>
              <Chip
                icon={<AutoAwesome />}
                label="Enhanced"
                size="small"
                sx={{
                  position: 'absolute',
                  top: 8,
                  right: 8,
                  background: 'var(--aurora-gradient)',
                  color: 'white',
                  fontFamily: 'var(--font-heading)',
                  fontWeight: 600,
                  boxShadow: 'var(--glow-medium)'
                }}
              />
            </Zoom>
          </Box>

          {/* Track Info & Controls */}
          <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            {/* Track Information */}
            <Box sx={{ mb: 2 }}>
              <Typography
                variant="h4"
                component="h1"
                sx={{
                  fontFamily: 'var(--font-heading)',
                  fontWeight: 600,
                  color: 'var(--silver)'
                }}
                gutterBottom
              >
                {currentTrack.title}
              </Typography>
              <Typography
                variant="h6"
                sx={{
                  fontFamily: 'var(--font-body)',
                  color: 'var(--silver)',
                  opacity: 0.8
                }}
                gutterBottom
              >
                {currentTrack.artist}
              </Typography>
              <Typography
                variant="body1"
                sx={{
                  fontFamily: 'var(--font-body)',
                  color: 'var(--silver)',
                  opacity: 0.6
                }}
              >
                {currentTrack.album}
              </Typography>
            </Box>

            {/* Audio Visualizer */}
            <Box sx={{ mb: 3, height: 60, position: 'relative' }}>
              <canvas
                ref={visualizerRef}
                width={400}
                height={60}
                style={{
                  width: '100%',
                  height: '100%',
                  borderRadius: '8px',
                  background: 'rgba(255,255,255,0.05)'
                }}
              />
              {!isPlaying && (
                <Box
                  sx={{
                    position: 'absolute',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: 'rgba(0,0,0,0.3)',
                    borderRadius: 2
                  }}
                >
                  <Typography variant="body2" color="text.secondary">
                    🎶 Classic visualizer ready
                  </Typography>
                </Box>
              )}
            </Box>

            {/* Progress Bar */}
            <Box sx={{ mb: 3 }}>
              <Slider
                value={currentTime}
                max={currentTrack.duration}
                onChange={(_, value) => setCurrentTime(value as number)}
                sx={{
                  '& .MuiSlider-track': {
                    background: 'var(--aurora-horizontal)'
                  },
                  '& .MuiSlider-thumb': {
                    background: 'var(--aurora-violet)',
                    '&:hover': {
                      boxShadow: 'var(--glow-medium)'
                    }
                  }
                }}
              />
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1 }}>
                <Typography variant="caption">
                  {formatTime(currentTime)}
                </Typography>
                <Typography variant="caption">
                  {formatTime(currentTrack.duration)}
                </Typography>
              </Box>
            </Box>

            {/* Main Controls */}
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', mb: 2, gap: 1 }}>
              <IconButton sx={{ color: 'white' }}>
                <Shuffle />
              </IconButton>

              <IconButton
                onClick={onPrevious}
                sx={{ color: 'white', fontSize: '2rem' }}
              >
                <SkipPrevious fontSize="large" />
              </IconButton>

              <IconButton
                onClick={onPlayPause}
                sx={{
                  background: 'var(--aurora-gradient)',
                  color: 'white',
                  width: 64,
                  height: 64,
                  mx: 2,
                  '&:hover': {
                    transform: 'scale(1.05)',
                    boxShadow: 'var(--glow-strong)'
                  }
                }}
              >
                {isPlaying ? <Pause fontSize="large" /> : <PlayArrow fontSize="large" />}
              </IconButton>

              <IconButton
                onClick={onNext}
                sx={{ color: 'white', fontSize: '2rem' }}
              >
                <SkipNext fontSize="large" />
              </IconButton>

              <IconButton sx={{ color: 'white' }}>
                <Repeat />
              </IconButton>
            </Box>

            {/* Secondary Controls */}
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              {/* Volume Control */}
              <Box sx={{ display: 'flex', alignItems: 'center', flex: 1, mr: 3 }}>
                <VolumeUp sx={{ mr: 1, color: 'text.secondary' }} />
                <Slider
                  value={volume}
                  onChange={(_, value) => setVolume(value as number)}
                  sx={{
                    maxWidth: 120,
                    '& .MuiSlider-track': {
                      background: 'linear-gradient(90deg, #666, #999)'
                    }
                  }}
                />
              </Box>

              {/* Enhancement Toggle */}
              <FormControlLabel
                control={
                  <Switch
                    checked={isEnhanced}
                    onChange={handleEnhancementToggle}
                    sx={{
                      '& .MuiSwitch-switchBase.Mui-checked': {
                        color: 'var(--aurora-violet)'
                      },
                      '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                        backgroundColor: 'var(--aurora-violet)'
                      }
                    }}
                  />
                }
                label={
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                    <AutoAwesome fontSize="small" />
                    <Typography
                      variant="body2"
                      sx={{
                        fontFamily: 'var(--font-heading)',
                        fontWeight: 600
                      }}
                    >
                      Magic
                    </Typography>
                  </Box>
                }
                labelPlacement="start"
              />

              {/* Love Button */}
              <IconButton
                onClick={() => setIsLoved(!isLoved)}
                sx={{
                  color: isLoved ? '#f44336' : 'text.secondary',
                  '&:hover': {
                    color: '#f44336',
                    transform: 'scale(1.1)'
                  }
                }}
              >
                {isLoved ? <Favorite /> : <FavoriteOutlined />}
              </IconButton>
            </Box>
          </Box>
        </Box>
      </Card>
    </Container>
  );
};

export default MagicalMusicPlayer;