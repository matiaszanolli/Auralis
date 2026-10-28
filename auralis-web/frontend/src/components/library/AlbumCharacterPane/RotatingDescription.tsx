import { useState, useEffect, useRef } from 'react';
import { Typography } from '@mui/material';
import { tokens } from '@/design-system';
import { themeVars } from '@/theme/semanticTheme';
import { usePrefersReducedMotion } from '@/hooks/shared/usePrefersReducedMotion';

interface RotatingDescriptionProps {
  descriptions: string[];
  staticDescription: string;
  isPlaying: boolean;
}

export const RotatingDescription = ({
  descriptions,
  staticDescription,
  isPlaying,
}: RotatingDescriptionProps) => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [isVisible, setIsVisible] = useState(true);
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>();
  const reducedMotion = usePrefersReducedMotion();

  // Rotate descriptions every 10 seconds when playing. Content that changes by itself for longer
  // than five seconds needs a way to stop (WCAG 2.2.2); reduced motion is that opt-out (#5676).
  useEffect(() => {
    if (!isPlaying || descriptions.length === 0 || reducedMotion) {
      setCurrentIndex(0);
      return;
    }

    const interval = setInterval(() => {
      setIsVisible(false);
      // Store timeout handle so cleanup can cancel it (#2770)
      timeoutRef.current = setTimeout(() => {
        setCurrentIndex((prev) => (prev + 1) % descriptions.length);
        setIsVisible(true);
      }, 400); // Crossfade duration
    }, 10000); // 10 seconds between rotations

    return () => {
      clearInterval(interval);
      clearTimeout(timeoutRef.current);
    };
  }, [isPlaying, descriptions.length, reducedMotion]);

  const displayText = isPlaying && descriptions.length > 0
    ? descriptions[currentIndex]
    : staticDescription;

  return (
    <Typography
      variant="body2"
      sx={{
        color: themeVars.textSecondary,
        fontSize: tokens.typography.fontSize.sm,
        lineHeight: 1.6,
        opacity: isVisible ? 1 : 0,
        transition: tokens.transitions.opacity,
        minHeight: '48px', // Prevent layout shift
      }}
    >
      {displayText}
    </Typography>
  );
};
