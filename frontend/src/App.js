import "@/App.css";
import React from "react";
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
import Backtest from "@/pages/views/Backtest";
import Heatmap from "@/pages/views/Heatmap";
import Alerts from "@/pages/views/Alerts";
import Verify from "@/pages/views/Verify";
import Wheel from "@/pages/views/Wheel";

const AppRoutes = () => {
  const location = useLocation();
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
        <Route path="heatmap" element={<Heatmap />} />
        <Route path="generator" element={<Generator />} />
        <Route path="backtest" element={<Backtest />} />
        <Route path="verify" element={<Verify />} />
        <Route path="wheel" element={<Wheel />} />
        <Route path="grids" element={<MyGrids />} />
        <Route path="alerts" element={<Alerts />} />
        <Route path="import" element={<DataImport />} />
      </Route>
    </Routes>
  );
};

/**
 * ErrorBoundary catches React DOM commit errors (e.g. insertBefore issues
 * caused by browser extensions like Chrome auto-translate, Google Translate,
 * or password managers that mutate the DOM). Instead of crashing the whole
 * app it re-mounts the tree.
 */
class RootErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }
  static getDerivedStateFromError() {
    return { hasError: true };
  }
  componentDidCatch(error, info) {
    // Log once. Auto-recover on next tick.
    // eslint-disable-next-line no-console
    console.warn("[Root recovery]", error?.message);
    setTimeout(() => this.setState({ hasError: false }), 50);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-[#050507]">
          <div className="text-xs uppercase tracking-[0.3em] text-zinc-500">Récupération…</div>
        </div>
      );
    }
    return this.props.children;
  }
}

function App() {
  return (
    <div className="App dark" translate="no" suppressHydrationWarning>
      <RootErrorBoundary>
        <AuthProvider>
          <BrowserRouter>
            <AppRoutes />
          </BrowserRouter>
        </AuthProvider>
      </RootErrorBoundary>
      {/* Toaster is OUTSIDE the router so it doesn't get re-mounted on route change */}
      <Toaster
        theme="dark"
        position="top-right"
        richColors={false}
        closeButton={false}
        toastOptions={{
          className: "!bg-[#0d0d10] !border-white/10 !text-white",
        }}
      />
    </div>
  );
}

export default App;
