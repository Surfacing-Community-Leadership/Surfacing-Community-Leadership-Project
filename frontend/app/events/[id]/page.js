// Server-rendered public event page: GET /api/events/{id}.
// Rendered server-side (not client-only) so links shared outside the app — e.g. a QR code on a
// flyer — resolve to real content for search engines, link previews, and people without accounts.
export default async function EventPage({ params }) {
  return null;
}
