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
  lastError: null,
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
          failures: [], unreadableFolders: [], duration: 2.0,
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
          unreadableFolders: [],
          duration: 1.5,
        },
      })
    );
    render(<ScanStatusCard onScanNow={vi.fn()} />);

    expect(screen.getByText('+4 added')).toBeInTheDocument();
    expect(screen.getByText('3 failed')).toBeInTheDocument();
    expect(screen.getByText('2 skipped')).toBeInTheDocument();
  });

  it('names the folders a scan could not read (#5877)', () => {
    mockUseScanProgress.mockReturnValue(
      scanStatus({
        lastResult: {
          filesAdded: 3, filesRemoved: 0, filesFailed: 0, filesSkipped: 0, failures: [],
          unreadableFolders: [{ filename: 'Locked Album', reason: 'permission denied' }],
          duration: 1.0,
        },
      })
    );
    render(<ScanStatusCard onScanNow={vi.fn()} />);

    expect(screen.getByText('1 folder unreadable')).toBeInTheDocument();
  });

  it('says the last scan failed instead of showing an ordinary idle state (#5877)', () => {
    mockUseScanProgress.mockReturnValue(scanStatus({ lastError: 'RuntimeError during library scan' }));
    render(<ScanStatusCard onScanNow={vi.fn()} />);

    expect(screen.getByRole('alert')).toHaveTextContent('Last scan failed: RuntimeError during library scan');
  });

  it('still shows "No scans yet" when nothing has run', () => {
    render(<ScanStatusCard onScanNow={vi.fn()} />);
    expect(screen.getByText('No scans yet')).toBeInTheDocument();
  });

  describe('scan progress label', () => {
    it('shows the running tally while the counting pass runs (#5910)', () => {
      mockUseScanProgress.mockReturnValue(
        scanStatus({ isScanning: true, phase: 'counting', current: 0, total: 500 })
      );
      render(<ScanStatusCard onScanNow={vi.fn()} />);

      expect(screen.getByText('Counting… 500 files found')).toBeInTheDocument();
      expect(screen.queryByText('0 files')).not.toBeInTheDocument();
    });

    it('shows N / total once a real fraction exists', () => {
      mockUseScanProgress.mockReturnValue(
        scanStatus({ isScanning: true, current: 50, total: 500, percentage: 10 })
      );
      render(<ScanStatusCard onScanNow={vi.fn()} />);

      expect(screen.getByText('50 / 500')).toBeInTheDocument();
    });

    it('shows the climbing count when the total is unknown', () => {
      mockUseScanProgress.mockReturnValue(scanStatus({ isScanning: true, current: 7 }));
      render(<ScanStatusCard onScanNow={vi.fn()} />);

      expect(screen.getByText('7 files')).toBeInTheDocument();
    });
  });

  describe('current file label', () => {
    it.each([
      ['C:\\a\\b.mp3', 'b.mp3'],
      ['/music/a/b.mp3', 'b.mp3'],
    ])('shows the basename of %s (#5913)', (currentFile, expected) => {
      mockUseScanProgress.mockReturnValue(scanStatus({ isScanning: true, currentFile }));
      render(<ScanStatusCard onScanNow={vi.fn()} />);

      expect(screen.getByText(expected)).toBeInTheDocument();
    });
  });
});
