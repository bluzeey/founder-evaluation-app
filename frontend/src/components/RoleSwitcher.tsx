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
    <div className="flex flex-col gap-2">
      <div className="label hidden lg:block">Role</div>
      <div className="flex flex-col gap-1">
        {ROLES.map((r) => (
          <button
            key={r.value}
            onClick={() => setRole(r.value)}
            title={r.description}
            className={`rounded-sm px-2 py-1.5 text-left text-xs font-sans font-medium transition ${
              state.user.role === r.value
                ? "bg-ink text-paper"
                : "text-ink/70 hover:bg-concrete/10 hover:text-ink"
            }`}
          >
            <span className="block truncate">{r.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

export default RoleSwitcher;
