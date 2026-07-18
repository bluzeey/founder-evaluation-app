import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Upload, FileText, Loader2, Search } from "lucide-react";
import { api } from "@/lib/api";

export default function ApplicationNew() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    company: "",
    name: "",
    email: "",
    linkedin_url: "",
    github_url: "",
  });
  const [researching, setResearching] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const update = (field: keyof typeof form, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleResearch = async () => {
    if (!form.name.trim()) {
      setError("Enter a founder name first");
      return;
    }
    setResearching(true);
    setError(null);
    try {
      const founder = await api.createFounder({
        name: form.name,
        email: form.email || `${form.name.toLowerCase().replace(/\s+/g, ".")}@example.com`,
        current_company: form.company,
        linkedin_url: form.linkedin_url,
        github_url: form.github_url,
        auto_score: true,
      });
      navigate(`/founders/${founder.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Research failed");
    } finally {
      setResearching(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim() || !form.email.trim()) {
      setError("Name and email are required");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const founder = await api.createFounder({
        name: form.name,
        email: form.email,
        current_company: form.company,
        linkedin_url: form.linkedin_url,
        github_url: form.github_url,
        auto_score: true,
      });
      navigate(`/founders/${founder.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Submission failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold text-ink">Inbound application</h1>
      <form onSubmit={handleSubmit} className="panel space-y-5">
        <div>
          <label className="label mb-1.5 block">Company name</label>
          <input
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            placeholder="Acme Inc"
            value={form.company}
            onChange={(e) => update("company", e.target.value)}
          />
        </div>
        <div>
          <label className="label mb-1.5 block">Founder name</label>
          <input
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            placeholder="Jane Doe"
            value={form.name}
            onChange={(e) => update("name", e.target.value)}
          />
        </div>
        <div>
          <label className="label mb-1.5 block">Email</label>
          <input
            type="email"
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            placeholder="jane@acme.example"
            value={form.email}
            onChange={(e) => update("email", e.target.value)}
          />
        </div>
        <div>
          <label className="label mb-1.5 block">LinkedIn URL</label>
          <input
            type="url"
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            placeholder="https://linkedin.com/in/janedoe"
            value={form.linkedin_url}
            onChange={(e) => update("linkedin_url", e.target.value)}
          />
        </div>
        <div>
          <label className="label mb-1.5 block">GitHub URL</label>
          <input
            type="url"
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            placeholder="https://github.com/janedoe"
            value={form.github_url}
            onChange={(e) => update("github_url", e.target.value)}
          />
        </div>
        <div className="rounded-lg border-2 border-dashed border-slate-300 p-8 text-center">
          <Upload className="mx-auto mb-2 text-slate-400" size={32} />
          <p className="text-sm text-slate-600">Drop pitch deck here or click to upload.</p>
          <p className="mt-1 text-xs text-slate-400">PDF, PPTX supported</p>
        </div>

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <div className="flex gap-3">
          <button
            type="button"
            onClick={handleResearch}
            disabled={researching || !form.name.trim()}
            className="flex flex-1 items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            {researching ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
            {researching ? "Researching…" : "Research & preview"}
          </button>
          <button
            type="submit"
            disabled={submitting || !form.name.trim() || !form.email.trim()}
            className="flex flex-1 items-center justify-center rounded-lg bg-action py-2.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {submitting ? <Loader2 size={16} className="animate-spin" /> : "Submit application"}
          </button>
        </div>
      </form>

      <div className="panel">
        <div className="mb-3 flex items-center gap-2 text-sm font-medium text-ink">
          <FileText size={16} /> Ingestion preview
        </div>
        <p className="text-xs text-slate-500">
          On submit, the system queues a background Celery worker to research LinkedIn/GitHub,
          extract claims, and convert findings into scored evidence with source locators and trust
          status.
        </p>
      </div>
    </div>
  );
}
