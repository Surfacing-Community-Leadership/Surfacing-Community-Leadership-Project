import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";
import CommunityPicker from "../components/CommunityPicker.jsx";

export default function Onboarding() {
  const navigate = useNavigate();
  const { data, loading, error } = useApi(async () => {
    const [interests, profile, myInterests] = await Promise.all([
      api.get("/api/interests"),
      api.get("/api/profiles/me"),
      api.get("/api/profiles/me/interests"),
    ]);
    return { interests, profile, myInterests };
  });

  const [selected, setSelected] = useState(new Set());
  const [communityId, setCommunityId] = useState("");
  const [openToHelp, setOpenToHelp] = useState(false);
  const [showAttending, setShowAttending] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  useEffect(() => {
    if (!data) return;
    setSelected(new Set(data.myInterests.interest_ids));
    setCommunityId(data.profile.community_id || "");
    setOpenToHelp(data.profile.open_to_help);
    setShowAttending(data.profile.show_attending);
  }, [data]);

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
      await api.put("/api/profiles/me/interests", { interest_ids: [...selected] });
      navigate("/map", { replace: true });
    } catch (err) {
      setSaveError(err.message);
      setSaving(false);
    }
  }

  if (loading) return <div className="org centered muted">Loading…</div>;
  if (error)
    return (
      <div className="org narrow">
        <div className="alert">{error}</div>
      </div>
    );

  return (
    <div className="org narrow">
      <span className="kicker">Quick setup · optional</span>
      <h1>Welcome to Ours</h1>
      <p className="muted" style={{ maxWidth: "52ch", lineHeight: 1.6, margin: "0 0 32px", fontSize: "16px" }}>
        A few optional preferences to shape what you see. You can change these
        anytime from your profile.
      </p>

      <section className="card">
        <h2>Your neighborhood</h2>
        <CommunityPicker value={communityId} onChange={setCommunityId} />
      </section>

      <section className="card">
        <h2>What are you into?</h2>
        <p className="muted" style={{ margin: 0 }}>
          Pick any that fit — we'll surface matching events.
        </p>
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
          <input type="checkbox" checked={openToHelp} onChange={(e) => setOpenToHelp(e.target.checked)} />
          I'm open to helping neighbors with tasks
        </label>
        <label className="checkbox">
          <input type="checkbox" checked={showAttending} onChange={(e) => setShowAttending(e.target.checked)} />
          Let my connections see what I'm attending
        </label>
      </section>

      {saveError && <div className="alert">{saveError}</div>}
      <div className="row-actions" style={{ justifyContent: "flex-end" }}>
        <button className="secondary" onClick={() => navigate("/map")} disabled={saving}>
          Skip for now
        </button>
        <button onClick={finish} disabled={saving}>
          {saving ? "Saving…" : "Finish →"}
        </button>
      </div>
    </div>
  );
}
