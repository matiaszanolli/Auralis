import { useState, useCallback, useRef } from 'react';

interface OptimisticUpdateOptions<T> {
  onSuccess?: (data: T) => void;
  onError?: (error: Error) => void;
  rollbackDelay?: number;
}

/**
 * Hook for optimistic UI updates
 * Updates the UI immediately and rolls back if the operation fails
 */
export function useOptimisticUpdate<T, Args extends any[]>(
  initialState: T,
  asyncOperation: (...args: Args) => Promise<T>,
  options: OptimisticUpdateOptions<T> = {}
) {
  const [state, setState] = useState<T>(initialState);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  // Refs to avoid recreating execute when callers pass inline options/callbacks
  const stateRef = useRef(state);
  stateRef.current = state;

  const onSuccessRef = useRef(options.onSuccess);
  onSuccessRef.current = options.onSuccess;

  const onErrorRef = useRef(options.onError);
  onErrorRef.current = options.onError;

  const initialStateRef = useRef(initialState);
  initialStateRef.current = initialState;

  const asyncOpRef = useRef(asyncOperation);
  asyncOpRef.current = asyncOperation;

  const execute = useCallback(
    async (optimisticValue: T, ...args: Args) => {
      const previousState = stateRef.current;

      // Optimistically update the UI
      setState(optimisticValue);
      setIsLoading(true);
      setError(null);

      try {
        // Perform the async operation
        const result = await asyncOpRef.current(...args);

        // Update with the actual result
        setState(result);
        onSuccessRef.current?.(result);

        return result;
      } catch (err) {
        // Rollback to previous state on error
        const error = err as Error;
        setState(previousState);
        setError(error);
        onErrorRef.current?.(error);

        throw error;
      } finally {
        setIsLoading(false);
      }
    },
    [] // stable — all varying deps are in refs
  );

  const reset = useCallback(() => {
    setState(initialStateRef.current);
    setError(null);
    setIsLoading(false);
  }, []);

  return {
    state,
    isLoading,
    error,
    execute,
    reset,
    setState,
  };
}

export default useOptimisticUpdate;
