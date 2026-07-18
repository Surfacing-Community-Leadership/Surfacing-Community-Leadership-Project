import { useCallback, useEffect, useRef, useState } from "react";

// Runs an async loader on mount (and whenever `deps` change), tracking the
// three states every screen needs: loading, error, and data. Returns a
// `reload` function for refreshing after a mutation.
export function useApi(loader, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  // Guards against a stale response overwriting a newer one: each run() gets a
  // ticket, and only the most recent ticket is allowed to apply its result. So
  // if you navigate between two event pages quickly, a slow earlier request
  // resolving last can't clobber the newer page's data.
  const latestCall = useRef(0);

  const run = useCallback(async () => {
    const callId = ++latestCall.current;
    setLoading(true);
    setError(null);
    try {
      const result = await loader();
      if (callId === latestCall.current) setData(result);
    } catch (err) {
      if (callId === latestCall.current) setError(err.message || "Something went wrong");
    } finally {
      if (callId === latestCall.current) setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    run();
  }, [run]);

  return { data, error, loading, reload: run, setData };
}
