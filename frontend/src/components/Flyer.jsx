import { forwardRef } from "react";
import { QRCodeSVG } from "qrcode.react";
import { kindLabel } from "../lib/eventKinds.js";

// The printable flyer.
//
// Deliberately built from nothing but text, our own CSS, and a QR code drawn as
// inline SVG. No <img>, no background-image, no cross-origin asset of any kind —
// html2canvas taints the canvas the moment it meets one, and a tainted canvas
// exports as a blank rectangle. The fonts are self-hosted for the same reason
// (see the @font-face block in organic.css).
//
// Fixed pixel dimensions rather than a responsive layout: this is a piece of
// paper, not a screen. A5 at 150dpi is 874x1240, which prints cleanly at A5 or
// scales down to half a sheet of A4 without resampling artefacts.
export const FLYER_WIDTH = 874;
export const FLYER_HEIGHT = 1240;

function formatDate(iso) {
  return new Date(iso).toLocaleDateString([], {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

function formatTime(iso) {
  return new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

const Flyer = forwardRef(function Flyer({ event, copy, url }, ref) {
  // The templated fallback's first option uses the title as the headline, which
  // would print the same words twice — once big, once in the "What" row. Drop
  // the row in that case rather than shipping a flyer that looks like a bug.
  const titleIsHeadline =
    copy.headline.trim().toLowerCase() === event.title.trim().toLowerCase();

  return (
    <div className="flyer" ref={ref} style={{ width: FLYER_WIDTH, height: FLYER_HEIGHT }}>
      <div className="flyer-top">
        <span className="flyer-kicker">{kindLabel(event.kind)}</span>
        {/* The AI copy. Everything below it is the event's real data — kept
            visually separate so a reader can tell the pitch from the facts. */}
        <h1 className="flyer-headline">{copy.headline}</h1>
        <p className="flyer-blurb">{copy.blurb}</p>
      </div>

      <div className="flyer-rule" />

      <div className="flyer-facts">
        {!titleIsHeadline && (
          <div className="flyer-fact">
            <span className="flyer-fact-label">What</span>
            <span className="flyer-fact-value">{event.title}</span>
          </div>
        )}
        <div className="flyer-fact">
          <span className="flyer-fact-label">When</span>
          <span className="flyer-fact-value">
            {formatDate(event.starts_at)}
            <br />
            {formatTime(event.starts_at)}
            {event.ends_at ? ` – ${formatTime(event.ends_at)}` : ""}
          </span>
        </div>
        <div className="flyer-fact">
          <span className="flyer-fact-label">Where</span>
          <span className="flyer-fact-value">
            {event.address || event.neighborhood || "Nearby"}
          </span>
        </div>
        {event.host_name && (
          <div className="flyer-fact">
            <span className="flyer-fact-label">Who</span>
            <span className="flyer-fact-value">{event.host_name}</span>
          </div>
        )}
      </div>

      <div className="flyer-foot">
        <div className="flyer-qr">
          {/* SVG, not the canvas renderer: html2canvas rasterises inline SVG
              reliably, while a <canvas> inside the captured tree comes out
              blank often enough to matter. */}
          <QRCodeSVG value={url} size={190} level="M" marginSize={2} />
        </div>
        <div className="flyer-foot-words">
          <strong>Scan to see the details</strong>
          <span>or visit {url.replace(/^https?:\/\//, "")}</span>
          <span className="flyer-brand">Ours — neighbors, in person</span>
        </div>
      </div>
    </div>
  );
});

export default Flyer;
