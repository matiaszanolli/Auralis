# Quick Start: UI Development

**Goal**: Get started immediately with Phase 1 of UI implementation

---

## Step 1: Set Up Directory Structure (2 minutes)

```bash
cd auralis-web/frontend

# Create new directories
mkdir -p src/theme
mkdir -p src/styles
mkdir -p src/components/shared
mkdir -p src/components/library
mkdir -p src/components/player
mkdir -p src/hooks
```

---

## Step 2: Create Theme System (30 minutes)

### File: `src/theme/auralisTheme.ts`

```typescript
import { createTheme } from '@mui/material/styles';

// Aurora gradient definitions
export const gradients = {
  aurora: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  auroraReverse: 'linear-gradient(135deg, #764ba2 0%, #667eea 100%)',
  neonSunset: 'linear-gradient(135deg, #ff6b9d 0%, #ffa502 100%)',
  deepOcean: 'linear-gradient(135deg, #4b7bec 0%, #26de81 100%)',
};

// Color palette
export const colors = {
  background: {
    primary: '#0A0E27',
    secondary: '#1a1f3a',
    surface: '#252b45',
    hover: '#2a3150',
  },
  text: {
    primary: '#ffffff',
    secondary: '#8b92b0',
    disabled: '#5a5f7a',
  },
  accent: {
    success: '#00d4aa',
    error: '#ff4757',
    warning: '#ffa502',
    info: '#4b7bec',
  },
  neon: {
    pink: '#ff6b9d',
    purple: '#c44569',
    blue: '#4b7bec',
    cyan: '#26de81',
    orange: '#ffa502',
  },
};

// Create MUI theme
export const auralisTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#667eea',
    },
    secondary: {
      main: '#764ba2',
    },
    background: {
      default: colors.background.primary,
      paper: colors.background.secondary,
    },
    text: {
      primary: colors.text.primary,
      secondary: colors.text.secondary,
    },
    success: {
      main: colors.accent.success,
    },
    error: {
      main: colors.accent.error,
    },
    warning: {
      main: colors.accent.warning,
    },
    info: {
      main: colors.accent.info,
    },
  },
  typography: {
    fontFamily: [
      '-apple-system',
      'BlinkMacSystemFont',
      '"Segoe UI"',
      'Roboto',
      '"Helvetica Neue"',
      'Arial',
      'sans-serif',
    ].join(','),
    h1: {
      fontSize: '32px',
      fontWeight: 700,
    },
    h2: {
      fontSize: '24px',
      fontWeight: 600,
    },
    h3: {
      fontSize: '20px',
      fontWeight: 600,
    },
    body1: {
      fontSize: '16px',
    },
    body2: {
      fontSize: '14px',
    },
    caption: {
      fontSize: '12px',
      color: colors.text.secondary,
    },
  },
  shape: {
    borderRadius: 8,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          borderRadius: '8px',
          padding: '10px 24px',
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          backgroundColor: colors.background.secondary,
          backgroundImage: 'none',
        },
      },
    },
  },
});

export default auralisTheme;
```

### File: `src/styles/globalStyles.ts`

```typescript
import { css } from '@mui/material/styles';
import { colors, gradients } from '../theme/auralisTheme';

export const globalStyles = css`
  :root {
    /* Color variables */
    --bg-primary: ${colors.background.primary};
    --bg-secondary: ${colors.background.secondary};
    --bg-surface: ${colors.background.surface};
    --bg-hover: ${colors.background.hover};

    --text-primary: ${colors.text.primary};
    --text-secondary: ${colors.text.secondary};

    /* Gradient variables */
    --gradient-aurora: ${gradients.aurora};
    --gradient-sunset: ${gradients.neonSunset};
  }

  * {
    box-sizing: border-box;
  }

  body {
    margin: 0;
    padding: 0;
    overflow: hidden;
  }

  /* Custom scrollbar */
  ::-webkit-scrollbar {
    width: 12px;
  }

  ::-webkit-scrollbar-track {
    background: ${colors.background.secondary};
  }

  ::-webkit-scrollbar-thumb {
    background: ${colors.background.surface};
    border-radius: 6px;
  }

  ::-webkit-scrollbar-thumb:hover {
    background: ${colors.background.hover};
  }

  /* Animation keyframes */
  @keyframes pulse {
    0%, 100% {
      opacity: 1;
    }
    50% {
      opacity: 0.6;
    }
  }

  @keyframes glow {
    0%, 100% {
      filter: drop-shadow(0 0 8px rgba(102, 126, 234, 0.4));
    }
    50% {
      filter: drop-shadow(0 0 16px rgba(102, 126, 234, 0.8));
    }
  }

  @keyframes shimmer {
    0% {
      background-position: -1000px 0;
    }
    100% {
      background-position: 1000px 0;
    }
  }

  /* Utility classes */
  .gradient-text {
    background: ${gradients.aurora};
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }

  .hover-lift {
    transition: transform 0.3s ease;
  }

  .hover-lift:hover {
    transform: translateY(-4px);
  }

  .smooth-transition {
    transition: all 0.3s ease;
  }
`;
```

---

## Step 3: Create First Shared Component (20 minutes)

### File: `src/components/shared/GradientButton.tsx`

```typescript
import React from 'react';
import { Button, ButtonProps, styled } from '@mui/material';
import { gradients } from '../../theme/auralisTheme';

interface GradientButtonProps extends ButtonProps {
  gradient?: string;
}

const StyledGradientButton = styled(Button)<GradientButtonProps>(({ gradient }) => ({
  background: gradient || gradients.aurora,
  color: '#ffffff',
  fontWeight: 600,
  border: 'none',
  transition: 'all 0.3s ease',
  position: 'relative',
  overflow: 'hidden',

  '&:hover': {
    background: gradient || gradients.aurora,
    filter: 'brightness(1.2)',
    transform: 'scale(1.05)',
  },

  '&::before': {
    content: '""',
    position: 'absolute',
    top: 0,
    left: '-100%',
    width: '100%',
    height: '100%',
    background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent)',
    transition: 'left 0.5s',
  },

  '&:hover::before': {
    left: '100%',
  },
}));

export const GradientButton: React.FC<GradientButtonProps> = ({
  children,
  gradient,
  ...props
}) => {
  return (
    <StyledGradientButton gradient={gradient} {...props}>
      {children}
    </StyledGradientButton>
  );
};

export default GradientButton;
```

---

## Step 4: Update App to Use Theme (10 minutes)

### File: `src/index.tsx` (update)

```typescript
import React from 'react';
import ReactDOM from 'react-dom/client';
import { ThemeProvider } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import App from './App';
import { auralisTheme } from './theme/auralisTheme';

const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);

root.render(
  <React.StrictMode>
    <ThemeProvider theme={auralisTheme}>
      <CssBaseline />
      <App />
    </ThemeProvider>
  </React.StrictMode>
);
```

---

## Step 5: Create Your First Visual Component (45 minutes)

### File: `src/components/library/AlbumCard.tsx`

```typescript
import React, { useState } from 'react';
import { Card, CardMedia, CardContent, Typography, Box, IconButton, styled } from '@mui/material';
import { PlayArrow, MoreVert } from '@mui/icons-material';
import { colors, gradients } from '../../theme/auralisTheme';

interface AlbumCardProps {
  id: number;
  title: string;
  artist: string;
  albumArt: string;
  trackCount?: number;
  onPlay: (id: number) => void;
  onContextMenu?: (id: number, event: React.MouseEvent) => void;
}

const StyledCard = styled(Card)(({ theme }) => ({
  position: 'relative',
  backgroundColor: colors.background.secondary,
  borderRadius: '8px',
  overflow: 'hidden',
  cursor: 'pointer',
  transition: 'all 0.3s ease',

  '&:hover': {
    transform: 'scale(1.05)',
    boxShadow: `0 8px 32px rgba(102, 126, 234, 0.3)`,
  },

  '&:hover .play-overlay': {
    opacity: 1,
  },
}));

const PlayOverlay = styled(Box)({
  position: 'absolute',
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  background: 'rgba(0, 0, 0, 0.6)',
  opacity: 0,
  transition: 'opacity 0.3s ease',
  zIndex: 2,
});

const PlayButton = styled(IconButton)({
  background: gradients.aurora,
  width: '64px',
  height: '64px',
  color: '#ffffff',

  '&:hover': {
    background: gradients.aurora,
    transform: 'scale(1.1)',
  },

  '& .MuiSvgIcon-root': {
    fontSize: '32px',
  },
});

export const AlbumCard: React.FC<AlbumCardProps> = ({
  id,
  title,
  artist,
  albumArt,
  trackCount,
  onPlay,
  onContextMenu,
}) => {
  const [imageError, setImageError] = useState(false);

  const handlePlay = (e: React.MouseEvent) => {
    e.stopPropagation();
    onPlay(id);
  };

  const handleContextMenu = (e: React.MouseEvent) => {
    e.preventDefault();
    onContextMenu?.(id, e);
  };

  // Placeholder gradient if image fails to load
  const placeholderGradient = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';

  return (
    <StyledCard onContextMenu={handleContextMenu}>
      <Box position="relative">
        {imageError || !albumArt ? (
          <Box
            sx={{
              width: '100%',
              paddingTop: '100%', // 1:1 aspect ratio
              background: placeholderGradient,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          />
        ) : (
          <CardMedia
            component="img"
            image={albumArt}
            alt={title}
            onError={() => setImageError(true)}
            sx={{
              width: '100%',
              aspectRatio: '1/1',
              objectFit: 'cover',
            }}
          />
        )}

        <PlayOverlay className="play-overlay">
          <PlayButton onClick={handlePlay}>
            <PlayArrow />
          </PlayButton>
        </PlayOverlay>
      </Box>

      <CardContent sx={{ p: 2 }}>
        <Typography
          variant="body1"
          sx={{
            color: colors.text.primary,
            fontWeight: 600,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {title}
        </Typography>
        <Typography
          variant="body2"
          sx={{
            color: colors.text.secondary,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          {artist}
        </Typography>
        {trackCount && (
          <Typography variant="caption" sx={{ mt: 0.5 }}>
            {trackCount} tracks
          </Typography>
        )}
      </CardContent>
    </StyledCard>
  );
};

export default AlbumCard;
```

---

## Step 6: Test Your Progress (5 minutes)

Update `CozyLibraryView.tsx` to use the new AlbumCard:

```typescript
import AlbumCard from './library/AlbumCard';

// In your render method:
<Grid container spacing={3}>
  {filteredTracks.map((track) => (
    <Grid item xs={12} sm={6} md={4} lg={3} key={track.id}>
      <AlbumCard
        id={track.id}
        title={track.album || track.title}
        artist={track.artist}
        albumArt={track.albumArt || ''}
        onPlay={handlePlay}
      />
    </Grid>
  ))}
</Grid>
```

Run the development server:

```bash
cd auralis-web/frontend
npm start
```

---

## What You Should See

After completing these steps, you should have:

✅ **Theme system** with aurora gradients and dark navy colors
✅ **Global styles** with smooth animations
✅ **GradientButton** component ready to use
✅ **AlbumCard** component showing your music with hover effects
✅ **Development server** running with hot reload

---

## Next Steps

Once you've completed Phase 1 foundations:

1. **Create GradientSlider** component
2. **Create LoadingSpinner** with aurora gradient
3. **Build TrackQueue** component (from screenshot)
4. **Enhance BottomPlayerBar** with gradient controls
5. **Add SearchBar** with pill shape

See `UI_IMPLEMENTATION_ROADMAP.md` for full details.

---

## Troubleshooting

**TypeScript errors?**
```bash
npm install --save-dev @types/react @types/react-dom
```

**MUI not found?**
```bash
npm install @mui/material @mui/icons-material @emotion/react @emotion/styled
```

**Can't see changes?**
```bash
# Clear cache and restart
rm -rf node_modules/.cache
npm start
```

---

**Happy coding! 🎨**
