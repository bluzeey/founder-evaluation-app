import { useEffect, useRef } from "react";

/**
 * Polling hook that:
 *   - Calls `callback` every `intervalMs` milliseconds.
 *   - Pauses while the tab is hidden (no wasted requests).
 *   - Fires immediately when the tab becomes visible again.
 *   - Re-schedules when `intervalMs` changes (adaptive cadence).
 *
 * The callback is stored in a ref so changes to it do not restart the
 * interval — only changes to `intervalMs` do. This lets callers pass
 * inline closures that read fresh state without rescheduling the timer.
 *
 * Pass `intervalMs <= 0` to pause polling entirely.
 */
export function useAdaptivePolling(callback: () => void, intervalMs: number): void {
  const savedCallback = useRef(callback);

  useEffect(() => {
    savedCallback.current = callback;
  });

  useEffect(() => {
    if (intervalMs <= 0) return;

    const tick = () => {
      if (typeof document !== "undefined" && document.hidden) return;
      savedCallback.current();
    };

    const timer = setInterval(tick, intervalMs);

    const onVisibilityChange = () => {
      if (typeof document === "undefined") return;
      if (!document.hidden) {
        // Fire immediately on return so the user sees fresh data without
        // waiting for the next tick.
        savedCallback.current();
      }
    };
    document.addEventListener("visibilitychange", onVisibilityChange);

    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisibilityChange);
    };
  }, [intervalMs]);
}
