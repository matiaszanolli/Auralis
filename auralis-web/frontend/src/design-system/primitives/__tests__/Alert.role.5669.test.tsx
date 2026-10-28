/**
 * Alert's live-region role follows its urgency (#5669)
 *
 * Every Alert was role="alert" (assertive), so the info echo of each keyboard shortcut
 * ("Playing", "Next track") interrupted a screen reader like an error would. Warnings and errors
 * stay assertive; info and success are polite status text.
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Alert } from '../Alert';
import { ToastItem } from '@/components/shared/Toast/ToastItem';

describe('Alert role (#5669)', () => {
  it.each(['error', 'warning'] as const)('%s interrupts (role=alert)', (variant) => {
    render(<Alert variant={variant}>Something is wrong</Alert>);

    expect(screen.getByRole('alert')).toHaveTextContent('Something is wrong');
  });

  it.each(['info', 'success'] as const)('%s is polite (role=status)', (variant) => {
    render(<Alert variant={variant}>Next track</Alert>);

    expect(screen.getByRole('status')).toHaveTextContent('Next track');
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('defaults to a polite info alert', () => {
    render(<Alert>FYI</Alert>);

    expect(screen.getByRole('status')).toHaveTextContent('FYI');
  });
});

describe('toast role (#5669)', () => {
  const toast = (type: 'info' | 'success' | 'warning' | 'error') => ({ id: 't', type, message: `${type} toast`, duration: 5000 });

  it('a shortcut echo (info toast) does not interrupt', () => {
    render(<ToastItem toast={toast('info')} index={0} onClose={() => {}} />);

    expect(screen.getByRole('status')).toHaveTextContent('info toast');
  });

  it('an error toast does', () => {
    render(<ToastItem toast={toast('error')} index={0} onClose={() => {}} />);

    expect(screen.getByRole('alert')).toHaveTextContent('error toast');
  });
});
