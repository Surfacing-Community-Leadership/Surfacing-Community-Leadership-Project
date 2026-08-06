import { Link, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";
import EventForm from "../components/EventForm.jsx";

// The only place an event is created. Arriving from the guide changes what the
// fields start out saying and nothing else — same form, same validation, same
// button, and the person still reads it before pressing anything.
export default function CreateEvent() {
  const navigate = useNavigate();
  const { state } = useLocation();
  const draft = state?.draft ?? null;

  // Only asked when we didn't come from the guide, so the guide's own page
  // never triggers a second status call.
  const { data: assistant } = useApi(
    () => (draft ? Promise.resolve(null) : api.get("/api/assistant/status")),
    [Boolean(draft)]
  );

  async function create(payload) {
    const created = await api.post("/api/events", payload);
    navigate(`/events/${created.id}`);
  }

  return (
    <div className="org narrow">
      <span className="kicker">Start something</span>
      <h1>Host an event</h1>

      {draft ? (
        <p className="guide-echo guide-echo-lead">
          Here's what we wrote together. Change anything — nothing is posted
          until you press the button at the bottom.
        </p>
      ) : (
        assistant?.available && (
          <p className="guide-offer">
            Not sure where to start?{" "}
            <Link to="/events/new/guide">Talk it through instead</Link> and come
            back with this filled in.
          </p>
        )
      )}

      <div style={{ marginTop: "20px" }}>
        <EventForm
          submitLabel="Create event"
          onSubmit={create}
          enforceFutureStart
          initial={
            draft
              ? {
                  kind: draft.kind ?? undefined,
                  title: draft.title ?? "",
                  description: draft.description ?? "",
                  capacity: draft.capacity ?? "",
                  tagSlug: draft.tag_slug ?? null,
                  durationMinutes: draft.duration_minutes ?? null,
                }
              : {}
          }
          // Words, not values — see the note on EventForm.
          hints={{ timing: draft?.timing_hint, place: draft?.place_hint }}
        />
      </div>
    </div>
  );
}
