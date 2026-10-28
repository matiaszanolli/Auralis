/**
 * The connection indicator carries its state as text, not colour alone (#6025).
 *
 * It used to be a 12px coloured dot with no text, role or live region, so
 * green/amber/red was the only channel (WCAG 1.4.1, 4.1.3).
 */

import { describe, expect, it } from 'vitest';
import { render, screen } from '@/test/test-utils';
import AppTopBarStatusIndicator from '../AppTopBarStatusIndicator';
import { connectionStatusLabel, type ConnectionStatusType } from '../useConnectionStatus';

describe('connectionStatusLabel', () => {
  it('names every state, keeping disconnected and error distinct', () => {
    const labels = (['connected', 'connecting', 'disconnected', 'error'] as ConnectionStatusType[])
      .map(connectionStatusLabel);
    expect(labels).toEqual(['Connected', 'Connecting', 'Disconnected', 'Connection lost']);
    expect(new Set(labels).size).toBe(4);
  });
});

describe('AppTopBarStatusIndicator', () => {
  it('is a polite status region with the state as text', () => {
    render(<AppTopBarStatusIndicator color="#0f0" status="connected" />);

    const region = screen.getByRole('status');
    expect(region).toHaveAttribute('aria-live', 'polite');
    expect(region).toHaveTextContent('Connected');
  });

  it('updates the text when the state changes, so the change is announced', () => {
    const { rerender } = render(<AppTopBarStatusIndicator color="#0f0" status="connected" />);

    rerender(<AppTopBarStatusIndicator color="#f00" status="error" />);

    expect(screen.getByRole('status')).toHaveTextContent('Connection lost');
  });

  it('hides the decorative dot from assistive tech and offers the text as a tooltip', () => {
    const { container } = render(<AppTopBarStatusIndicator color="#fa0" status="connecting" />);

    expect(container.querySelector('[aria-hidden="true"]')).not.toBeNull();
    expect(screen.getByRole('status')).toHaveAttribute('title', 'Connecting');
  });
});
