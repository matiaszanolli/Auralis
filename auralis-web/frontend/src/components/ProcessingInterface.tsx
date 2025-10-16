/**
 * Processing Interface Component
 * ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
 *
 * Main interface for audio processing operations.
 * Handles file upload, processing settings, job submission, and results.
 *
 * @copyright (C) 2024 Auralis Team
 * @license GPLv3
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  LinearProgress,
  Alert,
  AlertTitle,
  Grid,
  Chip,
  Divider,
  IconButton,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
} from '@mui/material';
import {
  CloudUpload,
  PlayArrow,
  Download,
  Cancel,
  CheckCircle,
  Error as ErrorIcon,
  Refresh,
  QueueMusic,
  Settings as SettingsIcon,
} from '@mui/icons-material';
import AudioProcessingControls from './AudioProcessingControls';
import processingService, {
  ProcessingSettings,
  ProcessingJob,
  QueueStatus,
} from '../services/processingService.ts';

interface ProcessingInterfaceProps {
  websocket: WebSocket | null;
}

const ProcessingInterface: React.FC<ProcessingInterfaceProps> = ({ websocket }) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [settings, setSettings] = useState<ProcessingSettings>({
    mode: 'adaptive',
    output_format: 'wav',
    bit_depth: 16,
    eq: {
      enabled: true,
      low: 0,
      lowMid: 0,
      mid: 0,
      highMid: 0,
      high: 0,
    },
    dynamics: {
      enabled: true,
      compressor: {
        threshold: -18,
        ratio: 4,
        attack: 3,
        release: 100,
      },
      limiter: {
        enabled: true,
        threshold: -0.3,
        lookahead: 5,
      },
    },
    levelMatching: {
      enabled: true,
      targetLufs: -16,
      maxGain: 12,
    },
  });

  const [currentJob, setCurrentJob] = useState<ProcessingJob | null>(null);
  const [recentJobs, setRecentJobs] = useState<ProcessingJob[]>([]);
  const [queueStatus, setQueueStatus] = useState<QueueStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(true);

  // Connect WebSocket on mount
  useEffect(() => {
    processingService.connectWebSocket().catch((err) => {
      console.error('Failed to connect WebSocket:', err);
    });
  }, []);

  // Poll queue status
  useEffect(() => {
    const pollQueueStatus = async () => {
      try {
        const status = await processingService.getQueueStatus();
        setQueueStatus(status);
      } catch (err) {
        console.error('Failed to get queue status:', err);
      }
    };

    pollQueueStatus();
    const interval = setInterval(pollQueueStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  // Load recent jobs
  const loadRecentJobs = useCallback(async () => {
    try {
      const { jobs } = await processingService.listJobs(undefined, 10);
      setRecentJobs(jobs);
    } catch (err) {
      console.error('Failed to load recent jobs:', err);
    }
  }, []);

  useEffect(() => {
    loadRecentJobs();
  }, [loadRecentJobs]);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files && files.length > 0) {
      setSelectedFile(files[0]);
      setError(null);
    }
  };

  const handleProcessAudio = async () => {
    if (!selectedFile) {
      setError('Please select an audio file first');
      return;
    }

    setError(null);

    try {
      // Upload and process the file
      const response = await processingService.uploadAndProcess(selectedFile, settings);

      // Create job object
      const job: ProcessingJob = {
        job_id: response.job_id,
        status: 'queued',
        progress: 0,
      };

      setCurrentJob(job);

      // Subscribe to job progress
      processingService.subscribeToJob(response.job_id, (updatedJob) => {
        setCurrentJob(updatedJob);

        // Reload recent jobs when complete
        if (updatedJob.status === 'completed' || updatedJob.status === 'failed') {
          loadRecentJobs();
        }
      });

      // Poll for completion
      await processingService.waitForCompletion(
        response.job_id,
        (job) => {
          setCurrentJob(job);
        },
        1000
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Processing failed');
      setCurrentJob(null);
    }
  };

  const handleCancelJob = async () => {
    if (!currentJob) return;

    try {
      await processingService.cancelJob(currentJob.job_id);
      setCurrentJob(null);
      loadRecentJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel job');
    }
  };

  const handleDownload = async (jobId: string) => {
    try {
      const blob = await processingService.downloadResult(jobId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `auralis_processed_${jobId}.${settings.output_format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to download result');
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle color="success" />;
      case 'failed':
      case 'cancelled':
        return <ErrorIcon color="error" />;
      case 'processing':
        return <PlayArrow color="primary" />;
      default:
        return <QueueMusic />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'success';
      case 'failed':
        return 'error';
      case 'cancelled':
        return 'default';
      case 'processing':
        return 'primary';
      default:
        return 'info';
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Grid container spacing={3}>
        {/* File Upload Section */}
        <Grid item xs={12} md={6}>
          <Card elevation={3}>
            <CardContent>
              <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <CloudUpload /> Upload Audio
              </Typography>

              <Box
                sx={{
                  border: '2px dashed',
                  borderColor: selectedFile ? 'success.main' : 'grey.400',
                  borderRadius: 2,
                  p: 4,
                  textAlign: 'center',
                  cursor: 'pointer',
                  transition: 'all 0.3s',
                  '&:hover': {
                    borderColor: 'primary.main',
                    backgroundColor: 'rgba(0,0,0,0.02)',
                  },
                }}
                onClick={() => document.getElementById('file-input')?.click()}
              >
                <input
                  id="file-input"
                  type="file"
                  accept="audio/*,.mp3,.wav,.flac,.ogg,.m4a"
                  style={{ display: 'none' }}
                  onChange={handleFileSelect}
                />

                {selectedFile ? (
                  <>
                    <Typography variant="h6" color="success.main">
                      ✓ {selectedFile.name}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                    </Typography>
                  </>
                ) : (
                  <>
                    <CloudUpload sx={{ fontSize: 48, color: 'grey.400', mb: 2 }} />
                    <Typography variant="body1">Click to select audio file</Typography>
                    <Typography variant="caption" color="text.secondary">
                      Supports: MP3, WAV, FLAC, OGG, M4A
                    </Typography>
                  </>
                )}
              </Box>

              <Box sx={{ mt: 3, display: 'flex', gap: 2 }}>
                <Button
                  variant="contained"
                  size="large"
                  fullWidth
                  onClick={handleProcessAudio}
                  disabled={!selectedFile || (currentJob?.status === 'processing' || currentJob?.status === 'queued')}
                  startIcon={<PlayArrow />}
                >
                  Process Audio
                </Button>

                {currentJob && (currentJob.status === 'processing' || currentJob.status === 'queued') && (
                  <Button
                    variant="outlined"
                    color="error"
                    onClick={handleCancelJob}
                    startIcon={<Cancel />}
                  >
                    Cancel
                  </Button>
                )}
              </Box>

              {error && (
                <Alert severity="error" sx={{ mt: 2 }}>
                  {error}
                </Alert>
              )}

              {/* Current Job Progress */}
              {currentJob && (
                <Box sx={{ mt: 3 }}>
                  <Typography variant="subtitle2" gutterBottom>
                    Current Job: {currentJob.job_id.slice(0, 8)}...
                  </Typography>

                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    <Chip
                      label={currentJob.status}
                      color={getStatusColor(currentJob.status) as any}
                      size="small"
                    />
                    <Typography variant="body2">
                      {currentJob.progress.toFixed(0)}%
                    </Typography>
                  </Box>

                  <LinearProgress
                    variant="determinate"
                    value={currentJob.progress}
                    sx={{ mb: 1 }}
                  />

                  {currentJob.status === 'completed' && (
                    <Button
                      variant="contained"
                      color="success"
                      fullWidth
                      onClick={() => handleDownload(currentJob.job_id)}
                      startIcon={<Download />}
                    >
                      Download Result
                    </Button>
                  )}

                  {currentJob.result_data && (
                    <Box sx={{ mt: 2, p: 2, bgcolor: 'background.paper', borderRadius: 1 }}>
                      <Typography variant="caption" display="block">
                        <strong>Format:</strong> {currentJob.result_data.format} ({currentJob.result_data.bit_depth}-bit)
                      </Typography>
                      <Typography variant="caption" display="block">
                        <strong>Duration:</strong> {currentJob.result_data.duration.toFixed(2)}s
                      </Typography>
                      {currentJob.result_data.genre_detected && (
                        <Typography variant="caption" display="block">
                          <strong>Genre:</strong> {currentJob.result_data.genre_detected}
                        </Typography>
                      )}
                      {currentJob.result_data.lufs !== undefined && (
                        <Typography variant="caption" display="block">
                          <strong>LUFS:</strong> {currentJob.result_data.lufs.toFixed(2)}
                        </Typography>
                      )}
                    </Box>
                  )}
                </Box>
              )}
            </CardContent>
          </Card>

          {/* Queue Status */}
          {queueStatus && (
            <Card elevation={3} sx={{ mt: 3 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Processing Queue
                </Typography>

                <Grid container spacing={2}>
                  <Grid item xs={6}>
                    <Typography variant="body2" color="text.secondary">
                      Queued
                    </Typography>
                    <Typography variant="h6">{queueStatus.queued}</Typography>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography variant="body2" color="text.secondary">
                      Processing
                    </Typography>
                    <Typography variant="h6">{queueStatus.processing}</Typography>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography variant="body2" color="text.secondary">
                      Completed
                    </Typography>
                    <Typography variant="h6" color="success.main">
                      {queueStatus.completed}
                    </Typography>
                  </Grid>
                  <Grid item xs={6}>
                    <Typography variant="body2" color="text.secondary">
                      Failed
                    </Typography>
                    <Typography variant="h6" color="error.main">
                      {queueStatus.failed}
                    </Typography>
                  </Grid>
                </Grid>
              </CardContent>
            </Card>
          )}
        </Grid>

        {/* Processing Settings */}
        <Grid item xs={12} md={6}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
            <Typography variant="h6">Processing Settings</Typography>
            <IconButton onClick={() => setShowSettings(!showSettings)}>
              <SettingsIcon />
            </IconButton>
          </Box>

          {showSettings && (
            <AudioProcessingControls
              websocket={websocket}
              onSettingsChange={(newSettings) => {
                // Convert UI settings to API settings format
                setSettings((prev) => ({
                  ...prev,
                  ...newSettings,
                }));
              }}
            />
          )}
        </Grid>

        {/* Recent Jobs */}
        <Grid item xs={12}>
          <Card elevation={3}>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6">Recent Jobs</Typography>
                <IconButton onClick={loadRecentJobs} size="small">
                  <Refresh />
                </IconButton>
              </Box>

              <List>
                {recentJobs.map((job) => (
                  <React.Fragment key={job.job_id}>
                    <ListItem>
                      <Box sx={{ mr: 2 }}>{getStatusIcon(job.status)}</Box>
                      <ListItemText
                        primary={job.job_id.slice(0, 12) + '...'}
                        secondary={
                          <>
                            <Chip
                              label={job.status}
                              size="small"
                              color={getStatusColor(job.status) as any}
                              sx={{ mr: 1 }}
                            />
                            {job.progress < 100 && `${job.progress.toFixed(0)}%`}
                          </>
                        }
                      />
                      <ListItemSecondaryAction>
                        {job.status === 'completed' && (
                          <IconButton
                            edge="end"
                            onClick={() => handleDownload(job.job_id)}
                            color="primary"
                          >
                            <Download />
                          </IconButton>
                        )}
                      </ListItemSecondaryAction>
                    </ListItem>
                    <Divider />
                  </React.Fragment>
                ))}

                {recentJobs.length === 0 && (
                  <Typography variant="body2" color="text.secondary" align="center" sx={{ p: 3 }}>
                    No recent jobs
                  </Typography>
                )}
              </List>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default ProcessingInterface;