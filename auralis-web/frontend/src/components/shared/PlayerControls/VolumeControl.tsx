import { tokens } from '@/design-system';

export function VolumeControl({
  volume,
  isMuted,
  onVolumeChange,
  onToggleMute,
}: {
  volume: number;
  isMuted: boolean;
  onVolumeChange: (value: number) => void;
  onToggleMute: () => void;
}) {
  const displayVolume = isMuted ? 0 : volume;

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: tokens.spacing.md,
        paddingTop: tokens.spacing.md,
        borderTop: `1px solid ${tokens.colors.border.light}`,
      }}
    >
      <button
        onClick={onToggleMute}
        aria-label={isMuted ? 'Unmute' : 'Mute'}
        style={{
          width: '32px',
          height: '32px',
          border: 'none',
          borderRadius: '6px',
          background: isMuted ? tokens.colors.semantic.warning : tokens.colors.bg.tertiary,
          color: tokens.colors.text.primary,
          cursor: 'pointer',
          fontSize: tokens.typography.fontSize.md,
          opacity: 0.8,
          transition: 'all 0.2s',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {isMuted ? '🔇' : '🔊'}
      </button>
      <input
        type="range"
        min="0"
        max="100"
        value={displayVolume}
        onChange={(e) => onVolumeChange(parseInt(e.target.value))}
        aria-label="Volume"
        style={{
          flex: 1,
          cursor: 'pointer',
          height: '6px',
          borderRadius: '3px',
          appearance: 'none',
          WebkitAppearance: 'none',
          background: `linear-gradient(to right, ${tokens.colors.accent.primary} 0%, ${tokens.colors.accent.primary} ${displayVolume}%, ${tokens.colors.bg.elevated} ${displayVolume}%, ${tokens.colors.bg.elevated} 100%)`,
        }}
      />
      <div
        style={{
          fontSize: tokens.typography.fontSize.sm,
          color: tokens.colors.text.tertiary,
          minWidth: '35px',
          textAlign: 'right',
        }}
      >
        {displayVolume}%
      </div>
    </div>
  );
}
