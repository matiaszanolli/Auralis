import React from 'react';
import {
  Box,
  Typography,
  Chip,
  LinearProgress,
} from '@mui/material';

interface StatusBarProps {
  status?: string;
  progress?: number;
  connected?: boolean;
}

const StatusBar: React.FC<StatusBarProps> = ({
  status = 'Ready',
  progress,
  connected = true,
}) => {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        px: 2,
        py: 0.5,
        backgroundColor: 'background.default',
        borderTop: 1,
        borderColor: 'divider',
        minHeight: 32,
      }}
    >
      {/* Status Message */}
      <Box display="flex" alignItems="center" gap={2}>
        <Typography variant="caption" color="text.secondary">
          {status}
        </Typography>
        {progress !== undefined && (
          <Box sx={{ width: 200 }}>
            <LinearProgress
              variant="determinate"
              value={progress}
              sx={{ height: 4, borderRadius: 2 }}
            />
          </Box>
        )}
      </Box>

      {/* Connection Status */}
      <Box display="flex" alignItems="center" gap={1}>
        <Chip
          label={connected ? 'Connected' : 'Disconnected'}
          color={connected ? 'success' : 'error'}
          size="small"
          variant="outlined"
        />
        <Typography variant="caption" color="text.secondary">
          Auralis Web v1.0.0
        </Typography>
      </Box>
    </Box>
  );
};

export default StatusBar;