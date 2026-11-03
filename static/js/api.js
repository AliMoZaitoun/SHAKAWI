const API_ROOT = "/api/v1";

export async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const response = await fetch(`${API_ROOT}${path}`, { ...options, headers, credentials: "include" });
  const raw = await response.text();
  let payload = null;
  if (raw) {
    try { payload = JSON.parse(raw); } catch { payload = { detail: raw }; }
  }
  if (!response.ok) {
    const detail = payload?.detail;
    const message = Array.isArray(detail) ? detail.map((item) => item.msg || item.message).join("، ") : (typeof detail === "string" ? detail : payload?.message);
    const error = new Error(message || `تعذر إكمال الطلب (${response.status}).`);
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return payload;
}

export function postFile(path, file) {
  const body = new FormData();
  body.append("file", file);
  return api(path, { method: "POST", body });
}

export function complaintDownloadUrl(id) {
  return `${API_ROOT}/complaints/attachments/${encodeURIComponent(id)}/download`;
}
