import { useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { LotteryBall } from "@/components/LotteryBall";
import { Loader2, Search, ShieldCheck } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell } from "recharts";

const RANK_COLORS = {
  "Rang 1 · Jackpot": "#EF4444",
  "Rang 2": "#F59E0B",
  "Rang 3": "#F59E0B",
  "Rang 4": "#10B981",
  "Rang 5": "#10B981",
  "Rang 6": "#0EA5E9",
  "Rang 7": "#0EA5E9",
  "Rang 8": "#71717a",
  "Rang 9 · N° Chance": "#a78bfa",
  "Perdu": "#3f3f46",
};

const NumberInput = ({ value, onChange, "data-testid": testId, placeholder }) => (
  <input
    data-testid={testId}
    type="number"
    min={1}
    max={49}
    value={value}
    placeholder={placeholder}
    onChange={(e) => onChange(e.target.value)}
    className="w-14 h-14 rounded-full bg-black/40 border border-white/10 text-center font-mono-tab text-lg text-white focus:outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-500/30 transition-colors"
  />
);

const Verify = () => {
  const [nums, setNums] = useState(["", "", "", "", ""]);
  const [chance, setChance] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);

  const update = (i, v) => {
    const next = [...nums]; next[i] = v; setNums(next);
  };

  const verify = async () => {
    const n = nums.map((x) => parseInt(x, 10));
    const c = parseInt(chance, 10);
    if (n.some(isNaN) || isNaN(c)) { toast.error("Complète tous les numéros"); return; }
    if (new Set(n).size !== 5) { toast.error("Les 5 numéros doivent être uniques"); return; }
    if (n.some((x) => x < 1 || x > 49)) { toast.error("Numéros entre 1 et 49"); return; }
    if (c < 1 || c > 10) { toast.error("Chance entre 1 et 10"); return; }

    setLoading(true);
    try {
      const { data } = await api.post("/grids/verify", { numbers: n, chance: c });
      setResult(data);
      toast.success("Grille analysée");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Analyse échouée");
    } finally { setLoading(false); }
  };

  return (
    <div className="space-y-10" data-testid="verify-page">
      <header className="space-y-3">
        <div className="text-xs uppercase tracking-[0.3em] text-zinc-500">Vérif Grille</div>
        <h1 className="font-heading text-4xl font-bold tracking-tighter">Une grille à tester ?</h1>
        <p className="text-sm text-zinc-500 max-w-2xl leading-relaxed">
          Colle une grille (jouée ou hypothétique) et découvre combien de fois elle aurait touché
          sur les {result?.total_draws ?? "3 années"} de tirages passés — nombre de bons numéros,
          taux de chance, rangs FDJ atteints, meilleurs coups historiques.
        </p>
      </header>

      <Card className="p-8 border-white/5 bg-[#0d0d10]">
        <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 mb-4">Vos 5 numéros + chance</div>
        <div className="flex flex-wrap items-center gap-3">
          {nums.map((v, i) => (
            <NumberInput key={i} value={v} onChange={(x) => update(i, x)} data-testid={`verify-num-${i}`} placeholder={`N${i+1}`} />
          ))}
          <div className="mx-2 text-zinc-600 text-xl">+</div>
          <input
            data-testid="verify-chance"
            type="number"
            min={1}
            max={10}
            value={chance}
            placeholder="C"
            onChange={(e) => setChance(e.target.value)}
            className="w-14 h-14 rounded-full bg-amber-500/10 border-2 border-amber-500/60 text-center font-mono-tab text-lg text-amber-400 focus:outline-none focus:ring-2 focus:ring-amber-500 transition-colors"
          />
          <div className="flex-1" />
          <Button
            data-testid="verify-btn"
            onClick={verify}
            disabled={loading}
            className="rounded-full bg-amber-400 hover:bg-amber-300 text-black font-semibold h-11 px-6"
          >
            {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Search className="w-4 h-4 mr-2" />}
            Analyser
          </Button>
        </div>
      </Card>

      {result && (
        <>
          <Card className="p-8 border-white/5 bg-[#0d0d10]">
            <div className="flex items-baseline justify-between mb-6">
              <div>
                <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-1">Résultats sur l'historique</div>
                <h2 className="font-heading text-2xl font-semibold">{result.total_draws} tirages analysés</h2>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {result.grid.numbers.map((n) => <LotteryBall key={n} number={n} size="sm" />)}
                <span className="mx-1 text-zinc-700">+</span>
                <LotteryBall number={result.grid.chance} variant="chance" size="sm" />
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
              {result.distribution.map((d) => {
                const pct = ((d.count / result.total_draws) * 100).toFixed(1);
                return (
                  <div key={d.main_matches} className="p-4 rounded-lg border border-white/5 bg-black/30">
                    <div className="text-[10px] uppercase text-zinc-500 mb-1">{d.main_matches} num</div>
                    <div className="font-heading text-2xl font-bold" data-testid={`match-${d.main_matches}`}>{d.count}</div>
                    <div className="text-[10px] text-zinc-500 mt-1">{pct}%</div>
                  </div>
                );
              })}
            </div>
          </Card>

          <Card className="p-8 border-white/5 bg-[#0d0d10]">
            <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-1">Rangs FDJ atteints</div>
            <h2 className="font-heading text-2xl font-semibold mb-6">Répartition des gains</h2>
            <div className="h-64">
              <ResponsiveContainer>
                <BarChart data={result.per_rank} layout="vertical" margin={{ left: 40 }}>
                  <CartesianGrid stroke="rgba(255,255,255,0.05)" horizontal={false} />
                  <XAxis type="number" stroke="#52525b" tick={{ fontSize: 10 }} />
                  <YAxis dataKey="rank" type="category" stroke="#52525b" tick={{ fontSize: 11 }} width={130} />
                  <Tooltip contentStyle={{ background: "#0a0a0c", border: "1px solid #27272a", borderRadius: 8, fontSize: 12 }} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
                  <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                    {result.per_rank.map((r) => <Cell key={r.rank} fill={RANK_COLORS[r.rank] || "#71717a"} fillOpacity={0.85} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-4 text-xs text-zinc-500">
              Chance seul touché : <span className="text-amber-400 font-semibold">{result.chance_hits}</span> fois ·
              Jackpot : <span className="text-red-400 font-semibold">{result.combined_5_and_chance}</span>
            </div>
          </Card>

          {result.best_hits.length > 0 && (
            <Card className="p-8 border-white/5 bg-[#0d0d10]" data-testid="best-hits">
              <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-1">Meilleurs coups</div>
              <h2 className="font-heading text-2xl font-semibold mb-6">Top {result.best_hits.length} tirages proches</h2>
              <div className="space-y-3">
                {result.best_hits.map((h, i) => {
                  const gridSet = new Set(result.grid.numbers);
                  return (
                    <div key={i} className="p-4 rounded-lg border border-white/5 bg-black/20">
                      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
                        <div className="flex items-center gap-3">
                          <ShieldCheck className="w-4 h-4 text-emerald-400" />
                          <span className="font-mono-tab text-sm text-zinc-300">{h.date}</span>
                          <span className="text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-full border" style={{ borderColor: RANK_COLORS[h.rank] + "80", color: RANK_COLORS[h.rank] }}>
                            {h.rank}
                          </span>
                        </div>
                        <div className="text-xs text-zinc-500">
                          <span className="text-emerald-400 font-semibold">{h.main_matches}/5</span>
                          {h.chance_match && <span className="text-amber-400 ml-2">+ chance</span>}
                        </div>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        {h.numbers.map((n) => (
                          <LotteryBall key={n} number={n} variant={gridSet.has(n) ? "hot" : "default"} size="sm" />
                        ))}
                        <span className="mx-1 text-zinc-700">+</span>
                        <LotteryBall number={h.chance} variant={h.chance === result.grid.chance ? "chance" : "muted"} size="sm" />
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
};

export default Verify;
