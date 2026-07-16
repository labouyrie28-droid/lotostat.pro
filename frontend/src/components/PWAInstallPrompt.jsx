import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Download, X } from "lucide-react";

/**
 * Small floating banner that appears once the browser fires `beforeinstallprompt`,
 * inviting the user to install the PWA. Persists dismissal in localStorage.
 */
export const PWAInstallPrompt = () => {
  const [deferred, setDeferred] = useState(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const dismissed = localStorage.getItem("pwa-install-dismissed");
    if (dismissed === "1") return;

    const onPrompt = (e) => {
      e.preventDefault();
      setDeferred(e);
      setVisible(true);
    };
    window.addEventListener("beforeinstallprompt", onPrompt);
    return () => window.removeEventListener("beforeinstallprompt", onPrompt);
  }, []);

  const install = async () => {
    if (!deferred) return;
    deferred.prompt();
    const { outcome } = await deferred.userChoice;
    if (outcome === "accepted") {
      setVisible(false);
    }
    setDeferred(null);
  };

  const dismiss = () => {
    localStorage.setItem("pwa-install-dismissed", "1");
    setVisible(false);
  };

  if (!visible) return null;

  return (
    <div
      data-testid="pwa-install-prompt"
      className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 max-w-sm w-[calc(100%-2rem)] rounded-2xl border border-white/10 bg-[#0d0d10]/95 backdrop-blur-xl shadow-2xl p-4 flex items-center gap-3 animate-in slide-in-from-bottom-4"
    >
      <div className="w-9 h-9 rounded-full bg-amber-500/15 border border-amber-500/40 flex items-center justify-center shrink-0">
        <Download className="w-4 h-4 text-amber-400" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-heading font-semibold text-white">Installer LotoStat.Pro</div>
        <div className="text-[11px] text-zinc-500">Accès rapide depuis ton écran d'accueil</div>
      </div>
      <Button
        data-testid="pwa-install-btn"
        size="sm"
        onClick={install}
        className="rounded-full bg-amber-400 hover:bg-amber-300 text-black font-semibold h-8 px-3 text-xs"
      >
        Installer
      </Button>
      <button
        data-testid="pwa-dismiss-btn"
        onClick={dismiss}
        className="text-zinc-500 hover:text-white transition-colors"
        aria-label="Fermer"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
};
