import { useEffect, useState } from "react";
import { calculateTimeRemaining } from "@/engine/stateMachine";

export function TimeRemaining({ deadline }: { deadline: string }) {
  const [duration, setDuration] = useState(() => calculateTimeRemaining(deadline));
  useEffect(() => {
    const id = setInterval(() => setDuration(calculateTimeRemaining(deadline)), 1000);
    return () => clearInterval(id);
  }, [deadline]);

  const color =
    duration.percentRemaining > 50
      ? "text-verified"
      : duration.percentRemaining > 25
      ? "text-uncertain"
      : "text-contradiction";

  return (
    <div className="flex items-center gap-3">
      <div className="h-2 w-24 overflow-hidden rounded-full bg-concrete/20">
        <div
          className={`h-full ${duration.isExpired ? "bg-concrete" : duration.percentRemaining > 25 ? "bg-action" : "bg-contradiction"}`}
          style={{ width: `${duration.percentRemaining}%` }}
        />
      </div>
      <span className={`text-xs font-mono font-semibold tabular ${color}`}>
        {duration.isExpired
          ? "SLA expired"
          : `${duration.hours.toString().padStart(2, "0")}:${duration.minutes.toString().padStart(2, "0")}:${duration.seconds
              .toString()
              .padStart(2, "0")} remaining`}
      </span>
    </div>
  );
}

export default TimeRemaining;
