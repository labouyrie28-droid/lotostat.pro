import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { LotteryBall } from "@/components/LotteryBall";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Loader2 } from "lucide-react";

const History = () => {
  const [draws, setDraws] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/draws?limit=1500");
        setDraws(data);
      } finally { setLoading(false); }
    })();
  }, []);

  const filtered = draws.filter((d) => !filter || d.date.includes(filter));

  return (
    <div className="space-y-8" data-testid="history-page">
      <header className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div className="space-y-3">
          <div className="text-xs uppercase tracking-[0.3em] text-zinc-500">Historique</div>
          <h1 className="font-heading text-4xl font-bold tracking-tighter">Tirages passés</h1>
        </div>
        <div className="w-full sm:w-72">
          <Input
            data-testid="history-filter-input"
            placeholder="Filtrer par date (ex: 2024)"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="bg-[#0d0d10] border-white/10 focus-visible:ring-amber-500"
          />
        </div>
      </header>

      <Card className="border-white/5 bg-[#0d0d10] overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-16"><Loader2 className="w-5 h-5 animate-spin text-zinc-500" /></div>
        ) : (
          <div className="max-h-[70vh] overflow-y-auto divide-y divide-white/5">
            <div className="px-6 py-3 flex items-center justify-between text-[10px] uppercase tracking-[0.2em] text-zinc-500 bg-black/40 sticky top-0 backdrop-blur">
              <div>Date</div>
              <div>Numéros + Chance</div>
            </div>
            {filtered.map((d) => (
              <div key={d.id} className="px-6 py-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div className="font-mono-tab text-sm text-zinc-300 w-32">{d.date}</div>
                <div className="flex flex-wrap items-center gap-2">
                  {d.numbers.map((n) => (<LotteryBall key={n} number={n} size="sm" />))}
                  <div className="mx-1 text-zinc-700">+</div>
                  <LotteryBall number={d.chance} variant="chance" size="sm" />
                </div>
              </div>
            ))}
            {filtered.length === 0 && <div className="p-10 text-center text-sm text-zinc-500">Aucun tirage.</div>}
          </div>
        )}
      </Card>
    </div>
  );
};

export default History;
