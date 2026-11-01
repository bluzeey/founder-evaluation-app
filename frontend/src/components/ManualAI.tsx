import { useState, useRef, useEffect } from "react";
import { Loader2, Play } from "lucide-react";
import { useAdaptivePolling } from "@/hooks/useAdaptivePolling";
import type { QueuedResponse } from "@/types/backend";

const API_BASE = "/api";

type TaskStatus = { status: string; error?: string | null };
type AIReadiness = { enabled: boolean; mode: "manual" };
const SETUP_PENDING = "AI setup pending";

function useAIReadiness() {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const active = useRef(false);
  const checking = useRef(false);
  const refresh = async () => {
    if (checking.current) return;
    checking.current = true;
    try {
      const config = await manualAIRequest<AIReadiness>("/v1/ai/config");
      if (active.current) setEnabled(config.enabled === true && config.mode === "manual");
    } catch {
      if (active.current) setEnabled(false);
    } finally {
      checking.current = false;
    }
  };
  useEffect(() => {
    active.current = true;
    void refresh();
    return () => { active.current = false; };
  }, []);
  // This only reads local readiness. It never starts or retries paid work.
  useAdaptivePolling(refresh, 30000);
  return { enabled, setEnabled };
}

// Same owner session cookie as the parent's authenticated API client.
export async function manualAIRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { ...init, credentials: "include" });
  if (response.status === 401 && typeof window !== "undefined") {
    window.dispatchEvent(new Event("founderos:auth-expired"));
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || "AI request failed. Please try again.");
  return body as T;
}

export function ManualModeIndicator() {
  return <p className="text-xs text-concrete">AI manual mode · runs only when you press a Run AI button.</p>;
}

export function ManualAIAction({ label, run, disabled, onComplete }: {
  label: string;
  run: () => Promise<QueuedResponse>;
  disabled?: boolean;
  onComplete?: () => void | Promise<void>;
}) {
  const { enabled, setEnabled } = useAIReadiness();
  const [busy, setBusy] = useState(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const startedAt = useRef(0);
  const submitting = useRef(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);

  const start = async () => {
    if (submitting.current || disabled || enabled !== true) return;
    submitting.current = true;
    setBusy(true);
    setError("");
    setMessage("Queuing AI…");
    try {
      const result = await run();
      if (!result.task_id) throw new Error("No AI task was returned. Please try again.");
      if (!mounted.current) return;
      startedAt.current = Date.now();
      setTaskId(result.task_id);
      setMessage("AI queued. Waiting for a worker…");
    } catch (err) {
      if (!mounted.current) return;
      setMessage("");
      const detail = (err as Error).message || "Could not start AI";
      if (detail === SETUP_PENDING) setEnabled(false);
      setError(detail === SETUP_PENDING ? "" : detail);
      setBusy(false);
      submitting.current = false;
    }
  };

  useAdaptivePolling(async () => {
    if (!taskId) return;
    if (Date.now() - startedAt.current > 30 * 60 * 1000) {
      setTaskId(null);
      setBusy(false);
      submitting.current = false;
      setMessage("");
      setError("Status tracking timed out. Check the existing job before starting another run.");
      return;
    }
    try {
      const result = await manualAIRequest<TaskStatus>(`/v1/ai/tasks/${encodeURIComponent(taskId)}`);
      if (!mounted.current) return;
      if (result.status === "queued" || result.status === "running") {
        setMessage(result.status === "running" ? "AI running…" : "AI queued. Waiting for a worker…");
        setError("");
        return;
      }
      setTaskId(null);
      setBusy(false);
      submitting.current = false;
      const failed = result.status === "failed" || result.status === "skipped_manual_required";
      setError(failed ? result.error || "AI did not complete. You can retry manually." : "");
      setMessage(failed ? "" : result.status === "skipped" ? "AI finished; no new evidence was available." : "AI completed.");
      try { await onComplete?.(); } catch { setError("AI finished, but the page could not refresh. Reload to see the result."); }
    } catch (err) {
      if (mounted.current) setError((err as Error).message || "Could not read AI progress");
    }
  }, taskId ? 3000 : 0);

  return (
    <div className="space-y-1">
      <button type="button" onClick={start} disabled={disabled || busy || enabled !== true}
        className="inline-flex items-center gap-2 rounded-sm bg-action px-3 py-2 text-sm font-medium text-paper disabled:opacity-50">
        {busy ? <Loader2 size={14} className="animate-spin" /> : <Play size={14} />}
        {label}
      </button>
      {enabled !== true && <p role="status" className="text-xs text-concrete">
        {enabled === null ? "Checking AI setup…" : SETUP_PENDING}
      </p>}
      {message && <p role="status" className="text-xs text-concrete">{message}</p>}
      {error && <p role="alert" className="text-xs text-contradiction">{error}</p>}
    </div>
  );
}

export function ManualDeckExtraction({ opportunityId, founderId, onComplete }: {
  opportunityId: string; founderId?: string; onComplete?: () => void | Promise<void>;
}) {
  const [file, setFile] = useState<File | null>(null);
  return (
    <div className="space-y-2 rounded-sm border border-concrete/20 p-3">
      <p className="text-sm text-concrete">Optional: use AI to extract structured claims from a deck.</p>
      <input aria-label="Deck for manual AI extraction" type="file" accept=".pdf,.docx,.txt,.md"
        onChange={(event) => setFile(event.target.files?.[0] || null)} />
      <ManualAIAction label="Run AI deck extraction" disabled={!file} onComplete={onComplete} run={async () => {
        if (!file) throw new Error("Choose a deck first");
        const form = new FormData();
        form.append("file", file);
        const query = founderId ? `?founder_id=${encodeURIComponent(founderId)}` : "";
        return manualAIRequest<QueuedResponse>(`/v1/opportunities/${encodeURIComponent(opportunityId)}/deck/extract${query}`,
          { method: "POST", body: form });
      }} />
    </div>
  );
}
