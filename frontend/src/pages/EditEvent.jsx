import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";
import { useAuth } from "../auth/AuthContext.jsx";
import EventForm from "../components/EventForm.jsx";

// Converts a stored UTC ISO string into the local "YYYY-MM-DDTHH:MM" a
// datetime-local input expects, so the form shows the host their own timezone.
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

  if (loading) return <div className="centered muted">Loading…</div>;
  if (error) return <div className="alert">{error}</div>;
  if (event.host_id !== user.id) {
    return <div className="alert">Only the host can edit this event.</div>;
  }

  const initial = {
    kind: event.kind,
    title: event.title,
    description: event.description || "",
    location: event.location, // { lat, lng }
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
    <div className="narrow">
      <h1>Edit {event.kind === "help_request" ? "help request" : "event"}</h1>
      <EventForm initial={initial} submitLabel="Save changes" onSubmit={save} lockKind />
    </div>
  );
}
