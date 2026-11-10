export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public detail: unknown,
  ) {
    super(message);
  }
}

export interface ApiOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  language?: string;
}

let accessToken: string | null = null;
let accessTokenExpiresAt = 0;
let refreshInFlight: Promise<boolean> | null = null;

const authPathsWithoutRetry = new Set(["/auth/login", "/auth/logout", "/auth/refresh"]);

function rememberAccessToken(value: unknown): unknown {
  if (!value || typeof value !== "object" || Array.isArray(value)) return value;
  const result = { ...(value as Record<string, unknown>) };
  if (typeof result.access_token !== "string") return value;

  accessToken = result.access_token;
  const expiresIn = typeof result.expires_in === "number" ? result.expires_in : 900;
  accessTokenExpiresAt = Date.now() + expiresIn * 1000;
  delete result.access_token;
  delete result.token_type;
  delete result.expires_in;
  return result;
}

async function refreshAccessToken(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;
  refreshInFlight = (async () => {
    try {
      const response = await fetch("/api/v1/auth/refresh", {
        method: "POST",
        credentials: "include",
      });
      if (!response.ok) {
        accessToken = null;
        accessTokenExpiresAt = 0;
        return false;
      }
      const payload: unknown = await response.json().catch(() => null);
      rememberAccessToken(payload);
      return accessToken !== null;
    } catch {
      accessToken = null;
      accessTokenExpiresAt = 0;
      return false;
    }
  })();
  try {
    return await refreshInFlight;
  } finally {
    refreshInFlight = null;
  }
}

async function sendRequest(
  path: string,
  init: RequestInit,
  payload: BodyInit | undefined,
): Promise<Response> {
  const headers = new Headers(init.headers);
  if (accessToken && path !== "/auth/login" && path !== "/auth/refresh") {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }
  return fetch(`/api/v1${path}`, {
    ...init,
    body: payload,
    headers,
    credentials: "include",
  });
}

export async function api<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const { body, language, ...init } = options;
  const headers = new Headers(init.headers);
  if (language) headers.set("Accept-Language", language);
  let payload: BodyInit | undefined;
  if (body instanceof FormData) payload = body;
  else if (body !== undefined) {
    headers.set("Content-Type", "application/json");
    payload = JSON.stringify(body);
  }
  const requestInit = { ...init, headers };
  if (accessToken && accessTokenExpiresAt <= Date.now() + 30_000
      && !authPathsWithoutRetry.has(path)) {
    await refreshAccessToken();
  }
  let response = await sendRequest(path, requestInit, payload);
  if (response.status === 401 && accessToken && !authPathsWithoutRetry.has(path)) {
    const rejectedToken = accessToken;
    if (refreshInFlight) {
      await refreshInFlight;
    } else if (accessToken === rejectedToken) {
      accessToken = null;
      accessTokenExpiresAt = 0;
      await refreshAccessToken();
    }
    if (accessToken && accessToken !== rejectedToken) {
      response = await sendRequest(path, requestInit, payload);
    }
  }
  const rawResult: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    let message = `تعذر إكمال الطلب (${response.status})`;
    if (rawResult && typeof rawResult === "object" && "detail" in rawResult) {
      const detail = rawResult.detail;
      if (typeof detail === "string") message = detail;
      else if (Array.isArray(detail))
        message = detail.map((item: { msg?: string }) => item.msg || "").join("، ");
    }
    throw new ApiError(message, response.status, rawResult);
  }
  const result = rememberAccessToken(rawResult);
  if (path === "/auth/logout") {
    accessToken = null;
    accessTokenExpiresAt = 0;
  }
  return result as T;
}

export function upload<T>(path: string, file: File): Promise<T> {
  const body = new FormData();
  body.append("file", file);
  return api<T>(path, { method: "POST", body });
}
