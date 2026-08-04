import { render, screen } from '@/test/test-utils';
import { describe, expect, it, vi } from 'vitest';
import { AppTopBarLeftSection } from '../AppTopBarLeftSection';

describe('AppTopBarLeftSection', () => {
  it('renders the app title as the sole level-one heading (#4958)', () => {
    render(
      <AppTopBarLeftSection
        showMobileMenu={false}
        title="Your Music"
        onOpenMobileDrawer={vi.fn()}
      />
    );

    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Your Music');
  });

  it('keeps the level-one title available to screen readers on mobile', () => {
    render(
      <AppTopBarLeftSection
        showMobileMenu
        title="Your Music"
        onOpenMobileDrawer={vi.fn()}
      />
    );

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Your Music');
    expect(screen.getByRole('button', { name: 'Open navigation menu' })).toBeInTheDocument();
  });
});
