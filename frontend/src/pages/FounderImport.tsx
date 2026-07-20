import { useState } from "react";
import { Link } from "react-router-dom";
import { AlertCircle, CheckCircle2, FileUp, Loader2, Upload } from "lucide-react";
import { api } from "@/api/client";
import type { ApiError, BackendCsvImportResult } from "@/types/backend";

export default function FounderImport() {
  const [file, setFile] = useState<File | null>(null);
  const [review, setReview] = useState<BackendCsvImportResult | null>(null);
  const [committed, setCommitted] = useState<BackendCsvImportResult | null>(null);
  const [loadingStep, setLoadingStep] = useState<"dry-run" | "commit" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleDryRun = async () => {
    if (!file) return;
    setLoadingStep("dry-run");
    setError(null);
    setCommitted(null);
    try {
      const result = await api.founders.importCsv(file, { dryRun: true });
      setReview(result);
    } catch (err) {
      setError((err as ApiError).message || "Dry run failed");
    } finally {
      setLoadingStep(null);
    }
  };

  const handleCommit = async () => {
    if (!file) return;
    setLoadingStep("commit");
    setError(null);
    try {
      const result = await api.founders.importCsv(file, { dryRun: false });
      setCommitted(result);
      setReview(result);
    } catch (err) {
      setError((err as ApiError).message || "Commit failed");
    } finally {
      setLoadingStep(null);
    }
  };

  const canCommit = Boolean(review && review.rows_invalid === 0 && review.rows_valid > 0 && file);

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="space-y-2">
        <div className="label">Internal tools</div>
        <h1 className="text-2xl font-bold text-ink">Founder CSV Import</h1>
        <p className="text-sm text-concrete">
          Hidden admin page for validating and importing founder screening CSV data. Imported founders use manual enrichment and do not auto-launch background research jobs.
        </p>
        <Link to="/discovery" className="text-sm text-action hover:underline">
          Back to Discovery
        </Link>
      </div>

      <div className="panel space-y-4">
        <div className="flex items-center gap-3">
          <div className="rounded-md bg-action/10 p-2 text-action">
            <FileUp size={18} />
          </div>
          <div>
            <div className="font-semibold text-ink">Upload a founder import CSV</div>
            <div className="text-sm text-concrete">
              Step 1 runs dry validation. Step 2 commits the same file into founders, screening profiles, opportunities, and import audit tables.
            </div>
          </div>
        </div>

        <label className="flex cursor-pointer items-center gap-3 rounded-sm border border-dashed border-concrete/30 bg-manila/20 px-4 py-4 text-sm text-ink hover:bg-manila/30">
          <Upload size={18} className="text-action" />
          <div className="flex-1">
            <div className="font-medium">{file ? file.name : "Choose CSV file"}</div>
            <div className="text-xs text-concrete">UTF-8 CSV up to 10 MB. Required fields are validated server-side.</div>
          </div>
          <input
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(event) => {
              const nextFile = event.target.files?.[0] ?? null;
              setFile(nextFile);
              setReview(null);
              setCommitted(null);
              setError(null);
            }}
          />
        </label>

        <div className="flex flex-wrap gap-2">
          <button
            onClick={handleDryRun}
            disabled={!file || loadingStep !== null}
            className="flex items-center gap-2 rounded-sm border border-concrete/30 bg-paper px-3 py-2 text-sm font-medium text-ink hover:bg-manila/40 disabled:opacity-50"
          >
            {loadingStep === "dry-run" ? <Loader2 size={16} className="animate-spin" /> : <FileUp size={16} />}
            Dry run
          </button>
          <button
            onClick={handleCommit}
            disabled={!canCommit || loadingStep !== null}
            className="flex items-center gap-2 rounded-sm bg-action px-3 py-2 text-sm font-medium text-paper hover:bg-action-dark disabled:opacity-50"
          >
            {loadingStep === "commit" ? <Loader2 size={16} className="animate-spin" /> : <Upload size={16} />}
            Commit import
          </button>
        </div>

        {error && (
          <div className="rounded-sm border border-contradiction/30 bg-contradiction/10 p-3 text-sm text-contradiction">
            <AlertCircle size={16} className="mr-1 inline" />
            {error}
          </div>
        )}
      </div>

      {review && (
        <div className="panel space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="font-display text-lg font-semibold text-ink">
                {review.dry_run ? "Dry-run review" : "Committed import result"}
              </h2>
              <p className="text-sm text-concrete">Review counts, warnings, and row errors before committing.</p>
            </div>
            {committed && (
              <div className="rounded-sm border border-verified/30 bg-verified/10 px-3 py-2 text-sm text-verified">
                <CheckCircle2 size={16} className="mr-1 inline" />
                Import committed
              </div>
            )}
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Rows received" value={review.rows_received} />
            <StatCard label="Rows valid" value={review.rows_valid} />
            <StatCard label="Rows invalid" value={review.rows_invalid} />
            <StatCard label="Import ID" value={review.import_id || "—"} />
            <StatCard label="Founders to create" value={review.founders_to_create} />
            <StatCard label="Founders to update" value={review.founders_to_update} />
            <StatCard label="Profiles to create" value={review.profiles_to_create} />
            <StatCard label="Profiles to update" value={review.profiles_to_update} />
          </div>

          {review.warnings.length > 0 && (
            <section className="space-y-2">
              <div className="label">Warnings</div>
              <div className="space-y-2">
                {review.warnings.map((warning) => (
                  <div key={warning} className="rounded-sm border border-uncertain/30 bg-uncertain/10 px-3 py-2 text-sm text-ink/80">
                    {warning}
                  </div>
                ))}
              </div>
            </section>
          )}

          {review.errors.length > 0 && (
            <section className="space-y-2">
              <div className="label">Row errors</div>
              <div className="overflow-hidden rounded-sm border border-contradiction/20">
                <table className="w-full text-left text-sm">
                  <thead className="bg-contradiction/10 text-contradiction">
                    <tr>
                      <th className="px-3 py-2 font-medium">Row</th>
                      <th className="px-3 py-2 font-medium">Record ID</th>
                      <th className="px-3 py-2 font-medium">Field</th>
                      <th className="px-3 py-2 font-medium">Message</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-concrete/10 bg-paper">
                    {review.errors.map((rowError, index) => (
                      <tr key={`${rowError.row_number}-${rowError.external_record_id ?? index}`}>
                        <td className="px-3 py-2">{rowError.row_number}</td>
                        <td className="px-3 py-2">{rowError.external_record_id || "—"}</td>
                        <td className="px-3 py-2">{rowError.field || "—"}</td>
                        <td className="px-3 py-2">{rowError.message}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          {review.dry_run && review.rows_invalid === 0 && (
            <div className="rounded-sm border border-verified/30 bg-verified/10 p-3 text-sm text-verified">
              Dry run passed. Commit stays manual and will not queue 150 enrichment jobs.
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-sm border border-concrete/20 bg-paper p-3">
      <div className="label">{label}</div>
      <div className="mt-1 font-display text-xl font-bold text-ink">{value}</div>
    </div>
  );
}
