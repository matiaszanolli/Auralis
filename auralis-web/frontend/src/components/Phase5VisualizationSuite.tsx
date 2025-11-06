import React, { useState, useCallback, useEffect } from 'react';
import { Box, Paper, Typography, Grid, Tabs, Tab, Button, IconButton } from '@mui/material';
import { FullscreenOutlined, FullscreenExitOutlined, SettingsOutlined } from '@mui/icons-material';

// Import our Phase 5.2 visualization components
import AnalysisWaveformDisplay from './AnalysisWaveformDisplay';
import SpectrumVisualization from './SpectrumVisualization';
import MeterBridge from './MeterBridge';
import CorrelationDisplay from './CorrelationDisplay';
import ProcessingActivityView from './ProcessingActivityView';

// Types for integrated visualization data
interface VisualizationData {
  // Waveform data
  waveform?: {
    peaks: number[];
    rms: number[];
    sampleRate: number;
    duration: number;
    channels: number;
    analysisData?: {
      spectrum?: any;
      loudness?: any;
      correlation?: any;
      dynamics?: any;
    };
  };

  // Spectrum data
  spectrum?: {
    frequency_bins: number[];
    magnitude_db: number[];
    peak_frequency: number;
    spectral_centroid: number;
    spectral_rolloff?: number;
    settings?: {
      fft_size: number;
      frequency_bands: number;
      weighting: string;
    };
  };

  // Meter data
  meters?: {
    momentary_loudness: number;
    short_term_loudness: number;
    integrated_loudness: number;
    loudness_range: number;
    peak_dbfs: number;
    true_peak_dbfs: number;
    rms_left: number;
    rms_right: number;
    correlation_coefficient: number;
    phase_coherence: number;
    stereo_width: number;
    crest_factor: number;
    dynamic_range: number;
    clipping_detected: boolean;
    clip_count: number;
  };

  // Correlation data
  correlation?: {
    correlation_coefficient: number;
    phase_correlation: number;
    stereo_width: number;
    mono_compatibility: number;
    phase_stability: number;
    phase_deviation: number;
    stereo_position: number;
    left_energy: number;
    right_energy: number;
    correlation_history?: number[];
  };

  // Processing activity data
  processing?: {
    stages: Array<{
      name: string;
      isActive: boolean;
      cpuUsage: number;
      latency: number;
      bufferUsage: number;
      inputLevel: number;
      outputLevel: number;
      gainReduction: number;
      parameters: { [key: string]: number };
      alerts: string[];
      timestamp: number;
    }>;
    globalCpuUsage: number;
    globalLatency: number;
    bufferUnderruns: number;
    sampleRate: number;
    bufferSize: number;
    isRealTime: boolean;
    processingLoad: number;
    systemStats: {
      memoryUsage: number;
      diskIO: number;
    };
  };
}

interface Phase5VisualizationSuiteProps {
  data?: VisualizationData;
  className?: string;
  real_time?: boolean;
  onAlert?: (component: string, message: string, severity: 'low' | 'medium' | 'high') => void;
  onComponentClick?: (component: string, data: any) => void;
}

export const Phase5VisualizationSuite: React.FC<Phase5VisualizationSuiteProps> = ({
  data,
  className,
  real_time = true,
  onAlert,
  onComponentClick,
}) => {
  const [activeTab, setActiveTab] = useState(0);
  const [fullscreenComponent, setFullscreenComponent] = useState<string | null>(null);
  const [layoutMode, setLayoutMode] = useState<'grid' | 'tabs' | 'stack'>('grid');

  // Handle tab change
  const handleTabChange = useCallback((event: React.SyntheticEvent, newValue: number) => {
    setActiveTab(newValue);
  }, []);

  // Handle fullscreen toggle
  const toggleFullscreen = useCallback((component: string) => {
    setFullscreenComponent(fullscreenComponent === component ? null : component);
  }, [fullscreenComponent]);

  // Handle alerts from components
  const handleAlert = useCallback((component: string, message: string, severity: 'low' | 'medium' | 'high') => {
    if (onAlert) {
      onAlert(component, message, severity);
    }
    console.log(`[${component}] ${severity.toUpperCase()}: ${message}`);
  }, [onAlert]);

  // Handle component interactions
  const handleComponentClick = useCallback((component: string, data: any) => {
    if (onComponentClick) {
      onComponentClick(component, data);
    }
  }, [onComponentClick]);

  // Generate mock data for demonstration if no data provided
  const getMockData = useCallback((): VisualizationData => {
    const now = Date.now();
    return {
      waveform: {
        peaks: Array.from({ length: 1000 }, () => Math.random() * 2 - 1),
        rms: Array.from({ length: 100 }, () => Math.random() * 0.5),
        sampleRate: 44100,
        duration: 180,
        channels: 2,
        analysisData: {
          loudness: { momentary_loudness: -18.5, peak_dbfs: -3.2 },
          dynamics: { dr_value: 12.8, crest_factor: 8.5 },
          correlation: { correlation_coefficient: 0.75, stereo_width: 0.6 },
        },
      },
      spectrum: {
        frequency_bins: Array.from({ length: 512 }, (_, i) => 20 + i * (20000 / 512)),
        magnitude_db: Array.from({ length: 512 }, (_, i) => -60 + Math.random() * 40 - i * 0.02),
        peak_frequency: 440 + Math.random() * 100,
        spectral_centroid: 2500 + Math.random() * 1000,
        settings: { fft_size: 4096, frequency_bands: 64, weighting: 'A' },
      },
      meters: {
        momentary_loudness: -18.5 + Math.random() * 5,
        short_term_loudness: -19.2 + Math.random() * 4,
        integrated_loudness: -20.1,
        loudness_range: 8.5,
        peak_dbfs: -3.2 + Math.random() * 2,
        true_peak_dbfs: -2.8 + Math.random() * 2,
        rms_left: -15.5 + Math.random() * 3,
        rms_right: -15.8 + Math.random() * 3,
        correlation_coefficient: 0.75 + Math.random() * 0.2,
        phase_coherence: 0.85,
        stereo_width: 0.6 + Math.random() * 0.3,
        crest_factor: 8.5 + Math.random() * 2,
        dynamic_range: 12.8,
        clipping_detected: Math.random() > 0.9,
        clip_count: Math.floor(Math.random() * 5),
      },
      correlation: {
        correlation_coefficient: 0.75 + Math.random() * 0.2,
        phase_correlation: 0.85,
        stereo_width: 0.6 + Math.random() * 0.3,
        mono_compatibility: 0.8,
        phase_stability: 0.9,
        phase_deviation: 0.1,
        stereo_position: (Math.random() - 0.5) * 0.4,
        left_energy: 0.6 + Math.random() * 0.3,
        right_energy: 0.65 + Math.random() * 0.25,
        correlation_history: Array.from({ length: 100 }, () => 0.5 + Math.random() * 0.4),
      },
      processing: {
        stages: [
          {
            name: 'Input',
            isActive: true,
            cpuUsage: 15 + Math.random() * 10,
            latency: 2.5,
            bufferUsage: 0.3 + Math.random() * 0.2,
            inputLevel: -12.5,
            outputLevel: -12.5,
            gainReduction: 0,
            parameters: { gain: 0, threshold: -12 },
            alerts: [],
            timestamp: now,
          },
          {
            name: 'EQ',
            isActive: true,
            cpuUsage: 25 + Math.random() * 15,
            latency: 3.2,
            bufferUsage: 0.4 + Math.random() * 0.3,
            inputLevel: -12.5,
            outputLevel: -11.8,
            gainReduction: 0,
            parameters: { lowGain: 2.5, midGain: 0, highGain: 1.2 },
            alerts: [],
            timestamp: now,
          },
          {
            name: 'Compressor',
            isActive: true,
            cpuUsage: 35 + Math.random() * 20,
            latency: 5.1,
            bufferUsage: 0.5 + Math.random() * 0.2,
            inputLevel: -11.8,
            outputLevel: -8.5,
            gainReduction: 3.2 + Math.random() * 2,
            parameters: { ratio: 4, attack: 10, release: 100 },
            alerts: Math.random() > 0.8 ? ['High CPU usage'] : [],
            timestamp: now,
          },
          {
            name: 'Limiter',
            isActive: true,
            cpuUsage: 20 + Math.random() * 10,
            latency: 1.8,
            bufferUsage: 0.6 + Math.random() * 0.2,
            inputLevel: -8.5,
            outputLevel: -0.1,
            gainReduction: 8.4 + Math.random() * 3,
            parameters: { ceiling: -0.1, lookahead: 5 },
            alerts: [],
            timestamp: now,
          },
        ],
        globalCpuUsage: 45 + Math.random() * 20,
        globalLatency: 12.6,
        bufferUnderruns: Math.floor(Math.random() * 3),
        sampleRate: 44100,
        bufferSize: 512,
        isRealTime: true,
        processingLoad: 0.65 + Math.random() * 0.2,
        systemStats: {
          memoryUsage: 1250 + Math.random() * 200,
          diskIO: 50 + Math.random() * 30,
        },
      },
    };
  }, []);

  // Use provided data or generate mock data
  const visualizationData = data || getMockData();

  // Update mock data periodically for real-time simulation
  const [mockData, setMockData] = useState(visualizationData);

  useEffect(() => {
    if (!data && real_time) {
      const interval = setInterval(() => {
        setMockData(getMockData());
      }, 100); // Update every 100ms for smooth animation

      return () => clearInterval(interval);
    }
  }, [data, real_time, getMockData]);

  const currentData = data || mockData;

  // Component definitions with fullscreen capability
  const components = [
    {
      id: 'waveform',
      title: 'Waveform Analysis',
      component: (
        <AnalysisWaveformDisplay
          waveformData={currentData.waveform}
          width={fullscreenComponent === 'waveform' ? window.innerWidth - 100 : 800}
          height={fullscreenComponent === 'waveform' ? window.innerHeight - 200 : 300}
          showControls={true}
          real_time={real_time}
          analysisMode="all"
        />
      ),
    },
    {
      id: 'spectrum',
      title: 'Spectrum Visualization',
      component: (
        <SpectrumVisualization
          spectrumData={currentData.spectrum}
          width={fullscreenComponent === 'spectrum' ? window.innerWidth - 100 : 800}
          height={fullscreenComponent === 'spectrum' ? window.innerHeight - 200 : 400}
          showControls={true}
          real_time={real_time}
          analysisMode="professional"
          onFrequencyClick={(freq) => handleComponentClick('spectrum', { frequency: freq })}
        />
      ),
    },
    {
      id: 'meters',
      title: 'Professional Meters',
      component: (
        <MeterBridge
          meterData={currentData.meters}
          width={fullscreenComponent === 'meters' ? window.innerWidth - 100 : 600}
          height={fullscreenComponent === 'meters' ? window.innerHeight - 200 : 300}
          showControls={true}
          real_time={real_time}
          onOverload={(channel, level) => handleAlert('meters', `Overload on ${channel}: ${level.toFixed(1)}dB`, 'high')}
          onCorrelationAlert={(corr) => handleAlert('meters', `Poor correlation: ${corr.toFixed(2)}`, 'medium')}
        />
      ),
    },
    {
      id: 'correlation',
      title: 'Phase & Correlation',
      component: (
        <CorrelationDisplay
          correlationData={currentData.correlation}
          width={fullscreenComponent === 'correlation' ? window.innerWidth - 100 : 400}
          height={fullscreenComponent === 'correlation' ? window.innerHeight - 200 : 400}
          showControls={true}
          real_time={real_time}
          onPhaseAlert={(issue, severity) => handleAlert('correlation', issue, severity)}
          onMonoCompatibilityAlert={(compat) => handleAlert('correlation', `Mono compatibility: ${(compat * 100).toFixed(0)}%`, 'low')}
        />
      ),
    },
    {
      id: 'processing',
      title: 'Processing Activity',
      component: (
        <ProcessingActivityView
          activityData={currentData.processing}
          width={fullscreenComponent === 'processing' ? window.innerWidth - 100 : 800}
          height={fullscreenComponent === 'processing' ? window.innerHeight - 200 : 500}
          showControls={true}
          real_time={real_time}
          onStageClick={(stage) => handleComponentClick('processing', { stage })}
          onAlert={(stage, alert, severity) => handleAlert('processing', `${stage}: ${alert}`, severity)}
        />
      ),
    },
  ];

  // Render fullscreen component
  if (fullscreenComponent) {
    const component = components.find(c => c.id === fullscreenComponent);
    if (component) {
      return (
        <Box
          sx={{
            position: 'fixed',
            top: 0,
            left: 0,
            width: '100vw',
            height: '100vh',
            bgcolor: '#0A0A0A',
            zIndex: 9999,
            p: 2,
          }}
        >
          <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
            <Typography variant="h4" color="white">
              {component.title} - Fullscreen
            </Typography>
            <IconButton
              onClick={() => toggleFullscreen(fullscreenComponent)}
              sx={{ color: 'white' }}
            >
              <FullscreenExitOutlined />
            </IconButton>
          </Box>
          {component.component}
        </Box>
      );
    }
  }

  // Grid layout
  if (layoutMode === 'grid') {
    return (
      <Paper className={className} sx={{ p: 2, backgroundColor: '#1A1A1A' }}>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
          <Typography variant="h4" color="white">
            Phase 5.2 - Visualization Suite
          </Typography>
          <Box display="flex" gap={1}>
            <Button
              variant="outlined"
              onClick={() => setLayoutMode(layoutMode === 'grid' ? 'tabs' : 'grid')}
              sx={{ color: 'white', borderColor: 'white' }}
            >
              {layoutMode === 'grid' ? 'Tab View' : 'Grid View'}
            </Button>
          </Box>
        </Box>

        <Grid container spacing={3}>
          {/* Top row - Waveform and Spectrum */}
          <Grid item xs={12} lg={6}>
            <Box position="relative">
              <IconButton
                sx={{ position: 'absolute', top: 8, right: 8, zIndex: 1, color: 'white' }}
                onClick={() => toggleFullscreen('waveform')}
              >
                <FullscreenOutlined />
              </IconButton>
              {components[0].component}
            </Box>
          </Grid>
          <Grid item xs={12} lg={6}>
            <Box position="relative">
              <IconButton
                sx={{ position: 'absolute', top: 8, right: 8, zIndex: 1, color: 'white' }}
                onClick={() => toggleFullscreen('spectrum')}
              >
                <FullscreenOutlined />
              </IconButton>
              {components[1].component}
            </Box>
          </Grid>

          {/* Middle row - Meters and Correlation */}
          <Grid item xs={12} lg={8}>
            <Box position="relative">
              <IconButton
                sx={{ position: 'absolute', top: 8, right: 8, zIndex: 1, color: 'white' }}
                onClick={() => toggleFullscreen('meters')}
              >
                <FullscreenOutlined />
              </IconButton>
              {components[2].component}
            </Box>
          </Grid>
          <Grid item xs={12} lg={4}>
            <Box position="relative">
              <IconButton
                sx={{ position: 'absolute', top: 8, right: 8, zIndex: 1, color: 'white' }}
                onClick={() => toggleFullscreen('correlation')}
              >
                <FullscreenOutlined />
              </IconButton>
              {components[3].component}
            </Box>
          </Grid>

          {/* Bottom row - Processing Activity */}
          <Grid item xs={12}>
            <Box position="relative">
              <IconButton
                sx={{ position: 'absolute', top: 8, right: 8, zIndex: 1, color: 'white' }}
                onClick={() => toggleFullscreen('processing')}
              >
                <FullscreenOutlined />
              </IconButton>
              {components[4].component}
            </Box>
          </Grid>
        </Grid>

        {/* Status bar */}
        <Box mt={3} p={2} sx={{ backgroundColor: '#0A0A0A', borderRadius: 1 }}>
          <Typography variant="body2" color="grey.400">
            Phase 5.2 Visualization Suite - Real-time Analysis & Monitoring
            {real_time && ' • Live Data'} • Click fullscreen icon to expand any component
          </Typography>
        </Box>
      </Paper>
    );
  }

  // Tab layout
  return (
    <Paper className={className} sx={{ p: 2, backgroundColor: '#1A1A1A' }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h4" color="white">
          Phase 5.2 - Visualization Suite
        </Typography>
        <Button
          variant="outlined"
          onClick={() => setLayoutMode('grid')}
          sx={{ color: 'white', borderColor: 'white' }}
        >
          Grid View
        </Button>
      </Box>

      <Tabs
        value={activeTab}
        onChange={handleTabChange}
        sx={{
          '& .MuiTab-root': { color: 'grey.400' },
          '& .Mui-selected': { color: 'white' },
        }}
      >
        {components.map((component, index) => (
          <Tab key={component.id} label={component.title} />
        ))}
      </Tabs>

      <Box mt={2}>
        {components.map((component, index) => (
          <Box
            key={component.id}
            role="tabpanel"
            hidden={activeTab !== index}
            sx={{ position: 'relative' }}
          >
            {activeTab === index && (
              <>
                <IconButton
                  sx={{ position: 'absolute', top: 8, right: 8, zIndex: 1, color: 'white' }}
                  onClick={() => toggleFullscreen(component.id)}
                >
                  <FullscreenOutlined />
                </IconButton>
                {component.component}
              </>
            )}
          </Box>
        ))}
      </Box>
    </Paper>
  );
};

export default Phase5VisualizationSuite;