import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { LotteryBall } from "@/components/LotteryBall";
import { toast } from "sonner";
import { Loader2, Wallet, TrendingUp, TrendingDown, Plus, Trophy } from "lucide-react";

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

const Bilan = () => {
  const [bilan, setBilan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [addOpen, setAddOpen] = useState(false);
  const [numbers, setNumbers] = useState(["", "", "", "", ""]);
  const [chance, setChance] = useState("");
  const [amount, setAmount] = useState("2.20");
  const [playedDate, setPlayedDate] = useState(new Date().toISOString().slice(0, 10));
  const [saving, setSaving] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/grids/bilan");
      setBilan(data);
    } catch {
      toast.error("Impossible de charger le bilan");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, []);

  const resetForm = () => {
    setNumbers(["", "", "", "", ""]);
    setChance("");
    setAmount("2.20");
    setPlayedDate(new Date().toISOString().slice(0, 10));
  };

  const submitManual = async () => {
    const nums = numbers.map((n) => parseInt(n, 10));
    const chanceNum = parseInt(chance, 10);
    const amt = parseFloat(amount);

    if (nums.some((n) => isNaN(n) || n < 1 || n > 49) || new Set(nums).size !== 5) {
      toast.error("5 numéros uniques entre 1 et 49 requis");
      return;
    }
    if (isNaN(chanceNum) || chanceNum < 1 || chanceNum > 10) {
      toast.error("Numéro chance entre 1 et 10 requis");
      return;
    }
    if (isNaN(amt) || amt < 0) {
      toast.error("Montant invalide");
      return;
    }

    setSaving(true);
    try {
      await api.post("/grids/manual", {
        numbers: nums,
        chance: chanceNum,
        amount_played: amt,
        played_date: playedDate,
      });
      toast.success("Grille ajoutée à votre bilan");
      setAddOpen(false);
      resetForm();
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Ajout impossible");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="w-6 h-6 animate-spin text-zinc-500" />
      </div>
    );
  }

  const net = bilan?.net ?? 0;
  const netColor = net > 0 ? "text-emerald-400" : net < 0 ? "text-red-400" : "text-zinc-400";
  const NetIcon = net >= 0 ? TrendingUp : TrendingDown;

  return (
    <div className="space-y-8" data-testid="bilan-page">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-3">
          <div className="text-xs uppercase tracking-[0.3em] text-zinc-500">Mon bilan</div>
          <h1 className="font-heading text-4xl font-bold tracking-tighter">Suivi de mes mises</h1>
          <p className="text-sm text-zinc-500 max-w-2xl leading-relaxed">
            Le total réel de ce que vous avez dépensé et gagné sur vos grilles jouées.
          </p>
        </div>
        <Button
          data-testid="add-manual-grid-btn"
          onClick={() => setAddOpen(true)}
          className="rounded-full bg-amber-400 hover:bg-amber-300 text-black font-semibold gap-2"
        >
          <Plus className="w-4 h-4" /> Ajouter une mise
        </Button>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="p-6 border-white/5 bg-[#0d0d10]">
          <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 mb-2">Total dépensé</div>
          <div className="font-mono-tab font-bold text-3xl text-white">{bilan?.total_spent?.toFixed(2)} €</div>
        </Card>
        <Card className="p-6 border-white/5 bg-[#0d0d10]">
          <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 mb-2">Total gagné</div>
          <div className="font-mono-tab font-bold text-3xl text-emerald-400">{bilan?.total_won?.toFixed(2)} €</div>
        </Card>
        <Card className="p-6 border-white/5 bg-[#0d0d10]">
          <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 mb-2 flex items-center gap-2">
            <NetIcon className="w-3.5 h-3.5" /> Solde net
          </div>
          <div className={`font-mono-tab font-bold text-3xl ${netColor}`}>
            {net > 0 ? "+" : ""}{net?.toFixed(2)} €
          </div>
        </Card>
      </div>

      {!bilan || bilan.grids_count === 0 ? (
        <Card className="p-12 text-center border-white/5 bg-[#0d0d10]">
          <Wallet className="w-10 h-10 mx-auto text-zinc-600 mb-4" />
          <p className="text-sm text-zinc-400">
            Aucune mise enregistrée. Marquez une grille comme "jouée" dans Mes grilles, ou ajoutez-en une manuellement.
          </p>
        </Card>
      ) : (
        <div className="grid gap-4">
          {bilan.grids.map((g) => (
            <Card key={g.id} className="p-6 border-white/5 bg-[#0d0d10]" data-testid={`bilan-grid-${g.id}`}>
              <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-3 text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                    <span>Jouée le {g.played_date}</span>
                    <span>·</span>
                    <span>{g.amount_played?.toFixed(2)} € misés</span>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {g.numbers.map((n) => <LotteryBall key={n} number={n} size="md" />)}
                    <div className="mx-1 text-zinc-700">+</div>
                    <LotteryBall number={g.chance} variant="chance" size="md" />
                  </div>
                </div>
                <div className="text-right shrink-0">
                  {g.result ? (
                    <>
                      <div className="flex items-center gap-2 justify-end mb-1">
                        <Trophy className={`w-4 h-4 ${rankColor(g.result.rank_label)}`} />
                        <span className={`font-heading font-semibold ${rankColor(g.result.rank_label)}`}>
                          {g.result.rank_label}
                        </span>
                      </div>
                      <div className="font-mono-tab font-bold text-lg">
                        {g.payout > 0 ? (
                          <span className="text-emerald-400">+{g.payout.toFixed(2)} €</span>
                        ) : (
                          <span className="text-zinc-500">0,00 €</span>
                        )}
                      </div>
                    </>
                  ) : (
                    <span className="text-xs text-zinc-500">En attente du tirage</span>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Add manual grid dialog */}
      <Dialog open={addOpen} onOpenChange={(o) => { setAddOpen(o); if (!o) resetForm(); }}>
        <DialogContent className="bg-[#0d0d10] border-white/10 text-white" data-testid="add-manual-dialog">
          <DialogHeader>
            <DialogTitle className="font-heading text-2xl">Ajouter une mise manuelle</DialogTitle>
            <DialogDescription className="text-zinc-500">
              Pour une grille jouée en dehors du générateur.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-2">
            <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">5 numéros (1-49)</div>
            <div className="flex gap-2">
              {numbers.map((n, i) => (
                <Input
                  key={i}
                  data-testid={`manual-num-${i}`}
                  type="number"
                  min="1"
                  max="49"
                  value={n}
                  onChange={(e) => {
                    const copy = [...numbers];
                    copy[i] = e.target.value;
                    setNumbers(copy);
                  }}
                  className="bg-black/30 border-white/10 text-center"
                />
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">Numéro chance (1-10)</div>
            <Input
              data-testid="manual-chance"
              type="number"
              min="1"
              max="10"
              value={chance}
              onChange={(e) => setChance(e.target.value)}
              className="bg-black/30 border-white/10"
            />
          </div>

          <div className="space-y-2">
            <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">Montant misé (€)</div>
            <Input
              data-testid="manual-amount"
              type="number"
              step="0.10"
              min="0"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="bg-black/30 border-white/10"
            />
          </div>

          <div className="space-y-2">
            <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">Date de jeu</div>
            <Input
              data-testid="manual-date"
              type="date"
              value={playedDate}
              onChange={(e) => setPlayedDate(e.target.value)}
              className="bg-black/30 border-white/10"
            />
          </div>

          <Button
            data-testid="submit-manual-grid-btn"
            onClick={submitManual}
            disabled={saving}
            className="w-full rounded-full bg-amber-400 hover:bg-amber-300 text-black font-semibold gap-2"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            Ajouter
          </Button>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Bilan;
