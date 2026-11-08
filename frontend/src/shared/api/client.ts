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
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    body: payload,
    headers,
    credentials: "include",
  });
  const result: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    let message = `تعذر إكمال الطلب (${response.status})`;
    if (result && typeof result === "object" && "detail" in result) {
      const detail = result.detail;
      if (typeof detail === "string") message = detail;
      else if (Array.isArray(detail))
        message = detail.map((item: { msg?: string }) => item.msg || "").join("، ");
    }
    throw new ApiError(message, response.status, result);
  }
  return result as T;
}

export function upload<T>(path: string, file: File): Promise<T> {
  const body = new FormData();
  body.append("file", file);
  return api<T>(path, { method: "POST", body });
}
