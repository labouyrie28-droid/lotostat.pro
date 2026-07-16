import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";

const AuthCallback = () => {
  const navigate = useNavigate();
  const hasProcessed = useRef(false);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const hash = window.location.hash || "";
    const match = hash.match(/session_id=([^&]+)/);
    if (!match) {
      navigate("/", { replace: true });
      return;
    }
    const session_id = decodeURIComponent(match[1]);
    (async () => {
      try {
        const { data } = await api.post("/auth/session", { session_id });
        // Clear hash and navigate
        window.history.replaceState(null, "", "/dashboard");
        navigate("/dashboard", { replace: true, state: { user: data } });
      } catch {
        navigate("/", { replace: true });
      }
    })();
  }, [navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#050507]">
      <div className="text-center">
        <div className="w-10 h-10 border-2 border-amber-400/40 border-t-amber-400 rounded-full animate-spin mx-auto mb-4" />
        <div className="text-xs uppercase tracking-[0.3em] text-zinc-500">Connexion en cours…</div>
      </div>
    </div>
  );
};

export default AuthCallback;
