import { tokens } from '@/design-system/tokens';

export type ThemeMode = 'light' | 'dark';

/**
 * Runtime theme contract for application chrome and shared surfaces.
 *
 * Component code should consume `themeVars` instead of choosing a palette
 * level directly. The resolved values live on `document.documentElement`, so
 * MUI, Emotion, and plain DOM controls all react to the same theme change.
 */
export interface SemanticTheme {
  colorScheme: ThemeMode;
  canvas: string;
  surfacePrimary: string;
  surfaceSecondary: string;
  surfaceRaised: string;
  surfaceOverlay: string;
  surfaceTranslucent: string;
  /** Popover/menu surface — theme-aware so menu text keeps its contrast (#5641). */
  menuSurface: string;
  /** Glass fill for prominent overlays (modals). */
  glassFillStrong: string;
  /** Glass fill for overlays at rest (track-card duration badge). */
  glassFill: string;
  /** Glass fill for hovered overlays — runs more opaque than glassFill. */
  glassFillHover: string;
  /** Two-state switch thumb, off state. */
  switchThumb: string;
  /** Two-state switch track, off state. */
  switchTrack: string;
  textPrimary: string;
  textStrong: string;
  textSecondary: string;
  textMuted: string;
  textDisabled: string;
  borderSubtle: string;
  borderDefault: string;
  borderStrong: string;
  accent: string;
  accentHover: string;
  accentSoft: string;
  onAccent: string;
  focusRing: string;
  success: string;
  warning: string;
  error: string;
  info: string;
  errorSoft: string;
  onError: string;
  backdrop: string;
  shadowRaised: string;
  shadowOverlay: string;
}

const darkSemanticTheme: SemanticTheme = {
  colorScheme: 'dark',
  canvas: tokens.colors.bg.level0,
  surfacePrimary: tokens.colors.bg.level1,
  surfaceSecondary: tokens.colors.bg.level2,
  surfaceRaised: tokens.colors.bg.level3,
  surfaceOverlay: tokens.colors.bg.level4,
  surfaceTranslucent: tokens.glass.starfield.strong,
  // #5641: these are the values the five glass/gradient surfaces already used
  // in dark mode, bound to semantic names so light mode can resolve its own.
  menuSurface: tokens.gradients.darkSubtle,
  glassFillStrong: tokens.glass.strong.background,
  glassFill: tokens.glass.starfield.medium,
  glassFillHover: tokens.glass.starfield.sharp,
  switchThumb: tokens.colors.opacityScale.white.veryStrong,
  switchTrack: tokens.colors.opacityScale.white.lighter,
  textPrimary: tokens.colors.text.primary,
  textStrong: tokens.colors.text.primaryFull,
  textSecondary: tokens.colors.text.secondary,
  textMuted: tokens.colors.text.metadata,
  textDisabled: tokens.colors.text.disabled,
  borderSubtle: tokens.colors.opacityScale.white.faint,
  borderDefault: tokens.colors.opacityScale.white.light,
  borderStrong: tokens.colors.border.medium,
  accent: tokens.colors.accent.primary,
  accentHover: tokens.colors.accent.primaryLight,
  accentSoft: tokens.colors.opacityScale.accent.light,
  onAccent: tokens.colors.text.primaryFull,
  focusRing: tokens.colors.opacityScale.accent.strong,
  success: tokens.colors.semantic.success,
  warning: tokens.colors.semantic.warning,
  error: tokens.colors.semantic.error,
  info: tokens.colors.semantic.info,
  errorSoft: tokens.colors.utility.errorBg,
  onError: tokens.colors.text.primaryFull,
  backdrop: tokens.colors.opacityScale.dark.nearOpaque,
  shadowRaised: tokens.shadows.lg,
  shadowOverlay: tokens.shadows['2xl'],
};

const lightSemanticTheme: SemanticTheme = {
  colorScheme: 'light',
  canvas: tokens.colors.lightMode.background.primary,
  surfacePrimary: tokens.colors.lightMode.background.secondary,
  surfaceSecondary: tokens.colors.lightMode.background.surface,
  surfaceRaised: tokens.colors.lightMode.background.secondary,
  surfaceOverlay: tokens.colors.lightMode.background.hover,
  surfaceTranslucent: tokens.colors.lightMode.background.glass,
  // #5641: light-mode fills for the roles the glass/gradient surfaces used to
  // take from fixed dark-only tokens. White-alphas are the dark ink's partner
  // — the same pair the dark palette forms with its white-alphas — so every
  // fill keeps >= 4.5:1 against the text that sits on it (>= 3:1 for the
  // switch, per the acceptance criteria in #5641).
  menuSurface: tokens.colors.lightMode.background.secondary,
  glassFillStrong: tokens.glass.strong.backgroundLight,
  glassFill: tokens.glass.medium.backgroundLight,
  glassFillHover: tokens.glass.strong.backgroundLight,
  switchThumb: tokens.colors.opacityScale.dark.nearOpaque,
  switchTrack: tokens.colors.opacityScale.dark.lighter,
  textPrimary: tokens.colors.lightMode.text.primary,
  textStrong: tokens.colors.lightMode.text.primary,
  textSecondary: tokens.colors.lightMode.text.secondary,
  textMuted: tokens.colors.lightMode.text.secondary,
  textDisabled: tokens.colors.lightMode.text.disabled,
  borderSubtle: tokens.colors.opacityScale.dark.veryLight,
  borderDefault: tokens.colors.opacityScale.dark.light,
  borderStrong: tokens.colors.opacityScale.accent.standard,
  accent: tokens.colors.accent.primary,
  accentHover: tokens.colors.accent.primaryDark,
  accentSoft: tokens.colors.opacityScale.accent.veryLight,
  onAccent: tokens.colors.text.primaryFull,
  focusRing: tokens.colors.opacityScale.accent.strong,
  success: tokens.colors.lightMode.accent.success,
  warning: tokens.colors.lightMode.accent.warning,
  error: tokens.colors.lightMode.accent.error,
  info: tokens.colors.lightMode.accent.info,
  errorSoft: tokens.colors.utility.errorBg,
  onError: tokens.colors.text.primaryFull,
  backdrop: tokens.colors.opacityScale.dark.veryStrong,
  shadowRaised: tokens.shadows.md,
  shadowOverlay: tokens.shadows.xl,
};

export const semanticThemes: Record<ThemeMode, SemanticTheme> = {
  dark: darkSemanticTheme,
  light: lightSemanticTheme,
};

export const getSemanticTheme = (mode: ThemeMode): SemanticTheme => semanticThemes[mode];

export const themeVars = {
  canvas: 'var(--app-canvas)',
  surfacePrimary: 'var(--app-surface-primary)',
  surfaceSecondary: 'var(--app-surface-secondary)',
  surfaceRaised: 'var(--app-surface-raised)',
  surfaceOverlay: 'var(--app-surface-overlay)',
  surfaceTranslucent: 'var(--app-surface-translucent)',
  menuSurface: 'var(--app-menu-surface)',
  glassFillStrong: 'var(--app-glass-fill-strong)',
  glassFill: 'var(--app-glass-fill)',
  glassFillHover: 'var(--app-glass-fill-hover)',
  switchThumb: 'var(--app-switch-thumb)',
  switchTrack: 'var(--app-switch-track)',
  textPrimary: 'var(--app-text-primary)',
  textStrong: 'var(--app-text-strong)',
  textSecondary: 'var(--app-text-secondary)',
  textMuted: 'var(--app-text-muted)',
  textDisabled: 'var(--app-text-disabled)',
  borderSubtle: 'var(--app-border-subtle)',
  borderDefault: 'var(--app-border-default)',
  borderStrong: 'var(--app-border-strong)',
  accent: 'var(--app-accent)',
  accentHover: 'var(--app-accent-hover)',
  accentSoft: 'var(--app-accent-soft)',
  onAccent: 'var(--app-on-accent)',
  focusRing: 'var(--app-focus-ring)',
  success: 'var(--app-success)',
  warning: 'var(--app-warning)',
  error: 'var(--app-error)',
  info: 'var(--app-info)',
  errorSoft: 'var(--app-error-soft)',
  onError: 'var(--app-on-error)',
  backdrop: 'var(--app-backdrop)',
  shadowRaised: 'var(--app-shadow-raised)',
  shadowOverlay: 'var(--app-shadow-overlay)',
} as const;

export const getSemanticCssVariables = (mode: ThemeMode): Record<string, string> => {
  const theme = getSemanticTheme(mode);

  return {
    '--app-canvas': theme.canvas,
    '--app-surface-primary': theme.surfacePrimary,
    '--app-surface-secondary': theme.surfaceSecondary,
    '--app-surface-raised': theme.surfaceRaised,
    '--app-surface-overlay': theme.surfaceOverlay,
    '--app-surface-translucent': theme.surfaceTranslucent,
    '--app-menu-surface': theme.menuSurface,
    '--app-glass-fill-strong': theme.glassFillStrong,
    '--app-glass-fill': theme.glassFill,
    '--app-glass-fill-hover': theme.glassFillHover,
    '--app-switch-thumb': theme.switchThumb,
    '--app-switch-track': theme.switchTrack,
    '--app-text-primary': theme.textPrimary,
    '--app-text-strong': theme.textStrong,
    '--app-text-secondary': theme.textSecondary,
    '--app-text-muted': theme.textMuted,
    '--app-text-disabled': theme.textDisabled,
    '--app-border-subtle': theme.borderSubtle,
    '--app-border-default': theme.borderDefault,
    '--app-border-strong': theme.borderStrong,
    '--app-accent': theme.accent,
    '--app-accent-hover': theme.accentHover,
    '--app-accent-soft': theme.accentSoft,
    '--app-on-accent': theme.onAccent,
    '--app-focus-ring': theme.focusRing,
    '--app-success': theme.success,
    '--app-warning': theme.warning,
    '--app-error': theme.error,
    '--app-info': theme.info,
    '--app-error-soft': theme.errorSoft,
    '--app-on-error': theme.onError,
    '--app-backdrop': theme.backdrop,
    '--app-shadow-raised': theme.shadowRaised,
    '--app-shadow-overlay': theme.shadowOverlay,
  };
};
