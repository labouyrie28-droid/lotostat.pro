import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Loader2 } from "lucide-react";

const Heatmap = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [hover, setHover] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/stats/heatmap");
        setData(data);
      } finally { setLoading(false); }
    })();
  }, []);

  const matrix = useMemo(() => {
    if (!data) return null;
    const m = Array.from({ length: 50 }, () => Array(50).fill(0));
    for (const p of data.pairs) {
      m[p.a][p.b] = p.count;
      m[p.b][p.a] = p.count;
    }
    return m;
  }, [data]);

  if (loading) return <div className="flex items-center justify-center py-24"><Loader2 className="w-6 h-6 animate-spin text-zinc-500" /></div>;
  if (!data || data.total_draws === 0) {
    return (
      <Card className="p-10 border-white/5 bg-[#0d0d10] text-center">
        <p className="text-sm text-zinc-400">Aucun tirage. Générez des données de démo ou importez un CSV.</p>
      </Card>
    );
  }

  const cellColor = (val) => {
    if (val === 0) return "rgba(255,255,255,0.02)";
    const ratio = Math.min(1, val / (data.max || 1));
    // interpolate: sky -> amber -> red
    const alpha = 0.15 + ratio * 0.75;
    let r, g, b;
    if (ratio < 0.5) {
      const t = ratio / 0.5;
      r = Math.round(14 + (245 - 14) * t);
      g = Math.round(165 + (158 - 165) * t);
      b = Math.round(233 + (11 - 233) * t);
    } else {
      const t = (ratio - 0.5) / 0.5;
      r = Math.round(245 + (239 - 245) * t);
      g = Math.round(158 + (68 - 158) * t);
      b = Math.round(11 + (68 - 11) * t);
    }
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  };

  const nums = Array.from({ length: 49 }, (_, i) => i + 1);

  return (
    <div className="space-y-8" data-testid="heatmap-page">
      <header className="space-y-3">
        <div className="text-xs uppercase tracking-[0.3em] text-zinc-500">Heatmap</div>
        <h1 className="font-heading text-4xl font-bold tracking-tighter">Paires de numéros</h1>
        <p className="text-sm text-zinc-500 max-w-2xl leading-relaxed">
          Grille 49×49 : chaque cellule montre combien de fois les 2 numéros sont sortis ensemble sur les {data.total_draws} tirages.
          Bleu = rare · Ambre = moyen · Rouge = fréquent. Max observé : <span className="text-amber-400 font-mono-tab">{data.max}</span> co-occurrences.
        </p>
      </header>

      <Card className="p-4 md:p-6 border-white/5 bg-[#0d0d10] overflow-auto">
        <div className="min-w-max mx-auto">
          <div className="flex">
            <div className="w-6" />
            {nums.map((n) => (
              <div key={n} className="w-4 text-[8px] text-zinc-600 text-center font-mono-tab">{n % 5 === 0 ? n : ""}</div>
            ))}
          </div>
          {nums.map((r) => (
            <div key={r} className="flex items-center">
              <div className="w-6 text-[8px] text-zinc-600 text-right pr-1 font-mono-tab">{r % 5 === 0 ? r : ""}</div>
              {nums.map((c) => {
                const val = matrix[r][c];
                const isDiag = r === c;
                return (
                  <div
                    key={c}
                    onMouseEnter={() => setHover({ a: r, b: c, count: val })}
                    onMouseLeave={() => setHover(null)}
                    data-testid={`heatmap-cell-${r}-${c}`}
                    className="w-4 h-4 border border-black/40 transition-transform duration-100 hover:scale-125 hover:z-10 relative cursor-crosshair"
                    style={{ backgroundColor: isDiag ? "rgba(255,255,255,0.06)" : cellColor(val) }}
                    title={isDiag ? `${r}` : `${r} + ${c} : ${val}×`}
                  />
                );
              })}
            </div>
          ))}
        </div>
      </Card>

      <Card className="p-5 border-white/5 bg-[#0d0d10] flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3 text-xs">
          <span className="text-zinc-500 uppercase tracking-widest text-[10px]">Échelle</span>
          <div className="flex items-center h-4 rounded overflow-hidden" style={{ width: 200 }}>
            {Array.from({ length: 20 }, (_, i) => (
              <div key={i} className="flex-1" style={{ backgroundColor: cellColor(((i + 1) / 20) * data.max) }} />
            ))}
          </div>
          <span className="font-mono-tab text-zinc-400">0 → {data.max}</span>
        </div>

        <div className="text-xs font-mono-tab" data-testid="heatmap-hover-info">
          {hover ? (
            hover.a === hover.b
              ? <span className="text-zinc-500">Diagonale (numéro {hover.a})</span>
              : <span className="text-white">
                  <span className="text-amber-400">{hover.a}</span> + <span className="text-amber-400">{hover.b}</span> ·
                  <span className="ml-2">{hover.count} co-occurrence{hover.count > 1 ? "s" : ""}</span>
                </span>
          ) : <span className="text-zinc-500">Survolez une cellule pour voir le détail</span>}
        </div>
      </Card>
    </div>
  );
};

export default Heatmap;
