import { useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { LotteryBall } from "@/components/LotteryBall";
import { Loader2, Search, ShieldCheck, Plus, X, Trophy } from "lucide-react";
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

const GRID_COLORS = ["#F59E0B", "#0EA5E9", "#10B981", "#EF4444", "#a78bfa", "#f97316"];

const emptyGrid = () => ({ nums: ["", "", "", "", ""], chance: "" });

const NumberInput = ({ value, onChange, "data-testid": testId, placeholder, size = 12 }) => (
  <input
    data-testid={testId}
    type="number"
    min={1}
    max={49}
    value={value}
    placeholder={placeholder}
    onChange={(e) => onChange(e.target.value)}
    className={`w-${size} h-${size} rounded-full bg-black/40 border border-white/10 text-center font-mono-tab text-lg text-white focus:outline-none focus:border-amber-500 focus:ring-2 focus:ring-amber-500/30 transition-colors`}
    style={{ width: size === 12 ? 48 : 56, height: size === 12 ? 48 : 56 }}
  />
);

const Verify = () => {
  const [grids, setGrids] = useState([emptyGrid()]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);   // single mode
  const [batch, setBatch] = useState(null);     // multi mode

  const updateNum = (gi, i, v) => {
    const next = [...grids];
    next[gi].nums[i] = v;
    setGrids(next);
  };
  const updateChance = (gi, v) => {
    const next = [...grids];
    next[gi].chance = v;
    setGrids(next);
  };
  const addGrid = () => {
    if (grids.length >= 10) return toast.error("Maximum 10 grilles");
    setGrids([...grids, emptyGrid()]);
  };
  const removeGrid = (i) => setGrids(grids.filter((_, idx) => idx !== i));
  const clearAll = () => { setGrids([emptyGrid()]); setResult(null); setBatch(null); };

  const parseGrids = () => {
    const parsed = [];
    for (let i = 0; i < grids.length; i++) {
      const n = grids[i].nums.map((x) => parseInt(x, 10));
      const c = parseInt(grids[i].chance, 10);
      if (n.some(isNaN) || isNaN(c)) { toast.error(`Grille #${i + 1}: remplissez tous les champs`); return null; }
      if (new Set(n).size !== 5) { toast.error(`Grille #${i + 1}: 5 numéros uniques`); return null; }
      if (n.some((x) => x < 1 || x > 49)) { toast.error(`Grille #${i + 1}: numéros entre 1 et 49`); return null; }
      if (c < 1 || c > 10) { toast.error(`Grille #${i + 1}: chance entre 1 et 10`); return null; }
      parsed.push({ numbers: n, chance: c });
    }
    return parsed;
  };

  const verify = async () => {
    const parsed = parseGrids();
    if (!parsed) return;
    setLoading(true); setResult(null); setBatch(null);
    try {
      if (parsed.length === 1) {
        const { data } = await api.post("/grids/verify", parsed[0]);
        setResult(data);
      } else {
        const { data } = await api.post("/grids/verify-batch", { grids: parsed });
        setBatch(data);
      }
      toast.success(parsed.length === 1 ? "Grille analysée" : `${parsed.length} grilles analysées`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Analyse échouée");
    } finally { setLoading(false); }
  };

  return (
    <div className="space-y-10" data-testid="verify-page">
      <header className="space-y-3">
        <div className="text-xs uppercase tracking-[0.3em] text-zinc-500">Vérif Grille</div>
        <h1 className="font-heading text-4xl font-bold tracking-tighter">Une ou plusieurs grilles ?</h1>
        <p className="text-sm text-zinc-500 max-w-2xl leading-relaxed">
          Colle 1 à 10 grilles et compare-les sur l'historique complet — nombre de bons numéros,
          rangs FDJ, gains théoriques cumulés. Utile pour choisir la meilleure combinaison.
        </p>
      </header>

      <Card className="p-6 border-white/5 bg-[#0d0d10]">
        <div className="flex items-center justify-between mb-4">
          <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">
            {grids.length} grille{grids.length > 1 ? "s" : ""} · {grids.length}/10
          </div>
          <div className="flex items-center gap-2">
            <Button
              data-testid="add-grid-btn"
              variant="outline"
              onClick={addGrid}
              disabled={grids.length >= 10}
              className="rounded-full border-white/10 bg-transparent hover:bg-white/5 h-9 gap-1"
            >
              <Plus className="w-3.5 h-3.5" /> Ajouter
            </Button>
            {grids.length > 1 && (
              <Button
                data-testid="clear-grids-btn"
                variant="ghost"
                onClick={clearAll}
                className="text-zinc-500 hover:text-red-400 h-9"
              >
                Réinitialiser
              </Button>
            )}
          </div>
        </div>

        <div className="space-y-3">
          {grids.map((g, gi) => (
            <div
              key={gi}
              data-testid={`grid-input-row-${gi}`}
              className="flex flex-wrap items-center gap-2 p-3 rounded-lg border border-white/5 bg-black/20"
              style={{ borderLeftColor: GRID_COLORS[gi % GRID_COLORS.length], borderLeftWidth: 3 }}
            >
              <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 w-14 font-mono-tab">
                #{String(gi + 1).padStart(2, "0")}
              </div>
              {g.nums.map((v, i) => (
                <NumberInput
                  key={i}
                  value={v}
                  onChange={(x) => updateNum(gi, i, x)}
                  data-testid={`grid-${gi}-num-${i}`}
                  placeholder={`${i + 1}`}
                />
              ))}
              <div className="mx-2 text-zinc-600">+</div>
              <input
                data-testid={`grid-${gi}-chance`}
                type="number"
                min={1}
                max={10}
                value={g.chance}
                placeholder="C"
                onChange={(e) => updateChance(gi, e.target.value)}
                className="rounded-full bg-amber-500/10 border-2 border-amber-500/60 text-center font-mono-tab text-lg text-amber-400 focus:outline-none focus:ring-2 focus:ring-amber-500 transition-colors"
                style={{ width: 48, height: 48 }}
              />
              {grids.length > 1 && (
                <button
                  data-testid={`remove-grid-${gi}`}
                  onClick={() => removeGrid(gi)}
                  className="ml-auto text-zinc-500 hover:text-red-400 p-2 rounded-full hover:bg-red-500/10 transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
          ))}
        </div>

        <div className="mt-6 flex justify-end">
          <Button
            data-testid="verify-btn"
            onClick={verify}
            disabled={loading}
            className="rounded-full bg-amber-400 hover:bg-amber-300 text-black font-semibold h-11 px-6"
          >
            {loading ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Search className="w-4 h-4 mr-2" />}
            {grids.length === 1 ? "Analyser cette grille" : `Comparer les ${grids.length} grilles`}
          </Button>
        </div>
      </Card>

      {/* Single-grid result (unchanged flow) */}
      {result && <SingleResult result={result} />}

      {/* Multi-grid batch result */}
      {batch && <BatchResult batch={batch} />}
    </div>
  );
};

const SingleResult = ({ result }) => (
  <>
    <Card className="p-8 border-white/5 bg-[#0d0d10]">
      <div className="flex items-baseline justify-between mb-6 flex-wrap gap-3">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-1">Résultats</div>
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
                    <span className="text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-full border" style={{ borderColor: RANK_COLORS[h.rank] + "80", color: RANK_COLORS[h.rank] }}>{h.rank}</span>
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
);

const BatchResult = ({ batch }) => {
  const winnerAvg = batch.best.by_avg;
  const winnerGain = batch.best.by_gain;
  const winnerHits = batch.best.by_hits_3plus;

  const chartData = batch.results.map((r) => ({
    name: `#${r.index + 1}`,
    avg: r.avg_main_matches,
    gross: r.gross_gain,
    hits3: r.hit_3plus,
  }));

  return (
    <>
      <Card className="p-6 border-white/5 bg-[#0d0d10]" data-testid="batch-result">
        <div className="flex items-baseline justify-between mb-6 flex-wrap gap-3">
          <div>
            <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-1">Comparaison</div>
            <h2 className="font-heading text-2xl font-semibold">{batch.grids_count} grilles sur {batch.total_draws} tirages</h2>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <TrophyCard label="Meilleure moyenne" value={`#${winnerAvg + 1}`} sub={`${batch.results[winnerAvg].avg_main_matches} num/tirage`} color="amber" />
          <TrophyCard label="Meilleur gain théorique" value={`#${winnerGain + 1}`} sub={`${batch.results[winnerGain].gross_gain} €`} color="emerald" />
          <TrophyCard label="Meilleur hits 3+" value={`#${winnerHits + 1}`} sub={`${batch.results[winnerHits].hit_3plus} fois`} color="sky" />
        </div>
      </Card>

      {/* Bar chart comparing avg */}
      <Card className="p-6 border-white/5 bg-[#0d0d10]">
        <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-1">Numéros trouvés en moyenne</div>
        <h2 className="font-heading text-xl font-semibold mb-4">Comparaison</h2>
        <div className="h-64">
          <ResponsiveContainer>
            <BarChart data={chartData}>
              <CartesianGrid stroke="rgba(255,255,255,0.05)" vertical={false} />
              <XAxis dataKey="name" stroke="#52525b" tick={{ fontSize: 11 }} />
              <YAxis stroke="#52525b" tick={{ fontSize: 10 }} domain={[0, "dataMax + 0.2"]} />
              <Tooltip contentStyle={{ background: "#0a0a0c", border: "1px solid #27272a", borderRadius: 8, fontSize: 12 }} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
              <Bar dataKey="avg" radius={[6, 6, 0, 0]}>
                {chartData.map((_, i) => <Cell key={i} fill={GRID_COLORS[i % GRID_COLORS.length]} fillOpacity={0.85} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      {/* Per-grid detail */}
      <div className="grid gap-4">
        {batch.results.map((r) => {
          const isBest = r.index === winnerAvg;
          return (
            <Card
              key={r.index}
              data-testid={`batch-grid-${r.index}`}
              className={`p-5 border bg-[#0d0d10] ${isBest ? "border-amber-500/40 shadow-[0_0_20px_rgba(245,158,11,0.08)]" : "border-white/5"}`}
              style={{ borderLeftColor: GRID_COLORS[r.index % GRID_COLORS.length], borderLeftWidth: 3 }}
            >
              <div className="flex items-center justify-between flex-wrap gap-3 mb-3">
                <div className="flex items-center gap-3">
                  {isBest && <Trophy className="w-4 h-4 text-amber-400" />}
                  <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 font-mono-tab">
                    #{String(r.index + 1).padStart(2, "0")}
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {r.grid.numbers.map((n) => <LotteryBall key={n} number={n} size="sm" />)}
                    <span className="mx-1 text-zinc-700">+</span>
                    <LotteryBall number={r.grid.chance} variant="chance" size="sm" />
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-3 border-t border-white/5">
                <Stat label="Avg num/tirage" value={r.avg_main_matches} />
                <Stat label="Hits 3+" value={r.hit_3plus} />
                <Stat label="Chance touchée" value={r.chance_hits} />
                <Stat label="Gain théorique" value={`${r.gross_gain} €`} color="emerald" />
              </div>
            </Card>
          );
        })}
      </div>
    </>
  );
};

const TrophyCard = ({ label, value, sub, color }) => {
  const cls = {
    amber: "border-amber-500/30 text-amber-400",
    emerald: "border-emerald-500/30 text-emerald-400",
    sky: "border-sky-500/30 text-sky-400",
  }[color];
  return (
    <div className={`p-5 rounded-xl border bg-black/30 ${cls}`}>
      <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 mb-2">{label}</div>
      <div className="flex items-baseline gap-2">
        <Trophy className="w-4 h-4" />
        <div className="font-heading text-2xl font-bold">{value}</div>
      </div>
      <div className="text-xs text-zinc-400 mt-1 font-mono-tab">{sub}</div>
    </div>
  );
};

const Stat = ({ label, value, color = "white" }) => (
  <div>
    <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-1">{label}</div>
    <div className={`font-mono-tab font-semibold ${color === "emerald" ? "text-emerald-400" : "text-white"}`}>{value}</div>
  </div>
);

export default Verify;
