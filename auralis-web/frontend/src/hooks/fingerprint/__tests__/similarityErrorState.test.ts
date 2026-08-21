/**
 * Similarity error classification — issue #4626
 *
 * The similarity router encodes the actionable part of a failure in
 * `HTTPException.detail`, and two of its three reachable failure states share a
 * status code. Every frontend hook used to throw on `response.status` /
 * `response.statusText` alone, so "we already queued this track, check back in a
 * second" and "that track does not exist" rendered as the same red error — and
 * over HTTP/2, where `statusText` is empty, the message degraded to
 * `"Similarity search failed: 404 "`, a string with no information in it.
 *
 * These pin the classification, including the coupling to the backend's wording.
 */

import { describe, it, expect } from 'vitest';
import { classifySimilarityError } from '../similarityErrorState';

/** The exact detail `similarity_common.require_fingerprinted_tracks` emits. */
const QUEUED_DETAIL =
  'Track 7 does not have a fingerprint. Queued for background processing.';

/** The exact detail the `is_fitted` guards in `similarity.py` emit. */
const NOT_INITIALISED_DETAIL =
  'Similarity system not initialized. Please wait for initialization.';

describe('classifySimilarityError', () => {
  describe('the queued 404 — the common first-run experience', () => {
    it('is distinguished from a genuine 404', () => {
      const queued = classifySimilarityError(QUEUED_DETAIL, 404);
      const missing = classifySimilarityError('Track 7 not found', 404);

      expect(queued.kind).toBe('queued');
      expect(missing.kind).toBe('not-found');
      expect(queued.kind).not.toBe(missing.kind);
    });

    it('reads as progress, not failure', () => {
      const state = classifySimilarityError(QUEUED_DETAIL, 404);
      expect(state.transient).toBe(true);
      expect(state.retryable).toBe(true);
      expect(state.title).toMatch(/analysing/i);
    });

    it('still classifies if the backend rewords around "queued"', () => {
      // The marker is one word rather than the full sentence precisely so a
      // meaning-preserving reword does not silently fall back to 'not-found'.
      const state = classifySimilarityError(
        'No fingerprint for track 7 — queued for analysis.',
        404
      );
      expect(state.kind).toBe('queued');
    });

    it('fails loudly if the backend stops saying "queued"', () => {
      // Guards the coupling documented on QUEUED_MARKER: if
      // require_fingerprinted_tracks drops the word, this is the test that
      // should turn red rather than the UI silently regressing.
      const state = classifySimilarityError(
        'Track 7 does not have a fingerprint. Scheduled for background processing.',
        404
      );
      expect(state.kind).toBe('not-found');
    });
  });

  describe('the 503 — similarity system still initialising', () => {
    it('is retryable and distinct from every 404', () => {
      const state = classifySimilarityError(NOT_INITIALISED_DETAIL, 503);

      expect(state.kind).toBe('initialising');
      expect(state.retryable).toBe(true);
      expect(state.transient).toBe(true);
      expect(state.kind).not.toBe(classifySimilarityError(QUEUED_DETAIL, 404).kind);
    });
  });

  describe('a genuine 404', () => {
    it('is not retryable and surfaces the backend detail', () => {
      const state = classifySimilarityError('Track 7 not found', 404);

      expect(state.retryable).toBe(false);
      expect(state.transient).toBe(false);
      expect(state.hint).toBe('Track 7 not found');
    });
  });

  describe('everything else', () => {
    it('surfaces the backend detail as the headline', () => {
      const state = classifySimilarityError('Database is locked', 500);

      expect(state.kind).toBe('failed');
      expect(state.title).toBe('Database is locked');
      expect(state.transient).toBe(false);
    });

    it('stays informative when there is no message at all', () => {
      // The HTTP/2 shape: empty statusText upstream must not produce a blank
      // headline here either.
      expect(classifySimilarityError('', 500).title).toBe('Similarity search failed');
      expect(classifySimilarityError('   ', null).title).toBe('Similarity search failed');
    });

    it('handles a network failure, which has no status', () => {
      const state = classifySimilarityError('Failed to fetch', null);
      expect(state.kind).toBe('failed');
      expect(state.title).toBe('Failed to fetch');
    });
  });
});
