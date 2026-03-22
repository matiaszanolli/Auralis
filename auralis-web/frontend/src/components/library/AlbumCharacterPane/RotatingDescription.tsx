import { useState, useEffect, useRef } from 'react';
import { Typography } from '@mui/material';
import { tokens } from '@/design-system';

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

  // Rotate descriptions every 10 seconds when playing
  useEffect(() => {
    if (!isPlaying || descriptions.length === 0) {
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
  }, [isPlaying, descriptions.length]);

  const displayText = isPlaying && descriptions.length > 0
    ? descriptions[currentIndex]
    : staticDescription;

  return (
    <Typography
      variant="body2"
      sx={{
        color: tokens.colors.text.secondary,
        fontSize: tokens.typography.fontSize.sm,
        lineHeight: 1.6,
        opacity: isVisible ? 1 : 0,
        transition: `opacity 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94)`,
        minHeight: '48px', // Prevent layout shift
      }}
    >
      {displayText}
    </Typography>
  );
};
