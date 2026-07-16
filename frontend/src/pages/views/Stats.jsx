import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { Loader2, AlertTriangle } from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell,
} from "recharts";

const AXIS_COLOR = "#52525b";
const GRID_COLOR = "rgba(255,255,255,0.05)";

const Stats = () => {
  const [freq, setFreq] = useState(null);
  const [sumParity, setSumParity] = useState(null);
  const [pairs, setPairs] = useState(null);
  const [trend, setTrend] = useState(null);
  const [trendWindow, setTrendWindow] = useState(20);
  const [loading, setLoading] = useState(true);

  const loadTrend = async (w) => {
    const { data } = await api.get(`/stats/trend?window=${w}`);
    setTrend(data);
  };

  useEffect(() => {
    (async () => {
      try {
        const [f, s, p] = await Promise.all([
          api.get("/stats/frequency"),
          api.get("/stats/sum-parity"),
          api.get("/stats/pairs"),
        ]);
        setFreq(f.data); setSumParity(s.data); setPairs(p.data);
        await loadTrend(20);
      } finally { setLoading(false); }
    })();
  }, []);

  useEffect(() => {
    if (loading) return;
    loadTrend(trendWindow);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [trendWindow]);

  if (loading) {
    return <div className="flex items-center justify-center py-24"><Loader2 className="w-6 h-6 animate-spin text-zinc-500" /></div>;
  }
  if (!freq || freq.total_draws === 0) {
    return (
      <Card className="p-10 border-white/5 bg-[#0d0d10] text-center">
        <p className="text-sm text-zinc-400">Aucun tirage. Générez des données de démo depuis la vue d'ensemble.</p>
      </Card>
    );
  }

  const maxMain = Math.max(...freq.main.map((d) => d.count));

  return (
    <div className="space-y-10" data-testid="stats-page">
      <header className="space-y-3">
        <div className="text-xs uppercase tracking-[0.3em] text-zinc-500">Statistiques</div>
        <h1 className="font-heading text-4xl font-bold tracking-tighter">Analyse des tirages</h1>
        <div className="text-xs text-zinc-500">Sur {freq.total_draws} tirages</div>
      </header>

      {/* Fréquences numéros principaux */}
      <Card className="p-6 border-white/5 bg-[#0d0d10]">
        <div className="flex items-baseline justify-between mb-6">
          <div>
            <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-1">Fréquences</div>
            <h2 className="font-heading text-2xl font-semibold">Sorties par numéro (1 à 49)</h2>
          </div>
        </div>
        <div className="h-72" data-testid="chart-frequency-main">
          <ResponsiveContainer>
            <BarChart data={freq.main} margin={{ top: 8, right: 8, bottom: 8, left: 0 }}>
              <CartesianGrid stroke={GRID_COLOR} vertical={false} />
              <XAxis dataKey="number" stroke={AXIS_COLOR} tick={{ fontSize: 10, fontFamily: "JetBrains Mono" }} />
              <YAxis stroke={AXIS_COLOR} tick={{ fontSize: 10 }} />
              <Tooltip
                contentStyle={{ background: "#0a0a0c", border: "1px solid #27272a", borderRadius: 8, fontSize: 12 }}
                cursor={{ fill: "rgba(255,255,255,0.03)" }}
              />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {freq.main.map((d) => {
                  const ratio = d.count / maxMain;
                  const color = ratio > 0.75 ? "#EF4444" : ratio < 0.4 ? "#0EA5E9" : "#F59E0B";
                  return <Cell key={d.number} fill={color} fillOpacity={0.85} />;
                })}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      {/* Fréquence chance */}
      <Card className="p-6 border-white/5 bg-[#0d0d10]">
        <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-1">Numéro chance</div>
        <h2 className="font-heading text-2xl font-semibold mb-6">Sorties (1 à 10)</h2>
        <div className="h-56" data-testid="chart-frequency-chance">
          <ResponsiveContainer>
            <BarChart data={freq.chance}>
              <CartesianGrid stroke={GRID_COLOR} vertical={false} />
              <XAxis dataKey="number" stroke={AXIS_COLOR} tick={{ fontSize: 11, fontFamily: "JetBrains Mono" }} />
              <YAxis stroke={AXIS_COLOR} tick={{ fontSize: 10 }} />
              <Tooltip contentStyle={{ background: "#0a0a0c", border: "1px solid #27272a", borderRadius: 8, fontSize: 12 }} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
              <Bar dataKey="count" fill="#F59E0B" fillOpacity={0.85} radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      {/* Sum & parity */}
      <div className="grid md:grid-cols-2 gap-6">
        <Card className="p-6 border-white/5 bg-[#0d0d10]">
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-1">Somme des 5 numéros</div>
          <h2 className="font-heading text-xl font-semibold mb-4">Distribution</h2>
          <div className="grid grid-cols-3 gap-3 mb-4">
            <Stat label="Min" value={sumParity.sum_min} />
            <Stat label="Moy" value={sumParity.sum_avg} />
            <Stat label="Max" value={sumParity.sum_max} />
          </div>
          <div className="h-40">
            <ResponsiveContainer>
              <BarChart data={sumParity.sum_distribution}>
                <XAxis dataKey="range" stroke={AXIS_COLOR} tick={{ fontSize: 9 }} />
                <YAxis stroke={AXIS_COLOR} tick={{ fontSize: 10 }} />
                <Tooltip contentStyle={{ background: "#0a0a0c", border: "1px solid #27272a", borderRadius: 8, fontSize: 12 }} />
                <Bar dataKey="count" fill="#10B981" fillOpacity={0.8} radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card className="p-6 border-white/5 bg-[#0d0d10]">
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-1">Parité</div>
          <h2 className="font-heading text-xl font-semibold mb-4">Nombre de pairs par tirage</h2>
          <div className="h-56">
            <ResponsiveContainer>
              <BarChart data={sumParity.parity_distribution}>
                <XAxis dataKey="even_count" stroke={AXIS_COLOR} tick={{ fontSize: 11 }} />
                <YAxis stroke={AXIS_COLOR} tick={{ fontSize: 10 }} />
                <Tooltip contentStyle={{ background: "#0a0a0c", border: "1px solid #27272a", borderRadius: 8, fontSize: 12 }} />
                <Bar dataKey="count" fill="#0EA5E9" fillOpacity={0.8} radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      {/* Trend (v0.7 inspired) */}
      <Card className="p-6 border-white/5 bg-[#0d0d10]">
        <div className="flex items-baseline justify-between mb-4">
          <div>
            <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-1">Tendances récentes</div>
            <h2 className="font-heading text-2xl font-semibold">Récent vs global</h2>
            <p className="text-xs text-zinc-500 mt-1">Écart en points de % entre le taux récent (fenêtre) et le taux historique.</p>
          </div>
          <div className="w-64">
            <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 mb-2">Fenêtre : {trendWindow} tirages</div>
            <Slider
              data-testid="trend-window-slider"
              min={5}
              max={Math.max(5, freq.total_draws)}
              value={[trendWindow]}
              onValueChange={([v]) => setTrendWindow(v)}
            />
          </div>
        </div>

        {trend && !trend.fiable && (
          <div className="rounded-lg border border-amber-500/20 bg-amber-500/[0.03] p-3 flex items-start gap-2 mb-4">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400 mt-0.5 shrink-0" />
            <div className="text-[11px] text-zinc-400 leading-relaxed">
              Fenêtre de {trend.fenetre_recente} tirages (seuil de fiabilité : {trend.seuil_fiabilite}).
              Les écarts sont probablement du bruit statistique. Augmentez la fenêtre pour un résultat plus fiable.
            </div>
          </div>
        )}

        <div className="grid md:grid-cols-2 gap-6">
          <TrendList title="En hausse" items={trend?.hausse || []} accent="text-emerald-400" />
          <TrendList title="En baisse" items={trend?.baisse || []} accent="text-red-400" />
        </div>
      </Card>

      {/* Pairs & triplets */}
      <div className="grid md:grid-cols-2 gap-6">
        <Card className="p-6 border-white/5 bg-[#0d0d10]">
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-1">Paires fréquentes</div>
          <h2 className="font-heading text-xl font-semibold mb-4">Numéros sortis ensemble</h2>
          <div className="space-y-2" data-testid="pairs-list">
            {pairs.top_pairs.slice(0, 10).map((p, i) => (
              <div key={`${p.a}-${p.b}`} className="flex items-center justify-between px-3 py-2 rounded-lg border border-white/5 hover:bg-white/[0.02]">
                <div className="flex items-center gap-2">
                  <div className="text-[10px] text-zinc-600 w-4">#{i + 1}</div>
                  <span className="font-mono-tab text-sm">{p.a}</span>
                  <span className="text-zinc-600 text-xs">+</span>
                  <span className="font-mono-tab text-sm">{p.b}</span>
                </div>
                <div className="text-xs text-zinc-400 tabular-nums">{p.count}× <span className="text-amber-400">{p.percent}%</span></div>
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-6 border-white/5 bg-[#0d0d10]">
          <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-1">Triplets fréquents</div>
          <h2 className="font-heading text-xl font-semibold mb-4">Trios les plus vus</h2>
          <div className="space-y-2" data-testid="triplets-list">
            {pairs.top_triplets.slice(0, 10).map((t, i) => (
              <div key={`${t.a}-${t.b}-${t.c}`} className="flex items-center justify-between px-3 py-2 rounded-lg border border-white/5 hover:bg-white/[0.02]">
                <div className="flex items-center gap-2">
                  <div className="text-[10px] text-zinc-600 w-4">#{i + 1}</div>
                  <span className="font-mono-tab text-sm">{t.a}</span>
                  <span className="text-zinc-600 text-xs">·</span>
                  <span className="font-mono-tab text-sm">{t.b}</span>
                  <span className="text-zinc-600 text-xs">·</span>
                  <span className="font-mono-tab text-sm">{t.c}</span>
                </div>
                <div className="text-xs text-zinc-400 tabular-nums">{t.count}× <span className="text-amber-400">{t.percent}%</span></div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
};

const Stat = ({ label, value }) => (
  <div className="p-3 rounded-lg border border-white/5 bg-black/30">
    <div className="text-[10px] uppercase tracking-widest text-zinc-500 mb-1">{label}</div>
    <div className="font-heading font-bold text-lg">{value}</div>
  </div>
);

const TrendList = ({ title, items, accent }) => (
  <div>
    <div className={`text-xs uppercase tracking-[0.2em] mb-3 ${accent}`}>{title}</div>
    <div className="space-y-1.5">
      {items.map((t) => (
        <div key={t.number} className="flex items-center justify-between px-3 py-2 rounded-md border border-white/5">
          <div className="flex items-center gap-3">
            <span className="font-mono-tab font-semibold">{t.number}</span>
            <span className="text-[10px] text-zinc-500">R: {t.taux_recent}% · G: {t.taux_global}%</span>
          </div>
          <span className={`font-mono-tab text-sm font-semibold ${t.ecart > 0 ? "text-emerald-400" : "text-red-400"}`}>
            {t.ecart > 0 ? "+" : ""}{t.ecart} pt
          </span>
        </div>
      ))}
    </div>
  </div>
);

export default Stats;
