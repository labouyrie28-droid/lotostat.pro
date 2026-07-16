import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import { Loader2, Mail, Bell, Calendar, Send, AlertTriangle, Trophy } from "lucide-react";

const strategies = [
  { key: "hot", label: "Chauds" },
  { key: "cold", label: "Froids" },
  { key: "balanced", label: "Équilibrée" },
  { key: "weighted_random", label: "Aléatoire pondérée" },
];

const Alerts = () => {
  const [nextDraw, setNextDraw] = useState(null);
  const [prefs, setPrefs] = useState(null);
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendingResults, setSendingResults] = useState(false);

  const load = async () => {
    try {
      const [nd, pf] = await Promise.all([
        api.get("/alerts/next-draw"),
        api.get("/alerts/prefs"),
      ]);
      setNextDraw(nd.data);
      setPrefs(pf.data);
    } catch (e) { toast.error("Erreur de chargement"); }
  };
  useEffect(() => { load(); }, []);

  const savePrefs = async (updates) => {
    setSaving(true);
    const next = { ...prefs, ...updates };
    setPrefs(next);
    try {
      await api.post("/alerts/prefs", next);
      toast.success("Préférences enregistrées");
    } catch { toast.error("Impossible d'enregistrer"); }
    finally { setSaving(false); }
  };

  const sendNow = async () => {
    setSending(true);
    try {
      const { data } = await api.post("/alerts/send", {
        email: prefs.email,
        strategy: prefs.strategy,
        grids_count: prefs.grids_count,
      });
      toast.success(`Email envoyé à ${data.to}`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Envoi échoué");
    } finally { setSending(false); }
  };

  const sendResultsNow = async () => {
    setSendingResults(true);
    try {
      const { data } = await api.post("/alerts/send-results", {});
      const net = data.total_won - data.total_cost;
      toast.success(
        `Résultats envoyés à ${data.to} · ${data.grids_count} grille(s) · ${net >= 0 ? "+" : ""}${net.toFixed(2)}€`,
      );
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Envoi échoué");
    } finally { setSendingResults(false); }
  };

  if (!nextDraw || !prefs) {
    return <div className="flex items-center justify-center py-24"><Loader2 className="w-6 h-6 animate-spin text-zinc-500" /></div>;
  }

  return (
    <div className="space-y-8" data-testid="alerts-page">
      <header className="space-y-3">
        <div className="text-xs uppercase tracking-[0.3em] text-zinc-500">Alertes email</div>
        <h1 className="font-heading text-4xl font-bold tracking-tighter">Recevez vos grilles</h1>
      </header>

      {!nextDraw.resend_configured && (
        <Card className="p-4 border-amber-500/30 bg-amber-500/[0.04] flex items-start gap-3">
          <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
          <div className="text-xs text-zinc-300 leading-relaxed">
            <strong className="text-amber-400">Service email non configuré.</strong> Ajoutez une clé
            <code className="mx-1 px-1.5 py-0.5 rounded bg-black/40 text-amber-400">RESEND_API_KEY</code>
            dans <code className="text-zinc-400">backend/.env</code> (obtenez-la sur
            <a href="https://resend.com" target="_blank" rel="noreferrer" className="underline mx-1">resend.com</a>).
          </div>
        </Card>
      )}

      <Card className="p-8 border-white/5 bg-[#0d0d10]">
        <div className="flex items-center gap-3 mb-4">
          <Calendar className="w-5 h-5 text-amber-400" />
          <div>
            <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">Prochain tirage</div>
            <div className="font-heading text-2xl font-semibold capitalize" data-testid="next-draw-date">
              {nextDraw.day_name} {nextDraw.next_draw_date}
            </div>
          </div>
        </div>
      </Card>

      <Card className="p-8 border-white/5 bg-[#0d0d10] space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Bell className="w-4 h-4 text-amber-400" />
              <h2 className="font-heading text-xl font-semibold">Alerte automatique</h2>
            </div>
            <p className="text-xs text-zinc-500">Reçoit un email à 12h chaque jour de tirage (lundi, mercredi, samedi).</p>
          </div>
          <Switch
            data-testid="alert-enabled-switch"
            checked={prefs.enabled}
            onCheckedChange={(v) => savePrefs({ enabled: v })}
            disabled={saving || !nextDraw.resend_configured}
          />
        </div>

        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 mb-2">Email de réception</div>
            <div className="flex items-center gap-2 bg-black/30 border border-white/10 rounded-lg px-3 py-2">
              <Mail className="w-4 h-4 text-zinc-500" />
              <Input
                data-testid="alert-email-input"
                value={prefs.email || ""}
                onChange={(e) => setPrefs({ ...prefs, email: e.target.value })}
                onBlur={() => savePrefs({ email: prefs.email })}
                className="bg-transparent border-none focus-visible:ring-0 h-8 p-0"
              />
            </div>
          </div>

          <div>
            <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 mb-2">Nombre de grilles</div>
            <div className="flex items-center gap-2">
              {[1, 3, 5, 10].map((n) => (
                <button
                  key={n}
                  data-testid={`alert-count-${n}`}
                  onClick={() => savePrefs({ grids_count: n })}
                  className={`w-10 h-10 rounded-full border font-mono-tab text-sm transition-colors ${
                    prefs.grids_count === n ? "bg-white text-black border-white" : "border-white/10 text-zinc-400 hover:text-white"
                  }`}
                >{n}</button>
              ))}
            </div>
          </div>
        </div>

        <div>
          <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 mb-2">Stratégie</div>
          <div className="flex flex-wrap gap-2">
            {strategies.map((s) => (
              <button
                key={s.key}
                data-testid={`alert-strategy-${s.key}`}
                onClick={() => savePrefs({ strategy: s.key })}
                className={`px-4 py-2 rounded-full text-xs border transition-colors ${
                  prefs.strategy === s.key
                    ? "bg-amber-400 text-black border-amber-400 font-semibold"
                    : "border-white/10 text-zinc-400 hover:text-white hover:border-white/30"
                }`}
              >{s.label}</button>
            ))}
          </div>
        </div>
      </Card>

      <Card className="p-8 border-white/5 bg-[#0d0d10]">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h2 className="font-heading text-xl font-semibold mb-1">Envoi manuel</h2>
            <p className="text-xs text-zinc-500">Reçoit tes grilles tout de suite avec les paramètres ci-dessus.</p>
          </div>
          <Button
            data-testid="send-now-btn"
            disabled={sending || !nextDraw.resend_configured}
            onClick={sendNow}
            className="rounded-full bg-amber-400 hover:bg-amber-300 text-black font-semibold h-11 px-6"
          >
            {sending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Send className="w-4 h-4 mr-2" />}
            M'envoyer les grilles maintenant
          </Button>
        </div>
      </Card>

      <Card className="p-8 border-white/5 bg-[#0d0d10] space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Trophy className="w-4 h-4 text-amber-400" />
              <h2 className="font-heading text-xl font-semibold">Résultat automatique</h2>
            </div>
            <p className="text-xs text-zinc-500 max-w-lg leading-relaxed">
              Reçois par email le lendemain de chaque tirage (mardi/jeudi/dimanche à 9h)
              le récapitulatif de tes grilles sauvegardées : rang, gains théoriques, ROI.
            </p>
          </div>
          <Switch
            data-testid="results-enabled-switch"
            checked={prefs.results_enabled || false}
            onCheckedChange={(v) => savePrefs({ results_enabled: v })}
            disabled={saving || !nextDraw.resend_configured}
          />
        </div>

        <div className="pt-4 border-t border-white/5 flex items-center justify-between flex-wrap gap-4">
          <div className="text-xs text-zinc-500">
            Tester en envoyant le récapitulatif du <span className="text-amber-400">dernier tirage connu</span>.
          </div>
          <Button
            data-testid="send-results-now-btn"
            disabled={sendingResults || !nextDraw.resend_configured}
            onClick={sendResultsNow}
            variant="outline"
            className="rounded-full border-amber-500/40 text-amber-400 hover:bg-amber-500/10 hover:text-amber-300 h-10 px-5"
          >
            {sendingResults ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Trophy className="w-4 h-4 mr-2" />}
            Envoyer le récap maintenant
          </Button>
        </div>
      </Card>
    </div>
  );
};

export default Alerts;
