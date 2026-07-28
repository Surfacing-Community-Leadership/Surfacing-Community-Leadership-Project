import { api } from "../api/client.js";
import { useApi } from "../hooks/useApi.js";

// A neighbor's track record: the tier they've reached plus the three counts
// behind it. Every number is backed by something that can't be self-declared —
// hosting a real event, self-confirming with a written reflection, or being
// thanked by the person you helped. Help *received* is deliberately not shown:
// it says nothing about trustworthiness and would discourage asking.
export default function TrustBadge({ userId, compact = false }) {
  const { data, loading } = useApi(
    () => api.get(`/api/profiles/${userId}/trust`),
    [userId],
  );

  if (loading || !data) return null;

  if (compact) {
    return (
      <span className="trust-inline">
        {data.verified && <span className="trust-verified">✓ Verified</span>}
        <span className="trust-tier">{data.tier}</span>
      </span>
    );
  }

  return (
    <div className="trust-card">
      <div className="trust-head">
        <span className="trust-tier">{data.tier}</span>
        {data.verified && <span className="trust-verified">✓ Verified</span>}
      </div>
      <dl className="trust-counts">
        <div>
          <dt>Hosted</dt>
          <dd>{data.hosted}</dd>
        </div>
        <div>
          <dt>Attended</dt>
          <dd>{data.attended}</dd>
        </div>
        <div>
          <dt>Helped</dt>
          <dd>{data.helped}</dd>
        </div>
      </dl>
      <p className="trust-note">
        Counts come from events they hosted, attendances they confirmed, and
        neighbors who said thanks.
      </p>
    </div>
  );
}
