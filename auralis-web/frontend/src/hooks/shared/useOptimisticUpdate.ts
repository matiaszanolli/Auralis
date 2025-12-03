import { useState, useCallback } from 'react';

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

  const execute = useCallback(
    async (optimisticValue: T, ...args: Args) => {
      const previousState = state;

      // Optimistically update the UI
      setState(optimisticValue);
      setIsLoading(true);
      setError(null);

      try {
        // Perform the async operation
        const result = await asyncOperation(...args);

        // Update with the actual result
        setState(result);
        options.onSuccess?.(result);

        return result;
      } catch (err) {
        // Rollback to previous state on error
        const error = err as Error;
        setState(previousState);
        setError(error);
        options.onError?.(error);

        throw error;
      } finally {
        setIsLoading(false);
      }
    },
    [state, asyncOperation, options]
  );

  const reset = useCallback(() => {
    setState(initialState);
    setError(null);
    setIsLoading(false);
  }, [initialState]);

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
