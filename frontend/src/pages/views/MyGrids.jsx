import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { LotteryBall } from "@/components/LotteryBall";
import { toast } from "sonner";
import { Loader2, Trash2, Bookmark, Trophy, Target, Clock } from "lucide-react";

const strategyLabels = {
  hot: "Chauds", cold: "Froids", balanced: "Équilibrée", weighted_random: "Aléatoire pondérée",
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
        <p className="text-sm text-zinc-500 max-w-2xl leading-relaxed">
          Chaque grille est automatiquement comparée au premier tirage réel qui suit sa date de sauvegarde.
          Si aucun tirage ultérieur n'existe encore dans la base, la grille est "en attente".
        </p>
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
          {grids.map((g) => {
            const r = g.result;
            const gridSet = new Set(g.numbers);
            return (
              <Card key={g.id} className="p-6 border-white/5 bg-[#0d0d10]" data-testid={`saved-grid-${g.id}`}>
                <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
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
                </div>

                {r ? (
                  <div className="mt-6 pt-5 border-t border-white/5 space-y-3">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <Trophy className={`w-4 h-4 ${rankColor(r.rank_label)}`} />
                        <div>
                          <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">Tirage du {r.target_date}</div>
                          <div className={`font-heading font-semibold text-lg ${rankColor(r.rank_label)}`}>{r.rank_label}</div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="font-mono-tab font-bold text-xl text-white">
                          {r.main_matches}<span className="text-zinc-500">/5</span>
                          {r.chance_match && <span className="text-amber-400 ml-2 text-base">+ ★</span>}
                        </div>
                        <div className="text-[10px] uppercase tracking-widest text-zinc-500">bons numéros</div>
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[10px] uppercase tracking-widest text-zinc-500 mr-1">Tirage :</span>
                      {r.target_numbers.map((n) => (
                        <LotteryBall
                          key={n}
                          number={n}
                          variant={gridSet.has(n) ? "hot" : "default"}
                          size="sm"
                        />
                      ))}
                      <div className="mx-1 text-zinc-700">+</div>
                      <LotteryBall
                        number={r.target_chance}
                        variant={r.chance_match ? "chance" : "muted"}
                        size="sm"
                      />
                    </div>
                  </div>
                ) : (
                  <div className="mt-6 pt-5 border-t border-white/5 flex items-center gap-2 text-xs text-zinc-500">
                    <Clock className="w-3.5 h-3.5" />
                    En attente du prochain tirage — le résultat apparaîtra automatiquement dès qu'un tirage postérieur sera dans la base.
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default MyGrids;
