import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { LotteryBall } from "@/components/LotteryBall";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AlertTriangle, Database, Loader2, TrendingUp } from "lucide-react";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";

const Overview = () => {
  const [draws, setDraws] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const navigate = useNavigate();

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/draws?limit=500");
      setDraws(data);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const generateDemo = async () => {
    setGenerating(true);
    try {
      const { data } = await api.post("/draws/generate-demo");
      toast.success(`${data.inserted} tirages de démo générés`);
      await load();
    } catch { toast.error("Échec de la génération"); }
    finally { setGenerating(false); }
  };

  const last = draws[0];

  return (
    <div className="space-y-10" data-testid="overview-page">
      <header className="space-y-3">
        <div className="text-xs uppercase tracking-[0.3em] text-zinc-500">Tableau de bord</div>
        <h1 className="font-heading text-4xl sm:text-5xl font-bold tracking-tighter">Vue d'ensemble</h1>
      </header>

      <div className="rounded-xl border border-amber-500/20 bg-amber-500/[0.03] p-4 flex items-start gap-3">
        <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
        <p className="text-xs text-zinc-400 leading-relaxed">
          Les tirages de loto sont indépendants les uns des autres. Aucune analyse statistique ne
          peut prédire un tirage futur. Cet outil sert uniquement à explorer les données passées.
        </p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="w-6 h-6 animate-spin text-zinc-500" />
        </div>
      ) : draws.length === 0 ? (
        <Card className="p-12 text-center border-white/5 bg-[#0d0d10]">
          <Database className="w-10 h-10 mx-auto text-zinc-600 mb-4" />
          <h3 className="font-heading text-xl font-semibold mb-2">Aucun tirage en base</h3>
          <p className="text-sm text-zinc-400 mb-6 max-w-md mx-auto">
            Générez 3 années de données de démonstration ou importez un fichier CSV pour commencer l'analyse.
          </p>
          <div className="flex items-center justify-center gap-3">
            <Button
              data-testid="generate-demo-btn"
              disabled={generating}
              onClick={generateDemo}
              className="rounded-full bg-amber-400 hover:bg-amber-300 text-black font-semibold"
            >
              {generating && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
              Générer 3 ans de démo
            </Button>
            <Button
              data-testid="goto-import-btn"
              variant="outline"
              onClick={() => navigate("/dashboard/import")}
              className="rounded-full border-white/10 bg-transparent hover:bg-white/5"
            >
              Importer un CSV
            </Button>
          </div>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Card className="p-6 border-white/5 bg-[#0d0d10]">
              <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-3">Tirages analysés</div>
              <div className="font-heading text-4xl font-bold" data-testid="stat-total-draws">{draws.length}</div>
              <div className="text-xs text-zinc-500 mt-1">du {draws[draws.length-1]?.date} au {draws[0]?.date}</div>
            </Card>
            <Card className="p-6 border-white/5 bg-[#0d0d10]">
              <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-3">Numéros joués</div>
              <div className="font-heading text-4xl font-bold">49<span className="text-zinc-500 text-2xl"> +10</span></div>
              <div className="text-xs text-zinc-500 mt-1">Principaux + Chance</div>
            </Card>
            <Card className="p-6 border-white/5 bg-[#0d0d10]">
              <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-3">Format</div>
              <div className="font-heading text-2xl font-bold">Loto FDJ</div>
              <div className="text-xs text-zinc-500 mt-1">5 numéros (1-49) + 1 chance (1-10)</div>
            </Card>
          </div>

          {last && (
            <Card className="p-8 border-white/5 bg-[#0d0d10]">
              <div className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-zinc-500 mb-6">
                <TrendingUp className="w-3 h-3" /> Dernier tirage · {last.date}
              </div>
              <div className="flex flex-wrap items-center gap-3">
                {last.numbers.map((n) => (
                  <LotteryBall key={n} number={n} size="lg" />
                ))}
                <div className="mx-2 text-zinc-600 text-xl">+</div>
                <LotteryBall number={last.chance} variant="chance" size="lg" />
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
};

export default Overview;
