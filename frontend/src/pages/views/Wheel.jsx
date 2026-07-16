import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LotteryBall } from "@/components/LotteryBall";
import { toast } from "sonner";
import { Loader2, Zap, Target, TrendingUp, BookOpen } from "lucide-react";

const Wheel = () => {
  const [poolSize, setPoolSize] = useState(8);
  const [pool, setPool] = useState([]);
  const [target, setTarget] = useState(3);
  const [chance, setChance] = useState(7);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [hotColdData, setHotColdData] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/stats/hot-cold");
        setHotColdData(data);
      } catch {}
    })();
  }, []);

  const applyPreset = (kind) => {
    if (!hotColdData) return toast.error("Données non chargées");
    let src;
    if (kind === "hot") src = hotColdData.hot;
    else if (kind === "cold") src = hotColdData.cold;
    else src = hotColdData.top_delays.map((d) => d.number);
    setPool(src.slice(0, poolSize));
  };

  const toggleBall = (n) => {
    if (pool.includes(n)) setPool(pool.filter((x) => x !== n));
    else if (pool.length < poolSize) setPool([...pool, n].sort((a, b) => a - b));
    else toast.error(`Pool limité à ${poolSize} numéros — retire-en un pour en ajouter`);
  };

  const compute = async () => {
    if (pool.length !== poolSize) return toast.error(`Sélectionne exactement ${poolSize} numéros`);
    setBusy(true);
    try {
      const { data } = await api.post("/grids/wheel", { numbers: pool, target_matches: target, chance });
      setResult(data);
      toast.success(`${data.tickets_count} grilles calculées`);
    } catch (e) { toast.error(e?.response?.data?.detail || "Échec"); }
    finally { setBusy(false); }
  };

  return (
    <div className="space-y-10" data-testid="wheel-page">
      <header className="space-y-3">
        <div className="text-xs uppercase tracking-[0.3em] text-zinc-500">Système Réducteur</div>
        <h1 className="font-heading text-4xl font-bold tracking-tighter">Couverture combinatoire</h1>
        <p className="text-sm text-zinc-500 max-w-3xl leading-relaxed">
          Méthode mathématique héritée de <em>Steiner (1853)</em>, <em>Erdős</em> et la <em>La Jolla Covering Repository</em> :
          au lieu de jouer 1 grille aléatoire, joue plusieurs grilles savamment combinées pour <strong>garantir</strong> mathématiquement
          que si <span className="text-amber-400">≥{target}</span> des 5 numéros tirés sont dans ton pool de {poolSize} numéros,
          au moins une de tes grilles aura <span className="text-emerald-400">{target}+ bons numéros</span>.
        </p>
      </header>

      <Card className="p-4 border-violet-500/20 bg-violet-500/[0.03] flex items-start gap-3">
        <BookOpen className="w-4 h-4 text-violet-400 mt-0.5 shrink-0" />
        <p className="text-xs text-zinc-400 leading-relaxed">
          <strong className="text-violet-400">Attention :</strong> cette méthode <em>n'augmente pas</em> la probabilité qu'un numéro
          donné sorte (impossible). Elle <strong>maximise la couverture combinatoire</strong> : plus tu joues de grilles
          (plus ton pool est grand), plus tu multiplies tes chances relatives — mais le coût explose. Algorithme utilisé :
          <span className="font-mono-tab text-white/70"> Greedy Set-Cover</span>, approximation ln(n) du minimum optimal (problème NP-difficile).
        </p>
      </Card>

      <Card className="p-6 border-white/5 bg-[#0d0d10] space-y-6">
        {/* Pool size + target */}
        <div className="grid md:grid-cols-2 gap-6">
          <div>
            <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 mb-3">Taille du pool</div>
            <div className="flex flex-wrap items-center gap-2">
              {[6, 7, 8, 9, 10, 11, 12].map((k) => (
                <button
                  key={k}
                  data-testid={`pool-size-${k}`}
                  onClick={() => { setPoolSize(k); setPool([]); setResult(null); }}
                  className={`w-10 h-10 rounded-full border font-mono-tab text-sm transition-colors ${
                    poolSize === k ? "bg-violet-400 text-black border-violet-400 font-semibold" : "border-white/10 text-zinc-400 hover:text-white"
                  }`}
                >{k}</button>
              ))}
            </div>
          </div>
          <div>
            <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 mb-3">Garantie (numéros minimum)</div>
            <div className="flex items-center gap-2">
              {[3, 4, 5].map((t) => (
                <button
                  key={t}
                  data-testid={`target-${t}`}
                  onClick={() => setTarget(t)}
                  disabled={t > poolSize || (t === 5 && poolSize > 8)}
                  className={`h-10 px-4 rounded-full border font-mono-tab text-sm transition-colors disabled:opacity-30 ${
                    target === t ? "bg-emerald-400 text-black border-emerald-400 font-semibold" : "border-white/10 text-zinc-400 hover:text-white"
                  }`}
                >{t}+ bons</button>
              ))}
            </div>
          </div>
        </div>

        {/* Presets */}
        <div>
          <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 mb-3">Pré-remplir depuis les stats</div>
          <div className="flex flex-wrap items-center gap-2">
            <Button data-testid="preset-hot" variant="outline" size="sm" onClick={() => applyPreset("hot")} className="rounded-full border-red-500/30 text-red-400 hover:bg-red-500/10">
              Top {poolSize} chauds
            </Button>
            <Button data-testid="preset-cold" variant="outline" size="sm" onClick={() => applyPreset("cold")} className="rounded-full border-sky-500/30 text-sky-400 hover:bg-sky-500/10">
              Top {poolSize} froids
            </Button>
            <Button data-testid="preset-delay" variant="outline" size="sm" onClick={() => applyPreset("delay")} className="rounded-full border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10">
              Top {poolSize} retards
            </Button>
            <Button data-testid="preset-clear" variant="ghost" size="sm" onClick={() => setPool([])} className="rounded-full text-zinc-500">
              Effacer
            </Button>
          </div>
        </div>

        {/* Pool selector grid */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">
              Pool ({pool.length}/{poolSize})
            </div>
            <div className="text-xs text-zinc-500">Clique pour ajouter / retirer</div>
          </div>
          <div className="grid grid-cols-7 sm:grid-cols-10 gap-2">
            {Array.from({ length: 49 }, (_, i) => i + 1).map((n) => {
              const selected = pool.includes(n);
              return (
                <button
                  key={n}
                  data-testid={`pool-toggle-${n}`}
                  onClick={() => toggleBall(n)}
                  className="flex items-center justify-center"
                >
                  <LotteryBall number={n} variant={selected ? "chance" : "muted"} size="sm" />
                </button>
              );
            })}
          </div>
        </div>

        {/* Chance number */}
        <div>
          <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 mb-3">Numéro chance (identique sur toutes les grilles)</div>
          <div className="flex flex-wrap gap-2">
            {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
              <button
                key={n}
                data-testid={`chance-${n}`}
                onClick={() => setChance(n)}
                className={`w-10 h-10 rounded-full font-mono-tab text-sm border-2 transition-colors ${
                  chance === n ? "border-amber-400 bg-amber-500/20 text-amber-400 font-semibold" : "border-white/10 text-zinc-500 hover:border-amber-500/40"
                }`}
              >{n}</button>
            ))}
          </div>
        </div>

        <div className="flex justify-end">
          <Button
            data-testid="compute-wheel-btn"
            onClick={compute}
            disabled={busy || pool.length !== poolSize}
            className="rounded-full bg-violet-400 hover:bg-violet-300 text-black font-semibold h-11 px-6"
          >
            {busy ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Zap className="w-4 h-4 mr-2" />}
            Calculer la couverture minimale
          </Button>
        </div>
      </Card>

      {result && (
        <>
          <Card className="p-8 border-emerald-500/20 bg-emerald-500/[0.03]" data-testid="wheel-result">
            <div className="flex items-center gap-3 mb-4">
              <Target className="w-5 h-5 text-emerald-400" />
              <div>
                <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">Résultat</div>
                <h2 className="font-heading text-2xl font-semibold">
                  {result.tickets_count} grilles · {result.cost_euros} €
                </h2>
              </div>
            </div>
            <p className="text-sm text-zinc-300 leading-relaxed">
              <strong className="text-emerald-400">Garantie mathématique :</strong> si au moins <span className="font-mono-tab">{result.target_matches}</span> des 5 numéros tirés font partie de ton pool <span className="font-mono-tab">{JSON.stringify(result.pool)}</span>,
              alors au moins une des {result.tickets_count} grilles ci-dessous aura {result.target_matches}+ bons numéros.
            </p>
            <div className="mt-6 grid grid-cols-1 md:grid-cols-3 gap-4">
              <MetricCard label={`P(pool contient ≥${result.target_matches} des tirés)`} value={`${result.p_pool_covers_pct}%`} color="emerald" />
              <MetricCard label="P(grille aléatoire seule)" value={`${result.p_single_random_pct}%`} color="zinc" />
              <MetricCard label="Multiplicateur" value={`×${result.improvement_factor}`} color="amber" icon={TrendingUp} />
            </div>
          </Card>

          <div className="space-y-3">
            <div className="text-xs uppercase tracking-[0.2em] text-zinc-500">Grilles à jouer</div>
            {result.tickets.map((t, i) => (
              <Card key={i} className="p-4 border-white/5 bg-[#0d0d10] flex items-center gap-3" data-testid={`wheel-ticket-${i}`}>
                <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 w-12 font-mono-tab">
                  #{String(i + 1).padStart(2, "0")}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {t.numbers.map((n) => <LotteryBall key={n} number={n} size="sm" />)}
                  <span className="mx-1 text-zinc-700">+</span>
                  <LotteryBall number={t.chance} variant="chance" size="sm" />
                </div>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
};

const MetricCard = ({ label, value, color, icon: Icon }) => {
  const colorMap = {
    emerald: "text-emerald-400 border-emerald-500/30",
    amber: "text-amber-400 border-amber-500/30",
    zinc: "text-zinc-400 border-white/10",
  };
  return (
    <div className={`p-4 rounded-lg border bg-black/30 ${colorMap[color]}`}>
      <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 mb-2">{label}</div>
      <div className="flex items-baseline gap-2">
        {Icon && <Icon className="w-4 h-4" />}
        <div className="font-heading text-2xl font-bold font-mono-tab">{value}</div>
      </div>
    </div>
  );
};

export default Wheel;
