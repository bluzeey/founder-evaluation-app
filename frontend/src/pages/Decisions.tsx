import { Link } from "react-router-dom";

export default function Decisions() {
  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <div className="label mb-1">Partner Decision Queue</div>
          <h1 className="text-2xl font-bold text-ink">$100K checks on the desk</h1>
          <p className="text-sm text-concrete">One decision every 4–5 days. 24h SLA.</p>
        </div>
      </div>

      <div className="panel py-12 text-center text-sm text-concrete">
        <p className="mb-4">The partner decision queue will show live opportunities ready for review.</p>
        <p>
          Open a case from{" "}
          <Link to="/cases" className="text-action hover:underline">
            Cases
          </Link>{" "}
          to evaluate it.
        </p>
      </div>
    </div>
  );
}
