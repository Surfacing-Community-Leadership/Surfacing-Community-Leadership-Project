import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";
import Field from "../components/Field.jsx";

// Optional first-run step. Everything here can be skipped and edited later
// from the profile page, so nothing blocks the user from reaching the map.
export default function Onboarding() {
  const navigate = useNavigate();
  const { data, loading, error } = useApi(async () => {
    const [interests, communities] = await Promise.all([
      api.get("/api/interests"),
      api.get("/api/communities"),
    ]);
    return { interests, communities };
  });

  const [selected, setSelected] = useState(new Set());
  const [communityId, setCommunityId] = useState("");
  const [openToHelp, setOpenToHelp] = useState(false);
  const [showAttending, setShowAttending] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  function toggle(id) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  async function finish() {
    setSaving(true);
    setSaveError(null);
    try {
      await api.patch("/api/profiles/me", {
        community_id: communityId || null,
        open_to_help: openToHelp,
        show_attending: showAttending,
      });
      await api.put("/api/profiles/me/interests", {
        interest_ids: [...selected],
      });
      navigate("/", { replace: true });
    } catch (err) {
      setSaveError(err.message);
      setSaving(false);
    }
  }

  if (loading) return <div className="centered muted">Loading…</div>;
  if (error) return <div className="alert">{error}</div>;

  return (
    <div className="narrow">
      <h1>Welcome to Ours</h1>
      <p className="muted">
        A few optional preferences to shape what you see. You can change these
        anytime from your profile.
      </p>

      <section className="card">
        <h2>Your neighborhood</h2>
        <Field label="Community">
          <select value={communityId} onChange={(e) => setCommunityId(e.target.value)}>
            <option value="">Choose later</option>
            {data.communities.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </Field>
      </section>

      <section className="card">
        <h2>What are you into?</h2>
        <p className="muted">Pick any that fit — we'll surface matching events.</p>
        <div className="chip-grid">
          {data.interests.map((interest) => (
            <button
              type="button"
              key={interest.id}
              className={selected.has(interest.id) ? "chip chip-on" : "chip"}
              onClick={() => toggle(interest.id)}
            >
              {interest.name}
            </button>
          ))}
        </div>
      </section>

      <section className="card">
        <h2>How you'd like to show up</h2>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={openToHelp}
            onChange={(e) => setOpenToHelp(e.target.checked)}
          />
          I'm open to helping neighbors with tasks
        </label>
        <label className="checkbox">
          <input
            type="checkbox"
            checked={showAttending}
            onChange={(e) => setShowAttending(e.target.checked)}
          />
          Let my connections see what I'm attending
        </label>
      </section>

      {saveError && <div className="alert">{saveError}</div>}
      <div className="row-actions">
        <button className="secondary" onClick={() => navigate("/")} disabled={saving}>
          Skip for now
        </button>
        <button onClick={finish} disabled={saving}>
          {saving ? "Saving…" : "Finish"}
        </button>
      </div>
    </div>
  );
}
