/**
 * FingerprintCoverageCard — issue #4865
 *
 * The library-wide fingerprint endpoints had built `progress_percent`, a
 * display-ready `status` line and `estimated_remaining_seconds` with nothing
 * rendering any of it. This card is that surface.
 *
 * Note what it is NOT: `hooks/enhancement/useFingerprintStatus` already reports
 * per-track `fingerprint_progress` during enhanced playback. That is a different
 * thing on a different clock — one track versus the whole library — which is why
 * this does not reuse it.
 */

import { render, screen } from '@/test/test-utils';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import userEvent from '@testing-library/user-event';
import { FingerprintCoverageCard, formatRemaining } from '../FingerprintCoverageCard';

const mockAnalyseRemaining = vi.fn();
const mockUseFingerprintCoverage = vi.fn();

vi.mock('@/hooks/library/useFingerprintCoverage', () => ({
  useFingerprintCoverage: (...args: unknown[]) => mockUseFingerprintCoverage(...args),
}));

const coverage = (overrides: Record<string, unknown> = {}) => ({
  totalTracks: 1203,
  fingerprintedTracks: 847,
  pendingTracks: 356,
  progressPercent: 70.4,
  status: '847 of 1203 tracks analysed',
  estimatedRemainingSeconds: 10680,
  ...overrides,
});

const hookState = (overrides: Record<string, unknown> = {}) => ({
  coverage: coverage(),
  loading: false,
  error: null,
  enqueueing: false,
  analyseRemaining: mockAnalyseRemaining,
  refresh: vi.fn(),
  ...overrides,
});

beforeEach(() => {
  vi.clearAllMocks();
  mockUseFingerprintCoverage.mockReturnValue(hookState());
});

describe('formatRemaining', () => {
  it('says nothing when there is nothing left', () => {
    expect(formatRemaining(0)).toBe('');
    expect(formatRemaining(-1)).toBe('');
  });

  it('rounds to a human unit rather than printing seconds', () => {
    expect(formatRemaining(30)).toBe('under a minute remaining');
    expect(formatRemaining(60)).toBe('about 1 minute remaining');
    expect(formatRemaining(600)).toBe('about 10 minutes remaining');
    expect(formatRemaining(3600)).toBe('about 1 hour remaining');
    expect(formatRemaining(10680)).toBe('about 3 hours remaining');
  });
});

describe('rendering coverage', () => {
  it('shows the analysed count against the library total', () => {
    render(<FingerprintCoverageCard />);

    expect(screen.getByText('847 / 1203')).toBeInTheDocument();
  });

  it("renders the backend's own status line", () => {
    render(<FingerprintCoverageCard />);

    // The wording lives in one place — the backend builds it.
    expect(screen.getByText(/847 of 1203 tracks analysed/)).toBeInTheDocument();
  });

  it('appends the ETA while work is outstanding', () => {
    render(<FingerprintCoverageCard />);

    expect(screen.getByText(/about 3 hours remaining/)).toBeInTheDocument();
  });

  it('exposes progress to assistive tech', () => {
    render(<FingerprintCoverageCard />);

    const bar = screen.getByLabelText('Library analysis progress');
    expect(bar).toHaveAttribute('aria-valuenow', '70.4');
  });

  it('renders nothing before the first response', () => {
    mockUseFingerprintCoverage.mockReturnValue(hookState({ coverage: null }));

    const { container } = render(<FingerprintCoverageCard />);

    // No empty card flashing on dialog open.
    expect(container).toBeEmptyDOMElement();
  });
});

describe('a fully-analysed library', () => {
  beforeEach(() => {
    mockUseFingerprintCoverage.mockReturnValue(
      hookState({
        coverage: coverage({
          fingerprintedTracks: 1203,
          pendingTracks: 0,
          progressPercent: 100,
          status: 'All 1203 tracks analysed',
          estimatedRemainingSeconds: 0,
        }),
      })
    );
  });

  it('offers no action', () => {
    render(<FingerprintCoverageCard />);

    expect(screen.queryByRole('button', { name: /analyse remaining/i })).not.toBeInTheDocument();
  });

  it('shows no ETA', () => {
    render(<FingerprintCoverageCard />);

    expect(screen.queryByText(/remaining/)).not.toBeInTheDocument();
  });
});

describe('queueing the remainder', () => {
  it('calls the hook when the button is pressed', async () => {
    const user = userEvent.setup();
    render(<FingerprintCoverageCard />);

    await user.click(screen.getByRole('button', { name: /analyse remaining/i }));

    expect(mockAnalyseRemaining).toHaveBeenCalledTimes(1);
  });

  it('disables the button and reports progress while enqueueing', () => {
    mockUseFingerprintCoverage.mockReturnValue(hookState({ enqueueing: true }));

    render(<FingerprintCoverageCard />);

    expect(screen.getByRole('button', { name: /queueing/i })).toBeDisabled();
  });
});

describe('failure', () => {
  it('surfaces the error instead of a stale bar', () => {
    mockUseFingerprintCoverage.mockReturnValue(
      hookState({ coverage: null, error: 'Library database is locked' })
    );

    render(<FingerprintCoverageCard />);

    expect(screen.getByText('Library database is locked')).toBeInTheDocument();
  });
});

describe('enabled flag', () => {
  it('forwards it to the hook so a hidden tab does not poll', () => {
    render(<FingerprintCoverageCard enabled={false} />);

    expect(mockUseFingerprintCoverage).toHaveBeenCalledWith(false);
  });
});
