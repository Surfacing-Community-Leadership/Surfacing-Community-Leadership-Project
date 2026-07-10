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

async function request(method, path, body) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const res = await fetch(path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
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
};
