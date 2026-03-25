/**
 * AlbumCharacterPane State Logic Tests
 *
 * Tests the top-level component state routing:
 * 1. Empty state — no track, no album fingerprint
 * 2. Loading state — isLoading=true
 * 3. Pending state — track playing, fingerprint not ready
 * 4. Full display — fingerprint available
 *
 * All sub-components and hooks are mocked to keep tests focused on branching logic.
 */

import { vi, describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@/test/test-utils';
import type { AudioFingerprint } from '@/utils/fingerprintToGradient';

// ---------------------------------------------------------------------------
// Mock sub-components (render simple stubs with test IDs)
// ---------------------------------------------------------------------------

vi.mock('../FloatingParticles', () => ({
  FloatingParticles: () => <div data-testid="floating-particles" />,
}));

vi.mock('../WaveformVisualization', () => ({
  WaveformVisualization: () => <div data-testid="waveform-visualization" />,
}));

vi.mock('../GlowingArc', () => ({
  GlowingArc: () => <div data-testid="glowing-arc" />,
}));

vi.mock('../CharacterTags', () => ({
  CharacterTags: () => <div data-testid="character-tags" />,
}));

vi.mock('../EnergyField', () => ({
  EnergyField: () => <div data-testid="energy-field" />,
}));

vi.mock('../RotatingDescription', () => ({
  RotatingDescription: () => <div data-testid="rotating-description" />,
}));

vi.mock('../PanePlaceholders', () => ({
  EmptyStatePane: ({ enhancementSection }: any) => (
    <div data-testid="empty-state-pane">{enhancementSection}</div>
  ),
  PendingStatePane: ({ enhancementSection, displayTitle }: any) => (
    <div data-testid="pending-state-pane">
      {enhancementSection}
      <span>{displayTitle}</span>
    </div>
  ),
  LoadingStatePane: ({ enhancementSection }: any) => (
    <div data-testid="loading-state-pane">{enhancementSection}</div>
  ),
  NoFingerprintPane: ({ enhancementSection }: any) => (
    <div data-testid="no-fingerprint-pane">{enhancementSection}</div>
  ),
}));

// ---------------------------------------------------------------------------
// Mock EnhancementToggle
// ---------------------------------------------------------------------------

vi.mock('@/components/shared/EnhancementToggle', () => ({
  EnhancementToggle: (props: any) => (
    <div data-testid="enhancement-toggle" data-enabled={props.isEnabled}>
      {props.label}
    </div>
  ),
}));

// ---------------------------------------------------------------------------
// Mock hooks
// ---------------------------------------------------------------------------

const mockUseEnhancementControl = vi.fn();
vi.mock('@/hooks/enhancement/useEnhancementControl', () => ({
  useEnhancementControl: () => mockUseEnhancementControl(),
}));

const mockUseTrackFingerprint = vi.fn();
vi.mock('@/hooks/fingerprint', () => ({
  useTrackFingerprint: (...args: any[]) => mockUseTrackFingerprint(...args),
}));

vi.mock('../usePlaybackWithDecay', () => ({
  usePlaybackWithDecay: () => ({ isAnimating: false, intensity: 0, isPlaying: false }),
}));

// ---------------------------------------------------------------------------
// Mock Redux selectors via react-redux useSelector
// ---------------------------------------------------------------------------

let mockIsPlaying = false;
let mockCurrentTrack: { id: number; title: string } | null = null;

vi.mock('react-redux', async () => {
  const actual = await vi.importActual<typeof import('react-redux')>('react-redux');
  return {
    ...actual,
    useSelector: (selector: any) => {
      // Match selectors by reference-checking their string representation
      // is unreliable — instead, call the selector with a fake state and
      // determine which value it wants based on the key it accesses.
      const fakeState = {
        player: {
          isPlaying: mockIsPlaying,
          currentTrack: mockCurrentTrack,
        },
      };
      return selector(fakeState);
    },
  };
});

// ---------------------------------------------------------------------------
// Mock computeAlbumCharacter
// ---------------------------------------------------------------------------

vi.mock('@/utils/albumCharacterDescriptors', () => ({
  computeAlbumCharacter: () => ({
    tags: [{ label: 'Warm', category: 'Tone' }],
    energyLevel: 0.6,
    description: 'A warm track',
    rotatingDescriptions: ['Warm and mellow', 'Smooth vibes'],
  }),
}));

// ---------------------------------------------------------------------------
// Import component under test AFTER all mocks are set up
// ---------------------------------------------------------------------------

import { AlbumCharacterPane } from '../AlbumCharacterPane';

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

const makeFakeFingerprint = (): AudioFingerprint =>
  ({
    spectral_centroid: 0.5,
    spectral_bandwidth: 0.4,
    spectral_rolloff: 0.6,
    spectral_contrast: 0.3,
    mfcc_mean: 0.5,
    chroma_mean: 0.7,
    rms_energy: 0.8,
  }) as unknown as AudioFingerprint;

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('AlbumCharacterPane', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    // Default hook returns
    mockUseEnhancementControl.mockReturnValue({
      enabled: false,
      setEnabled: vi.fn(),
    });

    mockUseTrackFingerprint.mockReturnValue({
      fingerprint: null,
      trackTitle: null,
      artist: null,
      isLoading: false,
      isPending: false,
      error: null,
    });

    // Default Redux state
    mockIsPlaying = false;
    mockCurrentTrack = null;
  });

  // -------------------------------------------------------------------------
  // State 1: Empty
  // -------------------------------------------------------------------------

  describe('Empty state', () => {
    it('renders EmptyStatePane when no fingerprint and no playing track', () => {
      render(<AlbumCharacterPane />);

      expect(screen.getByTestId('empty-state-pane')).toBeInTheDocument();
      expect(screen.queryByTestId('loading-state-pane')).not.toBeInTheDocument();
      expect(screen.queryByTestId('pending-state-pane')).not.toBeInTheDocument();
    });

    it('renders EmptyStatePane when fingerprint is explicitly null', () => {
      render(<AlbumCharacterPane fingerprint={null} />);

      expect(screen.getByTestId('empty-state-pane')).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // State 2: Loading
  // -------------------------------------------------------------------------

  describe('Loading state', () => {
    it('renders LoadingStatePane when isLoading is true', () => {
      render(<AlbumCharacterPane isLoading={true} />);

      expect(screen.getByTestId('loading-state-pane')).toBeInTheDocument();
      expect(screen.queryByTestId('empty-state-pane')).not.toBeInTheDocument();
    });

    it('renders LoadingStatePane when playing track is loading', () => {
      mockCurrentTrack = { id: 1, title: 'Test' };

      mockUseTrackFingerprint.mockReturnValue({
        fingerprint: null,
        trackTitle: null,
        artist: null,
        isLoading: true,
        isPending: false,
        error: null,
      });

      render(<AlbumCharacterPane />);

      expect(screen.getByTestId('loading-state-pane')).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // State 3: Pending (track playing, fingerprint being generated)
  // -------------------------------------------------------------------------

  describe('Pending state', () => {
    it('renders PendingStatePane when track is playing but fingerprint is pending', () => {
      mockCurrentTrack = { id: 42, title: 'My Track' };

      mockUseTrackFingerprint.mockReturnValue({
        fingerprint: null,
        trackTitle: null,
        artist: null,
        isLoading: false,
        isPending: true,
        error: null,
      });

      render(<AlbumCharacterPane />);

      expect(screen.getByTestId('pending-state-pane')).toBeInTheDocument();
      expect(screen.queryByTestId('empty-state-pane')).not.toBeInTheDocument();
      expect(screen.queryByTestId('loading-state-pane')).not.toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // State 4: Full display
  // -------------------------------------------------------------------------

  describe('Full display', () => {
    it('renders visualization components when fingerprint prop is provided', () => {
      const fingerprint = makeFakeFingerprint();
      render(<AlbumCharacterPane fingerprint={fingerprint} />);

      expect(screen.getByTestId('waveform-visualization')).toBeInTheDocument();
      expect(screen.getByTestId('glowing-arc')).toBeInTheDocument();
      expect(screen.getByTestId('character-tags')).toBeInTheDocument();
      expect(screen.getByTestId('energy-field')).toBeInTheDocument();
      expect(screen.getByTestId('rotating-description')).toBeInTheDocument();
      expect(screen.getByTestId('floating-particles')).toBeInTheDocument();
    });

    it('shows "Album Character" heading when displaying album fingerprint', () => {
      const fingerprint = makeFakeFingerprint();
      render(<AlbumCharacterPane fingerprint={fingerprint} albumTitle="Test Album" />);

      expect(screen.getByText('Album Character')).toBeInTheDocument();
      expect(screen.getByText('Test Album')).toBeInTheDocument();
    });

    it('shows "Track Character" heading when a track is playing', () => {
      mockCurrentTrack = { id: 1, title: 'Playing Track' };

      mockUseTrackFingerprint.mockReturnValue({
        fingerprint: makeFakeFingerprint(),
        trackTitle: 'Playing Track',
        artist: 'Test Artist',
        isLoading: false,
        isPending: false,
        error: null,
      });

      render(<AlbumCharacterPane />);

      expect(screen.getByText('Track Character')).toBeInTheDocument();
    });

    it('renders mood discovery prompt in full display', () => {
      const fingerprint = makeFakeFingerprint();
      render(<AlbumCharacterPane fingerprint={fingerprint} />);

      expect(screen.getByText(/Explore mood-based discovery/)).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // EnhancementToggle presence
  // -------------------------------------------------------------------------

  describe('EnhancementToggle', () => {
    it('renders EnhancementToggle in empty state', () => {
      render(<AlbumCharacterPane />);

      expect(screen.getByTestId('enhancement-toggle')).toBeInTheDocument();
    });

    it('renders EnhancementToggle in loading state', () => {
      render(<AlbumCharacterPane isLoading={true} />);

      expect(screen.getByTestId('enhancement-toggle')).toBeInTheDocument();
    });

    it('renders EnhancementToggle in full display', () => {
      const fingerprint = makeFakeFingerprint();
      render(<AlbumCharacterPane fingerprint={fingerprint} />);

      expect(screen.getByTestId('enhancement-toggle')).toBeInTheDocument();
    });

    it('passes enabled state from useEnhancementControl to EnhancementToggle', () => {
      mockUseEnhancementControl.mockReturnValue({
        enabled: true,
        setEnabled: vi.fn(),
      });

      const fingerprint = makeFakeFingerprint();
      render(<AlbumCharacterPane fingerprint={fingerprint} />);

      const toggle = screen.getByTestId('enhancement-toggle');
      expect(toggle).toHaveAttribute('data-enabled', 'true');
    });
  });
});
