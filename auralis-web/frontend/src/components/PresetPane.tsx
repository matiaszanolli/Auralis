import React, { useState } from 'react';
import {
  Box,
  Typography,
  Select,
  MenuItem,
  Switch,
  FormControlLabel,
  Divider,
  IconButton,
  Tooltip,
  Slider
} from '@mui/material';
import {
  ChevronRight,
  ChevronLeft,
  AutoAwesome,
  Tune
} from '@mui/icons-material';

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
  const [selectedPreset, setSelectedPreset] = useState('studio');
  const [masteringEnabled, setMasteringEnabled] = useState(true);
  const [intensity, setIntensity] = useState(50);

  const presets = [
    { value: 'studio', label: 'Studio', description: 'Balanced, professional sound' },
    { value: 'vinyl', label: 'Vinyl', description: 'Warm, analog character' },
    { value: 'live', label: 'Live', description: 'Dynamic, energetic presence' },
    { value: 'custom', label: 'Custom', description: 'Your personalized settings' }
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
            sx={{
              display: 'block',
              mb: 1.5,
              fontFamily: 'var(--font-body)',
              color: 'var(--silver)',
              opacity: 0.7,
              textTransform: 'uppercase',
              letterSpacing: 1,
              fontSize: 11
            }}
          >
            Preset
          </Typography>
          <Select
            fullWidth
            value={selectedPreset}
            onChange={(e) => handlePresetChange(e.target.value)}
            disabled={!masteringEnabled}
            sx={{
              fontFamily: 'var(--font-body)',
              color: 'var(--silver)',
              borderRadius: 'var(--radius-md)',
              '& .MuiOutlinedInput-notchedOutline': {
                borderColor: 'rgba(226, 232, 240, 0.2)'
              },
              '&:hover .MuiOutlinedInput-notchedOutline': {
                borderColor: 'rgba(226, 232, 240, 0.3)'
              },
              '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
                borderColor: 'var(--aurora-violet)',
                borderWidth: 1
              },
              '& .MuiSelect-icon': {
                color: 'var(--silver)'
              }
            }}
          >
            {presets.map((preset) => (
              <MenuItem key={preset.value} value={preset.value}>
                <Box>
                  <Typography
                    variant="body2"
                    sx={{
                      fontFamily: 'var(--font-body)',
                      fontWeight: 500
                    }}
                  >
                    {preset.label}
                  </Typography>
                  <Typography
                    variant="caption"
                    sx={{
                      fontFamily: 'var(--font-body)',
                      opacity: 0.7,
                      fontSize: 11
                    }}
                  >
                    {preset.description}
                  </Typography>
                </Box>
              </MenuItem>
            ))}
          </Select>
        </Box>

        <Divider sx={{ borderColor: 'rgba(226, 232, 240, 0.1)', my: 3 }} />

        {/* Intensity Slider */}
        <Box sx={{ mb: 3, opacity: masteringEnabled ? 1 : 0.4 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1.5 }}>
            <Typography
              variant="caption"
              sx={{
                fontFamily: 'var(--font-body)',
                color: 'var(--silver)',
                opacity: 0.7,
                textTransform: 'uppercase',
                letterSpacing: 1,
                fontSize: 11
              }}
            >
              Intensity
            </Typography>
            <Typography
              variant="caption"
              sx={{
                fontFamily: 'var(--font-body)',
                color: 'var(--aurora-violet)',
                fontWeight: 600,
                fontSize: 11
              }}
            >
              {intensity}%
            </Typography>
          </Box>
          <Slider
            value={intensity}
            onChange={(_, value) => setIntensity(value as number)}
            disabled={!masteringEnabled}
            sx={{
              '& .MuiSlider-track': {
                background: 'var(--aurora-horizontal)',
                border: 'none'
              },
              '& .MuiSlider-rail': {
                background: 'rgba(226, 232, 240, 0.2)'
              },
              '& .MuiSlider-thumb': {
                background: 'var(--aurora-violet)',
                '&:hover': {
                  boxShadow: 'var(--glow-medium)'
                }
              }
            }}
          />
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 0.5 }}>
            <Typography
              variant="caption"
              sx={{
                fontFamily: 'var(--font-body)',
                color: 'var(--silver)',
                opacity: 0.5,
                fontSize: 10
              }}
            >
              Subtle
            </Typography>
            <Typography
              variant="caption"
              sx={{
                fontFamily: 'var(--font-body)',
                color: 'var(--silver)',
                opacity: 0.5,
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
            borderRadius: 'var(--radius-md)',
            background: 'rgba(226, 232, 240, 0.05)',
            border: '1px solid rgba(226, 232, 240, 0.1)'
          }}
        >
          <Typography
            variant="caption"
            sx={{
              fontFamily: 'var(--font-body)',
              color: 'var(--silver)',
              opacity: 0.7,
              fontSize: 11,
              lineHeight: 1.6
            }}
          >
            {selectedPreset === 'studio' &&
              'Balanced frequency response with transparent dynamics processing. Perfect for most music.'}
            {selectedPreset === 'vinyl' &&
              'Adds warmth and analog character with gentle saturation. Great for classic rock and soul.'}
            {selectedPreset === 'live' &&
              'Preserves dynamics with enhanced presence and energy. Ideal for live recordings and energetic genres.'}
            {selectedPreset === 'custom' &&
              'Your personalized mastering settings. Adjust parameters to match your taste.'}
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
