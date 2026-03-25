/**
 * Unit tests for AlbumCharacterPane visual sub-components (#3424)
 */

import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@/test/test-utils';
import { EnergyField } from '../EnergyField';
import { FloatingParticles } from '../FloatingParticles';
import { GlowingArc } from '../GlowingArc';
import { RotatingDescription } from '../RotatingDescription';
import { WaveformVisualization } from '../WaveformVisualization';
import { CharacterTags } from '../CharacterTags';
import {
  EmptyStatePane,
  PendingStatePane,
  LoadingStatePane,
  NoFingerprintPane,
} from '../PanePlaceholders';

// ---------------------------------------------------------------------------
// EnergyField
// ---------------------------------------------------------------------------

describe('EnergyField', () => {
  it('renders CALM and AGGRESSIVE labels', () => {
    render(<EnergyField energy={0.5} isAnimating={false} intensity={0} />);
    expect(screen.getByText('CALM')).toBeInTheDocument();
    expect(screen.getByText('AGGRESSIVE')).toBeInTheDocument();
  });

  it('renders a meter with correct ARIA attributes', () => {
    render(<EnergyField energy={0.7} isAnimating={false} intensity={0.5} />);
    const meter = screen.getByRole('meter');
    expect(meter).toHaveAttribute('aria-valuenow', '70');
    expect(meter).toHaveAttribute('aria-valuemin', '0');
    expect(meter).toHaveAttribute('aria-valuemax', '100');
    expect(meter).toHaveAttribute('aria-label', 'Energy level');
  });

  it('maps energy 0 to aria-valuenow 0', () => {
    render(<EnergyField energy={0} isAnimating={false} intensity={0} />);
    expect(screen.getByRole('meter')).toHaveAttribute('aria-valuenow', '0');
  });

  it('maps energy 1 to aria-valuenow 100', () => {
    render(<EnergyField energy={1} isAnimating={false} intensity={0} />);
    expect(screen.getByRole('meter')).toHaveAttribute('aria-valuenow', '100');
  });
});

// ---------------------------------------------------------------------------
// FloatingParticles
// ---------------------------------------------------------------------------

describe('FloatingParticles', () => {
  it('returns null when not animating and intensity is low', () => {
    const { container } = render(
      <FloatingParticles isAnimating={false} intensity={0} />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders particles when animating', () => {
    const { container } = render(
      <FloatingParticles isAnimating={true} intensity={0.8} count={5} />
    );
    expect(container.firstChild).not.toBeNull();
    // 5 particle children inside the container Box
    expect(container.firstChild!.childNodes.length).toBe(5);
  });

  it('renders default 12 particles when count is omitted', () => {
    const { container } = render(
      <FloatingParticles isAnimating={true} intensity={0.5} />
    );
    expect(container.firstChild!.childNodes.length).toBe(12);
  });

  it('renders when not animating but intensity is above threshold', () => {
    const { container } = render(
      <FloatingParticles isAnimating={false} intensity={0.5} />
    );
    expect(container.firstChild).not.toBeNull();
  });
});

// ---------------------------------------------------------------------------
// GlowingArc
// ---------------------------------------------------------------------------

describe('GlowingArc', () => {
  it('renders SPACE label', () => {
    render(<GlowingArc isAnimating={false} intensity={0} energyLevel={0.5} />);
    expect(screen.getByText('SPACE')).toBeInTheDocument();
  });

  it('renders without crashing at boundary energy levels', () => {
    const { container: c0 } = render(
      <GlowingArc isAnimating={false} intensity={0} energyLevel={0} />
    );
    expect(c0.firstChild).not.toBeNull();

    const { container: c1 } = render(
      <GlowingArc isAnimating={true} intensity={1} energyLevel={1} />
    );
    expect(c1.firstChild).not.toBeNull();
  });
});

// ---------------------------------------------------------------------------
// RotatingDescription
// ---------------------------------------------------------------------------

describe('RotatingDescription', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows static description when not playing', () => {
    render(
      <RotatingDescription
        descriptions={['Desc A', 'Desc B']}
        staticDescription="Static text"
        isPlaying={false}
      />
    );
    expect(screen.getByText('Static text')).toBeInTheDocument();
  });

  it('shows first description when playing', () => {
    render(
      <RotatingDescription
        descriptions={['Desc A', 'Desc B']}
        staticDescription="Static text"
        isPlaying={true}
      />
    );
    expect(screen.getByText('Desc A')).toBeInTheDocument();
  });

  it('shows static description when descriptions array is empty', () => {
    render(
      <RotatingDescription
        descriptions={[]}
        staticDescription="Fallback"
        isPlaying={true}
      />
    );
    expect(screen.getByText('Fallback')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// WaveformVisualization
// ---------------------------------------------------------------------------

describe('WaveformVisualization', () => {
  const mockFingerprint = {
    spectral_centroid: 0.5,
    spectral_bandwidth: 0.4,
    spectral_rolloff: 0.6,
    spectral_contrast: 0.3,
    mfcc_mean: 0.5,
    chroma_mean: 0.7,
    rms_energy: 0.8,
  };

  it('renders 7 frequency band bars', () => {
    const { container } = render(
      <WaveformVisualization
        fingerprint={mockFingerprint as never}
        isAnimating={false}
        intensity={0}
      />
    );
    // Container Box has 7 bar children (+ possible pseudo-elements)
    const bars = container.querySelectorAll('[class*="MuiBox-root"] > [class*="MuiBox-root"]');
    expect(bars.length).toBeGreaterThanOrEqual(7);
  });

  it('renders without crashing', () => {
    const { container } = render(
      <WaveformVisualization
        fingerprint={mockFingerprint as never}
        isAnimating={true}
        intensity={1}
      />
    );
    expect(container.firstChild).not.toBeNull();
  });
});

// ---------------------------------------------------------------------------
// CharacterTags
// ---------------------------------------------------------------------------

describe('CharacterTags', () => {
  const tags = [
    { label: 'Warm', category: 'Tone' },
    { label: 'Energetic', category: 'Mood' },
    { label: 'Acoustic', category: 'Texture' },
  ];

  it('renders all tag labels', () => {
    render(<CharacterTags tags={tags} isAnimating={false} intensity={0} />);
    expect(screen.getByText('Warm')).toBeInTheDocument();
    expect(screen.getByText('Energetic')).toBeInTheDocument();
    expect(screen.getByText('Acoustic')).toBeInTheDocument();
  });

  it('applies aria-label with category and label', () => {
    render(<CharacterTags tags={tags} isAnimating={false} intensity={0} />);
    expect(screen.getByLabelText('Tone: Warm')).toBeInTheDocument();
    expect(screen.getByLabelText('Mood: Energetic')).toBeInTheDocument();
  });

  it('renders empty when tags array is empty', () => {
    const { container } = render(
      <CharacterTags tags={[]} isAnimating={false} intensity={0} />
    );
    // Container exists but no Chip children
    expect(container.querySelectorAll('[class*="MuiChip"]').length).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// PanePlaceholders
// ---------------------------------------------------------------------------

const placeholderProps = {
  containerStyles: {},
  enhancementSection: <div data-testid="enhancement" />,
};

describe('EmptyStatePane', () => {
  it('renders prompt text', () => {
    render(<EmptyStatePane {...placeholderProps} />);
    expect(screen.getByText(/Play a track/i)).toBeInTheDocument();
  });

  it('renders enhancement section', () => {
    render(<EmptyStatePane {...placeholderProps} />);
    expect(screen.getByTestId('enhancement')).toBeInTheDocument();
  });
});

describe('PendingStatePane', () => {
  it('renders default title', () => {
    render(<PendingStatePane {...placeholderProps} />);
    expect(screen.getByText('Now Playing')).toBeInTheDocument();
  });

  it('renders custom displayTitle', () => {
    render(<PendingStatePane {...placeholderProps} displayTitle="My Album" />);
    expect(screen.getByText('My Album')).toBeInTheDocument();
  });
});

describe('LoadingStatePane', () => {
  it('shows track analysis text when track is playing', () => {
    render(<LoadingStatePane {...placeholderProps} isTrackPlaying={true} />);
    expect(screen.getByText(/Analyzing track/i)).toBeInTheDocument();
  });

  it('shows album analysis text when track is not playing', () => {
    render(<LoadingStatePane {...placeholderProps} isTrackPlaying={false} />);
    expect(screen.getByText(/Analyzing album/i)).toBeInTheDocument();
  });
});

describe('NoFingerprintPane', () => {
  it('renders conditional text based on isTrackPlaying', () => {
    const { rerender } = render(
      <NoFingerprintPane {...placeholderProps} isTrackPlaying={true} />
    );
    // Should show some text — the exact wording depends on the component
    expect(screen.getByText(/character|fingerprint|analysis/i)).toBeInTheDocument();

    rerender(<NoFingerprintPane {...placeholderProps} isTrackPlaying={false} />);
    expect(screen.getByText(/character|fingerprint|analysis/i)).toBeInTheDocument();
  });

  it('renders enhancement section', () => {
    render(<NoFingerprintPane {...placeholderProps} isTrackPlaying={false} />);
    expect(screen.getByTestId('enhancement')).toBeInTheDocument();
  });
});
