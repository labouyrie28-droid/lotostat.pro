import { useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LotteryBall } from "@/components/LotteryBall";
import { toast } from "sonner";
import { Loader2, Sparkles, Save, Flame, Snowflake, Scale, Shuffle } from "lucide-react";

const strategies = [
  { key: "hot", label: "Numéros chauds", desc: "Priorise les numéros les plus fréquents", icon: Flame, color: "red" },
  { key: "cold", label: "Numéros froids", desc: "Priorise les moins sortis (compensation)", icon: Snowflake, color: "sky" },
  { key: "balanced", label: "Équilibrée", desc: "2 chauds + 2 froids + 1 en retard", icon: Scale, color: "emerald" },
  { key: "weighted_random", label: "Aléatoire pondérée", desc: "Random pondéré par les fréquences", icon: Shuffle, color: "amber" },
];

const colorMap = {
  red: "border-red-500/40 hover:border-red-500 bg-red-500/[0.03]",
  sky: "border-sky-500/40 hover:border-sky-500 bg-sky-500/[0.03]",
  emerald: "border-emerald-500/40 hover:border-emerald-500 bg-emerald-500/[0.03]",
  amber: "border-amber-500/40 hover:border-amber-500 bg-amber-500/[0.03]",
};
const activeMap = {
  red: "!border-red-500 !bg-red-500/10",
  sky: "!border-sky-500 !bg-sky-500/10",
  emerald: "!border-emerald-500 !bg-emerald-500/10",
  amber: "!border-amber-500 !bg-amber-500/10",
};

const Generator = () => {
  const [strategy, setStrategy] = useState("balanced");
  const [count, setCount] = useState(3);
  const [grids, setGrids] = useState([]);
  const [loading, setLoading] = useState(false);

  const generate = async () => {
    setLoading(true);
    try {
      const { data } = await api.post("/grids/generate", { strategy, count });
      setGrids(data.grids);
      toast.success(`${data.grids.length} grille(s) générée(s)`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Échec");
    } finally { setLoading(false); }
  };

  const saveGrid = async (g) => {
    try {
      await api.post("/grids/save", { strategy: g.strategy, numbers: g.numbers, chance: g.chance });
      toast.success("Grille sauvegardée");
    } catch { toast.error("Impossible de sauvegarder"); }
  };

  return (
    <div className="space-y-10" data-testid="generator-page">
      <header className="space-y-3">
        <div className="text-xs uppercase tracking-[0.3em] text-zinc-500">Générateur</div>
        <h1 className="font-heading text-4xl font-bold tracking-tighter">Créer des grilles</h1>
        <p className="text-sm text-zinc-500 max-w-2xl">Choisissez une stratégie basée sur l'analyse des tirages passés. Rappel : les tirages sont indépendants — aucune méthode ne garantit un gain.</p>
      </header>

      <Card className="p-6 border-white/5 bg-[#0d0d10]">
        <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-4">Stratégie</div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {strategies.map((s) => (
            <button
              key={s.key}
              data-testid={`strategy-${s.key}`}
              onClick={() => setStrategy(s.key)}
              className={`text-left p-4 rounded-xl border transition-colors duration-200 ${colorMap[s.color]} ${strategy === s.key ? activeMap[s.color] : ""}`}
            >
              <s.icon className="w-5 h-5 mb-3 text-white/80" />
              <div className="font-heading font-semibold mb-1">{s.label}</div>
              <div className="text-xs text-zinc-500 leading-relaxed">{s.desc}</div>
            </button>
          ))}
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center gap-4">
          <div>
            <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 mb-2">Nombre de grilles</div>
            <div className="flex items-center gap-2">
              {[1, 3, 5, 10].map((n) => (
                <button
                  key={n}
                  data-testid={`count-${n}`}
                  onClick={() => setCount(n)}
                  className={`w-10 h-10 rounded-full border font-mono-tab text-sm transition-colors duration-200 ${
                    count === n ? "bg-white text-black border-white" : "border-white/10 text-zinc-400 hover:text-white hover:border-white/30"
                  }`}
                >{n}</button>
              ))}
            </div>
          </div>
          <div className="flex-1" />
          <Button
            data-testid="generate-grid-button"
            onClick={generate}
            disabled={loading}
            className="rounded-full bg-amber-400 hover:bg-amber-300 text-black font-semibold h-11 px-6"
          >
            {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Sparkles className="w-4 h-4 mr-2" />}
            Générer
          </Button>
        </div>
      </Card>

      {grids.length > 0 && (
        <div className="space-y-4">
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">Grilles proposées</div>
          <div className="grid gap-4">
            {grids.map((g, i) => (
              <Card key={i} className="p-5 border-white/5 bg-[#0d0d10] flex flex-col md:flex-row md:items-center md:justify-between gap-4" data-testid={`generated-grid-${i}`}>
                <div className="flex flex-wrap items-center gap-3">
                  <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 w-16">#{String(i + 1).padStart(2, "0")}</div>
                  {g.numbers.map((n) => <LotteryBall key={n} number={n} size="md" />)}
                  <div className="mx-1 text-zinc-700">+</div>
                  <LotteryBall number={g.chance} variant="chance" size="md" />
                </div>
                <Button
                  data-testid={`save-grid-${i}`}
                  variant="outline"
                  onClick={() => saveGrid(g)}
                  className="rounded-full border-white/10 bg-transparent hover:bg-white/5 gap-2"
                >
                  <Save className="w-4 h-4" /> Sauvegarder
                </Button>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default Generator;
