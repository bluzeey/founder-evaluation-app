import { Routes, Route, Link, Navigate } from "react-router-dom";
import { AppProvider } from "@/store/appContext";
import { RoleSwitcher } from "@/components/RoleSwitcher";
import Discovery from "@/pages/Discovery";
import Apply from "@/pages/Apply";
import Cases from "@/pages/Cases";
import DealRoom from "@/pages/DealRoom";
import Decisions from "@/pages/Decisions";
import Thesis from "@/pages/Thesis";
import Validation from "@/pages/Validation";

function App() {
  return (
    <AppProvider>
      <div className="min-h-screen bg-canvas text-ink">
        <header className="sticky top-0 z-20 border-b border-slate-200 bg-canvas/90 backdrop-blur">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
            <Link to="/" className="flex items-center gap-2">
              <span className="text-xl font-bold text-ink">Seed Engine</span>
              <span className="rounded bg-ink px-1.5 py-0.5 text-[10px] font-bold text-white">DEMO</span>
            </Link>
            <nav className="flex items-center gap-6 text-sm font-medium text-slate-600">
              <Link to="/discovery" className="hover:text-ink">Discovery</Link>
              <Link to="/apply" className="hover:text-ink">Apply</Link>
              <Link to="/cases" className="hover:text-ink">Cases</Link>
              <Link to="/decisions" className="hover:text-ink">Decisions</Link>
              <Link to="/thesis" className="hover:text-ink">Thesis</Link>
              <Link to="/validation" className="hover:text-ink">Validation</Link>
              <RoleSwitcher />
            </nav>
          </div>
        </header>

        <main className="mx-auto max-w-7xl px-6 py-8">
          <Routes>
            <Route path="/" element={<Navigate to="/discovery" replace />} />
            <Route path="/discovery" element={<Discovery />} />
            <Route path="/apply" element={<Apply />} />
            <Route path="/cases" element={<Cases />} />
            <Route path="/cases/:caseId" element={<DealRoom />} />
            <Route path="/decisions" element={<Decisions />} />
            <Route path="/thesis" element={<Thesis />} />
            <Route path="/validation" element={<Validation />} />
          </Routes>
        </main>
      </div>
    </AppProvider>
  );
}

export default App;
