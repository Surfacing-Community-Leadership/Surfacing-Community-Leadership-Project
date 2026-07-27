import { useNavigate } from "react-router-dom";
import { api } from "../api/client.js";
import EventForm from "../components/EventForm.jsx";

export default function CreateEvent() {
  const navigate = useNavigate();

  async function create(payload) {
    const created = await api.post("/api/events", payload);
    navigate(`/events/${created.id}`);
  }

  return (
    <div className="org narrow">
      <span className="kicker">Start something</span>
      <h1>Host an event</h1>
      <div style={{ marginTop: "20px" }}>
        <EventForm submitLabel="Create event" onSubmit={create} enforceFutureStart />
      </div>
    </div>
  );
}
