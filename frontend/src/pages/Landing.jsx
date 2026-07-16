import { Button } from "@/components/ui/button";
import { LotteryBall } from "@/components/LotteryBall";
import { BarChart3, Sparkles, Target, TrendingUp, ArrowRight, LineChart } from "lucide-react";

const Landing = () => {
  const handleLogin = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    const redirectUrl = window.location.origin + "/dashboard";
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  return (
    <div className="min-h-screen bg-[#050507] text-white overflow-x-hidden">
      {/* Header */}
      <header className="sticky top-0 z-40 backdrop-blur-xl bg-black/60 border-b border-white/5">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-amber-500/15 border border-amber-500/40 flex items-center justify-center pulse-amber">
              <Sparkles className="w-4 h-4 text-amber-400" />
            </div>
            <span className="font-heading font-bold tracking-tight text-lg">LotoStat<span className="text-amber-400">.</span>Pro</span>
          </div>
          <Button
            data-testid="header-login-btn"
            onClick={handleLogin}
            className="rounded-full bg-amber-400 hover:bg-amber-300 text-black font-semibold px-5"
          >
            Se connecter <ArrowRight className="w-4 h-4 ml-1" />
          </Button>
        </div>
      </header>

      {/* Hero */}
      <section className="relative">
        <div
          className="absolute inset-0 opacity-40 pointer-events-none"
          style={{
            backgroundImage:
              "radial-gradient(circle at 20% 20%, rgba(245,158,11,0.12), transparent 40%), radial-gradient(circle at 80% 60%, rgba(14,165,233,0.10), transparent 45%)",
          }}
        />
        <div className="relative max-w-7xl mx-auto px-6 py-24 md:py-32 grid md:grid-cols-12 gap-12 items-center">
          <div className="md:col-span-7 space-y-8">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/10 bg-white/[0.02] text-xs uppercase tracking-[0.2em] text-zinc-400">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-400" /> Analyse Loto FDJ · 3 ans d'historique
            </div>
            <h1 className="font-heading text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tighter leading-[1.05]">
              Décodez les tirages du Loto.<br />
              <span className="text-zinc-400">Générez vos grilles</span>{" "}
              <span className="text-amber-400">avec méthode.</span>
            </h1>
            <p className="text-zinc-400 text-base md:text-lg max-w-xl leading-relaxed">
              Statistiques avancées sur 3 années — fréquences, retards, paires, sommes, parités.
              Quatre stratégies de génération pour construire vos grilles sur base rationnelle.
            </p>
            <div className="flex flex-wrap items-center gap-4">
              <Button
                data-testid="hero-login-btn"
                onClick={handleLogin}
                className="rounded-full bg-amber-400 hover:bg-amber-300 text-black font-semibold h-12 px-7 text-base"
              >
                Commencer avec Google <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
              <a
                href="#features"
                className="text-sm text-zinc-400 hover:text-white transition-colors duration-200 uppercase tracking-[0.2em]"
              >
                Découvrir →
              </a>
            </div>
          </div>

          <div className="md:col-span-5">
            <div className="relative rounded-2xl border border-white/5 bg-[#0d0d10] p-8">
              <div className="text-xs font-bold uppercase tracking-[0.2em] text-zinc-500 mb-6">
                Tirage type
              </div>
              <div className="flex flex-wrap gap-3 items-center">
                <LotteryBall number={7} variant="hot" size="lg" />
                <LotteryBall number={13} variant="hot" size="lg" />
                <LotteryBall number={22} variant="default" size="lg" />
                <LotteryBall number={31} variant="cold" size="lg" />
                <LotteryBall number={46} variant="default" size="lg" />
                <div className="mx-2 text-zinc-600 text-xl">+</div>
                <LotteryBall number={5} variant="chance" size="lg" />
              </div>
              <div className="mt-8 grid grid-cols-3 gap-4 text-center">
                <div className="p-3 rounded-lg border border-white/5 bg-black/40">
                  <div className="font-heading text-2xl text-red-400 font-bold">128</div>
                  <div className="text-[10px] uppercase tracking-widest text-zinc-500 mt-1">Chauds</div>
                </div>
                <div className="p-3 rounded-lg border border-white/5 bg-black/40">
                  <div className="font-heading text-2xl text-sky-400 font-bold">72</div>
                  <div className="text-[10px] uppercase tracking-widest text-zinc-500 mt-1">Froids</div>
                </div>
                <div className="p-3 rounded-lg border border-white/5 bg-black/40">
                  <div className="font-heading text-2xl text-emerald-400 font-bold">34j</div>
                  <div className="text-[10px] uppercase tracking-widest text-zinc-500 mt-1">Retards</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="max-w-7xl mx-auto px-6 py-24 border-t border-white/5">
        <div className="grid md:grid-cols-3 gap-6">
          {[
            { icon: BarChart3, title: "Fréquences", text: "Numéros chauds et froids, sur toute la période d'analyse." },
            { icon: LineChart, title: "Retards", text: "Combien de tirages depuis la dernière apparition." },
            { icon: Target, title: "Paires & triplets", text: "Combinaisons de numéros qui reviennent ensemble." },
            { icon: TrendingUp, title: "Somme & parité", text: "Distributions statistiques, écarts entre numéros." },
            { icon: Sparkles, title: "4 stratégies", text: "Chauds, froids, équilibrée ou aléatoire pondérée." },
            { icon: ArrowRight, title: "Mes grilles", text: "Sauvegardez vos grilles générées et suivez-les." },
          ].map((f, i) => (
            <div
              key={i}
              data-testid={`feature-card-${i}`}
              className="p-6 rounded-2xl border border-white/5 bg-[#0d0d10] hover:-translate-y-1 transition-transform duration-200"
            >
              <div className="w-10 h-10 rounded-lg bg-white/5 border border-white/5 flex items-center justify-center mb-4">
                <f.icon className="w-5 h-5 text-amber-400" />
              </div>
              <div className="font-heading text-lg font-semibold mb-2">{f.title}</div>
              <p className="text-sm text-zinc-400 leading-relaxed">{f.text}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="border-t border-white/5 py-10 text-center text-xs text-zinc-600 uppercase tracking-[0.2em]">
        LotoStat.Pro · Analyse statistique — Le loto reste un jeu de hasard
      </footer>
    </div>
  );
};

export default Landing;
