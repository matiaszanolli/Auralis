/**
 * Exactly one <h1> per library view (#5013)
 *
 * #4958 made AppTopBar's title an <h1>, believing none existed anywhere in
 * the app — a premise that was already stale: ViewContainer.tsx (mounted on
 * every library view) had rendered its own per-view <h1> since before that
 * fix. The two mounted simultaneously, giving screen-reader heading
 * navigation two unrelated level-1 headings on every view.
 *
 * AppTopBar and ViewContainer are siblings under ComfortableApp, not nested,
 * so rendering them together (rather than mocking one out) is what actually
 * proves the fix — a per-component test could pass on each side while still
 * regressing the combination.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import { AppTopBar } from '../AppTopBar';
import { ViewContainer } from '@/components/library/Views/ViewContainer';

describe('single h1 per library view (#5013)', () => {
  it('AppTopBar + ViewContainer together expose exactly one level-one heading', () => {
    render(
      <>
        <AppTopBar
          onSearch={vi.fn()}
          onOpenMobileDrawer={vi.fn()}
          title="Your Music"
          connectionStatus="connected"
          isMobile={false}
        />
        <ViewContainer icon="🎵" title="Songs" subtitle="All tracks">
          <div>content</div>
        </ViewContainer>
      </>
    );

    const headings = screen.getAllByRole('heading', { level: 1 });
    expect(headings).toHaveLength(1);
    expect(headings[0]).toHaveTextContent('Songs');
  });
});
