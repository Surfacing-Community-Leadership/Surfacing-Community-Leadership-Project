import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext.jsx";
import { HeartMark } from "../components/Logo.jsx";
import GoogleButton from "../components/GoogleButton.jsx";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isOrg, setIsOrg] = useState(false);
  const [org, setOrg] = useState({
    org_category: "",
    org_website: "",
    org_phone: "",
    org_address: "",
    org_contact_name: "",
    org_contact_role: "",
  });
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const setOrgField = (key) => (e) =>
    setOrg((o) => ({ ...o, [key]: e.target.value }));

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await register(email, password, displayName, isOrg ? org : null);
      navigate("/onboarding", { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="org auth-split">
      <aside className="auth-aside accent">
        <Link to="/" className="brand">
          <HeartMark size={28} color="var(--color-bg)" title="Ours" />
          <span className="wordmark">Ours</span>
        </Link>
        <div className="blob" aria-hidden="true" />
        <div className="lead">
          <p>Meet the people three doors down.</p>
          <ol>
            <li>
              <b>01</b> See what's happening this week nearby
            </li>
            <li>
              <b>02</b> Host a gathering or ask for a hand
            </li>
            <li>
              <b>03</b> Show up, then get on with your life
            </li>
          </ol>
        </div>
        <span className="foot">Neighbors helping neighbors</span>
      </aside>

      <main className="auth-main">
        <form onSubmit={handleSubmit}>
          <h1>Create your account</h1>
          <p className="auth-lead">
            Already a neighbor? <Link to="/login">Log in</Link>
          </p>
          {error && <div className="alert">{error}</div>}

          {/* Person or local institution. Declaring "organization" is
              self-service; the ✓ badge is granted separately. */}
          <div className="field">
            <span className="field-label">This account is for</span>
            <div className="pill-tabs">
              <button
                type="button"
                className={!isOrg ? "pill-tab on" : "pill-tab"}
                onClick={() => setIsOrg(false)}
              >
                A person
              </button>
              <button
                type="button"
                className={isOrg ? "pill-tab on" : "pill-tab"}
                onClick={() => setIsOrg(true)}
              >
                An organization
              </button>
            </div>
          </div>

          <div className="field">
            <label htmlFor="rg-name">
              {isOrg ? "Organization name" : "Display name"}
            </label>
            <input
              id="rg-name"
              className="input"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              required
              maxLength={80}
            />
          </div>
          <div className="field">
            <label htmlFor="rg-email">Email</label>
            <input
              id="rg-email"
              className="input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </div>
          <div className="field">
            <label htmlFor="rg-pw">Password</label>
            <input
              id="rg-pw"
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              autoComplete="new-password"
            />
            <span className="field-hint">At least 8 characters.</span>
          </div>

          {isOrg && (
            <div className="org-block">
              <p className="org-block-note">
                Libraries, schools, parks departments, faith groups, nonprofits
                and government bodies. We'll check these details before adding
                the verified mark — sign up with your official email address if
                you have one.
              </p>

              <div className="field">
                <label htmlFor="rg-cat">Type of organization</label>
                <select
                  id="rg-cat"
                  value={org.org_category}
                  onChange={setOrgField("org_category")}
                  required
                >
                  <option value="">Choose one…</option>
                  <option value="library">Library</option>
                  <option value="school">School</option>
                  <option value="parks">Parks &amp; recreation</option>
                  <option value="faith">Faith group</option>
                  <option value="nonprofit">Nonprofit</option>
                  <option value="government">Government body</option>
                  <option value="other">Other</option>
                </select>
              </div>

              <div className="field">
                <label htmlFor="rg-web">Website</label>
                <input
                  id="rg-web"
                  className="input"
                  type="url"
                  placeholder="https://…"
                  value={org.org_website}
                  onChange={setOrgField("org_website")}
                  required
                  maxLength={300}
                />
                <span className="field-hint">
                  How we confirm you're who you say you are.
                </span>
              </div>

              <div className="field-row">
                <div className="field">
                  <label htmlFor="rg-phone">Public phone</label>
                  <input
                    id="rg-phone"
                    className="input"
                    value={org.org_phone}
                    onChange={setOrgField("org_phone")}
                    maxLength={40}
                  />
                </div>
                <div className="field">
                  <label htmlFor="rg-addr">Public address</label>
                  <input
                    id="rg-addr"
                    className="input"
                    value={org.org_address}
                    onChange={setOrgField("org_address")}
                    maxLength={300}
                  />
                </div>
              </div>

              <div className="field-row">
                <div className="field">
                  <label htmlFor="rg-cname">Who's posting</label>
                  <input
                    id="rg-cname"
                    className="input"
                    placeholder="Full name"
                    value={org.org_contact_name}
                    onChange={setOrgField("org_contact_name")}
                    maxLength={120}
                  />
                </div>
                <div className="field">
                  <label htmlFor="rg-crole">Their role</label>
                  <input
                    id="rg-crole"
                    className="input"
                    placeholder="e.g. Programs Director"
                    value={org.org_contact_role}
                    onChange={setOrgField("org_contact_role")}
                    maxLength={120}
                  />
                </div>
              </div>
              <span className="field-hint">
                Only our moderators see who runs the account — never shown on
                your public page.
              </span>
            </div>
          )}

          <button type="submit" className="btn-block" disabled={submitting}>
            {submitting ? "Creating account…" : "Create account →"}
          </button>
          {/* Google signup always creates a personal account, so only offer it
              on the person tab — an organization needs to supply its details. */}
          {!isOrg && <GoogleButton next="/onboarding" label="Sign up with Google" />}
          <p
            className="field-hint"
            style={{ marginTop: "18px", lineHeight: 1.55 }}
          >
            By joining you agree to keep it neighborly — no politics, no spam,
            real people only.
          </p>
        </form>
      </main>
    </div>
  );
}
