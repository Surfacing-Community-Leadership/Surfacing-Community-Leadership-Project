import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";
import { kindLabel } from "../lib/eventKinds.js";

// The guide: a few plain questions that end with the ordinary Create Event form
// already filled in.
//
// Three things about this page are deliberate.
//
// The opening message is written here, in the client. It costs nothing, it
// appears instantly, and it means the model is never called until somebody has
// actually said something — a page nobody engages with spends no quota at all.
//
// The transcript lives in sessionStorage, not on the server. A refresh keeps
// your place; closing the tab throws it away. Nothing about an idea somebody
// thought better of is stored in our database.
//
// And the draft panel is a *preview*, not a form. Nothing here is submitted.
// Pressing "Use this" carries the draft to /events/new, where the normal form —
// with the normal map, the normal validation and the normal button — is what
// actually creates the event.

const STORAGE_KEY = "ours.guide.transcript";

const OPENING = {
  person:
    "Tell me what you have in mind and I'll help you write it up. It can be small — " +
    "a few neighbours on a stoop counts.",
  organization:
    "Tell me what you're planning and I'll help you write it up, whether that's " +
    "something open to the neighbourhood or a shift you need volunteers for.",
};

const STARTERS = {
  person: [
    "I'd like to meet my neighbours",
    "I need a hand with something",
    "There's something on my street I'd like to sort out",
  ],
  organization: [
    "We'd like to meet the neighbourhood",
    "We need volunteers for a shift",
    "We're running something people can drop into",
  ],
};

function loadTranscript() {
  try {
    const saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "[]");
    return Array.isArray(saved) ? saved : [];
  } catch {
    return [];
  }
}

// Everything the draft panel knows how to show, in the order it reads.
function draftRows(draft) {
  return [
    ["Type", draft.kind ? kindLabel(draft.kind) : null],
    ["Title", draft.title],
    ["About", draft.description],
    ["You said, about when", draft.timing_hint],
    ["You said, about where", draft.place_hint],
    ["Room for", draft.capacity ? `${draft.capacity} people` : null],
  ].filter(([, value]) => value);
}

export default function GuidedStart() {
  const navigate = useNavigate();
  const { data: status, loading: statusLoading } = useApi(() =>
    api.get("/api/assistant/status")
  );
  const { data: profile } = useApi(() => api.get("/api/profiles/me"));
  const accountType = profile?.account_type === "organization" ? "organization" : "person";

  const [transcript, setTranscript] = useState(loadTranscript);
  const [draft, setDraft] = useState({});
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(false);
  const threadRef = useRef(null);

  useEffect(() => {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(transcript));
  }, [transcript]);

  // Keep the newest message in view as the conversation grows.
  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: "smooth" });
  }, [transcript, thinking]);

  const turnsLeft = status ? status.max_turns - transcript.length : 0;
  const canSend = !thinking && !done && turnsLeft > 1;

  async function send(text) {
    const message = text.trim();
    if (!message || !canSend) return;

    // Show what they said immediately; the server gets the same list.
    const withTheirs = [...transcript, { role: "you", text: message.slice(0, 600) }];
    setTranscript(withTheirs);
    setInput("");
    setError(null);
    setThinking(true);
    try {
      const result = await api.post("/api/assistant/turn", {
        transcript: withTheirs,
      });
      setTranscript([...withTheirs, { role: "guide", text: result.reply }]);
      setDraft(result.draft);
      if (result.ready || result.exhausted) setDone(true);
    } catch (err) {
      // Roll their message back out of the thread so the retry isn't a
      // duplicate, and say plainly that the form is still there.
      setTranscript(transcript);
      setInput(message);
      setError(err.message);
    } finally {
      setThinking(false);
    }
  }

  function handOver() {
    // The draft travels in router state, not in the URL: it is a couple of
    // paragraphs of someone's words, and it has no business in a browser
    // history entry or a shared link.
    sessionStorage.removeItem(STORAGE_KEY);
    navigate("/events/new", { state: { draft } });
  }

  function startOver() {
    sessionStorage.removeItem(STORAGE_KEY);
    setTranscript([]);
    setDraft({});
    setDone(false);
    setError(null);
  }

  if (statusLoading) return <div className="org centered muted">Loading…</div>;

  // No key configured, or today's budget is spent. Say so once and get out of
  // the way — the form has never needed this page.
  if (!status?.available) {
    return (
      <div className="org narrow">
        <span className="kicker">Start something</span>
        <h1>Let's talk it through</h1>
        <div className="card guide-unavailable">
          <p>
            The guide isn't available right now
            {status && status.remaining_today === 0 ? " — you've used it a lot today" : ""}.
            Nothing is lost: the form does everything the guide does, just with
            the questions all on one page.
          </p>
          <Link to="/events/new" className="btn">
            Go to the form →
          </Link>
        </div>
      </div>
    );
  }

  const rows = draftRows(draft);
  const hasDraft = rows.length > 0;

  return (
    <div className="org wide">
      <div className="page-head">
        <div>
          <span className="kicker">Start something</span>
          <h1>Let's talk it through</h1>
        </div>
        <Link to="/events/new" className="btn btn-secondary">
          Skip to the form
        </Link>
      </div>

      <div className="guide-layout">
        <div className="card guide-chat">
          <div className="guide-thread" ref={threadRef}>
            <p className="guide-msg guide-msg-them">{OPENING[accountType]}</p>
            {transcript.map((turn, i) => (
              <p
                key={i}
                className={turn.role === "you" ? "guide-msg guide-msg-you" : "guide-msg guide-msg-them"}
              >
                {turn.text}
              </p>
            ))}
            {thinking && (
              <p className="guide-msg guide-msg-them guide-thinking">Thinking…</p>
            )}
          </div>

          {error && <div className="alert">{error}</div>}

          {transcript.length === 0 && (
            <div className="guide-starters">
              {STARTERS[accountType].map((starter) => (
                <button
                  key={starter}
                  type="button"
                  className="chip"
                  onClick={() => send(starter)}
                  disabled={!canSend}
                >
                  {starter}
                </button>
              ))}
            </div>
          )}

          {done ? (
            <div className="guide-done">
              <p className="muted">
                That's enough to start with. You can change every word on the next
                page.
              </p>
              <div className="guide-done-actions">
                <button type="button" onClick={handOver} disabled={!hasDraft}>
                  Open the form with this →
                </button>
                <button type="button" className="secondary" onClick={startOver}>
                  Start over
                </button>
              </div>
            </div>
          ) : (
            <form
              className="guide-compose"
              onSubmit={(e) => {
                e.preventDefault();
                send(input);
              }}
            >
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Say a bit about it…"
                maxLength={600}
                disabled={!canSend}
                aria-label="Your message"
              />
              <button type="submit" disabled={!canSend || !input.trim()}>
                Send
              </button>
            </form>
          )}

          {turnsLeft <= 3 && turnsLeft > 1 && !done && (
            <p className="field-hint">
              A couple more messages and we'll move to the form.
            </p>
          )}
        </div>

        <aside className="card guide-draft">
          <h2>The draft so far</h2>
          {hasDraft ? (
            <>
              <dl className="guide-draft-rows">
                {rows.map(([label, value]) => (
                  <div key={label}>
                    <dt>{label}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>
              <p className="field-hint">
                Where it happens and when are set by you on the next page — the
                guide doesn't place pins or pick dates.
              </p>
              {!done && (
                <button type="button" className="secondary" onClick={handOver}>
                  Use this now →
                </button>
              )}
            </>
          ) : (
            <p className="muted">
              This fills in as we talk. Nothing here is posted until you say so.
            </p>
          )}
        </aside>
      </div>
    </div>
  );
}
