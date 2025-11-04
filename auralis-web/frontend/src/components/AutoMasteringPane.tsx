/**
 * Auto-Mastering Visualizer Pane
 *
 * Displays real-time processing parameters and audio characteristics
 * from the continuous parameter space system. Shows what the auto-mastering
 * engine is doing without requiring preset selection.
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Switch,
  FormControlLabel,
  IconButton,
  Tooltip,
  LinearProgress,
  Chip,
  Stack,
  Paper
} from '@mui/material';
import {
  ChevronRight,
  ChevronLeft,
  AutoAwesome,
  GraphicEq,
  Compress,
  VolumeUp,
  Audiotrack
} from '@mui/icons-material';
import { colors, gradients } from '../theme/auralisTheme';
import { useEnhancement } from '../contexts/EnhancementContext';

interface ProcessingParams {
  // 3D space coordinates (0-1)
  spectral_balance: number;  // 0=dark, 1=bright
  dynamic_range: number;     // 0=compressed, 1=dynamic
  energy_level: number;      // 0=quiet, 1=loud

  // Target parameters
  target_lufs: number;       // Target loudness (dB)
  peak_target_db: number;    // Peak level target (dB)

  // EQ adjustments
  bass_boost: number;        // Bass boost (dB)
  air_boost: number;         // Air/treble boost (dB)

  // Dynamics
  compression_amount: number; // 0-1
  expansion_amount: number;   // 0-1

  // Stereo
  stereo_width: number;      // 0-1
}

interface AutoMasteringPaneProps {
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  onMasteringToggle?: (enabled: boolean) => void;
}

const AutoMasteringPane: React.FC<AutoMasteringPaneProps> = ({
  collapsed = false,
  onToggleCollapse,
  onMasteringToggle
}) => {
  const { settings, setEnabled, isProcessing } = useEnhancement();
  const [params, setParams] = useState<ProcessingParams | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  // Fetch current processing parameters from backend
  useEffect(() => {
    const fetchParams = async () => {
      try {
        setIsAnalyzing(true);
        const response = await fetch('/api/processing/parameters');
        if (response.ok) {
          const data = await response.json();
          setParams(data);
        }
      } catch (err) {
        console.error('Failed to fetch processing parameters:', err);
      } finally {
        setIsAnalyzing(false);
      }
    };

    if (settings.enabled) {
      fetchParams();
      // Poll for updates every 2 seconds when enabled
      const interval = setInterval(fetchParams, 2000);
      return () => clearInterval(interval);
    }
  }, [settings.enabled]);

  const handleMasteringToggle = async (enabled: boolean) => {
    await setEnabled(enabled);
    onMasteringToggle?.(enabled);
  };

  // Helper to format parameter values
  const formatParam = (value: number, decimals: number = 1): string => {
    return value.toFixed(decimals);
  };

  // Helper to get spectral balance label
  const getSpectralLabel = (value: number): string => {
    if (value < 0.3) return 'Dark';
    if (value < 0.7) return 'Balanced';
    return 'Bright';
  };

  // Helper to get dynamic range label
  const getDynamicLabel = (value: number): string => {
    if (value < 0.3) return 'Compressed';
    if (value < 0.7) return 'Moderate';
    return 'Dynamic';
  };

  // Helper to get energy level label
  const getEnergyLabel = (value: number): string => {
    if (value < 0.3) return 'Quiet';
    if (value < 0.7) return 'Moderate';
    return 'Loud';
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
          <Tooltip title="Auto-Mastering" placement="left">
            <AutoAwesome sx={{ color: 'var(--aurora-violet)' }} />
          </Tooltip>
        </Box>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        width: 320,
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
            Auto-Mastering
          </Typography>
        </Box>
        <IconButton onClick={onToggleCollapse} size="small" sx={{ color: 'var(--silver)' }}>
          <ChevronRight />
        </IconButton>
      </Box>

      {/* Content */}
      <Box sx={{ flex: 1, p: 3, overflowY: 'auto' }}>
        {/* Master Toggle */}
        <Paper
          elevation={0}
          sx={{
            p: 2,
            mb: 3,
            borderRadius: 'var(--radius-md)',
            background: settings.enabled
              ? 'rgba(124, 58, 237, 0.1)'
              : 'rgba(226, 232, 240, 0.05)',
            border: `1px solid ${
              settings.enabled
                ? 'rgba(124, 58, 237, 0.3)'
                : 'rgba(226, 232, 240, 0.1)'
            }`,
            transition: 'all 0.3s ease',
            opacity: isProcessing ? 0.7 : 1
          }}
        >
          <FormControlLabel
            control={
              <Switch
                checked={settings.enabled}
                onChange={(e) => handleMasteringToggle(e.target.checked)}
                disabled={isProcessing}
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
                Enable Auto-Mastering
              </Typography>
            }
          />
          <Typography
            variant="caption"
            sx={{
              display: 'block',
              mt: 1,
              ml: 5,
              color: colors.text.secondary,
              fontFamily: 'var(--font-body)'
            }}
          >
            {settings.enabled
              ? 'Analyzing audio and applying intelligent processing'
              : 'Turn on to enhance your music automatically'}
          </Typography>
        </Paper>

        {/* Processing Status */}
        {settings.enabled && (
          <>
            {isAnalyzing && (
              <Box sx={{ mb: 3 }}>
                <Typography variant="caption" sx={{ color: colors.text.secondary, mb: 1, display: 'block' }}>
                  Analyzing audio...
                </Typography>
                <LinearProgress
                  sx={{
                    backgroundColor: 'rgba(226, 232, 240, 0.1)',
                    '& .MuiLinearProgress-bar': {
                      background: gradients.purpleViolet
                    }
                  }}
                />
              </Box>
            )}

            {params && !isAnalyzing && (
              <Stack spacing={3}>
                {/* Audio Characteristics */}
                <Box>
                  <Typography
                    variant="caption"
                    sx={{
                      color: colors.text.secondary,
                      textTransform: 'uppercase',
                      letterSpacing: 1,
                      fontWeight: 600,
                      mb: 1.5,
                      display: 'block'
                    }}
                  >
                    <Audiotrack sx={{ fontSize: 14, mr: 0.5, verticalAlign: 'middle' }} />
                    Audio Characteristics
                  </Typography>

                  <Stack spacing={1.5}>
                    {/* Spectral Balance */}
                    <Box>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                        <Typography variant="body2" sx={{ color: colors.text.primary, fontSize: '0.875rem' }}>
                          Spectral Balance
                        </Typography>
                        <Chip
                          label={getSpectralLabel(params.spectral_balance)}
                          size="small"
                          sx={{
                            height: 20,
                            fontSize: '0.7rem',
                            background: gradients.purpleViolet,
                            color: 'white'
                          }}
                        />
                      </Box>
                      <LinearProgress
                        variant="determinate"
                        value={params.spectral_balance * 100}
                        sx={{
                          height: 6,
                          borderRadius: 1,
                          backgroundColor: 'rgba(226, 232, 240, 0.1)',
                          '& .MuiLinearProgress-bar': {
                            background: gradients.purpleViolet,
                            borderRadius: 1
                          }
                        }}
                      />
                    </Box>

                    {/* Dynamic Range */}
                    <Box>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                        <Typography variant="body2" sx={{ color: colors.text.primary, fontSize: '0.875rem' }}>
                          Dynamic Range
                        </Typography>
                        <Chip
                          label={getDynamicLabel(params.dynamic_range)}
                          size="small"
                          sx={{
                            height: 20,
                            fontSize: '0.7rem',
                            background: gradients.blueViolet,
                            color: 'white'
                          }}
                        />
                      </Box>
                      <LinearProgress
                        variant="determinate"
                        value={params.dynamic_range * 100}
                        sx={{
                          height: 6,
                          borderRadius: 1,
                          backgroundColor: 'rgba(226, 232, 240, 0.1)',
                          '& .MuiLinearProgress-bar': {
                            background: gradients.blueViolet,
                            borderRadius: 1
                          }
                        }}
                      />
                    </Box>

                    {/* Energy Level */}
                    <Box>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 0.5 }}>
                        <Typography variant="body2" sx={{ color: colors.text.primary, fontSize: '0.875rem' }}>
                          Energy Level
                        </Typography>
                        <Chip
                          label={getEnergyLabel(params.energy_level)}
                          size="small"
                          sx={{
                            height: 20,
                            fontSize: '0.7rem',
                            background: gradients.tealBlue,
                            color: 'white'
                          }}
                        />
                      </Box>
                      <LinearProgress
                        variant="determinate"
                        value={params.energy_level * 100}
                        sx={{
                          height: 6,
                          borderRadius: 1,
                          backgroundColor: 'rgba(226, 232, 240, 0.1)',
                          '& .MuiLinearProgress-bar': {
                            background: gradients.tealBlue,
                            borderRadius: 1
                          }
                        }}
                      />
                    </Box>
                  </Stack>
                </Box>

                {/* Processing Parameters */}
                <Box>
                  <Typography
                    variant="caption"
                    sx={{
                      color: colors.text.secondary,
                      textTransform: 'uppercase',
                      letterSpacing: 1,
                      fontWeight: 600,
                      mb: 1.5,
                      display: 'block'
                    }}
                  >
                    <GraphicEq sx={{ fontSize: 14, mr: 0.5, verticalAlign: 'middle' }} />
                    Applied Processing
                  </Typography>

                  <Stack spacing={1.5}>
                    {/* Target Loudness */}
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Typography variant="body2" sx={{ color: colors.text.secondary, fontSize: '0.8125rem' }}>
                        <VolumeUp sx={{ fontSize: 14, mr: 0.5, verticalAlign: 'middle' }} />
                        Target Loudness
                      </Typography>
                      <Typography variant="body2" sx={{ color: colors.text.primary, fontWeight: 600, fontSize: '0.8125rem' }}>
                        {formatParam(params.target_lufs)} LUFS
                      </Typography>
                    </Box>

                    {/* Peak Target */}
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Typography variant="body2" sx={{ color: colors.text.secondary, fontSize: '0.8125rem' }}>
                        Peak Level
                      </Typography>
                      <Typography variant="body2" sx={{ color: colors.text.primary, fontWeight: 600, fontSize: '0.8125rem' }}>
                        {formatParam(params.peak_target_db)} dB
                      </Typography>
                    </Box>

                    {/* Bass Boost */}
                    {Math.abs(params.bass_boost) > 0.1 && (
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2" sx={{ color: colors.text.secondary, fontSize: '0.8125rem' }}>
                          Bass Adjustment
                        </Typography>
                        <Typography
                          variant="body2"
                          sx={{
                            color: params.bass_boost > 0 ? colors.accent.green : colors.accent.orange,
                            fontWeight: 600,
                            fontSize: '0.8125rem'
                          }}
                        >
                          {params.bass_boost > 0 ? '+' : ''}{formatParam(params.bass_boost)} dB
                        </Typography>
                      </Box>
                    )}

                    {/* Air Boost */}
                    {Math.abs(params.air_boost) > 0.1 && (
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2" sx={{ color: colors.text.secondary, fontSize: '0.8125rem' }}>
                          Air Adjustment
                        </Typography>
                        <Typography
                          variant="body2"
                          sx={{
                            color: params.air_boost > 0 ? colors.accent.green : colors.accent.orange,
                            fontWeight: 600,
                            fontSize: '0.8125rem'
                          }}
                        >
                          {params.air_boost > 0 ? '+' : ''}{formatParam(params.air_boost)} dB
                        </Typography>
                      </Box>
                    )}

                    {/* Compression */}
                    {params.compression_amount > 0.05 && (
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2" sx={{ color: colors.text.secondary, fontSize: '0.8125rem' }}>
                          <Compress sx={{ fontSize: 14, mr: 0.5, verticalAlign: 'middle' }} />
                          Compression
                        </Typography>
                        <Typography variant="body2" sx={{ color: colors.text.primary, fontWeight: 600, fontSize: '0.8125rem' }}>
                          {Math.round(params.compression_amount * 100)}%
                        </Typography>
                      </Box>
                    )}

                    {/* Expansion (De-mastering) */}
                    {params.expansion_amount > 0.05 && (
                      <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Typography variant="body2" sx={{ color: colors.text.secondary, fontSize: '0.8125rem' }}>
                          Expansion
                        </Typography>
                        <Typography variant="body2" sx={{ color: colors.accent.blue, fontWeight: 600, fontSize: '0.8125rem' }}>
                          {Math.round(params.expansion_amount * 100)}%
                        </Typography>
                      </Box>
                    )}

                    {/* Stereo Width */}
                    <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Typography variant="body2" sx={{ color: colors.text.secondary, fontSize: '0.8125rem' }}>
                        Stereo Width
                      </Typography>
                      <Typography variant="body2" sx={{ color: colors.text.primary, fontWeight: 600, fontSize: '0.8125rem' }}>
                        {Math.round(params.stereo_width * 100)}%
                      </Typography>
                    </Box>
                  </Stack>
                </Box>

                {/* Info Box */}
                <Paper
                  elevation={0}
                  sx={{
                    p: 2,
                    borderRadius: 'var(--radius-md)',
                    background: 'rgba(67, 97, 238, 0.1)',
                    border: '1px solid rgba(67, 97, 238, 0.3)'
                  }}
                >
                  <Typography
                    variant="caption"
                    sx={{
                      color: colors.text.secondary,
                      fontSize: '0.75rem',
                      lineHeight: 1.6
                    }}
                  >
                    <strong style={{ color: colors.text.primary }}>Auto-Mastering</strong> analyzes your music in real-time
                    and applies intelligent processing tailored to each track's unique characteristics.
                    No presets needed!
                  </Typography>
                </Paper>
              </Stack>
            )}

            {!params && !isAnalyzing && (
              <Paper
                elevation={0}
                sx={{
                  p: 3,
                  borderRadius: 'var(--radius-md)',
                  background: 'rgba(226, 232, 240, 0.05)',
                  border: '1px solid rgba(226, 232, 240, 0.1)',
                  textAlign: 'center'
                }}
              >
                <AutoAwesome sx={{ fontSize: 48, color: 'var(--aurora-violet)', mb: 2, opacity: 0.5 }} />
                <Typography variant="body2" sx={{ color: colors.text.secondary }}>
                  Play a track to see auto-mastering parameters
                </Typography>
              </Paper>
            )}
          </>
        )}

        {!settings.enabled && (
          <Paper
            elevation={0}
            sx={{
              p: 3,
              borderRadius: 'var(--radius-md)',
              background: 'rgba(226, 232, 240, 0.05)',
              border: '1px solid rgba(226, 232, 240, 0.1)',
              textAlign: 'center'
            }}
          >
            <AutoAwesome sx={{ fontSize: 48, color: 'var(--aurora-violet)', mb: 2, opacity: 0.3 }} />
            <Typography variant="body2" sx={{ color: colors.text.secondary, mb: 2 }}>
              Auto-Mastering is currently disabled
            </Typography>
            <Typography variant="caption" sx={{ color: colors.text.disabled, lineHeight: 1.6 }}>
              Enable the toggle above to start enhancing your music with intelligent processing
            </Typography>
          </Paper>
        )}
      </Box>
    </Box>
  );
};

export default AutoMasteringPane;
