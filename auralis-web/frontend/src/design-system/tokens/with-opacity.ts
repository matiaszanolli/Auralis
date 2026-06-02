/**
 * Helper function to get color with opacity.
 * Extracted from the former tokens.ts monolith (#4079).
 */
export function withOpacity(color: string, opacity: number): string {
  // Simple hex to rgba conversion for 6-digit hex colors
  if (color.startsWith('#') && color.length === 7) {
    const r = parseInt(color.slice(1, 3), 16);
    const g = parseInt(color.slice(3, 5), 16);
    const b = parseInt(color.slice(5, 7), 16);
    return `rgba(${r}, ${g}, ${b}, ${opacity})`;
  }
  return color;
}
