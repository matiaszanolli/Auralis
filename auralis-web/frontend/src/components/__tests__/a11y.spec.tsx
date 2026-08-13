/**
 * Automated accessibility assertions for the interactive surfaces (#4637)
 *
 * There was no automated a11y testing anywhere in the frontend, which is why the
 * a11y defects exist: six accessible-name bugs (#4448, #4449, #4450, #4473,
 * #3996, #4180) were each found by manual audit, and each is mechanically
 * detectable. A developer could add an interactive `<div onClick>` with no role
 * or tabIndex, pass type-check, and merge.
 *
 * Deliberately scoped rather than blanket: axe on every component test would be
 * slow and noisy. This covers the four highest-interaction-density areas — the
 * player transport, QueuePanel, the MediaCard family and the dialogs — which is
 * where the open a11y defects live.
 *
 * **What this does NOT cover**: contrast and hit-target size, because jsdom has
 * no layout engine. Those rules are disabled explicitly in `src/test/a11y.ts`
 * (with the reasoning) rather than left to report meaningless results. Contrast
 * is covered separately by real token-value assertions in
 * `TextDisabledContrast.test.ts` (#4635). A clean run here does not mean
 * "accessible".
 */

import { describe, it, expect, vi } from 'vitest';
import { render } from '@/test/test-utils';
import {
  expectNoA11yViolations,
  findUnfocusableInteractiveRoles,
  getA11yIncomplete,
  getA11yViolations,
  JSDOM_UNSUPPORTED_RULES,
} from '@/test/a11y';

// jsdom has no AudioContext/WebSocket; the transport pulls both in transitively.
vi.mock('@/hooks/enhancement/usePlayEnhanced', () => ({
  usePlayEnhanced: () => ({
    playEnhanced: vi.fn(), playNormal: vi.fn(), seekTo: vi.fn(),
    pausePlayback: vi.fn(), resumePlayback: vi.fn(), stopPlayback: vi.fn(),
    setVolume: vi.fn(), isStreaming: false, streamingState: 'idle',
    streamingProgress: 0, bufferedSamples: 0, processedChunks: 0, totalChunks: 0,
    currentTime: 0, isPaused: false, isSeeking: false, error: null,
    fingerprintStatus: 'idle', fingerprintMessage: null,
  }),
}));

vi.mock('@/hooks/player/usePlaybackQueue', () => ({
  usePlaybackQueue: () => ({
    queue: [
      { id: 1, title: 'First', artist: 'A', album: 'X', duration: 100 },
      { id: 2, title: 'Second', artist: 'B', album: 'Y', duration: 200 },
    ],
    currentIndex: 0, isShuffled: false, repeatMode: 'off',
    removeTrack: vi.fn(), reorderTrack: vi.fn(), toggleShuffle: vi.fn(),
    setRepeatMode: vi.fn(), clearQueue: vi.fn(), isLoading: false, error: null,
  }),
}));

import Player from '../player/Player';
import QueuePanel from '../player/QueuePanel';
import PlaybackControls from '../player/PlaybackControls';
import VolumeControl from '../player/VolumeControl';
import { MediaCard } from '../shared/MediaCard';
import { ClearQueueDialog } from '../player/QueuePanel/ClearQueueDialog';
import { SettingsDialog } from '../settings/SettingsDialog';
import { EditMetadataDialog } from '../library/EditMetadataDialog/EditMetadataDialog';

const TRACK_STATE = {
  preloadedState: {
    player: {
      currentTrack: { id: 1, title: 'T', artist: 'A', album: 'B', duration: 200 },
      volume: 50,
      isMuted: false,
    },
  },
} as unknown as Parameters<typeof render>[1];

describe('a11y: player transport (#4637)', () => {
  it('Player has no violations', async () => {
    const { container } = render(<Player />, TRACK_STATE);
    await expectNoA11yViolations(container);
  });

  it('PlaybackControls has no violations', async () => {
    const { container } = render(
      <PlaybackControls
        isPlaying={false}
        onPlay={vi.fn()}
        onPause={vi.fn()}
        onNext={vi.fn()}
        onPrevious={vi.fn()}
      />
    );
    await expectNoA11yViolations(container);
  });

  it('PlaybackControls has no violations while disabled', async () => {
    const { container } = render(
      <PlaybackControls
        isPlaying
        onPlay={vi.fn()}
        onPause={vi.fn()}
        onNext={vi.fn()}
        onPrevious={vi.fn()}
        disabled
      />
    );
    await expectNoA11yViolations(container);
  });

  it('VolumeControl has no violations', async () => {
    const { container } = render(
      <VolumeControl volume={0.5} onVolumeChange={vi.fn()} onMuteToggle={vi.fn()} />
    );
    await expectNoA11yViolations(container);
  });
});

describe('a11y: QueuePanel (#4637)', () => {
  it('expanded has no violations', async () => {
    const { container } = render(<QueuePanel collapsed={false} onToggleCollapse={vi.fn()} />);
    await expectNoA11yViolations(container);
  });

  it('collapsed has no violations', async () => {
    const { container } = render(<QueuePanel collapsed onToggleCollapse={vi.fn()} />);
    await expectNoA11yViolations(container);
  });
});

describe('a11y: MediaCard family (#4637)', () => {
  // MediaCard has one KNOWN violation, filed as #5101 and found by this very
  // spec: the card wrapper is role="button" tabIndex={0} and contains a
  // focusable IconButton, so axe reports `nested-interactive`.
  //
  // It is pinned rather than left failing. The frontend CI gate is a baseline
  // ratchet whose list may shrink but never grow (#4640), so landing new
  // failures would work against it; and asserting the exact known violation
  // means the test fails loudly the moment #5101 is fixed, telling the next
  // author to flip it to a plain assertion. `disableRules` would have hidden it.
  const KNOWN = 'nested-interactive';

  const CASES: Array<[string, React.ReactElement]> = [
    ['track variant', <MediaCard variant="track" id={1} title="Song" artist="Artist" album="Album" />],
    ['album variant', <MediaCard variant="album" id={1} title="Album" artist="Artist" trackCount={9} year={2001} />],
    ['playing state', <MediaCard variant="track" id={1} title="Song" artist="Artist" album="Album" isPlaying />],
  ];

  it.each(CASES)('%s has no violations beyond the known #5101 one', async (_name, element) => {
    const { container } = render(element);

    const ids = (await getA11yViolations(container)).map((v) => v.id);

    expect(ids.filter((id) => id !== KNOWN)).toEqual([]);
  });

  it.each(CASES)('%s still exhibits #5101 (flip these to a plain assertion when fixed)', async (_name, element) => {
    const { container } = render(element);

    const ids = (await getA11yViolations(container)).map((v) => v.id);

    expect(ids).toContain(KNOWN);
  });

  it('MediaCard is at least keyboard reachable', async () => {
    const { container } = render(
      <MediaCard variant="track" id={1} title="Song" artist="Artist" album="Album" />
    );

    expect(findUnfocusableInteractiveRoles(container)).toEqual([]);
  });
});

describe('a11y: dialogs (#4637)', () => {
  it('ClearQueueDialog has no violations', async () => {
    const { container } = render(
      <ClearQueueDialog onConfirm={vi.fn()} onCancel={vi.fn()} />
    );
    await expectNoA11yViolations(container);
  });

  it('SettingsDialog has no violations', async () => {
    const { baseElement } = render(<SettingsDialog open onClose={vi.fn()} />);
    // MUI Dialog portals outside `container`, so scan from baseElement.
    await expectNoA11yViolations(baseElement);
  });

  // EditMetadataDialog has one KNOWN violation, filed as #5102 and found by this
  // spec: its Dialog's aria-labelledby points at an id that resolves to nothing,
  // so the modal has no accessible name. Pinned for the same reasons as #5101.
  const DIALOG_KNOWN = 'aria-dialog-name';

  const renderEditDialog = () => render(
    <EditMetadataDialog
      open
      trackId={1}
      currentMetadata={{ title: 'T', artist: 'A', album: 'B' }}
      onClose={vi.fn()}
    />
  );

  it('EditMetadataDialog has no violations beyond the known #5102 one', async () => {
    const { baseElement } = renderEditDialog();

    const ids = (await getA11yViolations(baseElement)).map((v) => v.id);

    expect(ids.filter((id) => id !== DIALOG_KNOWN)).toEqual([]);
  });

  it('EditMetadataDialog still exhibits #5102 (flip when fixed)', async () => {
    const { baseElement } = renderEditDialog();

    const ids = (await getA11yViolations(baseElement)).map((v) => v.id);

    expect(ids).toContain(DIALOG_KNOWN);
  });

  it('SettingsDialog does NOT exhibit #5102 — the contrast the fix should follow', async () => {
    const { baseElement } = render(<SettingsDialog open onClose={vi.fn()} />);

    const ids = (await getA11yViolations(baseElement)).map((v) => v.id);

    expect(ids).not.toContain(DIALOG_KNOWN);
  });
});

describe('the checker actually catches things (meta-tests)', () => {
  // Without these, a green suite above could mean "axe found nothing" or
  // "axe never ran".
  it('fails a role="button" that Tab skips — #4637 acceptance criterion', async () => {
    const { container } = render(
      <div role="button" onClick={() => {}}>
        Looks clickable, is not reachable
      </div>
    );

    // Measured, not assumed: axe-core reports NOTHING here — no violation and no
    // incomplete result — which is why expectNoA11yViolations pairs it with an
    // explicit focusability check. Asserting axe's silence pins the reason this
    // extra check exists, so nobody deletes it as redundant.
    expect(await getA11yViolations(container)).toEqual([]);
    expect(findUnfocusableInteractiveRoles(container)).toHaveLength(1);

    await expect(expectNoA11yViolations(container)).rejects.toThrow(
      /not keyboard focusable/
    );
  });

  it('flags a control with no accessible name — the class behind six past defects', async () => {
    const { container } = render(<button type="button" />);

    const violations = await getA11yViolations(container);

    expect(violations.map((v) => v.id)).toContain('button-name');
  });

  it('surfaces an aria reference to a missing element, which axe calls undecided', async () => {
    const { container } = render(
      <div aria-labelledby="does-not-exist" role="region">content</div>
    );

    // jsdom pushes aria-valid-attr-value into `incomplete`, not `violations`.
    // Treating a clean violations array as a pass would silently ignore it.
    expect(await getA11yViolations(container)).toEqual([]);
    expect((await getA11yIncomplete(container)).map((v) => v.id))
      .toContain('aria-valid-attr-value');

    await expect(
      expectNoA11yViolations(container, { strictIncomplete: true })
    ).rejects.toThrow(/undecided/);
  });

  it('passes a correctly-built interactive element', async () => {
    const { container } = render(
      <div role="button" tabIndex={0} onClick={() => {}} onKeyDown={() => {}}>
        Reachable
      </div>
    );

    await expectNoA11yViolations(container);
  });
});

describe('the disabled rule set is explicit and documented (#4637)', () => {
  it('names exactly the rules jsdom cannot evaluate', () => {
    // Pinned so nobody silently disables a rule that *does* work in jsdom to
    // make a failing test pass. Growing this list must be a deliberate edit.
    expect([...JSDOM_UNSUPPORTED_RULES]).toEqual(['color-contrast', 'target-size']);
  });

  it('color-contrast is covered elsewhere, not simply ignored', async () => {
    // The #4635 spec asserts real WCAG ratios from token values. This test
    // exists so the exclusion above cannot be read as "contrast is unchecked".
    const contrastSpec = await import('@/test/contrast');
    expect(typeof contrastSpec.contrastRatio).toBe('function');
  });
});
