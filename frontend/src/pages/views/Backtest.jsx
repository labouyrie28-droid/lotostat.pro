import { useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { toast } from "sonner";
import { Loader2, Trophy, Play } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell } from "recharts";

const labels = {
  hot: "Chauds", cold: "Froids", balanced: "Équilibrée",
  weighted_random: "Aléatoire pondérée", random: "Aléatoire pur",
};
const colorFor = (s) => ({
  hot: "#EF4444", cold: "#0EA5E9", balanced: "#10B981",
  weighted_random: "#F59E0B", random: "#71717a",
}[s] || "#a1a1aa");

const Backtest = () => {
  const [running, setRunning] = useState(false);
  const [data, setData] = useState(null);
  const [gridsPerStrat, setGridsPerStrat] = useState(20);
  const [sampleSize, setSampleSize] = useState(50);

  const run = async () => {
    setRunning(true);
    try {
      const { data } = await api.post("/backtest", {
        grids_per_strategy: gridsPerStrat,
        sample_size: sampleSize,
      });
      setData(data);
      toast.success(`Backtest terminé sur ${data.sample_size} tirages`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Backtest échoué");
    } finally { setRunning(false); }
  };

  return (
    <div className="space-y-10" data-testid="backtest-page">
      <header className="space-y-3">
        <div className="text-xs uppercase tracking-[0.3em] text-zinc-500">Backtesting</div>
        <h1 className="font-heading text-4xl font-bold tracking-tighter">Compare les stratégies</h1>
        <p className="text-sm text-zinc-500 max-w-2xl leading-relaxed">
          Pour chaque tirage passé, on génère des grilles avec les stats <em>disponibles à ce moment-là</em>
          (walk-forward, pas de triche par lecture du futur), puis on compte les numéros trouvés
          sur le tirage réel qui a suivi. Métrique : nombre moyen de bons numéros par grille.
        </p>
      </header>

      <Card className="p-6 border-white/5 bg-[#0d0d10]">
        <div className="grid md:grid-cols-2 gap-8 mb-6">
          <div>
            <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 mb-3">
              Grilles par stratégie : {gridsPerStrat}
            </div>
            <Slider data-testid="grids-per-strategy" min={5} max={50} step={5} value={[gridsPerStrat]} onValueChange={([v]) => setGridsPerStrat(v)} />
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 mb-3">
              Fenêtre de test (derniers tirages) : {sampleSize}
            </div>
            <Slider data-testid="sample-size" min={20} max={200} step={10} value={[sampleSize]} onValueChange={([v]) => setSampleSize(v)} />
          </div>
        </div>
        <Button
          data-testid="run-backtest-btn"
          onClick={run}
          disabled={running}
          className="rounded-full bg-amber-400 hover:bg-amber-300 text-black font-semibold h-11 px-6"
        >
          {running ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Play className="w-4 h-4 mr-2" />}
          Lancer le backtest
        </Button>
        <div className="text-xs text-zinc-500 mt-3">
          {sampleSize * gridsPerStrat * 5} grilles à évaluer — peut prendre 3-15 secondes.
        </div>
      </Card>

      {data && (
        <>
          <Card className="p-6 border-white/5 bg-[#0d0d10]" data-testid="backtest-results">
            <div className="flex items-baseline justify-between mb-2">
              <div>
                <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">Résultats</div>
                <h2 className="font-heading text-2xl font-semibold">Numéros trouvés en moyenne</h2>
              </div>
              <div className="text-xs text-zinc-500">
                {data.sample_size} tirages · {data.grids_per_strategy} grilles/strat · {data.grid_cost}€/grille
              </div>
            </div>

            <div className="h-80 mt-6">
              <ResponsiveContainer>
                <BarChart data={data.strategies.map((s) => ({ name: labels[s.strategy], strategy: s.strategy, value: s.avg_main_matches }))}>
                  <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis dataKey="name" stroke="#52525b" tick={{ fontSize: 11 }} />
                  <YAxis stroke="#52525b" tick={{ fontSize: 10 }} domain={[0, "dataMax + 0.2"]} />
                  <Tooltip contentStyle={{ background: "#0a0a0c", border: "1px solid #27272a", borderRadius: 8, fontSize: 12 }} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
                  <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                    {data.strategies.map((s) => (
                      <Cell key={s.strategy} fill={colorFor(s.strategy)} fillOpacity={0.85} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {/* Cumulative gains chart */}
          <Card className="p-6 border-white/5 bg-[#0d0d10]" data-testid="gains-chart">
            <div className="flex items-baseline justify-between mb-6">
              <div>
                <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">ROI théorique</div>
                <h2 className="font-heading text-2xl font-semibold">Gains cumulés (€)</h2>
                <p className="text-xs text-zinc-500 mt-1">Basé sur les rangs FDJ moyens · gains bruts - coût des grilles</p>
              </div>
            </div>
            <div className="h-72">
              <ResponsiveContainer>
                <BarChart
                  data={data.strategies.map((s) => ({
                    name: labels[s.strategy],
                    strategy: s.strategy,
                    "Gains bruts": s.gross_gains,
                    "Coût": -s.total_cost,
                    "Net": s.net_gains,
                  }))}
                >
                  <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
                  <XAxis dataKey="name" stroke="#52525b" tick={{ fontSize: 11 }} />
                  <YAxis stroke="#52525b" tick={{ fontSize: 10 }} tickFormatter={(v) => `${v}€`} />
                  <Tooltip
                    contentStyle={{ background: "#0a0a0c", border: "1px solid #27272a", borderRadius: 8, fontSize: 12 }}
                    cursor={{ fill: "rgba(255,255,255,0.03)" }}
                    formatter={(v) => `${v.toFixed(2)} €`}
                  />
                  <Bar dataKey="Gains bruts" fill="#10B981" fillOpacity={0.7} radius={[4, 4, 0, 0]} />
                  <Bar dataKey="Coût" fill="#EF4444" fillOpacity={0.6} radius={[0, 0, 4, 4]} />
                  <Bar dataKey="Net" fill="#F59E0B" fillOpacity={0.9} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>

          {/* Winner + detailed cards */}
          <div className="grid gap-4">
            {data.strategies.map((s, i) => (
              <Card
                key={s.strategy}
                data-testid={`strategy-result-${s.strategy}`}
                className={`p-6 border bg-[#0d0d10] ${i === 0 ? "border-amber-500/40 shadow-[0_0_30px_rgba(245,158,11,0.08)]" : "border-white/5"}`}
              >
                <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
                  <div className="flex items-center gap-3">
                    {i === 0 && <Trophy className="w-5 h-5 text-amber-400" />}
                    <div>
                      <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">#{i + 1}</div>
                      <div className="font-heading text-xl font-semibold">{labels[s.strategy]}</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="font-mono-tab text-3xl font-bold" style={{ color: colorFor(s.strategy) }}>
                      {s.avg_main_matches}
                    </div>
                    <div className="text-[10px] uppercase tracking-widest text-zinc-500">num/grille</div>
                  </div>
                </div>

                <div className="grid grid-cols-3 md:grid-cols-6 gap-2 mb-4">
                  {s.rank_distribution.map((count, r) => (
                    <div key={r} className="p-2 rounded-lg border border-white/5 bg-black/30 text-center">
                      <div className="text-[9px] uppercase text-zinc-500 mb-1">{r} num</div>
                      <div className="font-mono-tab font-semibold text-sm">{count}</div>
                    </div>
                  ))}
                </div>

                {/* Gains breakdown */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-4 border-t border-white/5">
                  <div>
                    <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-1">Gains bruts</div>
                    <div className="font-mono-tab font-semibold text-emerald-400">{s.gross_gains.toFixed(2)} €</div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-1">Coût grilles</div>
                    <div className="font-mono-tab font-semibold text-red-400">-{s.total_cost.toFixed(2)} €</div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-1">Net</div>
                    <div className={`font-mono-tab font-semibold ${s.net_gains >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                      {s.net_gains >= 0 ? "+" : ""}{s.net_gains.toFixed(2)} €
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-1">ROI</div>
                    <div className={`font-mono-tab font-semibold ${s.roi_percent >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                      {s.roi_percent >= 0 ? "+" : ""}{s.roi_percent.toFixed(1)}%
                    </div>
                  </div>
                </div>

                <div className="flex flex-wrap gap-4 text-xs text-zinc-400 mt-3">
                  <span>Taux ≥3 bons : <span className="text-emerald-400 font-semibold">{s.hit_3plus_rate}%</span></span>
                  <span>Chance trouvée : <span className="text-amber-400 font-semibold">{s.chance_hit_rate}%</span></span>
                  <span>5+chance : <span className="text-red-400 font-semibold">{s.hits_5plus_chance}</span></span>
                </div>
              </Card>
            ))}
          </div>

          <Card className="p-4 border-amber-500/20 bg-amber-500/[0.03]">
            <p className="text-xs text-zinc-400 leading-relaxed">
              <strong className="text-amber-400">Note :</strong> les gains utilisent les rangs FDJ moyens
              (Jackpot 5 000 000€, Rang 2 100 000€, Rang 3 1 000€, Rang 4 50€, Rang 5 20€, Rang 6 10€, Rang 7 5€, Rangs 8/9 2,20€).
              Le vrai jackpot varie selon les cagnottes réelles. Ce chiffre reste une estimation théorique.
            </p>
          </Card>
        </>
      )}
    </div>
  );
};

export default Backtest;
