import { Upload, FileText } from "lucide-react";

export default function ApplicationNew() {
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold text-ink">Inbound application</h1>
      <div className="panel space-y-5">
        <div>
          <label className="label mb-1.5 block">Company name</label>
          <input className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Acme Inc" />
        </div>
        <div>
          <label className="label mb-1.5 block">Founder name</label>
          <input className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="Jane Doe" />
        </div>
        <div>
          <label className="label mb-1.5 block">Email</label>
          <input type="email" className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" placeholder="jane@acme.example" />
        </div>
        <div className="rounded-lg border-2 border-dashed border-slate-300 p-8 text-center">
          <Upload className="mx-auto mb-2 text-slate-400" size={32} />
          <p className="text-sm text-slate-600">Drop pitch deck here or click to upload.</p>
          <p className="mt-1 text-xs text-slate-400">PDF, PPTX supported</p>
        </div>
        <button className="w-full rounded-lg bg-action py-2.5 text-sm font-medium text-white">Submit application</button>
      </div>

      <div className="panel">
        <div className="mb-3 flex items-center gap-2 text-sm font-medium text-ink">
          <FileText size={16} /> Ingestion preview
        </div>
        <p className="text-xs text-slate-500">
          After submission, the system will extract claims, source locations, and trust status transparently.
        </p>
      </div>
    </div>
  );
}
