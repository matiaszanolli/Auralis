import React from 'react';
import {
  Box,
  Typography,
  Paper,
  Stack,
  Chip,
  LinearProgress,
  Tooltip
} from '@mui/material';
import {
  Equalizer,
  CompressRounded,
  VolumeUp,
  SurroundSound
} from '@mui/icons-material';
import { gradients, colors } from '../theme/auralisTheme';

interface ProcessingParams {
  spectral_balance: number;  // 0-1 (dark to bright)
  dynamic_range: number;     // 0-1 (compressed to dynamic)
  energy_level: number;      // 0-1 (quiet to loud)
  target_lufs: number;       // Target loudness
  bass_boost: number;        // EQ bass boost in dB
  air_boost: number;         // EQ air boost in dB
  compression_amount: number; // 0-1
  stereo_width: number;      // 0-1
}

interface AutoMasteringVisualizerProps {
  params?: ProcessingParams | null;
  isProcessing?: boolean;
}

const AutoMasteringVisualizer: React.FC<AutoMasteringVisualizerProps> = ({
  params,
  isProcessing = false
}) => {
  // Show placeholder when no parameters
  if (!params) {
    return (
      <Paper
        elevation={0}
        sx={{
          p: 3,
          background: 'var(--charcoal)',
          border: '1px solid rgba(226, 232, 240, 0.1)',
          borderRadius: 2
        }}
      >
        <Stack spacing={2} alignItems="center">
          <Equalizer sx={{ fontSize: 48, color: 'var(--aurora-violet)', opacity: 0.5 }} />
          <Typography variant="body2" color="var(--silver)" textAlign="center">
            Play a track to see automatic mastering analysis
          </Typography>
        </Stack>
      </Paper>
    );
  }

  const getSpectrumLabel = (value: number) => {
    if (value < 0.3) return 'Dark';
    if (value < 0.7) return 'Balanced';
    return 'Bright';
  };

  const getDynamicsLabel = (value: number) => {
    if (value < 0.3) return 'Compressed';
    if (value < 0.7) return 'Moderate';
    return 'Dynamic';
  };

  const getEnergyLabel = (value: number) => {
    if (value < 0.3) return 'Quiet';
    if (value < 0.7) return 'Moderate';
    return 'Loud';
  };

  return (
    <Paper
      elevation={0}
      sx={{
        p: 3,
        background: 'var(--charcoal)',
        border: '1px solid rgba(226, 232, 240, 0.1)',
        borderRadius: 2
      }}
    >
      <Stack spacing={3}>
        {/* Header */}
        <Box>
          <Typography variant="h6" fontWeight={600} color="var(--white)" mb={0.5}>
            Auto-Mastering Analysis
          </Typography>
          <Typography variant="caption" color="var(--silver)">
            Intelligent processing based on audio fingerprint
          </Typography>
        </Box>

        {isProcessing && <LinearProgress sx={{ borderRadius: 1 }} />}

        {/* Audio Characteristics */}
        <Box>
          <Typography variant="subtitle2" color="var(--white)" mb={1.5} fontWeight={600}>
            Audio Characteristics
          </Typography>
          <Stack spacing={1.5}>
            {/* Spectral Balance */}
            <Box>
              <Stack direction="row" justifyContent="space-between" alignItems="center" mb={0.5}>
                <Typography variant="caption" color="var(--silver)">
                  Spectral Balance
                </Typography>
                <Chip
                  label={getSpectrumLabel(params.spectral_balance)}
                  size="small"
                  sx={{
                    height: 20,
                    fontSize: '0.7rem',
                    background: gradients.aurora,
                    color: 'white'
                  }}
                />
              </Stack>
              <LinearProgress
                variant="determinate"
                value={params.spectral_balance * 100}
                sx={{
                  height: 6,
                  borderRadius: 3,
                  backgroundColor: 'rgba(226, 232, 240, 0.1)',
                  '& .MuiLinearProgress-bar': {
                    background: gradients.aurora,
                    borderRadius: 3
                  }
                }}
              />
            </Box>

            {/* Dynamic Range */}
            <Box>
              <Stack direction="row" justifyContent="space-between" alignItems="center" mb={0.5}>
                <Typography variant="caption" color="var(--silver)">
                  Dynamic Range
                </Typography>
                <Chip
                  label={getDynamicsLabel(params.dynamic_range)}
                  size="small"
                  sx={{
                    height: 20,
                    fontSize: '0.7rem',
                    background: gradients.aurora,
                    color: 'white'
                  }}
                />
              </Stack>
              <LinearProgress
                variant="determinate"
                value={params.dynamic_range * 100}
                sx={{
                  height: 6,
                  borderRadius: 3,
                  backgroundColor: 'rgba(226, 232, 240, 0.1)',
                  '& .MuiLinearProgress-bar': {
                    background: gradients.aurora,
                    borderRadius: 3
                  }
                }}
              />
            </Box>

            {/* Energy Level */}
            <Box>
              <Stack direction="row" justifyContent="space-between" alignItems="center" mb={0.5}>
                <Typography variant="caption" color="var(--silver)">
                  Energy Level
                </Typography>
                <Chip
                  label={getEnergyLabel(params.energy_level)}
                  size="small"
                  sx={{
                    height: 20,
                    fontSize: '0.7rem',
                    background: gradients.aurora,
                    color: 'white'
                  }}
                />
              </Stack>
              <LinearProgress
                variant="determinate"
                value={params.energy_level * 100}
                sx={{
                  height: 6,
                  borderRadius: 3,
                  backgroundColor: 'rgba(226, 232, 240, 0.1)',
                  '& .MuiLinearProgress-bar': {
                    background: gradients.aurora,
                    borderRadius: 3
                  }
                }}
              />
            </Box>
          </Stack>
        </Box>

        {/* Applied Processing */}
        <Box>
          <Typography variant="subtitle2" color="var(--white)" mb={1.5} fontWeight={600}>
            Applied Processing
          </Typography>
          <Stack spacing={1}>
            {/* Target Loudness */}
            <Tooltip title="Target loudness (LUFS)" placement="left">
              <Stack direction="row" justifyContent="space-between" alignItems="center">
                <Stack direction="row" spacing={1} alignItems="center">
                  <VolumeUp sx={{ fontSize: 16, color: 'var(--aurora-violet)' }} />
                  <Typography variant="caption" color="var(--silver)">
                    Target Loudness
                  </Typography>
                </Stack>
                <Typography variant="caption" fontWeight={600} color="var(--white)">
                  {params.target_lufs.toFixed(1)} LUFS
                </Typography>
              </Stack>
            </Tooltip>

            {/* EQ Adjustments */}
            {(params.bass_boost > 0.1 || params.air_boost > 0.1) && (
              <>
                {params.bass_boost > 0.1 && (
                  <Tooltip title="Bass frequency boost" placement="left">
                    <Stack direction="row" justifyContent="space-between" alignItems="center">
                      <Stack direction="row" spacing={1} alignItems="center">
                        <Equalizer sx={{ fontSize: 16, color: 'var(--aurora-blue)' }} />
                        <Typography variant="caption" color="var(--silver)">
                          Bass Boost
                        </Typography>
                      </Stack>
                      <Typography variant="caption" fontWeight={600} color="var(--white)">
                        +{params.bass_boost.toFixed(1)} dB
                      </Typography>
                    </Stack>
                  </Tooltip>
                )}
                {params.air_boost > 0.1 && (
                  <Tooltip title="High frequency boost" placement="left">
                    <Stack direction="row" justifyContent="space-between" alignItems="center">
                      <Stack direction="row" spacing={1} alignItems="center">
                        <Equalizer sx={{ fontSize: 16, color: 'var(--aurora-pink)' }} />
                        <Typography variant="caption" color="var(--silver)">
                          Air Boost
                        </Typography>
                      </Stack>
                      <Typography variant="caption" fontWeight={600} color="var(--white)">
                        +{params.air_boost.toFixed(1)} dB
                      </Typography>
                    </Stack>
                  </Tooltip>
                )}
              </>
            )}

            {/* Compression */}
            {params.compression_amount > 0.1 && (
              <Tooltip title="Dynamic range compression" placement="left">
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                  <Stack direction="row" spacing={1} alignItems="center">
                    <CompressRounded sx={{ fontSize: 16, color: 'var(--aurora-violet)' }} />
                    <Typography variant="caption" color="var(--silver)">
                      Compression
                    </Typography>
                  </Stack>
                  <Typography variant="caption" fontWeight={600} color="var(--white)">
                    {(params.compression_amount * 100).toFixed(0)}%
                  </Typography>
                </Stack>
              </Tooltip>
            )}

            {/* Stereo Width */}
            {params.stereo_width > 0.1 && (
              <Tooltip title="Stereo width enhancement" placement="left">
                <Stack direction="row" justifyContent="space-between" alignItems="center">
                  <Stack direction="row" spacing={1} alignItems="center">
                    <SurroundSound sx={{ fontSize: 16, color: 'var(--aurora-blue)' }} />
                    <Typography variant="caption" color="var(--silver)">
                      Stereo Width
                    </Typography>
                  </Stack>
                  <Typography variant="caption" fontWeight={600} color="var(--white)">
                    {(params.stereo_width * 100).toFixed(0)}%
                  </Typography>
                </Stack>
              </Tooltip>
            )}
          </Stack>
        </Box>

        {/* Info Footer */}
        <Box
          sx={{
            p: 1.5,
            background: 'rgba(102, 126, 234, 0.1)',
            borderRadius: 1,
            border: '1px solid rgba(102, 126, 234, 0.2)'
          }}
        >
          <Typography variant="caption" color="var(--silver)" fontSize="0.7rem">
            Parameters automatically generated from audio fingerprint. No preset hunting required!
          </Typography>
        </Box>
      </Stack>
    </Paper>
  );
};

export default AutoMasteringVisualizer;
