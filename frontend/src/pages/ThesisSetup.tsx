import { useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { api } from "@/lib/api";

export default function ThesisSetup() {
  const [saved, setSaved] = useState(false);
  const [form, setForm] = useState({
    name: "",
    sectors: "",
    stages: "",
    geographies: "",
    check_size_min: "250000",
    check_size_max: "1500000",
    risk_appetite: "moderate",
  });

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    await api.createThesis({
      ...form,
      sectors: form.sectors.split(",").map((s) => s.trim()).filter(Boolean),
      stages: form.stages.split(",").map((s) => s.trim()).filter(Boolean),
      geographies: form.geographies.split(",").map((s) => s.trim()).filter(Boolean),
      check_size_min: Number(form.check_size_min),
      check_size_max: Number(form.check_size_max),
    });
    setSaved(true);
  }

  return (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
      <div className="lg:col-span-1">
        <h1 className="mb-2 text-2xl font-bold text-ink">Investment thesis</h1>
        <p className="text-sm text-slate-600">
          Configure the mandate that surfaces and screens opportunities. This is a versioned object.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6 lg:col-span-2">
        <div className="panel space-y-5">
          <div>
            <label className="label mb-1.5 block">Fund / Thesis name</label>
            <input
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-action focus:outline-none"
              placeholder="e.g. Early-stage B2B SaaS"
            />
          </div>

          <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
            <div>
              <label className="label mb-1.5 block">Sectors (comma separated)</label>
              <input
                value={form.sectors}
                onChange={(e) => setForm({ ...form, sectors: e.target.value })}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-action focus:outline-none"
                placeholder="B2B SaaS, AI Infrastructure"
              />
            </div>
            <div>
              <label className="label mb-1.5 block">Stages</label>
              <input
                value={form.stages}
                onChange={(e) => setForm({ ...form, stages: e.target.value })}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-action focus:outline-none"
                placeholder="pre-seed, seed"
              />
            </div>
            <div>
              <label className="label mb-1.5 block">Geographies</label>
              <input
                value={form.geographies}
                onChange={(e) => setForm({ ...form, geographies: e.target.value })}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-action focus:outline-none"
                placeholder="India, Europe"
              />
            </div>
            <div>
              <label className="label mb-1.5 block">Risk appetite</label>
              <select
                value={form.risk_appetite}
                onChange={(e) => setForm({ ...form, risk_appetite: e.target.value })}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-action focus:outline-none"
              >
                <option value="conservative">Conservative</option>
                <option value="moderate">Moderate</option>
                <option value="aggressive">Aggressive</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-5">
            <div>
              <label className="label mb-1.5 block">Check size min</label>
              <input
                type="number"
                value={form.check_size_min}
                onChange={(e) => setForm({ ...form, check_size_min: e.target.value })}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-action focus:outline-none"
              />
            </div>
            <div>
              <label className="label mb-1.5 block">Check size max</label>
              <input
                type="number"
                value={form.check_size_max}
                onChange={(e) => setForm({ ...form, check_size_max: e.target.value })}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-action focus:outline-none"
              />
            </div>
          </div>

          <div className="flex items-center justify-between pt-2">
            <button
              type="submit"
              className="rounded-lg bg-action px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-700"
            >
              Save thesis version
            </button>
            {saved && (
              <span className="flex items-center gap-1.5 text-sm font-medium text-verified">
                <CheckCircle2 size={16} /> Saved
              </span>
            )}
          </div>
        </div>
      </form>
    </div>
  );
}
