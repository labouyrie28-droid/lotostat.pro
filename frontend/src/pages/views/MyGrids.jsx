import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LotteryBall } from "@/components/LotteryBall";
import { toast } from "sonner";
import { Loader2, Trash2, Bookmark } from "lucide-react";

const strategyLabels = {
  hot: "Chauds", cold: "Froids", balanced: "Équilibrée", weighted_random: "Aléatoire pondérée",
};

const MyGrids = () => {
  const [grids, setGrids] = useState([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/grids");
      setGrids(data);
    } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const remove = async (id) => {
    try {
      await api.delete(`/grids/${id}`);
      toast.success("Grille supprimée");
      await load();
    } catch { toast.error("Impossible de supprimer"); }
  };

  return (
    <div className="space-y-8" data-testid="grids-page">
      <header className="space-y-3">
        <div className="text-xs uppercase tracking-[0.3em] text-zinc-500">Mes grilles</div>
        <h1 className="font-heading text-4xl font-bold tracking-tighter">Grilles sauvegardées</h1>
      </header>

      {loading ? (
        <div className="flex items-center justify-center py-24"><Loader2 className="w-6 h-6 animate-spin text-zinc-500" /></div>
      ) : grids.length === 0 ? (
        <Card className="p-12 text-center border-white/5 bg-[#0d0d10]">
          <Bookmark className="w-10 h-10 mx-auto text-zinc-600 mb-4" />
          <p className="text-sm text-zinc-400">Aucune grille sauvegardée. Générez-en dans l'onglet Générateur.</p>
        </Card>
      ) : (
        <div className="grid gap-4">
          {grids.map((g) => (
            <Card key={g.id} className="p-5 border-white/5 bg-[#0d0d10] flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-3 text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                  <span className="px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
                    {strategyLabels[g.strategy] || g.strategy}
                  </span>
                  <span>{new Date(g.created_at).toLocaleString("fr-FR")}</span>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {g.numbers.map((n) => <LotteryBall key={n} number={n} size="md" />)}
                  <div className="mx-1 text-zinc-700">+</div>
                  <LotteryBall number={g.chance} variant="chance" size="md" />
                </div>
              </div>
              <Button
                data-testid={`delete-grid-${g.id}`}
                variant="ghost"
                onClick={() => remove(g.id)}
                className="text-zinc-400 hover:text-red-400 hover:bg-red-500/10 gap-2"
              >
                <Trash2 className="w-4 h-4" /> Supprimer
              </Button>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

export default MyGrids;
