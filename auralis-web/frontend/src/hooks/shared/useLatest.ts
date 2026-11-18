import { useRef, type MutableRefObject } from 'react';

/**
 * A ref that always holds the value of the latest render.
 *
 * For a callback that reads a frequently-changing value only when it runs (not to
 * decide when to re-create itself): list the ref, not the value, in its deps so the
 * callback keeps its identity. The ref is assigned during render, the convention
 * already used by `tracksRef` in useTrackSelection.
 */
export function useLatest<T>(value: T): MutableRefObject<T> {
  const ref = useRef(value);
  ref.current = value;
  return ref;
}
