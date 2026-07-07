// TanStack Query hooks wrapping GET /api/connections and /api/connections/requests.
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export function useConnections() {
  return useQuery({ queryKey: ["connections"], queryFn: () => apiFetch("/api/connections") });
}
