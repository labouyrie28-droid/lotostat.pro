import { cn } from "@/lib/utils";

export const LotteryBall = ({ number, variant = "default", size = "md", className, ...rest }) => {
  const sizes = {
    sm: "w-9 h-9 text-sm",
    md: "w-12 h-12 text-base",
    lg: "w-14 h-14 text-lg",
  };
  const base =
    "rounded-full flex items-center justify-center font-mono-tab font-semibold border transition-transform duration-200 ease-out";

  const variants = {
    default:
      "border-zinc-700 bg-zinc-900 text-white shadow-[inset_0_2px_10px_rgba(255,255,255,0.05)] hover:-translate-y-0.5",
    hot:
      "border-red-500/70 bg-red-500/5 text-red-400 shadow-[0_0_18px_rgba(239,68,68,0.18),inset_0_2px_10px_rgba(255,255,255,0.06)] hover:-translate-y-0.5",
    cold:
      "border-sky-500/70 bg-sky-500/5 text-sky-400 shadow-[0_0_18px_rgba(14,165,233,0.18),inset_0_2px_10px_rgba(255,255,255,0.06)] hover:-translate-y-0.5",
    delay:
      "border-emerald-500/70 bg-emerald-500/5 text-emerald-400 shadow-[0_0_18px_rgba(16,185,129,0.16),inset_0_2px_10px_rgba(255,255,255,0.06)] hover:-translate-y-0.5",
    chance:
      "border-amber-500 bg-amber-500/10 text-amber-400 shadow-[0_0_20px_rgba(245,158,11,0.22),inset_0_2px_10px_rgba(255,255,255,0.08)] hover:-translate-y-0.5",
    muted:
      "border-zinc-800 bg-zinc-950 text-zinc-500",
  };

  return (
    <div
      data-testid={`lottery-ball-${variant}-${number}`}
      className={cn(base, sizes[size], variants[variant], "ball-in", className)}
      {...rest}
    >
      {number}
    </div>
  );
};
