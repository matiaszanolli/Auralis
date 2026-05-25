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
