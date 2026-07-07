// TanStack Query hook wrapping GET /api/events — the data source for MapView.
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export function useEvents(params) {
  return useQuery({
    queryKey: ["events", params],
    queryFn: () => apiFetch(`/api/events?${new URLSearchParams(params)}`),
  });
}
