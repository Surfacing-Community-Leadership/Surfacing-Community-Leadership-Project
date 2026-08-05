import { useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";
import Flyer, { FLYER_HEIGHT, FLYER_WIDTH } from "../components/Flyer.jsx";

// Make a printable flyer for an event you host.
//
// Two halves: ask the server for copy options (it calls Gemini; we never see a
// key), then render and export the flyer entirely in the browser. The export
// costs nothing on the server, which is the point — the only paid step is the
// one behind an explicit button press.

function slugify(text) {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 50);
}

export default function FlyerStudio() {
  const { id } = useParams();
  const flyerRef = useRef(null);

  // The event's real details come from the public endpoint on purpose: it is
  // exactly the set of fields a stranger reading the flyer will be able to see,
  // so the flyer can never promise something the QR code won't deliver.
  const { data: event, error, loading } = useApi(
    () => api.get(`/api/public/events/${id}`),
    [id],
  );

  const [copy, setCopy] = useState(null); // { options, generated, remaining_today }
  const [chosen, setChosen] = useState(0);
  const [asking, setAsking] = useState(false);
  const [askError, setAskError] = useState(null);
  const [exporting, setExporting] = useState(null); // "png" | "pdf" | null

  const publicUrl = `${window.location.origin}/e/${id}`;

  async function generate() {
    setAsking(true);
    setAskError(null);
    try {
      const result = await api.post(`/api/events/${id}/flyer-copy`);
      setCopy(result);
      setChosen(0);
    } catch (err) {
      // The server falls back to templated copy rather than failing, so an error
      // here means something structural — not signed in, not the host, a private
      // event, or the daily cap. Those are worth showing.
      setAskError(err.message);
    } finally {
      setAsking(false);
    }
  }

  async function exportFlyer(format) {
    if (!flyerRef.current) return;
    setExporting(format);
    // The preview shrinks the flyer with a CSS transform, and html2canvas
    // honours that transform — capturing while it's applied produced an 840px
    // image instead of 1748px, i.e. text rasterised at half size and then
    // enlarged. Neutralise the scale for the duration of the capture. The
    // wrapper is `overflow: hidden`, so nothing visibly jumps.
    const scaler = flyerRef.current.parentElement;
    const previousTransform = scaler?.style.transform ?? "";
    if (scaler) scaler.style.transform = "none";
    try {
      // Imported on demand: html2canvas and jsPDF are large, and nobody who
      // isn't making a flyer should pay for them on first page load.
      const [{ default: html2canvas }, { jsPDF }] = await Promise.all([
        import("html2canvas"),
        import("jspdf"),
      ]);

      // Make sure the self-hosted fonts are in before rasterising, or the
      // export lands on the Georgia fallback and the flyer looks wrong.
      if (document.fonts?.ready) await document.fonts.ready;

      const canvas = await html2canvas(flyerRef.current, {
        // 2x for print: at 1x the QR code and small type soften noticeably.
        scale: 2,
        width: FLYER_WIDTH,
        height: FLYER_HEIGHT,
        backgroundColor: "#f5ead8",
        // No remote fetching at all — everything in this tree is same-origin,
        // and leaving it enabled would only add a way to fail.
        useCORS: false,
        allowTaint: false,
        logging: false,
      });

      const name = `flyer-${slugify(event.title)}`;
      if (format === "png") {
        const link = document.createElement("a");
        link.download = `${name}.png`;
        link.href = canvas.toDataURL("image/png");
        link.click();
      } else {
        // Portrait A5, and the image is placed at exactly the page size so
        // there is no white margin to trim off before printing.
        const pdf = new jsPDF({ orientation: "portrait", unit: "pt", format: "a5" });
        const w = pdf.internal.pageSize.getWidth();
        const h = pdf.internal.pageSize.getHeight();
        pdf.addImage(canvas.toDataURL("image/png"), "PNG", 0, 0, w, h);
        pdf.save(`${name}.pdf`);
      }
    } catch (err) {
      setAskError(`Couldn't export the flyer: ${err.message}`);
    } finally {
      if (scaler) scaler.style.transform = previousTransform;
      setExporting(null);
    }
  }

  if (loading) return <div className="org centered muted">Loading…</div>;
  if (error || !event)
    return (
      <div className="org narrow">
        <div className="alert">
          {error || "That event isn't available."} A flyer can only be made for a
          public or community event you host.
        </div>
        <Link className="btn btn-secondary" to="/my-events">
          Back to your events
        </Link>
      </div>
    );

  const selected = copy?.options?.[chosen];

  return (
    <div className="org wide">
      <div className="page-head">
        <div>
          <span className="kicker">{event.title}</span>
          <h1>Make a flyer</h1>
        </div>
        <Link className="btn btn-secondary" to={`/events/${id}`}>
          Back to the event
        </Link>
      </div>

      <p className="muted board-intro">
        A printable poster with a code people can scan. Print it, put it in a
        window, hand it to a neighbour who isn't on the app.
      </p>

      {askError && <div className="alert">{askError}</div>}

      {!copy ? (
        <div className="flyer-start">
          <h2>Write the words</h2>
          <p className="muted">
            We'll suggest a few headlines based on what you already wrote about
            this event. Nothing is invented — you pick the one you like, and every
            fact on the flyer comes from the event itself.
          </p>
          <button className="btn btn-primary" onClick={generate} disabled={asking}>
            {asking ? "Writing…" : "Suggest headlines"}
          </button>
        </div>
      ) : (
        <div className="flyer-layout">
          <div className="flyer-controls">
            <h2>Pick a headline</h2>
            {!copy.generated && (
              <p className="field-hint">
                Written from your own description this time. You can edit the
                event and try again for different wording.
              </p>
            )}
            <ul className="plain-list">
              {copy.options.map((option, i) => (
                <li key={i}>
                  <button
                    className={i === chosen ? "copy-option on" : "copy-option"}
                    onClick={() => setChosen(i)}
                    aria-pressed={i === chosen}
                  >
                    <strong>{option.headline}</strong>
                    <span>{option.blurb}</span>
                  </button>
                </li>
              ))}
            </ul>

            <div className="row-actions">
              <button
                className="btn btn-secondary"
                onClick={generate}
                disabled={asking || copy.remaining_today === 0}
              >
                {asking ? "Writing…" : "Try again"}
              </button>
            </div>
            <p className="field-hint">
              {copy.remaining_today} of {copy.daily_limit} suggestions left today.
            </p>

            <h2 className="flyer-export-head">Download it</h2>
            <div className="row-actions">
              <button
                className="btn btn-primary"
                onClick={() => exportFlyer("png")}
                disabled={exporting !== null}
              >
                {exporting === "png" ? "Making the image…" : "PNG image"}
              </button>
              <button
                className="btn btn-secondary"
                onClick={() => exportFlyer("pdf")}
                disabled={exporting !== null}
              >
                {exporting === "pdf" ? "Making the PDF…" : "PDF for printing"}
              </button>
            </div>
            <p className="field-hint">
              The PDF is A5 — half a sheet of A4, no margins to trim.
            </p>
          </div>

          {/* The real flyer, scaled down to fit the screen. The export captures
              the element at full size regardless of this preview transform. */}
          <div className="flyer-preview">
            <div
              className="flyer-scale"
              style={{
                width: FLYER_WIDTH,
                height: FLYER_HEIGHT,
                transform: `scale(${420 / FLYER_WIDTH})`,
              }}
            >
              {selected && (
                <Flyer ref={flyerRef} event={event} copy={selected} url={publicUrl} />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
