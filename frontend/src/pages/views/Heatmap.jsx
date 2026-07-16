import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { LotteryBall } from "@/components/LotteryBall";
import { Loader2, TrendingUp } from "lucide-react";

const Heatmap = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/stats/heatmap");
        setData(data);
      } finally { setLoading(false); }
    })();
  }, []);

  const topPairs = useMemo(() => {
    if (!data) return [];
    return [...data.pairs]
      .sort((a, b) => b.count - a.count)
      .slice(0, 20);
  }, [data]);

  if (loading) return <div className="flex items-center justify-center py-24"><Loader2 className="w-6 h-6 animate-spin text-zinc-500" /></div>;
  if (!data || data.total_draws === 0) {
    return (
      <Card className="p-10 border-white/5 bg-[#0d0d10] text-center">
        <p className="text-sm text-zinc-400">Aucun tirage. Charge le dataset officiel FDJ depuis Vue d'ensemble.</p>
      </Card>
    );
  }

  return (
    <div className="space-y-8" data-testid="heatmap-page">
      <header className="space-y-3">
        <div className="text-xs uppercase tracking-[0.3em] text-zinc-500">Paires</div>
        <h1 className="font-heading text-4xl font-bold tracking-tighter">Numéros qui sortent ensemble</h1>
        <p className="text-sm text-zinc-500 max-w-2xl leading-relaxed">
          Top 20 des paires les plus fréquentes sur {data.total_draws} tirages. Une barre plus longue = paire plus fréquente.
          Le max observé est <span className="text-amber-400 font-mono-tab">{data.max}</span> co-occurrences.
        </p>
      </header>

      <Card className="p-6 border-white/5 bg-[#0d0d10]">
        <div className="flex items-center gap-2 text-xs uppercase tracking-[0.2em] text-zinc-500 mb-6">
          <TrendingUp className="w-3 h-3" /> Top 20 des paires
        </div>
        <div className="space-y-3" data-testid="top-pairs-list">
          {topPairs.map((p, i) => {
            const pct = (p.count / data.max) * 100;
            const percent_all = ((p.count / data.total_draws) * 100).toFixed(1);
            return (
              <div key={`${p.a}-${p.b}`} className="flex items-center gap-3" data-testid={`pair-row-${i}`}>
                <div className="text-[10px] uppercase tracking-widest text-zinc-600 font-mono-tab w-8 shrink-0">
                  #{String(i + 1).padStart(2, "0")}
                </div>
                <div className="flex items-center gap-1.5 w-24 shrink-0">
                  <LotteryBall number={p.a} size="sm" />
                  <span className="text-zinc-700 text-xs">+</span>
                  <LotteryBall number={p.b} size="sm" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="h-3 rounded-full bg-black/40 overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500 ease-out"
                      style={{
                        width: `${pct}%`,
                        background: `linear-gradient(90deg, #0EA5E9 0%, #F59E0B 50%, #EF4444 100%)`,
                      }}
                    />
                  </div>
                </div>
                <div className="text-right shrink-0 w-24">
                  <div className="font-mono-tab font-semibold text-white">{p.count}×</div>
                  <div className="text-[10px] text-zinc-500">{percent_all}% des tirages</div>
                </div>
              </div>
            );
          })}
        </div>
      </Card>

      <Card className="p-4 border-white/5 bg-[#0d0d10] flex items-center justify-between text-xs">
        <div className="text-zinc-500">Échelle de fréquence :</div>
        <div className="flex items-center gap-2">
          <span className="text-sky-400">rare</span>
          <div className="w-24 h-2 rounded-full" style={{ background: "linear-gradient(90deg, #0EA5E9 0%, #F59E0B 50%, #EF4444 100%)" }} />
          <span className="text-red-400">fréquente</span>
        </div>
      </Card>
    </div>
  );
};

export default Heatmap;
