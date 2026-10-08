import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

/** Backend reachability, polled once a minute. */
export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => api.getHealth(),
    refetchInterval: 60_000,
    retry: false,
  });
}
