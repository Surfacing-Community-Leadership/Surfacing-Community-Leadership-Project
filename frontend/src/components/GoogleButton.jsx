import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";

// Google's mark, drawn inline so the button needs no external asset (a strict
// CSP and an offline dev machine both still work).
function GoogleMark() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
      <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9 3.6l6.7-6.7C35.6 2.5 30.2 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.8 6.1C12.3 13.2 17.7 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.1 24.6c0-1.6-.1-2.8-.4-4H24v8.1h12.6c-.3 2.1-1.6 5.2-4.6 7.3l7.6 5.9c4.4-4.1 6.5-10.1 6.5-17.3z" />
      <path fill="#FBBC05" d="M10.4 28.7a14.8 14.8 0 0 1 0-9.4l-7.8-6.1a24 24 0 0 0 0 21.6l7.8-6.1z" />
      <path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.6-5.8l-7.6-5.9c-2 1.4-4.8 2.4-8 2.4-6.3 0-11.7-3.7-13.6-9l-7.8 6.1C6.5 42.6 14.6 48 24 48z" />
    </svg>
  );
}

// Sign in with Google. A plain link, not fetch(): the OAuth round trip is a
// browser navigation, and the callback needs to set cookies on a top-level
// response. Hidden entirely when the deployment has no Google client
// configured, so nobody clicks through to an error.
export default function GoogleButton({ next = "/map", label = "Continue with Google" }) {
  const { data: providers } = useApi(() => api.get("/api/auth/providers"));
  if (!providers?.google) return null;

  return (
    <>
      <div className="auth-divider">
        <span>or</span>
      </div>
      <a
        className="btn google-btn"
        href={`/api/auth/google/start?next=${encodeURIComponent(next)}`}
      >
        <GoogleMark />
        {label}
      </a>
    </>
  );
}
