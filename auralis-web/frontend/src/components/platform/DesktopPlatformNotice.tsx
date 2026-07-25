import InfoOutlined from '@mui/icons-material/InfoOutlined';
import { Box, Typography } from '@mui/material';
import { tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';
import { isElectron } from '@/utils/electron';

/**
 * Standalone browser execution is retained as a development and review aid.
 * The supported product is the Electron desktop application.
 */
export const DesktopPlatformNotice = () => {
  if (isElectron()) {
    return null;
  }

  return (
    <Box
      role="status"
      aria-label="Platform support notice"
      sx={{
        minHeight: 34,
        px: tokens.spacing.lg,
        py: tokens.spacing.sm,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: tokens.spacing.cluster,
        flexShrink: 0,
        backgroundColor: themeVars.surfaceRaised,
        color: themeVars.textSecondary,
        borderBottom: `1px solid ${themeVars.borderDefault}`,
        position: 'relative',
        zIndex: tokens.zIndex.sticky,
      }}
    >
      <InfoOutlined sx={{ color: themeVars.warning, fontSize: 16 }} />
      <Typography
        component="span"
        sx={{
          color: 'inherit',
          fontSize: tokens.typography.fontSize.xs,
          lineHeight: 1.4,
        }}
      >
        Browser preview — unsupported platform. Official Auralis releases are desktop applications.
      </Typography>
    </Box>
  );
};

export default DesktopPlatformNotice;
