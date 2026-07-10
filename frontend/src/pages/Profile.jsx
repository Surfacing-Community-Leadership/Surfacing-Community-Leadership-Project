import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";
import Field from "../components/Field.jsx";

// The signed-in user's own editable profile.
export default function Profile() {
  const { data, error, loading } = useApi(async () => {
    const [profile, communities] = await Promise.all([
      api.get("/api/profiles/me"),
      api.get("/api/communities"),
    ]);
    return { profile, communities };
  });

  const [form, setForm] = useState(null);
  const [status, setStatus] = useState(null);
  const [saving, setSaving] = useState(false);

  // Seed the form once the profile arrives.
  useEffect(() => {
    if (data?.profile) {
      const p = data.profile;
      setForm({
        display_name: p.display_name,
        bio: p.bio || "",
        avatar_key: p.avatar_key || "",
        community_id: p.community_id || "",
        show_attending: p.show_attending,
        open_to_help: p.open_to_help,
      });
    }
  }, [data]);

  if (loading || !form) return <div className="centered muted">Loading…</div>;
  if (error) return <div className="alert">{error}</div>;

  const set = (key) => (e) => {
    const value = e.target.type === "checkbox" ? e.target.checked : e.target.value;
    setForm((f) => ({ ...f, [key]: value }));
  };

  async function save(e) {
    e.preventDefault();
    setSaving(true);
    setStatus(null);
    try {
      await api.patch("/api/profiles/me", {
        ...form,
        community_id: form.community_id || null,
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
        <Field label="Avatar" hint="An emoji or short label for now.">
          <input value={form.avatar_key} onChange={set("avatar_key")} />
        </Field>
        <Field label="Community">
          <select value={form.community_id} onChange={set("community_id")}>
            <option value="">None</option>
            {data.communities.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </Field>
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
        Want to update your interests? <Link to="/onboarding">Redo the quick setup</Link>. ·{" "}
        <Link to="/blocks">Manage blocked users</Link>
      </p>
    </div>
  );
}
