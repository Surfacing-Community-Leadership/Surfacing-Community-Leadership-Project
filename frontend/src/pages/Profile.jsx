import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, avatarUrl } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";
import Field from "../components/Field.jsx";
import CommunityPicker from "../components/CommunityPicker.jsx";

// The signed-in user's own editable profile. This is the one place to manage
// everything the first-run "quick setup" (Onboarding) collects — community,
// interests, and preferences — so there's no separate page to visit later.
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
  // Avatar lives in its own state (not `form`) so uploading it can update the
  // preview without re-seeding — and discarding — the user's unsaved edits.
  const [avatarKey, setAvatarKey] = useState(null);
  const [status, setStatus] = useState(null);
  const [saving, setSaving] = useState(false);

  // Seed the form once the profile and interests arrive.
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

  if (loading || !form) return <div className="centered muted">Loading…</div>;
  if (error) return <div className="alert">{error}</div>;

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
      // Update only the preview from the response — don't reload the whole
      // profile, which would reseed the form and lose unsaved edits.
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
      // Profile fields and interests live behind two endpoints (PATCH the
      // profile, PUT the full interest set), same as first-run onboarding.
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

  return (
    <div className="narrow">
      <h1>Your profile</h1>
      <form className="card" onSubmit={save}>
        {status && <div className="muted">{status}</div>}
        <Field label="Display name">
          <input value={form.display_name} onChange={set("display_name")} required maxLength={80} />
        </Field>
        <Field label="Bio">
          <textarea value={form.bio} onChange={set("bio")} rows={3} maxLength={1000} />
        </Field>
        <Field label="Avatar" hint="JPEG, PNG or WebP, up to 2 MB.">
          <div className="row-actions">
            {avatarUrl(avatarKey) ? (
              <img className="avatar-img" src={avatarUrl(avatarKey)} alt="Your avatar" />
            ) : (
              <span className="avatar-lg">{avatarKey || "🙂"}</span>
            )}
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={onAvatarPick}
            />
          </div>
        </Field>
        {/* Community and Interests use div.field (not <Field>, which wraps a
            <label>) — nesting the picker/chip buttons inside a label is
            invalid and forwards stray clicks. */}
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
        <button type="submit" disabled={saving}>
          {saving ? "Saving…" : "Save"}
        </button>
      </form>
      <p className="muted">
        <Link to="/my-events">Your events</Link> ·{" "}
        <Link to="/blocks">Manage blocked users</Link>
      </p>
    </div>
  );
}
