import { useMemo } from 'react';

interface ThemeToggleSizes {
  iconSize: number;
  buttonSize: number;
}

export const useThemeToggleSize = (size: 'small' | 'medium' | 'large'): ThemeToggleSizes => {
  return useMemo(() => {
    return {
      iconSize: size === 'small' ? 20 : size === 'large' ? 28 : 24,
      buttonSize: size === 'small' ? 36 : size === 'large' ? 52 : 44,
    };
  }, [size]);
};
