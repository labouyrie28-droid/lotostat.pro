import { useState, useRef } from "react";
import { api, API } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Upload, Loader2, Sparkles, Trash2, FileDown } from "lucide-react";

const DataImport = () => {
  const [busy, setBusy] = useState(false);
  const fileRef = useRef(null);

  const generateDemo = async () => {
    setBusy(true);
    try {
      const { data } = await api.post("/draws/generate-demo");
      toast.success(`${data.inserted} tirages générés`);
    } catch { toast.error("Échec"); }
    finally { setBusy(false); }
  };

  const clearDraws = async () => {
    if (!window.confirm("Supprimer tous les tirages ?")) return;
    setBusy(true);
    try {
      const { data } = await api.delete("/draws");
      toast.success(`${data.deleted} tirages supprimés`);
    } catch { toast.error("Échec"); }
    finally { setBusy(false); }
  };

  const importCSV = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post("/draws/import-csv", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success(`${data.inserted} tirages importés${data.errors ? ` (${data.errors} erreurs)` : ""}`);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Import échoué");
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <div className="space-y-8" data-testid="data-page">
      <header className="space-y-3">
        <div className="text-xs uppercase tracking-[0.3em] text-zinc-500">Données</div>
        <h1 className="font-heading text-4xl font-bold tracking-tighter">Gestion des tirages</h1>
      </header>

      <div className="grid md:grid-cols-2 gap-6">
        <Card className="p-8 border-white/5 bg-[#0d0d10]">
          <Sparkles className="w-6 h-6 text-amber-400 mb-4" />
          <h2 className="font-heading text-xl font-semibold mb-2">Données de démonstration</h2>
          <p className="text-sm text-zinc-400 mb-6 leading-relaxed">
            Génère 3 années de tirages simulés (lundi, mercredi, samedi) avec une distribution
            réaliste pour tester toutes les analyses.
          </p>
          <div className="flex gap-3">
            <Button
              data-testid="generate-demo-data-btn"
              onClick={generateDemo}
              disabled={busy}
              className="rounded-full bg-amber-400 hover:bg-amber-300 text-black font-semibold"
            >
              {busy ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Sparkles className="w-4 h-4 mr-2" />}
              Générer 3 ans
            </Button>
            <Button
              data-testid="clear-draws-btn"
              variant="outline"
              onClick={clearDraws}
              disabled={busy}
              className="rounded-full border-white/10 bg-transparent hover:bg-red-500/10 hover:text-red-400 hover:border-red-500/40"
            >
              <Trash2 className="w-4 h-4 mr-2" /> Effacer
            </Button>
          </div>
        </Card>

        <Card className="p-8 border-white/5 bg-[#0d0d10]">
          <Upload className="w-6 h-6 text-sky-400 mb-4" />
          <h2 className="font-heading text-xl font-semibold mb-2">Import CSV</h2>
          <p className="text-sm text-zinc-400 mb-3 leading-relaxed">
            Format compatible LotoAI Pro v0.7 : <code className="text-amber-400">date,n1,n2,n3,n4,n5,chance</code>.
            Dates au format <code>YYYY-MM-DD</code> ou <code>DD/MM/YYYY</code>.
          </p>
          <a
            href={`${API}/draws/csv-template`}
            data-testid="download-template-link"
            className="inline-flex items-center gap-1 text-xs text-sky-400 hover:text-sky-300 mb-6"
          >
            <FileDown className="w-3 h-3" /> Télécharger le template CSV
          </a>
          <div>
            <input
              ref={fileRef}
              data-testid="csv-file-input"
              type="file"
              accept=".csv"
              onChange={importCSV}
              disabled={busy}
              className="block text-sm text-zinc-400 file:mr-3 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-white file:text-black hover:file:bg-zinc-200 file:cursor-pointer cursor-pointer"
            />
          </div>
        </Card>
      </div>

      <Card className="p-5 border-amber-500/20 bg-amber-500/[0.03]">
        <p className="text-xs text-zinc-400 leading-relaxed">
          <strong className="text-amber-400">Note sur l'import FDJ officiel :</strong> la v0.7 embarquait un scraper direct depuis fdj.fr,
          mais leur format évolue régulièrement (colonnes différentes selon la période, URLs mouvantes) et
          la connexion depuis notre environnement de test n'était pas fiable. Vous pouvez télécharger l'archive
          officielle depuis <a href="https://www.fdj.fr/jeux-de-tirage/loto/historique" target="_blank" rel="noreferrer" className="text-amber-400 underline">fdj.fr</a>,
          renommer les colonnes selon le template ci-dessus et importer le CSV.
        </p>
      </Card>
    </div>
  );
};

export default DataImport;
