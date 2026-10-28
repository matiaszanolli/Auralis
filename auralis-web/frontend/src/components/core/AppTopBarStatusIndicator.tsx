import { StatusIndicator, VisuallyHidden } from './AppTopBar.styles';
import { connectionStatusLabel, type ConnectionStatusType } from './useConnectionStatus';

interface AppTopBarStatusIndicatorProps {
  color: string;
  status: ConnectionStatusType;
}

/**
 * AppTopBarStatusIndicator - Connection status dot with glow effect
 *
 * The coloured dot is decorative; the state itself is a visually hidden text
 * label inside a polite live region, so a change (connected -> reconnecting ->
 * lost) is announced and colour is not the only channel (#6025). The region is
 * mounted with its initial text, which screen readers do not announce.
 */
export const AppTopBarStatusIndicator = ({
  color,
  status,
}: AppTopBarStatusIndicatorProps) => {
  const label = connectionStatusLabel(status);
  return (
    <span
      role="status"
      aria-live="polite"
      title={label}
      data-testid="connection-status"
      style={{ display: 'inline-flex', alignItems: 'center' }}
    >
      <StatusIndicator color={color} aria-hidden="true" />
      <VisuallyHidden>{label}</VisuallyHidden>
    </span>
  );
};

export default AppTopBarStatusIndicator;
