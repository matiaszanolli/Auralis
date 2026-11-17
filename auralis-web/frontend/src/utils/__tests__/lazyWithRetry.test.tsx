/**
 * lazyWithRetry recovers from a failed chunk load (#6035).
 */

import { Suspense } from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ErrorBoundary } from '@/components/core/ErrorBoundary';
import { lazyWithRetry } from '../lazyWithRetry';

const Loaded = () => <div>loaded view</div>;

function flaky(failures: number) {
  let calls = 0;
  const importer = vi.fn(async () => {
    calls += 1;
    if (calls <= failures) throw new Error(`chunk load failed (${calls})`);
    return { default: Loaded };
  });
  return importer;
}

const withBoundary = (View: React.ComponentType) => (
  <ErrorBoundary
    fallback={(error, retry) => (
      <div>
        <p>failed: {error.message}</p>
        <button onClick={retry}>Try again</button>
      </div>
    )}
  >
    <Suspense fallback={<p>loading</p>}>
      <View />
    </Suspense>
  </ErrorBoundary>
);

describe('lazyWithRetry', () => {
  it('retries a transient failure and renders the component', async () => {
    const importer = flaky(1);
    const View = lazyWithRetry(importer, [1, 1]);

    render(withBoundary(View));

    expect(await screen.findByText('loaded view')).toBeInTheDocument();
    expect(importer).toHaveBeenCalledTimes(2);
  });

  it('shows the boundary after the retries run out, and its Try again performs a fresh import', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const importer = flaky(3); // initial + two retries fail; the next import succeeds
    const View = lazyWithRetry(importer, [1, 1]);

    render(withBoundary(View));

    expect(await screen.findByText(/failed: chunk load failed/)).toBeInTheDocument();
    expect(importer).toHaveBeenCalledTimes(3);

    await userEvent.click(screen.getByRole('button', { name: 'Try again' }));

    await waitFor(() => expect(screen.getByText('loaded view')).toBeInTheDocument());
    expect(importer).toHaveBeenCalledTimes(4);
    vi.restoreAllMocks();
  });

  it('does not keep re-importing a chunk that stays dead', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const importer = flaky(Number.POSITIVE_INFINITY);
    const View = lazyWithRetry(importer, [1, 1]);

    render(withBoundary(View));
    expect(await screen.findByText(/failed: chunk load failed/)).toBeInTheDocument();
    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(importer).toHaveBeenCalledTimes(3);
    vi.restoreAllMocks();
  });

  it('a plain React.lazy replays its stored failure on retry (why this wrapper exists)', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    const { lazy } = await import('react');
    const importer = flaky(1);
    const Plain = lazy(importer);

    render(withBoundary(Plain));
    expect(await screen.findByText(/failed:/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }));

    expect(await screen.findByText(/failed:/)).toBeInTheDocument();
    expect(importer).toHaveBeenCalledTimes(1);
    vi.restoreAllMocks();
  });
});
