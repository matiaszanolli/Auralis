import React, { useState } from 'react';
import {
  Box,
  Typography,
  Switch,
  FormControlLabel,
  Divider,
  IconButton,
  Tooltip,
  Stack
} from '@mui/material';
import {
  ChevronRight,
  ChevronLeft,
  AutoAwesome,
  Tune
} from '@mui/icons-material';
import GradientButton from './shared/GradientButton';
import GradientSlider from './shared/GradientSlider';
import { gradients, colors } from '../theme/auralisTheme';

interface PresetPaneProps {
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  onPresetChange?: (preset: string) => void;
  onMasteringToggle?: (enabled: boolean) => void;
}

const PresetPane: React.FC<PresetPaneProps> = ({
  collapsed = false,
  onToggleCollapse,
  onPresetChange,
  onMasteringToggle
}) => {
  const [selectedPreset, setSelectedPreset] = useState('adaptive');
  const [masteringEnabled, setMasteringEnabled] = useState(true);
  const [intensity, setIntensity] = useState(50);

  const presets = [
    { value: 'adaptive', label: 'Adaptive', description: 'Intelligent content-aware mastering' },
    { value: 'gentle', label: 'Gentle', description: 'Subtle mastering with minimal processing' },
    { value: 'warm', label: 'Warm', description: 'Adds warmth and smoothness' },
    { value: 'bright', label: 'Bright', description: 'Enhances clarity and presence' },
    { value: 'punchy', label: 'Punchy', description: 'Increases impact and dynamics' }
  ];

  const handlePresetChange = (value: string) => {
    setSelectedPreset(value);
    onPresetChange?.(value);
  };

  const handleMasteringToggle = (enabled: boolean) => {
    setMasteringEnabled(enabled);
    onMasteringToggle?.(enabled);
  };

  if (collapsed) {
    return (
      <Box
        sx={{
          width: 48,
          height: '100%',
          background: 'var(--charcoal)',
          borderLeft: '1px solid rgba(226, 232, 240, 0.1)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          py: 2,
          transition: 'width 0.3s ease'
        }}
      >
        <IconButton onClick={onToggleCollapse} sx={{ color: 'var(--silver)' }}>
          <ChevronLeft />
        </IconButton>
        <Box
          sx={{
            mt: 2,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: 2
          }}
        >
          <Tooltip title="Mastering Presets" placement="left">
            <Tune sx={{ color: 'var(--aurora-violet)' }} />
          </Tooltip>
        </Box>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        width: 280,
        height: '100%',
        background: 'var(--charcoal)',
        borderLeft: '1px solid rgba(226, 232, 240, 0.1)',
        display: 'flex',
        flexDirection: 'column',
        transition: 'width 0.3s ease',
        overflow: 'hidden'
      }}
    >
      {/* Header */}
      <Box
        sx={{
          p: 2,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid rgba(226, 232, 240, 0.1)'
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <AutoAwesome sx={{ color: 'var(--aurora-violet)', fontSize: 20 }} />
          <Typography
            variant="subtitle1"
            sx={{
              fontFamily: 'var(--font-heading)',
              fontWeight: 600,
              color: 'var(--silver)'
            }}
          >
            Mastering
          </Typography>
        </Box>
        <IconButton onClick={onToggleCollapse} size="small" sx={{ color: 'var(--silver)' }}>
          <ChevronRight />
        </IconButton>
      </Box>

      {/* Content */}
      <Box sx={{ flex: 1, p: 3, overflowY: 'auto' }}>
        {/* Master Toggle */}
        <Box
          sx={{
            p: 2,
            mb: 3,
            borderRadius: 'var(--radius-md)',
            background: masteringEnabled
              ? 'rgba(124, 58, 237, 0.1)'
              : 'rgba(226, 232, 240, 0.05)',
            border: `1px solid ${
              masteringEnabled
                ? 'rgba(124, 58, 237, 0.3)'
                : 'rgba(226, 232, 240, 0.1)'
            }`,
            transition: 'all 0.3s ease'
          }}
        >
          <FormControlLabel
            control={
              <Switch
                checked={masteringEnabled}
                onChange={(e) => handleMasteringToggle(e.target.checked)}
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
              <Typography
                variant="body2"
                sx={{
                  fontFamily: 'var(--font-heading)',
                  fontWeight: 600,
                  color: 'var(--silver)'
                }}
              >
                Enable Mastering
              </Typography>
            }
          />
          <Typography
            variant="caption"
            sx={{
              display: 'block',
              mt: 1,
              ml: 5,
              fontFamily: 'var(--font-body)',
              color: 'var(--silver)',
              opacity: 0.7,
              fontSize: 11
            }}
          >
            {masteringEnabled
              ? 'Auralis is enhancing your music'
              : 'Original audio quality'}
          </Typography>
        </Box>

        {/* Preset Selection */}
        <Box sx={{ mb: 3, opacity: masteringEnabled ? 1 : 0.4 }}>
          <Typography
            variant="caption"
            className="gradient-text"
            sx={{
              display: 'block',
              mb: 2,
              fontFamily: 'var(--font-body)',
              fontWeight: 600,
              textTransform: 'uppercase',
              letterSpacing: 1.5,
              fontSize: 12
            }}
          >
            Presets
          </Typography>
          <Stack spacing={1.5}>
            {presets.map((preset) => (
              <GradientButton
                key={preset.value}
                fullWidth
                onClick={() => handlePresetChange(preset.value)}
                disabled={!masteringEnabled}
                sx={{
                  justifyContent: 'flex-start',
                  textAlign: 'left',
                  py: 1.5,
                  px: 2,
                  opacity: selectedPreset === preset.value ? 1 : 0.7,
                  background: selectedPreset === preset.value
                    ? gradients.aurora
                    : colors.background.surface,
                  transform: selectedPreset === preset.value ? 'scale(1.02)' : 'scale(1)',
                  transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                  '&:hover': {
                    opacity: 1,
                    transform: 'scale(1.02)',
                  },
                }}
              >
                <Box>
                  <Typography
                    variant="button"
                    sx={{
                      fontWeight: 600,
                      color: selectedPreset === preset.value ? '#fff' : colors.text.primary
                    }}
                  >
                    {preset.label}
                  </Typography>
                  <Typography
                    variant="caption"
                    display="block"
                    sx={{
                      fontSize: 11,
                      opacity: 0.9,
                      color: selectedPreset === preset.value ? '#fff' : colors.text.secondary
                    }}
                  >
                    {preset.description}
                  </Typography>
                </Box>
              </GradientButton>
            ))}
          </Stack>
        </Box>

        <Divider sx={{ borderColor: 'rgba(226, 232, 240, 0.1)', my: 3 }} />

        {/* Intensity Slider */}
        <Box sx={{ mb: 3, opacity: masteringEnabled ? 1 : 0.4 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
            <Typography
              variant="caption"
              className="gradient-text"
              sx={{
                fontFamily: 'var(--font-body)',
                fontWeight: 600,
                textTransform: 'uppercase',
                letterSpacing: 1.5,
                fontSize: 12
              }}
            >
              Intensity
            </Typography>
            <Typography
              variant="caption"
              sx={{
                fontFamily: 'var(--font-body)',
                color: colors.text.primary,
                fontWeight: 600,
                fontSize: 12,
                background: gradients.aurora,
                backgroundClip: 'text',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent'
              }}
            >
              {intensity}%
            </Typography>
          </Box>
          <GradientSlider
            value={intensity}
            onChange={(_, value) => setIntensity(value as number)}
            disabled={!masteringEnabled}
            min={0}
            max={100}
            gradientbg={gradients.aurora}
            aria-label="Processing Intensity"
          />
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1 }}>
            <Typography
              variant="caption"
              sx={{
                fontFamily: 'var(--font-body)',
                color: colors.text.disabled,
                fontSize: 10
              }}
            >
              Subtle
            </Typography>
            <Typography
              variant="caption"
              sx={{
                fontFamily: 'var(--font-body)',
                color: colors.text.disabled,
                fontSize: 10
              }}
            >
              Strong
            </Typography>
          </Box>
        </Box>

        {/* Preset Info */}
        <Box
          sx={{
            p: 2,
            borderRadius: '8px',
            background: `linear-gradient(135deg, ${colors.background.surface} 0%, ${colors.background.secondary} 100%)`,
            border: `1px solid rgba(102, 126, 234, 0.2)`,
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.1)'
          }}
        >
          <Typography
            variant="caption"
            sx={{
              fontFamily: 'var(--font-body)',
              color: colors.text.secondary,
              fontSize: 11,
              lineHeight: 1.6,
              display: 'block'
            }}
          >
            {selectedPreset === 'adaptive' &&
              'Intelligent, content-aware mastering that analyzes your audio and applies optimal processing. Best for most use cases.'}
            {selectedPreset === 'gentle' &&
              'Subtle enhancement with minimal processing. Preserves the original character while adding professional polish.'}
            {selectedPreset === 'warm' &&
              'Adds warmth and smoothness to the sound. Perfect for vocals, acoustic instruments, and classic genres.'}
            {selectedPreset === 'bright' &&
              'Enhances clarity and presence in the high frequencies. Ideal for modern pop, electronic, and energetic music.'}
            {selectedPreset === 'punchy' &&
              'Increases impact and dynamics for powerful, energetic sound. Great for rock, hip-hop, and EDM.'}
          </Typography>
        </Box>
      </Box>

      {/* Footer Tip */}
      <Box
        sx={{
          p: 2,
          borderTop: '1px solid rgba(226, 232, 240, 0.1)',
          background: 'rgba(6, 182, 212, 0.05)'
        }}
      >
        <Typography
          variant="caption"
          sx={{
            fontFamily: 'var(--font-body)',
            color: 'var(--silver)',
            opacity: 0.6,
            fontSize: 10,
            lineHeight: 1.5,
            display: 'block'
          }}
        >
          💡 Tip: Mastering happens in real-time. Try different presets to find your perfect sound!
        </Typography>
      </Box>
    </Box>
  );
};

export default PresetPane;
