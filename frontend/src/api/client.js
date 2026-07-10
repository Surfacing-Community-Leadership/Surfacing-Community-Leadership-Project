// A thin wrapper around the native Fetch API. Every request goes through
// here so token handling, JSON encoding, and error shaping live in one place.

const TOKEN_KEY = "ours.token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

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
// drop the stale token and bounce the user to /login.
let onUnauthorized = () => {};
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

async function request(method, path, body, { auth = true } = {}) {
  const headers = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const token = getToken();
  if (auth && token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(path, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401) {
    onUnauthorized();
    throw new ApiError(401, "Your session has expired. Please log in again.");
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
  get: (path, opts) => request("GET", path, undefined, opts),
  post: (path, body, opts) => request("POST", path, body, opts),
  put: (path, body, opts) => request("PUT", path, body, opts),
  patch: (path, body, opts) => request("PATCH", path, body, opts),
  del: (path, opts) => request("DELETE", path, undefined, opts),
};
