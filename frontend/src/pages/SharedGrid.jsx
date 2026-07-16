import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "@/lib/api";
import { LotteryBall } from "@/components/LotteryBall";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader2, Share2, ExternalLink } from "lucide-react";

const strategyLabels = {
  hot: "Chauds", cold: "Froids", balanced: "Équilibrée",
  weighted_random: "Aléatoire pondérée", credible_top5: "Top 5 crédibles",
};

const SharedGrid = () => {
  const { token } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get(`/share/${token}`);
        setData(data);
      } catch (e) {
        setError(e?.response?.data?.detail || "Lien invalide");
      } finally { setLoading(false); }
    })();
  }, [token]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#050507]">
        <Loader2 className="w-8 h-8 animate-spin text-amber-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#050507] px-6">
        <Card className="p-10 border-white/5 bg-[#0d0d10] text-center max-w-md">
          <div className="text-red-400 mb-3 text-4xl">✗</div>
          <h1 className="font-heading text-2xl font-bold mb-2">Lien invalide</h1>
          <p className="text-sm text-zinc-400 mb-6">{error}</p>
          <Link to="/">
            <Button className="rounded-full bg-amber-400 hover:bg-amber-300 text-black font-semibold">
              Aller sur LotoStat.Pro
            </Button>
          </Link>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#050507] flex items-center justify-center px-6 py-12" data-testid="shared-grid-page">
      <Card className="p-8 md:p-12 border-white/5 bg-[#0d0d10] max-w-lg w-full text-center">
        <div className="flex items-center justify-center gap-2 text-xs uppercase tracking-[0.3em] text-amber-400 mb-3">
          <Share2 className="w-3 h-3" /> Grille partagée
        </div>
        <h1 className="font-heading text-3xl font-bold tracking-tighter mb-2">
          {data.shared_by} vous partage
        </h1>
        <p className="text-sm text-zinc-500 mb-8">Stratégie : <span className="text-amber-400">{strategyLabels[data.strategy] || data.strategy}</span></p>

        <div className="flex flex-wrap items-center justify-center gap-3 mb-10">
          {data.numbers.map((n) => <LotteryBall key={n} number={n} size="lg" />)}
          <div className="mx-2 text-zinc-600 text-xl">+</div>
          <LotteryBall number={data.chance} variant="chance" size="lg" />
        </div>

        <div className="pt-6 border-t border-white/5 space-y-3">
          <p className="text-xs text-zinc-500 leading-relaxed">
            Envie de créer tes propres grilles ? Analyse les 1048 derniers tirages FDJ, teste tes combinaisons,
            génère des stratégies… gratuitement.
          </p>
          <Link to="/">
            <Button className="rounded-full bg-amber-400 hover:bg-amber-300 text-black font-semibold gap-2">
              Ouvrir LotoStat.Pro <ExternalLink className="w-4 h-4" />
            </Button>
          </Link>
        </div>

        <p className="text-[10px] uppercase tracking-widest text-zinc-600 mt-8">
          Le loto reste un jeu de hasard · Aucune méthode ne garantit un gain
        </p>
        <p
          data-testid="signature-shared"
          className="text-[10px] uppercase tracking-[0.25em] text-zinc-600 mt-3"
        >
          © 2026 <span className="text-amber-400/80 font-medium">Thomas Labouyrie</span> — Tous droits réservés
        </p>
      </Card>
    </div>
  );
};

export default SharedGrid;
