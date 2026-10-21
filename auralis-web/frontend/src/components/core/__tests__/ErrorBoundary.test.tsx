/**
 * ErrorBoundary tests — primitives + Player-fallback regression (#3115).
 *
 * Pre-fix: only a top-level ErrorBoundary in `index.tsx` wrapped the whole
 * `<App />`. If the Player crashed mid-render, the boundary caught it but
 * replaced the entire application with the "Something went wrong" page —
 * library, queue, settings all gone. Post-fix: a dedicated ErrorBoundary
 * around `<Player />` in ComfortableApp.tsx renders a small "Player
 * encountered an error" strip while the rest of the app stays usable.
 *
 * These tests cover the boundary primitive itself and the specific
 * fallback pattern wired into ComfortableApp.
 */

import type { JSX } from 'react';
import { render, screen, fireEvent } from '@/test/test-utils';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ErrorBoundary } from '../ErrorBoundary';


function Boom({ message = 'kaboom' }: { message?: string }): JSX.Element {
  throw new Error(message);
}

function Fine(): JSX.Element {
  return <div>healthy child</div>;
}


describe('ErrorBoundary', () => {
  // Silence the noisy React error log during throw-on-render tests
  let consoleErr: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    consoleErr = vi.spyOn(console, 'error').mockImplementation(() => {});
  });
  afterEach(() => {
    consoleErr.mockRestore();
  });

  it('renders children when nothing throws', () => {
    render(
      <ErrorBoundary>
        <Fine />
      </ErrorBoundary>
    );
    expect(screen.getByText('healthy child')).toBeInTheDocument();
  });

  it('renders default fallback UI when a child throws', () => {
    render(
      <ErrorBoundary>
        <Boom message="kaboom" />
      </ErrorBoundary>
    );
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    expect(screen.getByText('kaboom')).toBeInTheDocument();
    expect(screen.queryByText('healthy child')).not.toBeInTheDocument();
  });

  it('renders a custom fallback when provided (the Player pattern)', () => {
    // This is the exact pattern wired into ComfortableApp for the
    // Player subtree (#3115).
    const fallback = (
      <div data-testid="player-fallback">
        Player encountered an error. Refresh the page to restart playback.
      </div>
    );

    render(
      <ErrorBoundary fallback={fallback}>
        <Boom message="player crash" />
      </ErrorBoundary>
    );

    expect(screen.getByTestId('player-fallback')).toBeInTheDocument();
    // Default fallback's "Something went wrong" must NOT render when a
    // custom fallback is provided.
    expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument();
  });

  it('contains the error to the wrapped subtree — sibling content unaffected (#3115)', () => {
    // The contract that #3115 cares about: when only ONE child subtree
    // throws, the parent's other children continue to render. This is
    // why ComfortableApp wraps only <Player /> in its own boundary.
    render(
      <div>
        <div data-testid="library-sibling">library still here</div>
        <ErrorBoundary
          fallback={<div data-testid="player-fallback">player crashed</div>}
        >
          <Boom />
        </ErrorBoundary>
        <div data-testid="settings-sibling">settings still here</div>
      </div>
    );

    expect(screen.getByTestId('library-sibling')).toBeInTheDocument();
    expect(screen.getByTestId('settings-sibling')).toBeInTheDocument();
    expect(screen.getByTestId('player-fallback')).toBeInTheDocument();
  });

  it('Try Again button clears the error state', () => {
    // We need a child that throws ONCE then renders fine after retry —
    // simulates a transient render glitch.
    let shouldThrow = true;
    function Flaky(): JSX.Element {
      if (shouldThrow) {
        throw new Error('transient');
      }
      return <div>recovered</div>;
    }

    render(
      <ErrorBoundary>
        <Flaky />
      </ErrorBoundary>
    );
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();

    // Simulate the underlying condition resolving, then click Try Again
    shouldThrow = false;
    fireEvent.click(screen.getByText('Try Again'));

    expect(screen.getByText('recovered')).toBeInTheDocument();
    expect(screen.queryByText('Something went wrong')).not.toBeInTheDocument();
  });
});


describe('ComfortableApp Player wrapping (#3115 static check)', () => {
  it('source declares an ErrorBoundary around <Player />', async () => {
    // Static check on the source file: ensures a future refactor doesn't
    // accidentally unwrap the Player. Cheap and catches the intent
    // regression — full integration test would require mocking the
    // entire app's hook surface.
    const fs = await import('fs');
    const path = await import('path');
    const src = fs.readFileSync(
      path.join(process.cwd(), 'src/ComfortableApp.tsx'),
      'utf-8'
    );

    // The Player must be wrapped in an ErrorBoundary with a fallback,
    // not bare like `<Box><Player /></Box>`.
    const playerBlock = src.match(/<ErrorBoundary[\s\S]*?<Player\s*\/>[\s\S]*?<\/ErrorBoundary>/);
    expect(playerBlock).not.toBeNull();
  });
});

describe('ErrorBoundary recovery contract (#5627)', () => {
  let consoleErr: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    consoleErr = vi.spyOn(console, 'error').mockImplementation(() => {});
  });
  afterEach(() => {
    consoleErr.mockRestore();
  });

  it('a functional fallback receives (error, retry) and its retry recovers', () => {
    let shouldThrow = true;
    function Flaky(): JSX.Element {
      if (shouldThrow) {
        throw new Error('transient region crash');
      }
      return <div>region recovered</div>;
    }

    // This is the contract the ComfortableApp region fallbacks use: the
    // old static-node fallbacks made retry unreachable (#5627).
    render(
      <ErrorBoundary
        fallback={(error, retry) => (
          <div>
            <span>{error.message}</span>
            <button onClick={retry}>Try again</button>
          </div>
        )}
      >
        <Flaky />
      </ErrorBoundary>
    );

    expect(screen.getByText('transient region crash')).toBeInTheDocument();
    shouldThrow = false;
    fireEvent.click(screen.getByText('Try again'));
    expect(screen.getByText('region recovered')).toBeInTheDocument();
  });

  it('resetKeys clears the error when a key changes', () => {
    let shouldThrow = true;
    function Flaky(): JSX.Element {
      if (shouldThrow) {
        throw new Error('crash for view A');
      }
      return <div>back on screen</div>;
    }

    const { rerender } = render(
      <ErrorBoundary resetKeys={['songs']} fallback={<div>static region fallback</div>}>
        <Flaky />
      </ErrorBoundary>
    );
    expect(screen.getByText('static region fallback')).toBeInTheDocument();

    // Changing the key (e.g. currentView) resets the boundary: the children
    // re-render — and with the underlying condition resolved, the region
    // recovers without any click (#5627). The reset only fires on a VALUE
    // change: re-rendering with value-equal keys (a new array each render,
    // as JSX inline literals are) must not churn the boundary.
    shouldThrow = false;
    rerender(
      <ErrorBoundary resetKeys={['albums']} fallback={<div>static region fallback</div>}>
        <Flaky />
      </ErrorBoundary>
    );
    expect(screen.getByText('back on screen')).toBeInTheDocument();
  });

  it('resetKeys with unchanged values does not reset a shown error', () => {
    let renderCount = 0;
    function AlwaysBoom(): JSX.Element {
      renderCount += 1;
      throw new Error('still broken');
    }

    const { rerender } = render(
      <ErrorBoundary resetKeys={['songs']} fallback={<div>static region fallback</div>}>
        <AlwaysBoom />
      </ErrorBoundary>
    );
    expect(screen.getByText('static region fallback')).toBeInTheDocument();
    const rendersAfterFirstCrash = renderCount;

    // Value-equal keys: no reset, so the (still-throwing) child is NOT
    // re-rendered — the boundary stays down instead of crash-looping.
    rerender(
      <ErrorBoundary resetKeys={['songs']} fallback={<div>static region fallback</div>}>
        <AlwaysBoom />
      </ErrorBoundary>
    );
    expect(renderCount).toBe(rendersAfterFirstCrash);
    expect(screen.getByText('static region fallback')).toBeInTheDocument();
  });

  it('reports errors to the optional onError callback', () => {
    const onError = vi.fn();
    render(
      <ErrorBoundary onError={onError} fallback={<div>handled</div>}>
        <Boom message="observed crash" />
      </ErrorBoundary>
    );
    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError.mock.calls[0][0]).toBeInstanceOf(Error);
    expect(onError.mock.calls[0][0].message).toBe('observed crash');
  });
});
