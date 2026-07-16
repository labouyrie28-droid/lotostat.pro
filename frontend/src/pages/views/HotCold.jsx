import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { LotteryBall } from "@/components/LotteryBall";
import { Loader2 } from "lucide-react";

const HotCold = () => {
  const [data, setData] = useState(null);
  const [freq, setFreq] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [hc, f] = await Promise.all([
          api.get("/stats/hot-cold"),
          api.get("/stats/frequency"),
        ]);
        setData(hc.data); setFreq(f.data);
      } finally { setLoading(false); }
    })();
  }, []);

  if (loading) return <div className="flex items-center justify-center py-24"><Loader2 className="w-6 h-6 animate-spin text-zinc-500" /></div>;
  if (!data || !freq || freq.total_draws === 0) {
    return (
      <Card className="p-10 border-white/5 bg-[#0d0d10] text-center">
        <p className="text-sm text-zinc-400">Aucun tirage. Générez des données de démo.</p>
      </Card>
    );
  }

  const hotSet = new Set(data.hot);
  const coldSet = new Set(data.cold);
  const delayMap = new Map(data.all_delays.map((d) => [d.number, d.delay]));
  const freqMap = new Map(freq.main.map((d) => [d.number, d.count]));
  const topDelayNums = new Set(data.top_delays.map((d) => d.number));

  const variantFor = (n) => hotSet.has(n) ? "hot" : coldSet.has(n) ? "cold" : "default";

  return (
    <div className="space-y-10" data-testid="hotcold-page">
      <header className="space-y-3">
        <div className="text-xs uppercase tracking-[0.3em] text-zinc-500">Analyse Chaleur</div>
        <h1 className="font-heading text-4xl font-bold tracking-tighter">Chauds · Froids · Retards</h1>
      </header>

      <Tabs defaultValue="hot" className="w-full">
        <TabsList className="bg-[#0d0d10] border border-white/5 rounded-full p-1">
          <TabsTrigger data-testid="tab-hot" value="hot" className="rounded-full data-[state=active]:bg-red-500/15 data-[state=active]:text-red-400 px-5">🔥 Chauds</TabsTrigger>
          <TabsTrigger data-testid="tab-cold" value="cold" className="rounded-full data-[state=active]:bg-sky-500/15 data-[state=active]:text-sky-400 px-5">❄️ Froids</TabsTrigger>
          <TabsTrigger data-testid="tab-delay" value="delay" className="rounded-full data-[state=active]:bg-emerald-500/15 data-[state=active]:text-emerald-400 px-5">⏳ Retards</TabsTrigger>
          <TabsTrigger data-testid="tab-all" value="all" className="rounded-full data-[state=active]:bg-amber-500/15 data-[state=active]:text-amber-400 px-5">Tous</TabsTrigger>
        </TabsList>

        <TabsContent value="hot" className="mt-6">
          <Card className="p-8 border-white/5 bg-[#0d0d10]">
            <div className="text-xs uppercase tracking-[0.2em] text-red-400 mb-4">Top 10 des plus fréquents</div>
            <div className="flex flex-wrap gap-3 mb-6">
              {data.hot.map((n) => <LotteryBall key={n} number={n} variant="hot" size="lg" />)}
            </div>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              {data.hot.map((n) => (
                <div key={n} className="px-3 py-2 rounded-lg border border-red-500/20 bg-red-500/[0.03]">
                  <div className="text-[10px] uppercase text-zinc-500">Numéro</div>
                  <div className="font-heading font-bold text-lg">{n}</div>
                  <div className="text-[10px] text-zinc-500 mt-1">{freqMap.get(n)} sorties</div>
                </div>
              ))}
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="cold" className="mt-6">
          <Card className="p-8 border-white/5 bg-[#0d0d10]">
            <div className="text-xs uppercase tracking-[0.2em] text-sky-400 mb-4">Top 10 des moins fréquents</div>
            <div className="flex flex-wrap gap-3 mb-6">
              {data.cold.map((n) => <LotteryBall key={n} number={n} variant="cold" size="lg" />)}
            </div>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              {data.cold.map((n) => (
                <div key={n} className="px-3 py-2 rounded-lg border border-sky-500/20 bg-sky-500/[0.03]">
                  <div className="text-[10px] uppercase text-zinc-500">Numéro</div>
                  <div className="font-heading font-bold text-lg">{n}</div>
                  <div className="text-[10px] text-zinc-500 mt-1">{freqMap.get(n)} sorties</div>
                </div>
              ))}
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="delay" className="mt-6">
          <Card className="p-8 border-white/5 bg-[#0d0d10]">
            <div className="text-xs uppercase tracking-[0.2em] text-emerald-400 mb-4">Numéros les plus en retard</div>
            <div className="flex flex-wrap gap-3 mb-6">
              {data.top_delays.map((d) => <LotteryBall key={d.number} number={d.number} variant="delay" size="lg" />)}
            </div>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              {data.top_delays.map((d) => (
                <div key={d.number} className="px-3 py-2 rounded-lg border border-emerald-500/20 bg-emerald-500/[0.03]">
                  <div className="text-[10px] uppercase text-zinc-500">Numéro</div>
                  <div className="font-heading font-bold text-lg">{d.number}</div>
                  <div className="text-[10px] text-zinc-500 mt-1">retard : {d.delay} tirages</div>
                </div>
              ))}
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="all" className="mt-6">
          <Card className="p-8 border-white/5 bg-[#0d0d10]">
            <div className="text-xs uppercase tracking-[0.2em] text-zinc-500 mb-6">Grille 1 à 49 · code couleur global</div>
            <div className="grid grid-cols-7 sm:grid-cols-10 gap-3">
              {Array.from({ length: 49 }, (_, i) => i + 1).map((n) => {
                const isTopDelay = topDelayNums.has(n);
                const variant = isTopDelay && !hotSet.has(n) && !coldSet.has(n) ? "delay" : variantFor(n);
                return (
                  <div key={n} className="flex flex-col items-center gap-1">
                    <LotteryBall number={n} variant={variant} />
                    <div className="text-[9px] text-zinc-600 font-mono-tab">{freqMap.get(n)}× · {delayMap.get(n)}j</div>
                  </div>
                );
              })}
            </div>
            <div className="mt-6 flex flex-wrap items-center gap-4 text-[11px] text-zinc-400">
              <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-red-500" /> Chauds</div>
              <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-sky-500" /> Froids</div>
              <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-emerald-500" /> Grand retard</div>
              <div className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-zinc-600" /> Neutre</div>
            </div>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default HotCold;
