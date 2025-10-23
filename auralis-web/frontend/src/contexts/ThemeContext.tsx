import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { ThemeProvider as MuiThemeProvider } from '@mui/material/styles';
import { CssBaseline } from '@mui/material';
import { createAuralisTheme, darkColors, lightColors, glassEffects } from '../theme/themeConfig';

type ThemeMode = 'light' | 'dark';

interface ThemeContextType {
  mode: ThemeMode;
  toggleTheme: () => void;
  setTheme: (mode: ThemeMode) => void;
  colors: typeof darkColors | typeof lightColors;
  glassEffects: typeof glassEffects;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

interface ThemeProviderProps {
  children: ReactNode;
}

export const ThemeProvider: React.FC<ThemeProviderProps> = ({ children }) => {
  // Check localStorage for saved theme preference, default to dark
  const [mode, setMode] = useState<ThemeMode>(() => {
    const savedTheme = localStorage.getItem('auralis-theme');
    return (savedTheme as ThemeMode) || 'dark';
  });

  // Create theme based on current mode
  const theme = createAuralisTheme(mode);
  const colors = mode === 'dark' ? darkColors : lightColors;

  // Save theme preference to localStorage
  useEffect(() => {
    localStorage.setItem('auralis-theme', mode);

    // Update CSS custom properties for components not using MUI
    const root = document.documentElement;
    if (mode === 'dark') {
      root.style.setProperty('--bg-primary', darkColors.background.primary);
      root.style.setProperty('--bg-secondary', darkColors.background.secondary);
      root.style.setProperty('--bg-surface', darkColors.background.surface);
      root.style.setProperty('--bg-glass', darkColors.background.glass);
      root.style.setProperty('--text-primary', darkColors.text.primary);
      root.style.setProperty('--text-secondary', darkColors.text.secondary);
      root.style.setProperty('--glass-border', darkColors.glass.border);
    } else {
      root.style.setProperty('--bg-primary', lightColors.background.primary);
      root.style.setProperty('--bg-secondary', lightColors.background.secondary);
      root.style.setProperty('--bg-surface', lightColors.background.surface);
      root.style.setProperty('--bg-glass', lightColors.background.glass);
      root.style.setProperty('--text-primary', lightColors.text.primary);
      root.style.setProperty('--text-secondary', lightColors.text.secondary);
      root.style.setProperty('--glass-border', lightColors.glass.border);
    }
  }, [mode]);

  const toggleTheme = () => {
    setMode((prevMode) => (prevMode === 'dark' ? 'light' : 'dark'));
  };

  const setTheme = (newMode: ThemeMode) => {
    setMode(newMode);
  };

  const value = {
    mode,
    toggleTheme,
    setTheme,
    colors,
    glassEffects,
  };

  return (
    <ThemeContext.Provider value={value}>
      <MuiThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </MuiThemeProvider>
    </ThemeContext.Provider>
  );
};

// Custom hook to use theme context
export const useTheme = (): ThemeContextType => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};

export default ThemeContext;
