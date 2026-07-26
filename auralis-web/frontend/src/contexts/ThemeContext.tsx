import { createContext, useCallback, useContext, useMemo, useState, useEffect, ReactNode } from 'react';
import { ThemeProvider as MuiThemeProvider } from '@mui/material/styles';
import { CssBaseline } from '@mui/material';
import { createAuralisTheme } from '@/theme/themeConfig';
import {
  getSemanticCssVariables,
  type ThemeMode,
} from '@/theme/semanticTheme';

/**
 * Theme context.
 *
 * #4584: `colors` and `glassEffects` used to be surfaced here as a second,
 * parallel colour API alongside `themeVars`. They are gone — `themeVars` (and
 * the `--app-*` CSS variables this provider writes) is the only theme-aware
 * colour source. The raw `tokens.colors.*` primitives remain dark-only build
 * blocks and are not for direct component use.
 */
interface ThemeContextType {
  mode: ThemeMode;
  toggleTheme: () => void;
  setTheme: (mode: ThemeMode) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

interface ThemeProviderProps {
  children: ReactNode;
}

export const ThemeProvider = ({ children }: ThemeProviderProps) => {
  // Check localStorage for saved theme preference, default to dark
  const [mode, setMode] = useState<ThemeMode>(() => {
    const savedTheme = localStorage.getItem('auralis-theme');
    const VALID_THEMES: ThemeMode[] = ['light', 'dark'];
    return VALID_THEMES.includes(savedTheme as ThemeMode) ? (savedTheme as ThemeMode) : 'dark';
  });

  // Theme creation is relatively expensive. Rebuild only when mode changes.
  const theme = useMemo(() => createAuralisTheme(mode), [mode]);

  // Save theme preference to localStorage
  useEffect(() => {
    localStorage.setItem('auralis-theme', mode);

    // Keep MUI, Emotion, and plain DOM controls on one semantic color contract.
    const root = document.documentElement;
    root.dataset.theme = mode;
    root.style.colorScheme = mode;

    Object.entries(getSemanticCssVariables(mode)).forEach(([property, value]) => {
      root.style.setProperty(property, value);
    });
  }, [mode]);

  const toggleTheme = useCallback(() => {
    setMode((prevMode) => (prevMode === 'dark' ? 'light' : 'dark'));
  }, []);

  const setTheme = useCallback((newMode: ThemeMode) => {
    setMode(newMode);
  }, []);

  const value = useMemo(() => ({
    mode,
    toggleTheme,
    setTheme,
  }), [mode, toggleTheme, setTheme]);

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
