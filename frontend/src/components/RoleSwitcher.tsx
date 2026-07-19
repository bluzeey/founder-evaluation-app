import { useApp } from "@/store/appContext";
import type { Role } from "@/domain/types";

const ROLES: { value: Role; label: string; description: string }[] = [
  { value: "ANALYST", label: "Analyst", description: "Screen, diligence, and source" },
  { value: "ASSOCIATE", label: "Associate", description: "Review spikes and write memo" },
  { value: "PARTNER", label: "Partner", description: "Make $100K decisions" },
];

export function RoleSwitcher() {
  const { state, setRole } = useApp();
  return (
    <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white p-1 shadow-sm">
      {ROLES.map((r) => (
        <button
          key={r.value}
          onClick={() => setRole(r.value)}
          title={r.description}
          className={`rounded-md px-3 py-1.5 text-xs font-semibold transition ${
            state.user.role === r.value
              ? "bg-ink text-white"
              : "text-slate-600 hover:bg-slate-100"
          }`}
        >
          {r.label}
        </button>
      ))}
    </div>
  );
}

export default RoleSwitcher;
