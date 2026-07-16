import { useEffect, useState, useMemo } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LotteryBall } from "@/components/LotteryBall";
import { toast } from "sonner";
import { Loader2, GitCompareArrows, Check, Sparkles } from "lucide-react";

const strategyLabels = {
  hot: "Chauds", cold: "Froids", balanced: "Équilibrée",
  weighted_random: "Aléatoire pondérée", credible_top5: "Top 5 crédibles",
};

const rankColor = (rank) => {
  if (!rank) return "text-zinc-500";
  if (rank.includes("Jackpot")) return "text-red-400";
  if (rank.includes("Rang 2") || rank.includes("Rang 3")) return "text-amber-400";
  if (rank.includes("Rang 4") || rank.includes("Rang 5")) return "text-emerald-400";
  if (rank.includes("Rang 6") || rank.includes("Rang 7")) return "text-sky-400";
  if (rank.includes("Chance")) return "text-violet-400";
  if (rank === "Perdu") return "text-zinc-500";
  return "text-zinc-400";
};

// Compute statistics for a grid of numbers
const gridStats = (numbers, hotSet, coldSet) => {
  const sum = numbers.reduce((a, b) => a + b, 0);
  const evens = numbers.filter((n) => n % 2 === 0).length;
  const odds = numbers.length - evens;
  const spread = Math.max(...numbers) - Math.min(...numbers);
  // decades: 1-10, 11-20, 21-30, 31-40, 41-49
  const decades = [0, 0, 0, 0, 0];
  numbers.forEach((n) => {
    if (n <= 10) decades[0]++;
    else if (n <= 20) decades[1]++;
    else if (n <= 30) decades[2]++;
    else if (n <= 40) decades[3]++;
    else decades[4]++;
  });
  const hotCount = numbers.filter((n) => hotSet.has(n)).length;
  const coldCount = numbers.filter((n) => coldSet.has(n)).length;
  return { sum, evens, odds, spread, decades, hotCount, coldCount };
};

const Compare = () => {
  const [grids, setGrids] = useState([]);
  const [selected, setSelected] = useState([]); // grid ids
  const [hotCold, setHotCold] = useState({ hot: new Set(), cold: new Set() });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [g, hc] = await Promise.all([
          api.get("/grids"),
          api.get("/stats/hot-cold").catch(() => ({ data: { hot: [], cold: [] } })),
        ]);
        setGrids(g.data);
        setHotCold({
          hot: new Set((hc.data.hot || []).slice(0, 10).map((x) => x.number)),
          cold: new Set((hc.data.cold || []).slice(0, 10).map((x) => x.number)),
        });
      } catch { toast.error("Erreur de chargement"); }
      finally { setLoading(false); }
    })();
  }, []);

  const toggleSelect = (id) => {
    setSelected((s) => {
      if (s.includes(id)) return s.filter((x) => x !== id);
      if (s.length >= 3) {
        toast.info("Maximum 3 grilles à comparer");
        return s;
      }
      return [...s, id];
    });
  };

  const comparisonGrids = useMemo(
    () => selected.map((id) => grids.find((g) => g.id === id)).filter(Boolean),
    [selected, grids],
  );

  const commonNumbers = useMemo(() => {
    if (comparisonGrids.length < 2) return new Set();
    const sets = comparisonGrids.map((g) => new Set(g.numbers));
    const common = new Set();
    for (const n of sets[0]) {
      if (sets.every((s) => s.has(n))) common.add(n);
    }
    return common;
  }, [comparisonGrids]);

  const stats = useMemo(
    () => comparisonGrids.map((g) => gridStats(g.numbers, hotCold.hot, hotCold.cold)),
    [comparisonGrids, hotCold],
  );

  if (loading) {
    return <div className="flex items-center justify-center py-24"><Loader2 className="w-6 h-6 animate-spin text-zinc-500" /></div>;
  }

  return (
    <div className="space-y-8" data-testid="compare-page">
      <header className="space-y-3">
        <div className="text-xs uppercase tracking-[0.3em] text-zinc-500">Comparateur</div>
        <h1 className="font-heading text-4xl font-bold tracking-tighter">Comparer 2 ou 3 grilles</h1>
        <p className="text-sm text-zinc-400 max-w-2xl">
          Sélectionne jusqu'à 3 grilles sauvegardées pour les analyser côte à côte : numéros communs,
          somme, parité, distribution par décennie, ratio chauds/froids.
        </p>
      </header>

      {grids.length === 0 ? (
        <Card className="p-10 border-white/5 bg-[#0d0d10] text-center">
          <Sparkles className="w-8 h-8 text-amber-400 mx-auto mb-4" />
          <div className="font-heading text-lg font-semibold mb-2">Aucune grille sauvegardée</div>
          <p className="text-sm text-zinc-500">Génère et sauvegarde d'abord quelques grilles pour pouvoir les comparer.</p>
        </Card>
      ) : (
        <>
          {/* Selection grid */}
          <div>
            <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 mb-3">
              Grilles sauvegardées · {selected.length}/3 sélectionnée{selected.length > 1 ? "s" : ""}
            </div>
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
              {grids.map((g) => {
                const isSelected = selected.includes(g.id);
                return (
                  <button
                    key={g.id}
                    data-testid={`select-grid-${g.id}`}
                    onClick={() => toggleSelect(g.id)}
                    className={`text-left p-4 rounded-xl border transition-all duration-200 ${
                      isSelected
                        ? "border-amber-500/60 bg-amber-500/[0.06]"
                        : "border-white/5 bg-[#0d0d10] hover:border-white/20"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                        {strategyLabels[g.strategy] || g.strategy}
                      </span>
                      {isSelected && (
                        <div className="w-5 h-5 rounded-full bg-amber-400 flex items-center justify-center">
                          <Check className="w-3 h-3 text-black" />
                        </div>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-1.5 items-center">
                      {g.numbers.map((n) => <LotteryBall key={n} number={n} size="sm" />)}
                      <span className="mx-1 text-zinc-600">+</span>
                      <LotteryBall number={g.chance} variant="chance" size="sm" />
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Comparison */}
          {comparisonGrids.length >= 2 && (
            <Card className="p-6 md:p-8 border-white/5 bg-[#0d0d10]" data-testid="comparison-result">
              <div className="flex items-center gap-3 mb-6">
                <GitCompareArrows className="w-5 h-5 text-amber-400" />
                <h2 className="font-heading text-xl font-semibold">Analyse comparative</h2>
              </div>

              {/* Common numbers */}
              {commonNumbers.size > 0 && (
                <div className="mb-6 p-4 rounded-lg bg-amber-500/[0.06] border border-amber-500/20">
                  <div className="text-[10px] uppercase tracking-[0.2em] text-amber-400 mb-2">
                    Numéros communs · {commonNumbers.size}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {Array.from(commonNumbers).sort((a, b) => a - b).map((n) => (
                      <LotteryBall key={n} number={n} size="sm" variant="hot" />
                    ))}
                  </div>
                </div>
              )}

              {/* Side by side */}
              <div className={`grid gap-4 ${comparisonGrids.length === 2 ? "md:grid-cols-2" : "md:grid-cols-3"}`}>
                {comparisonGrids.map((g, idx) => {
                  const s = stats[idx];
                  return (
                    <div key={g.id} className="p-5 rounded-xl border border-white/5 bg-black/40">
                      <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 mb-1">
                        Grille {String.fromCharCode(65 + idx)}
                      </div>
                      <div className="text-sm font-semibold text-amber-400 mb-4">
                        {strategyLabels[g.strategy] || g.strategy}
                      </div>

                      <div className="flex flex-wrap gap-1.5 items-center mb-5">
                        {g.numbers.map((n) => (
                          <LotteryBall
                            key={n}
                            number={n}
                            size="sm"
                            variant={commonNumbers.has(n) ? "hot" : "default"}
                          />
                        ))}
                        <span className="mx-1 text-zinc-600">+</span>
                        <LotteryBall number={g.chance} variant="chance" size="sm" />
                      </div>

                      {/* Stats table */}
                      <div className="space-y-2 text-xs">
                        <div className="flex justify-between py-1.5 border-b border-white/5">
                          <span className="text-zinc-500">Somme</span>
                          <span className="font-mono-tab text-white font-semibold">{s.sum}</span>
                        </div>
                        <div className="flex justify-between py-1.5 border-b border-white/5">
                          <span className="text-zinc-500">Pairs / Impairs</span>
                          <span className="font-mono-tab text-white">{s.evens} / {s.odds}</span>
                        </div>
                        <div className="flex justify-between py-1.5 border-b border-white/5">
                          <span className="text-zinc-500">Étendue</span>
                          <span className="font-mono-tab text-white">{s.spread}</span>
                        </div>
                        <div className="flex justify-between py-1.5 border-b border-white/5">
                          <span className="text-zinc-500">Chauds (top 10)</span>
                          <span className="font-mono-tab text-red-400 font-semibold">{s.hotCount}</span>
                        </div>
                        <div className="flex justify-between py-1.5 border-b border-white/5">
                          <span className="text-zinc-500">Froids (top 10)</span>
                          <span className="font-mono-tab text-sky-400 font-semibold">{s.coldCount}</span>
                        </div>
                        <div className="py-1.5 border-b border-white/5">
                          <div className="text-zinc-500 mb-2">Décennies</div>
                          <div className="grid grid-cols-5 gap-1">
                            {s.decades.map((d, i) => (
                              <div key={i} className="text-center">
                                <div className={`h-8 rounded flex items-center justify-center font-mono-tab text-xs font-bold ${
                                  d === 0 ? "bg-white/[0.02] text-zinc-600"
                                  : d === 1 ? "bg-amber-500/10 text-amber-400"
                                  : "bg-amber-400 text-black"
                                }`}>{d}</div>
                                <div className="text-[9px] text-zinc-600 mt-1">
                                  {i === 0 ? "1-10" : i === 1 ? "11-20" : i === 2 ? "21-30" : i === 3 ? "31-40" : "41-49"}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                        {g.result && (
                          <div className="pt-2">
                            <div className="text-zinc-500 mb-1">Résultat vs {g.result.target_date}</div>
                            <div className={`font-semibold ${rankColor(g.result.rank_label)}`}>
                              {g.result.main_matches}/5 · {g.result.rank_label}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="mt-6 pt-6 border-t border-white/5">
                <Button
                  data-testid="clear-selection-btn"
                  variant="ghost"
                  onClick={() => setSelected([])}
                  className="text-zinc-400 hover:text-white"
                >
                  Réinitialiser la sélection
                </Button>
              </div>
            </Card>
          )}

          {comparisonGrids.length === 1 && (
            <Card className="p-6 border-white/5 bg-[#0d0d10] text-center">
              <p className="text-sm text-zinc-400">
                Sélectionne au moins <span className="text-amber-400 font-semibold">2 grilles</span> pour lancer la comparaison.
              </p>
            </Card>
          )}
        </>
      )}
    </div>
  );
};

export default Compare;
