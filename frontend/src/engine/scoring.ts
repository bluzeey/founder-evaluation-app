import type { DriverAssessment, DriverKey } from "@/domain/types";
import { DRIVER_WEIGHTS } from "@/config/weights";

export function calculateQueuePriority(drivers: DriverAssessment[]): number {
  const map = Object.fromEntries(drivers.map((d) => [d.key, d.score])) as Record<DriverKey, number>;
  let total = 0;
  for (const key of Object.keys(DRIVER_WEIGHTS) as DriverKey[]) {
    total += (map[key] ?? 50) * DRIVER_WEIGHTS[key];
  }
  return Math.round(total * 10) / 10;
}

export function getDriver(drivers: DriverAssessment[], key: DriverKey): DriverAssessment | undefined {
  return drivers.find((d) => d.key === key);
}
