import React, { useState, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Slider,
  Switch,
  FormControlLabel,
  Grid,
  Chip,
  Button,
  ButtonGroup,
  Divider,
  Tooltip,
  Alert
} from '@mui/material';
import {
  Equalizer,
  Tune,
  VolumeUp,
  RestartAlt,
  Save,
  Layers,
  GraphicEq,
  TrendingUp
} from '@mui/icons-material';

interface ProcessingSettings {
  // EQ Settings
  eq: {
    enabled: boolean;
    low: number;      // 60Hz
    lowMid: number;   // 250Hz
    mid: number;      // 1kHz
    highMid: number;  // 4kHz
    high: number;     // 16kHz
  };

  // Dynamics Settings
  dynamics: {
    enabled: boolean;
    compressor: {
      threshold: number;
      ratio: number;
      attack: number;
      release: number;
    };
    limiter: {
      enabled: boolean;
      threshold: number;
      lookahead: number;
    };
  };

  // Level Matching
  levelMatching: {
    enabled: boolean;
    targetLufs: number;
    maxGain: number;
  };
}

interface AudioProcessingControlsProps {
  websocket: WebSocket | null;
  onSettingsChange?: (settings: ProcessingSettings) => void;
}

const AudioProcessingControls: React.FC<AudioProcessingControlsProps> = ({
  websocket,
  onSettingsChange
}) => {
  const [settings, setSettings] = useState<ProcessingSettings>({
    eq: {
      enabled: true,
      low: 0,
      lowMid: 0,
      mid: 0,
      highMid: 0,
      high: 0
    },
    dynamics: {
      enabled: true,
      compressor: {
        threshold: -18,
        ratio: 4,
        attack: 3,
        release: 100
      },
      limiter: {
        enabled: true,
        threshold: -0.3,
        lookahead: 5
      }
    },
    levelMatching: {
      enabled: true,
      targetLufs: -16,
      maxGain: 12
    }
  });

  const [activePreset, setActivePreset] = useState<string>('custom');
  const [isProcessing, setIsProcessing] = useState(false);

  // Predefined presets
  const presets = {
    gentle: {
      name: '🌸 Gentle Enhancement',
      eq: { enabled: true, low: 1, lowMid: 0.5, mid: 0, highMid: 1, high: 2 },
      dynamics: {
        enabled: true,
        compressor: { threshold: -24, ratio: 2, attack: 10, release: 200 },
        limiter: { enabled: true, threshold: -1, lookahead: 10 }
      }
    },
    warm: {
      name: '🔥 Warm & Rich',
      eq: { enabled: true, low: 2, lowMid: 1, mid: -0.5, highMid: 0, high: 1 },
      dynamics: {
        enabled: true,
        compressor: { threshold: -20, ratio: 3, attack: 5, release: 150 },
        limiter: { enabled: true, threshold: -0.5, lookahead: 8 }
      }
    },
    bright: {
      name: '✨ Bright & Crisp',
      eq: { enabled: true, low: -1, lowMid: 0, mid: 1, highMid: 2, high: 3 },
      dynamics: {
        enabled: true,
        compressor: { threshold: -16, ratio: 4, attack: 1, release: 50 },
        limiter: { enabled: true, threshold: -0.1, lookahead: 3 }
      }
    },
    punchy: {
      name: '💥 Punchy & Dynamic',
      eq: { enabled: true, low: 3, lowMid: 1, mid: 0, highMid: 1, high: 2 },
      dynamics: {
        enabled: true,
        compressor: { threshold: -12, ratio: 6, attack: 0.5, release: 30 },
        limiter: { enabled: true, threshold: 0, lookahead: 2 }
      }
    }
  };

  // API call helper
  const apiCall = useCallback(async (endpoint: string, data: any) => {
    try {
      const response = await fetch(`/api${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });

      if (!response.ok) {
        throw new Error(`API call failed: ${response.statusText}`);
      }

      return await response.json();
    } catch (err) {
      console.error('API Error:', err);
      throw err;
    }
  }, []);

  // Update settings and notify parent
  const updateSettings = useCallback((newSettings: ProcessingSettings) => {
    setSettings(newSettings);
    onSettingsChange?.(newSettings);

    // Send to backend via WebSocket or API
    if (websocket && websocket.readyState === WebSocket.OPEN) {
      websocket.send(JSON.stringify({
        type: 'processing_settings_update',
        data: newSettings
      }));
    }
  }, [websocket, onSettingsChange]);

  // Apply preset
  const applyPreset = (presetKey: string) => {
    if (presetKey === 'custom') return;

    const preset = presets[presetKey as keyof typeof presets];
    if (!preset) return;

    const newSettings = {
      ...settings,
      eq: { ...settings.eq, ...preset.eq },
      dynamics: { ...settings.dynamics, ...preset.dynamics }
    };

    updateSettings(newSettings);
    setActivePreset(presetKey);
  };

  // Reset to defaults
  const resetSettings = () => {
    const defaultSettings: ProcessingSettings = {
      eq: { enabled: true, low: 0, lowMid: 0, mid: 0, highMid: 0, high: 0 },
      dynamics: {
        enabled: true,
        compressor: { threshold: -18, ratio: 4, attack: 3, release: 100 },
        limiter: { enabled: true, threshold: -0.3, lookahead: 5 }
      },
      levelMatching: { enabled: true, targetLufs: -16, maxGain: 12 }
    };

    updateSettings(defaultSettings);
    setActivePreset('custom');
  };

  // Handle EQ changes
  const handleEqChange = (band: string, value: number) => {
    const newSettings = {
      ...settings,
      eq: { ...settings.eq, [band]: value }
    };
    updateSettings(newSettings);
    setActivePreset('custom');
  };

  // Handle dynamics changes
  const handleDynamicsChange = (section: string, param: string, value: number | boolean) => {
    const newSettings = {
      ...settings,
      dynamics: {
        ...settings.dynamics,
        [section]: { ...settings.dynamics[section as keyof typeof settings.dynamics], [param]: value }
      }
    };
    updateSettings(newSettings);
    setActivePreset('custom');
  };

  return (
    <Card
      elevation={3}
      sx={{
        background: 'linear-gradient(135deg, #2d1b69 0%, #11998e 100%)',
        color: 'white',
        borderRadius: 3
      }}
    >
      <CardContent>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
          <Typography variant="h6" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Tune /> Audio Processing Controls
          </Typography>

          <Box display="flex" gap={1}>
            <Tooltip title="Reset to defaults">
              <Button
                variant="outlined"
                size="small"
                onClick={resetSettings}
                sx={{ color: 'white', borderColor: 'rgba(255,255,255,0.5)' }}
              >
                <RestartAlt />
              </Button>
            </Tooltip>
            <Tooltip title="Save current settings">
              <Button
                variant="outlined"
                size="small"
                sx={{ color: 'white', borderColor: 'rgba(255,255,255,0.5)' }}
              >
                <Save />
              </Button>
            </Tooltip>
          </Box>
        </Box>

        {/* Presets */}
        <Box mb={3}>
          <Typography variant="subtitle2" gutterBottom>
            🎨 Enhancement Presets
          </Typography>
          <Box display="flex" gap={1} flexWrap="wrap">
            {Object.entries(presets).map(([key, preset]) => (
              <Chip
                key={key}
                label={preset.name}
                onClick={() => applyPreset(key)}
                variant={activePreset === key ? 'filled' : 'outlined'}
                sx={{
                  color: 'white',
                  borderColor: 'rgba(255,255,255,0.5)',
                  backgroundColor: activePreset === key ? 'rgba(255,255,255,0.2)' : 'transparent',
                  '&:hover': {
                    backgroundColor: 'rgba(255,255,255,0.1)'
                  }
                }}
              />
            ))}
          </Box>
        </Box>

        <Grid container spacing={3}>
          {/* EQ Section */}
          <Grid item xs={12} md={6}>
            <Box
              sx={{
                p: 2,
                border: '1px solid rgba(255,255,255,0.2)',
                borderRadius: 2,
                background: 'rgba(255,255,255,0.05)'
              }}
            >
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                <Typography variant="subtitle1" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Equalizer /> 5-Band EQ
                </Typography>
                <FormControlLabel
                  control={
                    <Switch
                      checked={settings.eq.enabled}
                      onChange={(e) => handleEqChange('enabled', e.target.checked)}
                      sx={{
                        '& .MuiSwitch-switchBase.Mui-checked': { color: 'white' },
                        '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                          backgroundColor: 'rgba(255,255,255,0.5)'
                        }
                      }}
                    />
                  }
                  label=""
                  sx={{ m: 0 }}
                />
              </Box>

              {settings.eq.enabled && (
                <Grid container spacing={2}>
                  {[
                    { key: 'low', label: '60Hz', value: settings.eq.low },
                    { key: 'lowMid', label: '250Hz', value: settings.eq.lowMid },
                    { key: 'mid', label: '1kHz', value: settings.eq.mid },
                    { key: 'highMid', label: '4kHz', value: settings.eq.highMid },
                    { key: 'high', label: '16kHz', value: settings.eq.high }
                  ].map(({ key, label, value }) => (
                    <Grid item xs={12} key={key}>
                      <Typography variant="caption" gutterBottom>
                        {label}: {value > 0 ? '+' : ''}{value.toFixed(1)}dB
                      </Typography>
                      <Slider
                        value={value}
                        onChange={(_, newValue) => handleEqChange(key, newValue as number)}
                        min={-12}
                        max={12}
                        step={0.1}
                        sx={{
                          color: 'rgba(255,255,255,0.8)',
                          '& .MuiSlider-thumb': { backgroundColor: 'white' }
                        }}
                      />
                    </Grid>
                  ))}
                </Grid>
              )}
            </Box>
          </Grid>

          {/* Dynamics Section */}
          <Grid item xs={12} md={6}>
            <Box
              sx={{
                p: 2,
                border: '1px solid rgba(255,255,255,0.2)',
                borderRadius: 2,
                background: 'rgba(255,255,255,0.05)'
              }}
            >
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                <Typography variant="subtitle1" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <TrendingUp /> Dynamics
                </Typography>
                <FormControlLabel
                  control={
                    <Switch
                      checked={settings.dynamics.enabled}
                      onChange={(e) => handleDynamicsChange('enabled', '', e.target.checked)}
                      sx={{
                        '& .MuiSwitch-switchBase.Mui-checked': { color: 'white' },
                        '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                          backgroundColor: 'rgba(255,255,255,0.5)'
                        }
                      }}
                    />
                  }
                  label=""
                  sx={{ m: 0 }}
                />
              </Box>

              {settings.dynamics.enabled && (
                <Box>
                  {/* Compressor */}
                  <Typography variant="caption" gutterBottom>
                    Compressor
                  </Typography>
                  <Grid container spacing={1} mb={2}>
                    <Grid item xs={6}>
                      <Typography variant="caption">
                        Threshold: {settings.dynamics.compressor.threshold}dB
                      </Typography>
                      <Slider
                        value={settings.dynamics.compressor.threshold}
                        onChange={(_, value) => handleDynamicsChange('compressor', 'threshold', value as number)}
                        min={-60}
                        max={0}
                        sx={{
                          color: 'rgba(255,255,255,0.8)',
                          '& .MuiSlider-thumb': { backgroundColor: 'white' }
                        }}
                      />
                    </Grid>
                    <Grid item xs={6}>
                      <Typography variant="caption">
                        Ratio: {settings.dynamics.compressor.ratio}:1
                      </Typography>
                      <Slider
                        value={settings.dynamics.compressor.ratio}
                        onChange={(_, value) => handleDynamicsChange('compressor', 'ratio', value as number)}
                        min={1}
                        max={20}
                        sx={{
                          color: 'rgba(255,255,255,0.8)',
                          '& .MuiSlider-thumb': { backgroundColor: 'white' }
                        }}
                      />
                    </Grid>
                  </Grid>

                  <Divider sx={{ my: 2, borderColor: 'rgba(255,255,255,0.2)' }} />

                  {/* Limiter */}
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
                    <Typography variant="caption">
                      Limiter
                    </Typography>
                    <Switch
                      checked={settings.dynamics.limiter.enabled}
                      onChange={(e) => handleDynamicsChange('limiter', 'enabled', e.target.checked)}
                      size="small"
                      sx={{
                        '& .MuiSwitch-switchBase.Mui-checked': { color: 'white' },
                        '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                          backgroundColor: 'rgba(255,255,255,0.5)'
                        }
                      }}
                    />
                  </Box>
                  {settings.dynamics.limiter.enabled && (
                    <Box>
                      <Typography variant="caption">
                        Threshold: {settings.dynamics.limiter.threshold}dB
                      </Typography>
                      <Slider
                        value={settings.dynamics.limiter.threshold}
                        onChange={(_, value) => handleDynamicsChange('limiter', 'threshold', value as number)}
                        min={-3}
                        max={0}
                        step={0.1}
                        sx={{
                          color: 'rgba(255,255,255,0.8)',
                          '& .MuiSlider-thumb': { backgroundColor: 'white' }
                        }}
                      />
                    </Box>
                  )}
                </Box>
              )}
            </Box>
          </Grid>

          {/* Level Matching Section */}
          <Grid item xs={12}>
            <Box
              sx={{
                p: 2,
                border: '1px solid rgba(255,255,255,0.2)',
                borderRadius: 2,
                background: 'rgba(255,255,255,0.05)'
              }}
            >
              <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                <Typography variant="subtitle1" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <VolumeUp /> Level Matching
                </Typography>
                <FormControlLabel
                  control={
                    <Switch
                      checked={settings.levelMatching.enabled}
                      onChange={(e) => updateSettings({
                        ...settings,
                        levelMatching: { ...settings.levelMatching, enabled: e.target.checked }
                      })}
                      sx={{
                        '& .MuiSwitch-switchBase.Mui-checked': { color: 'white' },
                        '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                          backgroundColor: 'rgba(255,255,255,0.5)'
                        }
                      }}
                    />
                  }
                  label=""
                  sx={{ m: 0 }}
                />
              </Box>

              {settings.levelMatching.enabled && (
                <Grid container spacing={2}>
                  <Grid item xs={6}>
                    <Typography variant="caption">
                      Target LUFS: {settings.levelMatching.targetLufs}
                    </Typography>
                    <Slider
                      value={settings.levelMatching.targetLufs}
                      onChange={(_, value) => updateSettings({
                        ...settings,
                        levelMatching: { ...settings.levelMatching, targetLufs: value as number }
                      })}
                      min={-30}
                      max={-6}
                      sx={{
                        color: 'rgba(255,255,255,0.8)',
                        '& .MuiSlider-thumb': { backgroundColor: 'white' }
                      }}
                    />
                  </Grid>
                  <Grid item xs={6}>
                    <Typography variant="caption">
                      Max Gain: {settings.levelMatching.maxGain}dB
                    </Typography>
                    <Slider
                      value={settings.levelMatching.maxGain}
                      onChange={(_, value) => updateSettings({
                        ...settings,
                        levelMatching: { ...settings.levelMatching, maxGain: value as number }
                      })}
                      min={0}
                      max={24}
                      sx={{
                        color: 'rgba(255,255,255,0.8)',
                        '& .MuiSlider-thumb': { backgroundColor: 'white' }
                      }}
                    />
                  </Grid>
                </Grid>
              )}
            </Box>
          </Grid>
        </Grid>

        {/* Status */}
        <Box mt={3}>
          <Alert
            severity="info"
            sx={{
              backgroundColor: 'rgba(25, 118, 210, 0.1)',
              color: 'white',
              '& .MuiAlert-icon': { color: 'white' }
            }}
          >
            {activePreset !== 'custom'
              ? `Using "${presets[activePreset as keyof typeof presets]?.name}" preset`
              : 'Custom settings • Real-time processing active'
            }
          </Alert>
        </Box>
      </CardContent>
    </Card>
  );
};

export default AudioProcessingControls;