import { tokens } from '@/design-system';

export function TransportControls({
  isPlaying,
  isLoading,
  onPlayPause,
  onNext,
  onPrevious,
}: {
  isPlaying: boolean;
  isLoading: boolean;
  onPlayPause: () => void;
  onNext: () => void;
  onPrevious: () => void;
}) {
  const smallButtonStyle = {
    width: '44px',
    height: '44px',
    border: 'none',
    borderRadius: '50%',
    background: tokens.colors.bg.tertiary,
    color: tokens.colors.text.primary,
    fontSize: tokens.typography.fontSize.lg,
    cursor: isLoading ? 'not-allowed' : 'pointer',
    opacity: isLoading ? 0.5 : 0.8,
    transition: 'all 0.2s',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  } as const;

  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: tokens.spacing.md }}>
      <button onClick={onPrevious} disabled={isLoading} aria-label="Previous" style={smallButtonStyle}>
        ⏮️
      </button>
      <button
        onClick={onPlayPause}
        disabled={isLoading}
        aria-label={isPlaying ? 'Pause' : 'Play'}
        style={{
          width: '64px',
          height: '64px',
          border: `2px solid ${tokens.colors.accent.primary}`,
          borderRadius: '50%',
          background: tokens.colors.accent.primary,
          color: tokens.colors.text.primary,
          fontSize: tokens.typography.fontSize.xl,
          fontWeight: tokens.typography.fontWeight.bold,
          cursor: isLoading ? 'not-allowed' : 'pointer',
          opacity: isLoading ? 0.5 : 0.9,
          transition: 'all 0.2s',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {isLoading ? '⏳' : isPlaying ? '⏸️' : '▶️'}
      </button>
      <button onClick={onNext} disabled={isLoading} aria-label="Next" style={smallButtonStyle}>
        ⏭️
      </button>
    </div>
  );
}
