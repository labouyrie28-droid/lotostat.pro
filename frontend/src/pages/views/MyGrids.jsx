import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { LotteryBall } from "@/components/LotteryBall";
import { toast } from "sonner";
import { Loader2, Trash2, Bookmark, Trophy, Target, Clock, Share2, Link as LinkIcon, Mail, Copy, Check, Wallet, Euro } from "lucide-react";

const strategyLabels = {
  hot: "Chauds", cold: "Froids", balanced: "Équilibrée", weighted_random: "Aléatoire pondérée",
  credible_top5: "Top 5 crédibles",
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
  const [shareOpen, setShareOpen] = useState(false);
  const [shareGrid, setShareGrid] = useState(null);
  const [shareLink, setShareLink] = useState("");
  const [shareEmail, setShareEmail] = useState("");
  const [shareMessage, setShareMessage] = useState("");
  const [copied, setCopied] = useState(false);
  const [sending, setSending] = useState(false);
  const [markOpen, setMarkOpen] = useState(false);
  const [markGrid, setMarkGrid] = useState(null);
  const [markAmount, setMarkAmount] = useState("2.20");
  const [markDate, setMarkDate] = useState(new Date().toISOString().slice(0, 10));
  const [marking, setMarking] = useState(false);
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
  const openMark = (g) => {
    setMarkGrid(g);
    setMarkAmount("2.20");
    setMarkDate(new Date().toISOString().slice(0, 10));
    setMarkOpen(true);
  };

  const submitMark = async () => {
    if (!markGrid) return;
    const amount = parseFloat(markAmount);
    if (isNaN(amount) || amount < 0) {
      toast.error("Montant invalide");
      return;
    }
    setMarking(true);
    try {
      await api.post(`/grids/${markGrid.id}/mark-played`, {
        amount_played: amount,
        played_date: markDate,
      });
      toast.success("Grille marquée comme jouée");
      setMarkOpen(false);
      await load();
    } catch {
      toast.error("Impossible de marquer la grille");
    } finally {
      setMarking(false);
    }
  };

  const openShare = async (g) => {
    setShareGrid(g);
    setShareEmail("");
    setShareMessage("");
    setCopied(false);
    setShareOpen(true);
    try {
      const { data } = await api.post("/grids/share", { grid_id: g.id });
      const url = `${window.location.origin}/share/${data.token}`;
      setShareLink(url);
    } catch { toast.error("Impossible de créer le lien"); setShareOpen(false); }
  };

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(shareLink);
      setCopied(true);
      toast.success("Lien copié !");
      setTimeout(() => setCopied(false), 2000);
    } catch { toast.error("Copie manuelle nécessaire"); }
  };

  const sendEmail = async () => {
    if (!shareEmail || !shareGrid) return;
    setSending(true);
    try {
      await api.post("/grids/share-email", {
        grid_id: shareGrid.id,
        to_email: shareEmail,
        message: shareMessage || null,
      });
      toast.success(`Email envoyé à ${shareEmail}`);
      setShareOpen(false);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Envoi échoué");
    } finally { setSending(false); }
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
                  <div className="flex items-center gap-2">
                    <Button
                      data-testid={`share-grid-${g.id}`}
                      variant="ghost"
                      onClick={() => openShare(g)}
                      className="text-zinc-400 hover:text-amber-400 hover:bg-amber-500/10 gap-2"
                    >
                      <Share2 className="w-4 h-4" /> Partager
                    </Button>
                    <Button
                      data-testid={`delete-grid-${g.id}`}
                      variant="ghost"
                      onClick={() => remove(g.id)}
                      className="text-zinc-400 hover:text-red-400 hover:bg-red-500/10 gap-2"
                    >
                      <Trash2 className="w-4 h-4" /> Supprimer
                    </Button>
                  </div>
                </div>

                {r ? (
                  <div className="mt-6 pt-5 border-t border-white/5 space-y-3">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <Trophy className={`w-4 h-4 ${rankColor(r.rank_label)}`} />
                        <div>
                          <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 flex items-center gap-2">
                            <span>Tirage du {r.target_date}</span>
                            {r.is_historical && (
                              <span className="px-1.5 py-0.5 rounded-full bg-violet-500/15 text-violet-400 text-[9px] font-semibold uppercase tracking-widest">
                                simulation historique
                              </span>
                            )}
                          </div>
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

      {/* Share dialog */}
      <Dialog open={shareOpen} onOpenChange={setShareOpen}>
        <DialogContent className="bg-[#0d0d10] border-white/10 text-white" data-testid="share-dialog">
          <DialogHeader>
            <DialogTitle className="font-heading text-2xl">Partager la grille</DialogTitle>
            <DialogDescription className="text-zinc-500">
              Envoie le lien à un proche ou par email direct.
            </DialogDescription>
          </DialogHeader>

          {shareGrid && (
            <div className="flex flex-wrap items-center gap-2 pb-4 border-b border-white/5">
              {shareGrid.numbers.map((n) => <LotteryBall key={n} number={n} size="sm" />)}
              <div className="mx-1 text-zinc-700">+</div>
              <LotteryBall number={shareGrid.chance} variant="chance" size="sm" />
            </div>
          )}

          <div className="space-y-2">
            <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 flex items-center gap-2">
              <LinkIcon className="w-3 h-3" /> Lien de partage
            </div>
            <div className="flex items-center gap-2">
              <Input
                data-testid="share-link-input"
                readOnly
                value={shareLink}
                className="bg-black/30 border-white/10 font-mono-tab text-xs"
              />
              <Button
                data-testid="copy-link-btn"
                onClick={copyLink}
                variant="outline"
                className="rounded-full border-white/10 shrink-0 gap-2"
              >
                {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                {copied ? "Copié" : "Copier"}
              </Button>
            </div>
          </div>

          <div className="space-y-2 pt-4 border-t border-white/5">
            <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500 flex items-center gap-2">
              <Mail className="w-3 h-3" /> Envoyer par email
            </div>
            <Input
              data-testid="share-email-input"
              type="email"
              placeholder="destinataire@exemple.com"
              value={shareEmail}
              onChange={(e) => setShareEmail(e.target.value)}
              className="bg-black/30 border-white/10"
            />
            <Input
              data-testid="share-message-input"
              placeholder="Message optionnel (ex: joue avec moi cette semaine !)"
              value={shareMessage}
              onChange={(e) => setShareMessage(e.target.value)}
              className="bg-black/30 border-white/10 text-sm"
            />
            <Button
              data-testid="send-share-email-btn"
              onClick={sendEmail}
              disabled={sending || !shareEmail}
              className="w-full rounded-full bg-amber-400 hover:bg-amber-300 text-black font-semibold gap-2"
            >
              {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Mail className="w-4 h-4" />}
              Envoyer
            </Button>
            <p className="text-[11px] text-zinc-500 leading-relaxed">
              Note : sans domaine vérifié sur resend.com, les emails ne partent qu'à l'adresse du compte Resend.
            </p>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default MyGrids;
