import { NavLink, Outlet, useNavigate, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import {
  LayoutDashboard, History, BarChart3, Flame, Grid3X3, Sparkles, TrendingUp, Search, Zap, Bookmark, Bell, Upload, LogOut, Sparkle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

const navItems = [
  { to: "/dashboard", end: true, icon: LayoutDashboard, label: "Vue d'ensemble" },
  { to: "/dashboard/history", icon: History, label: "Historique" },
  { to: "/dashboard/stats", icon: BarChart3, label: "Statistiques" },
  { to: "/dashboard/hot-cold", icon: Flame, label: "Chauds / Froids" },
  { to: "/dashboard/heatmap", icon: Grid3X3, label: "Heatmap" },
  { to: "/dashboard/generator", icon: Sparkles, label: "Générateur" },
  { to: "/dashboard/wheel", icon: Zap, label: "Système Réducteur" },
  { to: "/dashboard/backtest", icon: TrendingUp, label: "Backtest" },
  { to: "/dashboard/verify", icon: Search, label: "Vérif grille" },
  { to: "/dashboard/grids", icon: Bookmark, label: "Mes grilles" },
  { to: "/dashboard/alerts", icon: Bell, label: "Alertes email" },
  { to: "/dashboard/import", icon: Upload, label: "Données" },
];

const Dashboard = () => {
  const { user, setUser, loading, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [checking, setChecking] = useState(!user);

  useEffect(() => {
    if (location.state?.user) {
      setUser(location.state.user);
      setChecking(false);
      return;
    }
    if (loading) return;
    if (!user) {
      (async () => {
        try {
          const { data } = await api.get("/auth/me");
          setUser(data);
        } catch {
          navigate("/", { replace: true });
        } finally {
          setChecking(false);
        }
      })();
    } else {
      setChecking(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, user]);

  if (checking || loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-amber-400/40 border-t-amber-400 rounded-full animate-spin" />
      </div>
    );
  }
  if (!user) return null;

  return (
    <div className="min-h-screen bg-[#050507] text-white flex">
      {/* Sidebar */}
      <aside className="w-64 border-r border-white/5 bg-[#0a0a0c] flex flex-col shrink-0">
        <div className="px-6 py-5 border-b border-white/5">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-amber-500/15 border border-amber-500/40 flex items-center justify-center">
              <Sparkle className="w-4 h-4 text-amber-400" />
            </div>
            <div>
              <div className="font-heading font-bold tracking-tight">LotoStat<span className="text-amber-400">.</span>Pro</div>
              <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">Analytics</div>
            </div>
          </div>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              data-testid={`nav-${item.label.toLowerCase().replace(/[^a-z]/g, "-")}`}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors duration-200 ${
                  isActive
                    ? "bg-amber-400/10 text-amber-300 border border-amber-500/20"
                    : "text-zinc-400 hover:text-white hover:bg-white/[0.03] border border-transparent"
                }`
              }
            >
              <item.icon className="w-4 h-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-white/5">
          <div className="flex items-center gap-3 mb-3 px-2">
            {user.picture ? (
              <img src={user.picture} alt="" className="w-8 h-8 rounded-full border border-white/10" />
            ) : (
              <div className="w-8 h-8 rounded-full bg-white/10" />
            )}
            <div className="min-w-0 flex-1">
              <div className="text-xs font-medium truncate">{user.name}</div>
              <div className="text-[10px] text-zinc-500 truncate">{user.email}</div>
            </div>
          </div>
          <Button
            data-testid="logout-btn"
            variant="ghost"
            onClick={async () => { await logout(); toast.success("Déconnecté"); }}
            className="w-full justify-start gap-2 text-zinc-400 hover:text-white"
          >
            <LogOut className="w-4 h-4" /> Déconnexion
          </Button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 min-w-0 overflow-x-hidden">
        <div className="max-w-7xl mx-auto px-8 py-10">
          <Outlet />
        </div>
      </main>
    </div>
  );
};

export default Dashboard;
