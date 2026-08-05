import { useEffect, useRef } from "react";
import {
  MapContainer,
  TileLayer,
  Marker,
  Tooltip,
  ZoomControl,
  useMap,
  useMapEvents,
} from "react-leaflet";
import { useNavigate } from "react-router-dom";
import L from "leaflet";
import { tagIcon } from "../lib/tagIcons.js";
import { kindLabel } from "../lib/eventKinds.js";
import { categoryShort } from "../lib/noticeCategories.js";

// Markers: a circle whose border color is the event kind (green gathering /
// orange help) with the tag's emoji in the middle — so one pin conveys both.
// Using divIcon sidesteps the classic Leaflet-with-bundlers broken-image-path
// problem entirely.
//
// The visible circle is an *inner* <span>, not the icon element itself: Leaflet
// positions the icon element with its own `transform: translate3d(...)`, so
// scaling it on hover (in CSS) would clobber that and fling the pin to the
// map's origin. Scaling the inner span leaves Leaflet's transform alone.
//
// Icons are cached by "kind|tagSlug" so panning/re-rendering reuses them
// instead of allocating a fresh divIcon per marker every render.
const iconCache = new Map();

// Notice pins are deliberately a different shape as well as a different colour:
// a small rounded square with an ⓘ, so nobody mistakes an informational notice
// for something they can turn up to. Shape survives colour-blindness; colour
// alone would not.
let noticeIcon;
function pinIconForNotice() {
  if (!noticeIcon) {
    noticeIcon = L.divIcon({
      className: "pin-wrap",
      html: '<span class="pin pin-notice"><span class="pin-emoji">ⓘ</span></span>',
      iconSize: [24, 24],
      iconAnchor: [12, 12],
    });
  }
  return noticeIcon;
}

function pinIcon(kind, tagSlug) {
  const key = `${kind}|${tagSlug || ""}`;
  let icon = iconCache.get(key);
  if (!icon) {
    const suffix =
      kind === "help_request" ? "help" : kind === "volunteer_work" ? "volunteer" : "gathering";
    icon = L.divIcon({
      className: "pin-wrap",
      html: `<span class="pin pin-${suffix}"><span class="pin-emoji">${tagIcon(tagSlug)}</span></span>`,
      iconSize: [30, 30],
      iconAnchor: [15, 15],
    });
    iconCache.set(key, icon);
  }
  return icon;
}

function formatWhen(iso) {
  return new Date(iso).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDistance(m) {
  return m < 1000 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(1)} km`;
}

// How far in "fly to this event" lands: close enough to read the street it's on.
const FOCUS_ZOOM = 17;

// Measures how much of the map the floating list panel covers, and returns the
// pixel offset needed to put a pin in the *visible* part rather than the
// geometric centre of the container.
//
// Measured from the live element rather than hardcoded, because the panel is a
// 358px column on desktop and a bottom sheet on mobile — reading the DOM means
// one code path covers both, and it can't drift out of sync with the CSS.
function panelOffset(mapEl) {
  const panel = document.querySelector(".map-panel");
  if (!panel || !mapEl) return { x: 0, y: 0 };

  const map = mapEl.getBoundingClientRect();
  const box = panel.getBoundingClientRect();
  if (!box.width || !box.height) return { x: 0, y: 0 };

  // A sheet spanning most of the width occludes from the bottom; anything
  // narrower is the side column and occludes from the left.
  if (box.width > map.width * 0.8) {
    const covered = Math.max(0, map.bottom - box.top);
    return { x: 0, y: covered / 2 };
  }
  const covered = Math.max(0, box.right - map.left);
  return { x: -covered / 2, y: 0 };
}

// Flies to whichever event the sidebar asked for and pops its tooltip open.
//
// `focus` carries a sequence number as well as an id: clicking the same row
// twice should fly there twice, and a bare id wouldn't change between renders.
function FocusFlyer({ focus, events, markerRefs }) {
  const map = useMap();
  const lastSeq = useRef(0);

  useEffect(() => {
    if (!focus || focus.seq === lastSeq.current) return;
    lastSeq.current = focus.seq;

    const target = events.find((e) => e.id === focus.id);
    if (!target?.location) return;

    // Shift the centre so the panel isn't sitting on top of the pin. Done in
    // projected pixels at the destination zoom, then converted back, which is
    // the only way to express "200px west of here" as a coordinate.
    const offset = panelOffset(map.getContainer());
    const point = map.project([target.location.lat, target.location.lng], FOCUS_ZOOM);
    const center = map.unproject(
      L.point(point.x + offset.x, point.y + offset.y),
      FOCUS_ZOOM,
    );

    map.flyTo(center, FOCUS_ZOOM, { duration: 0.9 });

    // Open the tooltip once the flight lands — during the animation Leaflet is
    // still repositioning, and a tooltip opened mid-flight drifts.
    const marker = markerRefs.current[focus.id];
    if (marker) {
      map.once("moveend", () => marker.openTooltip());
    }
  }, [focus, events, map, markerRefs]);

  return null;
}

// Lives inside MapContainer so it can use the map hooks. Lifts the map
// instance up on mount and reports when the user finishes panning/zooming.
function MapBridge({ onReady, onMoveEnd }) {
  const map = useMap();
  useEffect(() => {
    onReady(map);
  }, [map, onReady]);
  useMapEvents({ moveend: () => onMoveEnd?.() });
  return null;
}

export default function MapView({
  center,
  events,
  notices = [],
  focus = null,
  onReady,
  onMoveEnd,
}) {
  const navigate = useNavigate();
  // Keyed by event id so FocusFlyer can open the right tooltip after landing.
  const markerRefs = useRef({});

  return (
    <MapContainer
      center={center}
      zoom={14}
      className="map"
      scrollWheelZoom
      zoomControl={false}
    >
      {/* Top-right so it clears the floating list panel on the left. */}
      <ZoomControl position="topright" />
      {/* Standard OpenStreetMap tiles — the familiar, clear base. A light warm
          tint (see .leaflet-tile in styles.css) nudges it toward the app's
          earthy palette without muddying the detail. */}
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <MapBridge onReady={onReady} onMoveEnd={onMoveEnd} />
      <FocusFlyer focus={focus} events={events} markerRefs={markerRefs} />
      {events.map((ev) => (
        <Marker
          key={ev.id}
          position={[ev.location.lat, ev.location.lng]}
          icon={pinIcon(ev.kind, ev.tag_slug)}
          ref={(marker) => {
            if (marker) markerRefs.current[ev.id] = marker;
            else delete markerRefs.current[ev.id];
          }}
          eventHandlers={{ click: () => navigate(`/events/${ev.id}`) }}
        >
          {/* Hover: a quick peek. Shows on mouseover, hides on mouseout.
              Clicking the pin goes straight to the event's page. */}
          <Tooltip direction="top" offset={[0, -14]} opacity={1} className="pin-tip">
            <strong>{ev.title}</strong>
            <div className="muted">
              {kindLabel(ev.kind)}
              {ev.tag_name && ` · ${ev.tag_name}`} · {formatWhen(ev.starts_at)}
              {ev.distance_m != null && ` · ${formatDistance(ev.distance_m)}`}
            </div>
            {ev.status !== "open" && <div className="muted">{ev.status}</div>}
          </Tooltip>
        </Marker>
      ))}
      {/* Informational notice pins. Rendered after the event markers so a
          notice never sits on top of something you could actually attend. */}
      {notices.map((n) => (
        <Marker
          key={n.id}
          position={[n.location.lat, n.location.lng]}
          icon={pinIconForNotice()}
          eventHandlers={{ click: () => navigate(`/board/${n.id}`) }}
        >
          <Tooltip direction="top" offset={[0, -12]} opacity={1} className="pin-tip">
            <strong>{n.title}</strong>
            <div className="muted">
              Notice · {categoryShort(n.category)}
              {n.place_hint && ` · ${n.place_hint}`}
            </div>
          </Tooltip>
        </Marker>
      ))}
    </MapContainer>
  );
}
