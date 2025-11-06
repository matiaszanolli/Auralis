import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Grid,
  Paper,
  Typography,
  Tabs,
  Tab,
  Card,
  CardContent,
  IconButton,
  Collapse,
  FormControlLabel,
  Switch,
  Slider,
  Chip
} from '@mui/material';
import {
  ExpandMore,
  ExpandLess,
  Settings,
  Fullscreen,
  Analytics,
  Equalizer,
  Waves,
  Timeline,
  TrendingUp
} from '@mui/icons-material';

import AnalysisWaveformDisplay from './AnalysisWaveformDisplay';
import MeterBridge from './MeterBridge';
import CorrelationDisplay from './CorrelationDisplay';
import ProcessingActivityView from './ProcessingActivityView';
import RealtimeAudioVisualizer from './RealtimeAudioVisualizer';
import { useVisualizationOptimization } from '../hooks/useVisualizationOptimization';

interface AnalysisData {
  // Waveform data
  waveform?: {
    peaks: number[];
    rms: number[];
    sampleRate: number;
    duration: number;
    channels: number;
  };

  // Meter data
  meters?: {
    peakLevelL: number;
    peakLevelR: number;
    rmsLevelL: number;
    rmsLevelR: number;
    momentaryLUFS: number;
    shortTermLUFS: number;
    integratedLUFS: number;
    loudnessRange: number;
    truePeakL: number;
    truePeakR: number;
    correlation: number;
    dynamicRange: number;
    crestFactor: number;
  };

  // Correlation data
  correlation?: {
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
    phaseHistory: number[];
  };

  // Spectrum data
  spectrum?: {
    frequencies: number[];
    magnitudes: number[];
    binSize: number;
  };

  // Quality metrics
  quality?: {
    overallScore: number;
    frequencyScore: number;
    dynamicScore: number;
    stereoScore: number;
    distortionScore: number;
    loudnessScore: number;
    category: string;
    issues: string[];
  };
}

interface DashboardSettings {
  layout: 'grid' | 'tabs' | 'compact';
  showWaveform: boolean;
  showMeters: boolean;
  showCorrelation: boolean;
  showSpectrum: boolean;
  showProcessing: boolean;
  autoUpdate: boolean;
  updateRate: number;
  performanceMode: 'high' | 'balanced' | 'low';
}

interface AnalysisDashboardProps {
  analysisData?: AnalysisData;
  isRealTime?: boolean;
  onSettingsChange?: (settings: DashboardSettings) => void;
  className?: string;
}

const defaultSettings: DashboardSettings = {
  layout: 'grid',
  showWaveform: true,
  showMeters: true,
  showCorrelation: true,
  showSpectrum: true,
  showProcessing: false,
  autoUpdate: true,
  updateRate: 30,
  performanceMode: 'balanced'
};

const performanceConfigs = {
  high: { targetFPS: 60, maxDataPoints: 2048, adaptiveQuality: false },
  balanced: { targetFPS: 30, maxDataPoints: 1024, adaptiveQuality: true },
  low: { targetFPS: 15, maxDataPoints: 512, adaptiveQuality: true }
};

export const AnalysisDashboard: React.FC<AnalysisDashboardProps> = ({
  analysisData,
  isRealTime = false,
  onSettingsChange,
  className
}) => {
  const [settings, setSettings] = useState<DashboardSettings>(defaultSettings);
  const [activeTab, setActiveTab] = useState(0);
  const [expandedPanels, setExpandedPanels] = useState<Set<string>>(
    new Set(['waveform', 'meters', 'correlation'])
  );
  const [showSettings, setShowSettings] = useState(false);

  // Performance optimization
  const optimization = useVisualizationOptimization({
    ...performanceConfigs[settings.performanceMode],
    enableMonitoring: true,
    onStatsUpdate: (stats) => {
      // Could emit performance stats to parent component
      console.debug('Performance stats:', stats);
    }
  });

  // Auto-update effect
  useEffect(() => {
    if (!settings.autoUpdate || !isRealTime) return;

    const interval = setInterval(() => {
      // Trigger re-render of visualizations
      // In real implementation, this would fetch new data
    }, 1000 / settings.updateRate);

    return () => clearInterval(interval);
  }, [settings.autoUpdate, settings.updateRate, isRealTime]);

  const handleSettingsChange = (newSettings: Partial<DashboardSettings>) => {
    const updatedSettings = { ...settings, ...newSettings };
    setSettings(updatedSettings);
    onSettingsChange?.(updatedSettings);

    // Update performance config
    if (newSettings.performanceMode) {
      optimization.updateConfig(performanceConfigs[newSettings.performanceMode]);
    }
  };

  const togglePanel = (panelId: string) => {
    setExpandedPanels(prev => {
      const newSet = new Set(prev);
      if (newSet.has(panelId)) {
        newSet.delete(panelId);
      } else {
        newSet.add(panelId);
      }
      return newSet;
    });
  };

  const renderQualityOverview = () => {
    if (!analysisData?.quality) return null;

    const { quality } = analysisData;

    return (
      <Card sx={{ backgroundColor: '#1A1A1A', color: 'white', mb: 2 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Audio Quality Assessment
          </Typography>

          <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
            <Typography variant="h4" sx={{ mr: 2 }}>
              {quality.overallScore.toFixed(0)}
            </Typography>
            <Chip
              label={quality.category}
              color={
                quality.overallScore >= 80 ? 'success' :
                quality.overallScore >= 60 ? 'warning' : 'error'
              }
              sx={{ mr: 2 }}
            />
            <Typography variant="body2" color="textSecondary">
              Overall Score
            </Typography>
          </Box>

          <Grid container spacing={2}>
            <Grid item xs={6} sm={2}>
              <Typography variant="caption">Frequency</Typography>
              <Typography variant="h6">{quality.frequencyScore.toFixed(0)}</Typography>
            </Grid>
            <Grid item xs={6} sm={2}>
              <Typography variant="caption">Dynamic</Typography>
              <Typography variant="h6">{quality.dynamicScore.toFixed(0)}</Typography>
            </Grid>
            <Grid item xs={6} sm={2}>
              <Typography variant="caption">Stereo</Typography>
              <Typography variant="h6">{quality.stereoScore.toFixed(0)}</Typography>
            </Grid>
            <Grid item xs={6} sm={2}>
              <Typography variant="caption">Distortion</Typography>
              <Typography variant="h6">{quality.distortionScore.toFixed(0)}</Typography>
            </Grid>
            <Grid item xs={6} sm={2}>
              <Typography variant="caption">Loudness</Typography>
              <Typography variant="h6">{quality.loudnessScore.toFixed(0)}</Typography>
            </Grid>
          </Grid>

          {quality.issues.length > 0 && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="subtitle2" gutterBottom>
                Detected Issues:
              </Typography>
              {quality.issues.map((issue, index) => (
                <Chip key={index} label={issue} size="small" sx={{ mr: 1, mb: 1 }} />
              ))}
            </Box>
          )}
        </CardContent>
      </Card>
    );
  };

  const renderGridLayout = () => (
    <Grid container spacing={2}>
      {/* Quality Overview */}
      <Grid item xs={12}>
        {renderQualityOverview()}
      </Grid>

      {/* Waveform Display */}
      {settings.showWaveform && (
        <Grid item xs={12}>
          <Card sx={{ backgroundColor: '#2A2A2A' }}>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                <Typography variant="h6" sx={{ color: 'white' }}>
                  <Waves sx={{ mr: 1, verticalAlign: 'middle' }} />
                  Enhanced Waveform
                </Typography>
                <IconButton size="small" onClick={() => togglePanel('waveform')}>
                  {expandedPanels.has('waveform') ? <ExpandLess /> : <ExpandMore />}
                </IconButton>
              </Box>
              <Collapse in={expandedPanels.has('waveform')}>
                <AnalysisWaveformDisplay
                  waveformData={analysisData?.waveform}
                  width={800}
                  height={200}
                  showControls={true}
                />
              </Collapse>
            </CardContent>
          </Card>
        </Grid>
      )}

      {/* Meters and Spectrum */}
      <Grid item xs={12} lg={6}>
        {settings.showMeters && (
          <Card sx={{ backgroundColor: '#2A2A2A', mb: 2 }}>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                <Typography variant="h6" sx={{ color: 'white' }}>
                  <Equalizer sx={{ mr: 1, verticalAlign: 'middle' }} />
                  Professional Meters
                </Typography>
                <IconButton size="small" onClick={() => togglePanel('meters')}>
                  {expandedPanels.has('meters') ? <ExpandLess /> : <ExpandMore />}
                </IconButton>
              </Box>
              <Collapse in={expandedPanels.has('meters')}>
                <MeterBridge
                  meterData={analysisData?.meters}
                  width={400}
                  height={500}
                />
              </Collapse>
            </CardContent>
          </Card>
        )}

        {settings.showSpectrum && (
          <Card sx={{ backgroundColor: '#2A2A2A' }}>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                <Typography variant="h6" sx={{ color: 'white' }}>
                  <Timeline sx={{ mr: 1, verticalAlign: 'middle' }} />
                  Spectrum Analyzer
                </Typography>
                <IconButton size="small" onClick={() => togglePanel('spectrum')}>
                  {expandedPanels.has('spectrum') ? <ExpandLess /> : <ExpandMore />}
                </IconButton>
              </Box>
              <Collapse in={expandedPanels.has('spectrum')}>
                <RealtimeAudioVisualizer
                  width={400}
                  height={300}
                  isActive={isRealTime}
                />
              </Collapse>
            </CardContent>
          </Card>
        )}
      </Grid>

      {/* Correlation Display */}
      <Grid item xs={12} lg={6}>
        {settings.showCorrelation && (
          <Card sx={{ backgroundColor: '#2A2A2A' }}>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                <Typography variant="h6" sx={{ color: 'white' }}>
                  <TrendingUp sx={{ mr: 1, verticalAlign: 'middle' }} />
                  Stereo Correlation
                </Typography>
                <IconButton size="small" onClick={() => togglePanel('correlation')}>
                  {expandedPanels.has('correlation') ? <ExpandLess /> : <ExpandMore />}
                </IconButton>
              </Box>
              <Collapse in={expandedPanels.has('correlation')}>
                <CorrelationDisplay
                  correlationData={analysisData?.correlation}
                  width={400}
                  height={400}
                />
              </Collapse>
            </CardContent>
          </Card>
        )}
      </Grid>

      {/* Processing Activity */}
      {settings.showProcessing && (
        <Grid item xs={12}>
          <ProcessingActivityView
            realTimeMode={isRealTime}
          />
        </Grid>
      )}

      {/* Performance Stats */}
      <Grid item xs={12}>
        <Card sx={{ backgroundColor: '#1A1A1A', color: 'white' }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Performance Monitor
            </Typography>
            <Grid container spacing={2}>
              <Grid item xs={3}>
                <Typography variant="caption">FPS</Typography>
                <Typography variant="h6">{optimization.stats.fps.toFixed(1)}</Typography>
              </Grid>
              <Grid item xs={3}>
                <Typography variant="caption">Render Time</Typography>
                <Typography variant="h6">{optimization.stats.renderTime.toFixed(1)}ms</Typography>
              </Grid>
              <Grid item xs={3}>
                <Typography variant="caption">Quality Level</Typography>
                <Typography variant="h6">{(optimization.qualityLevel * 100).toFixed(0)}%</Typography>
              </Grid>
              <Grid item xs={3}>
                <Typography variant="caption">Data Points</Typography>
                <Typography variant="h6">{optimization.stats.dataPoints}</Typography>
              </Grid>
            </Grid>
          </CardContent>
        </Card>
      </Grid>
    </Grid>
  );

  const renderTabsLayout = () => (
    <Box>
      {renderQualityOverview()}

      <Paper sx={{ backgroundColor: '#2A2A2A' }}>
        <Tabs
          value={activeTab}
          onChange={(_, newValue) => setActiveTab(newValue)}
          sx={{ borderBottom: 1, borderColor: 'divider' }}
        >
          <Tab label="Waveform" icon={<Waves />} />
          <Tab label="Meters" icon={<Equalizer />} />
          <Tab label="Correlation" icon={<TrendingUp />} />
          <Tab label="Spectrum" icon={<Timeline />} />
          {settings.showProcessing && <Tab label="Processing" icon={<Analytics />} />}
        </Tabs>

        <Box sx={{ p: 2 }}>
          {activeTab === 0 && settings.showWaveform && (
            <AnalysisWaveformDisplay
              waveformData={analysisData?.waveform}
              width={800}
              height={300}
              showControls={true}
            />
          )}
          {activeTab === 1 && settings.showMeters && (
            <MeterBridge
              meterData={analysisData?.meters}
              width={600}
              height={500}
            />
          )}
          {activeTab === 2 && settings.showCorrelation && (
            <CorrelationDisplay
              correlationData={analysisData?.correlation}
              width={800}
              height={500}
            />
          )}
          {activeTab === 3 && settings.showSpectrum && (
            <RealtimeAudioVisualizer
              width={800}
              height={400}
              isActive={isRealTime}
            />
          )}
          {activeTab === 4 && settings.showProcessing && (
            <ProcessingActivityView realTimeMode={isRealTime} />
          )}
        </Box>
      </Paper>
    </Box>
  );

  const renderSettingsPanel = () => (
    <Collapse in={showSettings}>
      <Card sx={{ backgroundColor: '#1A1A1A', color: 'white', mb: 2 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Dashboard Settings
          </Typography>

          <Grid container spacing={3}>
            <Grid item xs={12} sm={6}>
              <Typography variant="subtitle2" gutterBottom>
                Layout & Visibility
              </Typography>

              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showWaveform}
                    onChange={(e) => handleSettingsChange({ showWaveform: e.target.checked })}
                  />
                }
                label="Show Waveform"
              />

              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showMeters}
                    onChange={(e) => handleSettingsChange({ showMeters: e.target.checked })}
                  />
                }
                label="Show Meters"
              />

              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showCorrelation}
                    onChange={(e) => handleSettingsChange({ showCorrelation: e.target.checked })}
                  />
                }
                label="Show Correlation"
              />

              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showSpectrum}
                    onChange={(e) => handleSettingsChange({ showSpectrum: e.target.checked })}
                  />
                }
                label="Show Spectrum"
              />

              <FormControlLabel
                control={
                  <Switch
                    checked={settings.showProcessing}
                    onChange={(e) => handleSettingsChange({ showProcessing: e.target.checked })}
                  />
                }
                label="Show Processing"
              />
            </Grid>

            <Grid item xs={12} sm={6}>
              <Typography variant="subtitle2" gutterBottom>
                Performance & Updates
              </Typography>

              <FormControlLabel
                control={
                  <Switch
                    checked={settings.autoUpdate}
                    onChange={(e) => handleSettingsChange({ autoUpdate: e.target.checked })}
                  />
                }
                label="Auto Update"
              />

              <Box sx={{ mt: 2 }}>
                <Typography variant="body2" gutterBottom>
                  Update Rate: {settings.updateRate} Hz
                </Typography>
                <Slider
                  value={settings.updateRate}
                  onChange={(_, value) => handleSettingsChange({ updateRate: value as number })}
                  min={1}
                  max={60}
                  step={1}
                  valueLabelDisplay="auto"
                />
              </Box>

              <Box sx={{ mt: 2 }}>
                <Typography variant="body2" gutterBottom>
                  Performance Mode
                </Typography>
                <Box>
                  {(['high', 'balanced', 'low'] as const).map((mode) => (
                    <Chip
                      key={mode}
                      label={mode}
                      variant={settings.performanceMode === mode ? 'filled' : 'outlined'}
                      onClick={() => handleSettingsChange({ performanceMode: mode })}
                      sx={{ mr: 1, mb: 1 }}
                    />
                  ))}
                </Box>
              </Box>
            </Grid>
          </Grid>
        </CardContent>
      </Card>
    </Collapse>
  );

  return (
    <Box className={className}>
      <Paper elevation={2} sx={{ p: 2, backgroundColor: '#0D1B2A' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Typography variant="h5" sx={{ color: 'white' }}>
            Audio Analysis Dashboard
          </Typography>
          <Box>
            <Chip
              label={`${settings.performanceMode} performance`}
              color="info"
              size="small"
              sx={{ mr: 1 }}
            />
            {isRealTime && (
              <Chip
                label="LIVE"
                color="success"
                size="small"
                sx={{ mr: 1 }}
              />
            )}
            <IconButton
              size="small"
              onClick={() => setShowSettings(!showSettings)}
              sx={{ color: 'white' }}
            >
              <Settings />
            </IconButton>
          </Box>
        </Box>

        {renderSettingsPanel()}

        {settings.layout === 'grid' ? renderGridLayout() : renderTabsLayout()}
      </Paper>
    </Box>
  );
};

export default AnalysisDashboard;