import { tokens } from '@/design-system';

export function TrackInfo({ title, artist }: { title: string; artist: string }) {
  return (
    <div
      style={{
        paddingBottom: tokens.spacing.md,
        borderBottom: `1px solid ${tokens.colors.border.light}`,
      }}
    >
      <div
        style={{
          fontSize: tokens.typography.fontSize.sm,
          fontWeight: tokens.typography.fontWeight.semibold,
          color: tokens.colors.text.primary,
          marginBottom: tokens.spacing.xs,
        }}
      >
        {title}
      </div>
      <div
        style={{
          fontSize: tokens.typography.fontSize.xs,
          color: tokens.colors.text.secondary,
        }}
      >
        {artist}
      </div>
    </div>
  );
}
