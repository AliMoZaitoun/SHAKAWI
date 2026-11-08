import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type ApiOptions } from "./client";
import type { SessionEmployee, Directorate, Language } from "./types";

export function useResource<T>(path: string, language = "ar", enabled = true) {
  return useQuery({
    queryKey: [path, language],
    queryFn: () => api<T>(path, { language }),
    enabled,
    retry: false,
  });
}
export function useAction<Input, Output>(path: string, method = "POST") {
  const cache = useQueryClient();
  return useMutation({
    mutationFn: (body: Input) => api<Output>(path, { method, body }),
    onSuccess: () => cache.invalidateQueries(),
  });
}
export function useSession() {
  return useResource<SessionEmployee>("/auth/me");
}
export function useDirectorates(language = "ar") {
  return useResource<Directorate[]>("/directorates", language);
}
export function useLanguages() {
  return useResource<Language[]>("/languages");
}
export function useApiMutation() {
  const cache = useQueryClient();
  return useMutation({
    mutationFn: ({ path, options }: { path: string; options?: ApiOptions }) =>
      api<unknown>(path, options),
    onSuccess: () => cache.invalidateQueries(),
  });
}
