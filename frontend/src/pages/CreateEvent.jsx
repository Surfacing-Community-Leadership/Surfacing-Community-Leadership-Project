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
    <div className="narrow">
      <h1>Create</h1>
      <EventForm submitLabel="Create" onSubmit={create} enforceFutureStart />
    </div>
  );
}
