// In-memory response cache with stale-while-revalidate semantics and
// in-flight request deduplication. Shared across all callers in the SPA.
//
// Goals:
//   - Collapse concurrent identical GETs into one network request.
//   - Serve cached data instantly when fresh; refetch in the background
//     when stale so the UI never blocks on a spinner during polling.
//   - Allow mutations to invalidate entries by URL prefix.

interface CacheEntry {
  data: unknown;
  fetchedAt: number;
  inflight?: Promise<unknown>;
}

interface TtlConfig {
  freshMs: number;
  staleMs: number;
}

const DEFAULT_FRESH_MS = 5_000;
const DEFAULT_STALE_MS = 30_000;

// Order matters: more-specific patterns first.
const TTL_RULES: Array<{ match: RegExp; ttl: TtlConfig }> = [
  { match: /\/v1\/founders\/[^/]+\/score$/, ttl: { freshMs: 2_000, staleMs: 10_000 } },
  { match: /\/v1\/enrichment\/runs/, ttl: { freshMs: 2_000, staleMs: 10_000 } },
  { match: /\/v1\/sourcing\/status/, ttl: { freshMs: 3_000, staleMs: 15_000 } },
  { match: /\/v1\/theses(\?|$)/, ttl: { freshMs: 10_000, staleMs: 60_000 } },
  { match: /\/v1\/sourcing\/schedules(\?|$)/, ttl: { freshMs: 10_000, staleMs: 60_000 } },
  { match: /\/v1\/founders\/pool/, ttl: { freshMs: 5_000, staleMs: 30_000 } },
  { match: /\/v1\/opportunities\/[^/]+\/diligence/, ttl: { freshMs: 5_000, staleMs: 30_000 } },
  { match: /\/v1\/founders\/[^/]+$/, ttl: { freshMs: 10_000, staleMs: 60_000 } },
  { match: /\/v1\/opportunities\/[^/]+$/, ttl: { freshMs: 5_000, staleMs: 30_000 } },
  { match: /\/v1\/founders(\?|$)/, ttl: { freshMs: 5_000, staleMs: 30_000 } },
  { match: /\/v1\/opportunities(\?|$)/, ttl: { freshMs: 5_000, staleMs: 30_000 } },
];

function ttlFor(path: string): TtlConfig {
  for (const rule of TTL_RULES) {
    if (rule.match.test(path)) return rule.ttl;
  }
  return { freshMs: DEFAULT_FRESH_MS, staleMs: DEFAULT_STALE_MS };
}

const store = new Map<string, CacheEntry>();

/**
 * Fetch with cache. Returns cached data immediately when fresh; returns
 * stale data and refetches in the background when stale; fetches fresh
 * on miss. Concurrent callers for the same key share a single in-flight
 * request (deduplication).
 */
export function cacheGet<T>(fetcher: () => Promise<T>, key: string): Promise<T> {
  const now = Date.now();
  const entry = store.get(key);
  const ttl = ttlFor(key);

  // In-flight dedup: if a request for this key is already running, reuse it.
  // If we have stale data, return it now; otherwise await the in-flight.
  if (entry?.inflight) {
    if (entry.data !== undefined && now - entry.fetchedAt < ttl.staleMs) {
      return Promise.resolve(entry.data as T);
    }
    return entry.inflight as Promise<T>;
  }

  // Fresh hit: return cached, no network.
  if (entry && entry.data !== undefined && now - entry.fetchedAt < ttl.freshMs) {
    return Promise.resolve(entry.data as T);
  }

  // Stale hit: return cached now, refetch in the background.
  if (entry && entry.data !== undefined && now - entry.fetchedAt < ttl.staleMs) {
    kickOffBackgroundRefetch(fetcher, entry);
    return Promise.resolve(entry.data as T);
  }

  // Miss (or fully expired): fetch fresh, dedupe future concurrent callers.
  const inflight = fetcher()
    .then((data) => {
      const e = store.get(key);
      if (e) {
        e.data = data;
        e.fetchedAt = Date.now();
        e.inflight = undefined;
      } else {
        store.set(key, { data, fetchedAt: Date.now() });
      }
      return data;
    })
    .catch((err) => {
      const e = store.get(key);
      if (e) e.inflight = undefined;
      throw err;
    });

  if (entry) {
    entry.inflight = inflight;
  } else {
    store.set(key, { data: undefined, fetchedAt: 0, inflight });
  }
  return inflight;
}

function kickOffBackgroundRefetch<T>(
  fetcher: () => Promise<T>,
  entry: CacheEntry
): void {
  const inflight = fetcher()
    .then((data) => {
      entry.data = data;
      entry.fetchedAt = Date.now();
      return data;
    })
    .catch(() => {
      // keep stale data; background refetch failed silently
    })
    .finally(() => {
      entry.inflight = undefined;
    });
  entry.inflight = inflight;
}

/**
 * Drop all cache entries whose key starts with `prefix`. Used after
 * mutations to force the next read to hit the network.
 */
export function invalidate(prefix: string): void {
  for (const key of store.keys()) {
    if (key.startsWith(prefix)) {
      store.delete(key);
    }
  }
}

export function invalidateAll(): void {
  store.clear();
}

// Test-only helpers (not exported via client.ts).
export const __cacheInternals = {
  peek: () => store,
  reset: () => store.clear(),
  size: () => store.size,
};
