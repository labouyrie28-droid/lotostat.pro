import "@/App.css";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import { AuthProvider } from "@/context/AuthContext";
import { Toaster } from "@/components/ui/sonner";

import Landing from "@/pages/Landing";
import AuthCallback from "@/pages/AuthCallback";
import Dashboard from "@/pages/Dashboard";
import Overview from "@/pages/views/Overview";
import History from "@/pages/views/History";
import Stats from "@/pages/views/Stats";
import HotCold from "@/pages/views/HotCold";
import Generator from "@/pages/views/Generator";
import MyGrids from "@/pages/views/MyGrids";
import DataImport from "@/pages/views/DataImport";

const AppRoutes = () => {
  const location = useLocation();
  // Synchronous check: catch OAuth callback before any other route
  if (location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/dashboard" element={<Dashboard />}>
        <Route index element={<Overview />} />
        <Route path="history" element={<History />} />
        <Route path="stats" element={<Stats />} />
        <Route path="hot-cold" element={<HotCold />} />
        <Route path="generator" element={<Generator />} />
        <Route path="grids" element={<MyGrids />} />
        <Route path="import" element={<DataImport />} />
      </Route>
    </Routes>
  );
};

function App() {
  return (
    <div className="App dark">
      <AuthProvider>
        <BrowserRouter>
          <AppRoutes />
          <Toaster
            theme="dark"
            position="top-right"
            toastOptions={{
              className: "!bg-[#0d0d10] !border-white/10 !text-white",
            }}
          />
        </BrowserRouter>
      </AuthProvider>
    </div>
  );
}

export default App;
