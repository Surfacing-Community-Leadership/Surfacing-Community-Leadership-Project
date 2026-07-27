import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, avatarUrl } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";
import Field from "../components/Field.jsx";
import CommunityPicker from "../components/CommunityPicker.jsx";

function initial(name) {
  return (name || "?").trim().charAt(0).toUpperCase();
}

// The signed-in user's own editable profile — community, interests and
// preferences all in one place, so there's no separate settings page.
export default function Profile() {
  const { data, error, loading } = useApi(async () => {
    const [profile, interests, myInterests] = await Promise.all([
      api.get("/api/profiles/me"),
      api.get("/api/interests"),
      api.get("/api/profiles/me/interests"),
    ]);
    return { profile, interests, myInterests };
  });

  const [form, setForm] = useState(null);
  const [selectedInterests, setSelectedInterests] = useState(new Set());
  const [avatarKey, setAvatarKey] = useState(null);
  const [status, setStatus] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!data?.profile) return;
    const p = data.profile;
    setForm({
      display_name: p.display_name,
      bio: p.bio || "",
      community_id: p.community_id || "",
      show_attending: p.show_attending,
      open_to_help: p.open_to_help,
    });
    setSelectedInterests(new Set(data.myInterests.interest_ids));
    setAvatarKey(p.avatar_key);
  }, [data]);

  if (loading || !form) return <div className="org centered muted">Loading…</div>;
  if (error)
    return (
      <div className="org narrow">
        <div className="alert">{error}</div>
      </div>
    );

  const set = (key) => (e) => {
    const value = e.target.type === "checkbox" ? e.target.checked : e.target.value;
    setForm((f) => ({ ...f, [key]: value }));
  };

  function toggleInterest(id) {
    setSelectedInterests((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  async function onAvatarPick(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setStatus(null);
    const formData = new FormData();
    formData.append("file", file);
    try {
      const updated = await api.upload("/api/profiles/me/avatar", formData);
      setAvatarKey(updated.avatar_key);
      setStatus("Avatar updated.");
    } catch (err) {
      setStatus(err.message);
    }
  }

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setStatus(null);
    try {
      await api.patch("/api/profiles/me", {
        ...form,
        community_id: form.community_id || null,
      });
      await api.put("/api/profiles/me/interests", {
        interest_ids: [...selectedInterests],
      });
      setStatus("Saved.");
    } catch (err) {
      setStatus(err.message);
    } finally {
      setSaving(false);
    }
  }

  const imgSrc = avatarUrl(avatarKey);

  return (
    <div className="org narrow">
      <span className="kicker">Yours to tend</span>
      <h1>Your profile</h1>
      <form className="card" onSubmit={save} style={{ marginTop: "20px" }}>
        {status && <div className="muted">{status}</div>}
        <Field label="Display name">
          <input value={form.display_name} onChange={set("display_name")} required maxLength={80} />
        </Field>
        <Field label="Bio">
          <textarea value={form.bio} onChange={set("bio")} rows={3} maxLength={1000} />
        </Field>
        <Field label="Avatar" hint="JPEG, PNG or WebP, up to 2 MB.">
          <div className="row-actions">
            {imgSrc ? (
              <img className="avatar-img" src={imgSrc} alt="Your avatar" />
            ) : (
              <span className="avatar-initial">{initial(form.display_name)}</span>
            )}
            <input type="file" accept="image/jpeg,image/png,image/webp" onChange={onAvatarPick} />
          </div>
        </Field>
        <div className="field">
          <span className="field-label">Community</span>
          <CommunityPicker
            value={form.community_id}
            onChange={(id) => setForm((f) => ({ ...f, community_id: id }))}
          />
        </div>
        <div className="field">
          <span className="field-label">Interests</span>
          <span className="field-hint">Pick any that fit — we'll surface matching events.</span>
          <div className="chip-grid">
            {data.interests.map((interest) => (
              <button
                type="button"
                key={interest.id}
                className={selectedInterests.has(interest.id) ? "chip chip-on" : "chip"}
                onClick={() => toggleInterest(interest.id)}
              >
                {interest.name}
              </button>
            ))}
          </div>
        </div>
        <label className="checkbox">
          <input type="checkbox" checked={form.open_to_help} onChange={set("open_to_help")} />
          Open to helping neighbors
        </label>
        <label className="checkbox">
          <input type="checkbox" checked={form.show_attending} onChange={set("show_attending")} />
          Let connections see what I'm attending
        </label>
        <button type="submit" disabled={saving} style={{ alignSelf: "flex-start" }}>
          {saving ? "Saving…" : "Save changes"}
        </button>
      </form>
      <p className="muted">
        <Link to="/my-events">Your events</Link> ·{" "}
        <Link to="/blocks">Manage blocked users</Link>
      </p>
    </div>
  );
}
