// A thin wrapper around the native Fetch API. Auth rides in an httpOnly
// cookie set by the backend, so there is no token handling here at all —
// JavaScript never sees the JWT. The browser attaches the cookie itself
// (fetch's default credentials mode is "same-origin", and the Vite proxy
// makes /api same-origin in development).

// Thrown for any non-2xx response. Carries the HTTP status and the backend's
// { message } text so callers can branch on either.
export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// Callback registered by the auth layer; fires on any 401 so the app can
// drop its user state and bounce to /login.
let onUnauthorized = () => {};
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

// The CSRF cookie is deliberately readable by JavaScript: we prove we're the
// real frontend by echoing it in a header, which other origins cannot do.
function readCsrfCookie() {
  const match = document.cookie.match(/(?:^|;\s*)ours_csrf=([^;]+)/);
  return match ? match[1] : null;
}

async function request(method, path, body, isForm = false) {
  const headers = {};
  if (body !== undefined && !isForm) headers["Content-Type"] = "application/json";
  if (method !== "GET") {
    const csrf = readCsrfCookie();
    if (csrf) headers["X-CSRF-Token"] = csrf;
  }

  const res = await fetch(path, {
    method,
    headers,
    body:
      body === undefined ? undefined : isForm ? body : JSON.stringify(body),
  });

  if (res.status === 401) {
    onUnauthorized();
    throw new ApiError(401, "Please log in to continue.");
  }

  // 204 No Content and other empty bodies: nothing to parse.
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;

  if (!res.ok) {
    const message = data?.message || `Request failed (${res.status})`;
    throw new ApiError(res.status, message);
  }
  return data;
}

export const api = {
  get: (path) => request("GET", path),
  post: (path, body) => request("POST", path, body),
  put: (path, body) => request("PUT", path, body),
  patch: (path, body) => request("PATCH", path, body),
  del: (path) => request("DELETE", path),
  // multipart upload: pass a FormData; the browser sets the content type.
  upload: (path, formData) => request("POST", path, formData, true),
};

// avatar_key is either an uploaded file path ("avatars/<id>.jpg") or a
// legacy text/emoji label. Returns an image URL or null.
export function avatarUrl(key) {
  return key && key.startsWith("avatars/") ? `/media/${key}` : null;
}
