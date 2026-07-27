import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";
import { useAuth } from "../auth/AuthContext.jsx";
import EventForm from "../components/EventForm.jsx";

function isoToLocal(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return new Date(d - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

export default function EditEvent() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { data: event, error, loading } = useApi(() => api.get(`/api/events/${id}`), [id]);

  if (loading) return <div className="org centered muted">Loading…</div>;
  if (error)
    return (
      <div className="org narrow">
        <div className="alert">{error}</div>
      </div>
    );
  if (event.host_id !== user.id) {
    return (
      <div className="org narrow">
        <div className="alert">Only the host can edit this event.</div>
      </div>
    );
  }

  const initial = {
    kind: event.kind,
    title: event.title,
    description: event.description || "",
    location: event.location,
    address: event.address || "",
    startsAt: isoToLocal(event.starts_at),
    endsAt: isoToLocal(event.ends_at),
    visibility: event.visibility,
    capacity: event.capacity ?? "",
    tagId: event.tag_id || "",
  };

  async function save(payload) {
    await api.patch(`/api/events/${id}`, payload);
    navigate(`/events/${id}`);
  }

  return (
    <div className="org narrow">
      <span className="kicker">Editing</span>
      <h1>Edit {event.kind === "help_request" ? "help request" : "event"}</h1>
      <div style={{ marginTop: "20px" }}>
        <EventForm initial={initial} submitLabel="Save changes" onSubmit={save} lockKind />
      </div>
    </div>
  );
}
