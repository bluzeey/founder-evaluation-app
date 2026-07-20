import { Routes, Route, Link, Navigate, useLocation } from "react-router-dom";
import { AppProvider } from "@/store/appContext";
import {
  Inbox,
  Sparkles,
  FolderOpen,
  Gavel,
  SlidersHorizontal,
  Zap,
} from "lucide-react";
import Discovery from "@/pages/Discovery";
import Recommended from "@/pages/Recommended";
import Cases from "@/pages/Cases";
import DealRoom from "@/pages/DealRoom";
import Decisions from "@/pages/Decisions";
import Thesis from "@/pages/Thesis";
import Sourcing from "@/pages/Sourcing";
import FounderImport from "@/pages/FounderImport";

const NAV = [
  { path: "/discovery", label: "Discovery", icon: Inbox },
  { path: "/recommended", label: "Recommended", icon: Sparkles },
  { path: "/sourcing", label: "Sourcing", icon: Zap },
  { path: "/cases", label: "Cases", icon: FolderOpen },
  { path: "/decisions", label: "Decisions", icon: Gavel },
  { path: "/thesis", label: "Thesis", icon: SlidersHorizontal },
];

function App() {
  const location = useLocation();

  return (
    <AppProvider>
      <div className="flex min-h-screen bg-canvas">
        {/* File rail */}
        <aside className="sticky top-0 z-20 flex h-screen w-16 flex-col border-r border-concrete/20 bg-manila shadow-paper lg:w-56">
          <div className="flex h-16 items-center justify-center gap-2.5 border-b border-concrete/20 px-4 lg:justify-start">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-action shadow-paper">
              <span className="font-display text-lg font-bold leading-none text-paper">F</span>
            </div>
            <span className="hidden font-display text-lg font-bold tracking-tight text-ink lg:block">
              Founder<span className="text-action">OS</span>
            </span>
          </div>

          <nav className="flex flex-1 flex-col gap-1 py-4">
            {NAV.map((item) => {
              const Icon = item.icon;
              const active = location.pathname.startsWith(item.path);
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`file-tab ${active ? "file-tab-active" : ""}`}
                >
                  <Icon size={18} />
                  <span className="hidden lg:inline">{item.label}</span>
                </Link>
              );
            })}
          </nav>

        </aside>

        {/* Main workspace */}
        <div className="flex flex-1 flex-col">
          <header className="flex h-16 items-center justify-between border-b border-concrete/20 bg-paper/80 px-6 backdrop-blur">
            <div className="text-xs font-mono uppercase tracking-widest text-concrete">
              {NAV.find((n) => location.pathname.startsWith(n.path))?.label || "Workspace"}
            </div>
            <div className="text-xs text-concrete">Live backend data</div>
          </header>

          <main className="flex-1 p-6 lg:p-8">
            <Routes>
              <Route path="/" element={<Navigate to="/discovery" replace />} />
              <Route path="/discovery" element={<Discovery />} />
              <Route path="/recommended" element={<Recommended />} />
              <Route path="/founders/import" element={<FounderImport />} />
              <Route path="/sourcing" element={<Sourcing />} />
              <Route path="/cases" element={<Cases />} />
              <Route path="/cases/:caseId" element={<DealRoom />} />
              <Route path="/decisions" element={<Decisions />} />
              <Route path="/thesis" element={<Thesis />} />
            </Routes>
          </main>
        </div>
      </div>
    </AppProvider>
  );
}

export default App;
