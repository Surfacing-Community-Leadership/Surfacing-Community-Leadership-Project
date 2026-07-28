import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client.js";
import { useAuth } from "../auth/AuthContext.jsx";
import { HeartMark } from "../components/Logo.jsx";

// Landing page for the emailed confirmation link. Public on purpose: the signed
// token is the credential, so the link works on whatever device opened the mail
// — including one that was never signed in.
export default function ConfirmEmail() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const { refreshUser } = useAuth();
  const [state, setState] = useState(token ? "working" : "missing");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  // React 18 StrictMode double-invokes effects in dev; confirm only once.
  const sent = useRef(false);

  useEffect(() => {
    if (!token || sent.current) return;
    sent.current = true;
    api
      .post("/api/auth/confirm-email", { token })
      .then(async (data) => {
        setResult(data);
        setState("done");
        // If this browser is signed in, pick up the new flags right away.
        await refreshUser?.().catch(() => {});
      })
      .catch((err) => {
        setError(err.message);
        setState("failed");
      });
  }, [token, refreshUser]);

  return (
    <div className="org confirm-page">
      <div className="confirm-card">
        <HeartMark size={34} />

        {state === "working" && <h1>Confirming…</h1>}

        {state === "missing" && (
          <>
            <h1>Link incomplete</h1>
            <p className="muted">
              That address is missing its confirmation code. Open the link
              straight from the email, or ask for a fresh one from your profile.
            </p>
          </>
        )}

        {state === "failed" && (
          <>
            <h1>That link didn't work</h1>
            <div className="alert">{error}</div>
            <p className="muted">
              Links expire after 48 hours. Log in and ask for a new one.
            </p>
          </>
        )}

        {state === "done" && (
          <>
            <h1>{result.already_confirmed ? "Already confirmed" : "You're confirmed"}</h1>
            <p className="muted">
              {result.already_confirmed
                ? `${result.email} was already confirmed — nothing more to do.`
                : `We can reach you at ${result.email}.`}
            </p>
            {result.organization_verified && (
              <p className="confirm-verified">
                ✓ Your organization is now verified — neighbors will see the
                verified mark on your profile.
              </p>
            )}
          </>
        )}

        <div className="row-actions">
          <Link className="btn" to="/map">
            Go to the map
          </Link>
        </div>
      </div>
    </div>
  );
}
