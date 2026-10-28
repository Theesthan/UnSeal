"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export interface Action<A extends unknown[], R> {
  run: (...args: A) => Promise<R | undefined>;
  /** Runs the last call again with the same arguments (the "Try again" button). */
  retry: () => Promise<R | undefined>;
  pending: boolean;
  error: unknown;
  clearError: () => void;
}

/**
 * Wraps one async API call with pending and error state. Errors are kept for <ErrorNotice>,
 * never thrown into React, so a failure never blanks the screen.
 */
export function useAction<A extends unknown[], R>(fn: (...args: A) => Promise<R>): Action<A, R> {
  const fnRef = useRef(fn);
  useEffect(() => {
    fnRef.current = fn;
  });
  const lastArgs = useRef<A | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const run = useCallback(async (...args: A): Promise<R | undefined> => {
    lastArgs.current = args;
    setPending(true);
    setError(null);
    try {
      return await fnRef.current(...args);
    } catch (caught) {
      setError(caught);
      return undefined;
    } finally {
      setPending(false);
    }
  }, []);

  const retry = useCallback(
    () => (lastArgs.current ? run(...lastArgs.current) : Promise.resolve(undefined)),
    [run],
  );
  const clearError = useCallback(() => setError(null), []);

  return { run, retry, pending, error, clearError };
}
