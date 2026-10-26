import { createTheme, Theme } from '@mui/material/styles';
import { tokens } from '@/design-system';
import { getSemanticTheme, type ThemeMode } from './semanticTheme';
import { createComponents } from './themeComponents';
import { createPalette } from './themePalette';
import { createTypography } from './themeTypography';

// ============================================================================
// CREATE THEME FUNCTION
// ============================================================================
/** MUI spacing unit in px, taken from `tokens.spacing.cluster` (#5384). */
export const MUI_SPACING_UNIT_PX = Number.parseFloat(tokens.spacing.cluster);

export const createAuralisTheme = (mode: ThemeMode): Theme => {
  const isDark = mode === 'dark';
  const semantic = getSemanticTheme(mode);

  return createTheme({
    // Auralis owns one semantic CSS-variable namespace. Keeping MUI's generated
    // variables disabled avoids two competing runtime theme contracts.
    cssVariables: false,
    palette: createPalette(mode, semantic),
    // #5384: MUI's numeric sx spacing (`p: 2`, `mb: 3`) and its components'
    // internal padding resolve through theme.spacing(n) = n x unit. The unit
    // is the 8px `cluster` token rather than MUI's own default, so the two
    // scales are one: spacing(1) = cluster, (2) = group, (4) = section,
    // (0.5) = xs, (1.5) = md. The value is unchanged, so rendering is too.
    spacing: MUI_SPACING_UNIT_PX,
    // #6059: MUI's own defaults happen to equal tokens.breakpoints; derive them
    // so retuning the tokens moves useMediaQuery(down('md')) with the CSS rules.
    breakpoints: {
      values: {
        xs: Number.parseFloat(tokens.breakpoints.xs),
        sm: Number.parseFloat(tokens.breakpoints.sm),
        md: Number.parseFloat(tokens.breakpoints.md),
        lg: Number.parseFloat(tokens.breakpoints.lg),
        xl: Number.parseFloat(tokens.breakpoints.xl),
      },
    },
    typography: createTypography(semantic),
    shape: {
      borderRadius: parseInt(tokens.borderRadius.sm),
    },
    components: createComponents(semantic, isDark),
  });
};

// Use `themeVars` for theme-aware colours; the MUI success/error/warning/info
// palette is built from `getSemanticTheme(mode)`.
