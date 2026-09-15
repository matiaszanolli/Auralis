/**
 * ScanStatusCard — failed/skipped file visibility (#5466)
 *
 * Settings "Scan Now" (and every auto-scan, since this card is the same
 * live status surface for both) never rendered failed/skipped counts even
 * though useScanProgress already captured them from the scan_complete WS
 * message -- the closed fix for this class of bug (#4841) covered only the
 * separate Library-view "Scan Folder" flow (useLibraryScan.ts).
 */

import { render, screen } from '@/test/test-utils';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { ScanStatusCard } from '../ScanStatusCard';

const mockUseScanProgress = vi.fn();

vi.mock('@/hooks/library/useScanProgress', () => ({
  useScanProgress: () => mockUseScanProgress(),
}));

const scanStatus = (overrides: Record<string, unknown> = {}) => ({
  isScanning: false,
  current: 0,
  total: 0,
  percentage: null,
  currentFile: null,
  phase: 'processing' as const,
  lastResult: null,
  ...overrides,
});

beforeEach(() => {
  vi.clearAllMocks();
  mockUseScanProgress.mockReturnValue(scanStatus());
});

describe('ScanStatusCard', () => {
  it('shows no failed/skipped chips when a scan had none', () => {
    mockUseScanProgress.mockReturnValue(
      scanStatus({
        lastResult: {
          filesAdded: 10, filesRemoved: 0, filesFailed: 0, filesSkipped: 0,
          failures: [], duration: 2.0,
        },
      })
    );
    render(<ScanStatusCard onScanNow={vi.fn()} />);

    expect(screen.getByText('+10 added')).toBeInTheDocument();
    expect(screen.queryByText(/failed/)).not.toBeInTheDocument();
    expect(screen.queryByText(/skipped/)).not.toBeInTheDocument();
  });

  it('renders failed and skipped counts when a scan reports them (#5466)', () => {
    mockUseScanProgress.mockReturnValue(
      scanStatus({
        lastResult: {
          filesAdded: 4,
          filesRemoved: 0,
          filesFailed: 3,
          filesSkipped: 2,
          failures: [{ filename: 'bad.flac', reason: 'decode error' }],
          duration: 1.5,
        },
      })
    );
    render(<ScanStatusCard onScanNow={vi.fn()} />);

    expect(screen.getByText('+4 added')).toBeInTheDocument();
    expect(screen.getByText('3 failed')).toBeInTheDocument();
    expect(screen.getByText('2 skipped')).toBeInTheDocument();
  });

  it('still shows "No scans yet" when nothing has run', () => {
    render(<ScanStatusCard onScanNow={vi.fn()} />);
    expect(screen.getByText('No scans yet')).toBeInTheDocument();
  });
});
