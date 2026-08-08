import { render, screen } from '@/test/test-utils';
import { describe, expect, it, vi } from 'vitest';
import { AppTopBarLeftSection } from '../AppTopBarLeftSection';

describe('AppTopBarLeftSection', () => {
  // #4958 made the top-bar title an <h1>, believing none existed anywhere in
  // the app. ViewContainer.tsx (every library view) had rendered its own
  // per-view <h1> since before that fix, so the two mounted simultaneously —
  // #5013. ViewContainer's is the sole <h1>; this title is not a heading.
  it('renders the app title as visible text, not a heading (#5013)', () => {
    render(
      <AppTopBarLeftSection
        showMobileMenu={false}
        title="Your Music"
        onOpenMobileDrawer={vi.fn()}
      />
    );

    expect(screen.queryByRole('heading', { level: 1 })).not.toBeInTheDocument();
    expect(screen.getByText('Your Music')).toBeInTheDocument();
  });

  it('keeps the title available to screen readers on mobile', () => {
    render(
      <AppTopBarLeftSection
        showMobileMenu
        title="Your Music"
        onOpenMobileDrawer={vi.fn()}
      />
    );

    expect(screen.getByText('Your Music')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Open navigation menu' })).toBeInTheDocument();
  });
});
