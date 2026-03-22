import { useState } from 'react';
import { tokens } from '@/design-system';
import { formatDuration } from '@/utils/timeFormat';

export function ProgressBar({
  currentTime,
  duration,
  onSeek,
}: {
  currentTime: number;
  duration: number;
  onSeek: (position: number) => void;
}) {
  const [isSeeking, setIsSeeking] = useState(false);
  const seekPercentage = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: tokens.spacing.sm }}>
      <div
        role="slider"
        aria-label="Seek"
        aria-valuenow={Math.round(currentTime)}
        aria-valuemin={0}
        aria-valuemax={Math.round(duration)}
        tabIndex={0}
        style={{
          height: '6px',
          background: tokens.colors.bg.elevated,
          borderRadius: '3px',
          overflow: 'hidden',
          cursor: 'pointer',
        }}
        onClick={(e) => {
          const rect = (e.target as HTMLElement).getBoundingClientRect();
          const percentage = (e.clientX - rect.left) / rect.width;
          onSeek(percentage * duration);
        }}
        onMouseDown={() => setIsSeeking(true)}
        onMouseUp={() => setIsSeeking(false)}
        onKeyDown={(e) => {
          const step = 5;
          if (e.key === 'ArrowRight' || e.key === 'ArrowUp') {
            e.preventDefault();
            onSeek(Math.min(currentTime + step, duration));
          } else if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') {
            e.preventDefault();
            onSeek(Math.max(currentTime - step, 0));
          } else if (e.key === 'Home') {
            e.preventDefault();
            onSeek(0);
          } else if (e.key === 'End') {
            e.preventDefault();
            onSeek(duration);
          }
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${seekPercentage}%`,
            background: tokens.colors.accent.primary,
            transition: isSeeking ? 'none' : 'width 0.1s linear',
          }}
        />
      </div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: tokens.typography.fontSize.xs,
          color: tokens.colors.text.tertiary,
        }}
      >
        <span>{formatDuration(currentTime)}</span>
        <span>{formatDuration(duration)}</span>
      </div>
    </div>
  );
}
