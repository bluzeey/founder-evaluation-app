import { Routes, Route, Link } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import ThesisSetup from "./pages/ThesisSetup";
import FounderProfile from "./pages/FounderProfile";
import ScoreExplorer from "./pages/ScoreExplorer";
import AssessmentSession from "./pages/AssessmentSession";
import OpportunityScreen from "./pages/OpportunityScreen";
import Sourcing from "./pages/Sourcing";
import ApplicationNew from "./pages/ApplicationNew";

function App() {
  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-canvas/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <Link to="/" className="flex items-center gap-2">
            <span className="text-xl font-bold text-ink">FounderOS</span>
            <span className="rounded bg-ink px-1.5 py-0.5 text-[10px] font-bold text-white">ALPHA</span>
          </Link>
          <nav className="flex gap-6 text-sm font-medium text-slate-600">
            <Link to="/" className="hover:text-ink">Dashboard</Link>
            <Link to="/onboarding/thesis" className="hover:text-ink">Thesis</Link>
            <Link to="/sourcing" className="hover:text-ink">Sourcing</Link>
            <Link to="/applications/new" className="hover:text-ink">Apply</Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-8">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/onboarding/thesis" element={<ThesisSetup />} />
          <Route path="/founders/:founderId" element={<FounderProfile />} />
          <Route path="/founders/:founderId/score" element={<ScoreExplorer />} />
          <Route path="/assessment/:founderId" element={<AssessmentSession />} />
          <Route path="/opportunities/:opportunityId/screen" element={<OpportunityScreen />} />
          <Route path="/sourcing" element={<Sourcing />} />
          <Route path="/applications/new" element={<ApplicationNew />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
