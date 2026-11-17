"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Load data, and keep re-loading every `intervalMs` while `shouldPoll(data)`
 * is true (e.g. while a book is processing or a paper is generating).
 */
export function usePolling<T>(load: () => Promise<T>, shouldPoll: (data: T) => boolean, intervalMs = 2000) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const loadRef = useRef(load);
  const pollRef = useRef(shouldPoll);
  loadRef.current = load;
  pollRef.current = shouldPoll;

  const reload = useCallback(async () => {
    try {
      const d = await loadRef.current();
      setData(d);
      setError(null);
      return d;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
      return null;
    }
  }, []);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      const d = await reload();
      if (alive && d && pollRef.current(d)) timer = setTimeout(tick, intervalMs);
    };
    tick();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [reload, intervalMs]);

  return { data, setData, error, reload };
}

export function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}
