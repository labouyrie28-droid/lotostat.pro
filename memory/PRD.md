# LotoStat.Pro — PRD

## Problem Statement (verbatim)
> Je voudrais créer une application qui puisse analyser les statistiques des tirages loto sur les trois dernières années et proposer en fonction des tirages...

## Context & Data
- User uploaded LotoAI-Pro v0.7 (Streamlit+SQLite) for comparison.
- User uploaded real FDJ CSV (loto_201911.csv) with **1048 draws from Nov 2019 to July 2026**.
- Migrated to modern stack: React + FastAPI + MongoDB, keeping v0.7 statistical concepts.

## Architecture
- Frontend: React 19 + Tailwind + shadcn/ui + Recharts, dark premium theme (Outfit/IBM Plex/JetBrains Mono).
- Backend: FastAPI + Motor (MongoDB async), Emergent Google Auth, APScheduler for daily cron.
- Email: Resend (labouyrie28@gmail.com account, test mode limits recipients).
- Storage: MongoDB collections `users`, `user_sessions`, `draws`, `saved_grids`, `alert_prefs`.

## Implemented
### Iteration 1 — MVP (2026-02-XX)
- Landing + Google Auth Emergent + AuthCallback
- 7 dashboard views: Overview, History, Stats, HotCold, Generator, MyGrids, DataImport
- Backend endpoints: auth, draws (list/import/demo/clear), stats (frequency/hot-cold/pairs/sum-parity/trend), grids (generate/save/list/delete), csv-template
- CSV importer auto-detects FDJ official format (`;` separator, `date_de_tirage;boule_1..5;numero_chance`) and v0.7 template (`date,n1..5,chance`)
- Bug fix: save_grid ObjectId serialization (pop _id after insert)

### Iteration 2 — Backtest + Heatmap + Alerts (2026-02-XX)
- **Backtest** (`/api/backtest`): walk-forward comparison of 5 strategies (hot/cold/balanced/weighted_random/random) with avg matches, hit ≥3 rate, chance hit rate, rank distribution
- **Heatmap** (`/api/stats/heatmap`): 49x49 pair co-occurrence matrix with sky→amber→red gradient
- **Alerts** (`/api/alerts/*`): user prefs (email/strategy/grids_count/enabled), manual send, APScheduler daily cron at 12:00 Paris that fires on Mon/Wed/Sat (Loto draw days)
- Balanced strategy: added random sampling from top-8 pools to avoid deterministic identical grids

## Backlog
- **P1** Verify a played grid against full history (was it ever a winner?)
- **P2** Verify Resend domain to send to any email (currently test mode restricts to account owner)
- **P2** Estimated payout per strategy in backtest (2 nums = 2.20€, 3=10€, 4=800€, 5=100k€, 5+chance = jackpot)
- **P2** Compare user's saved grid to next actual draw
- **P2** Timeline chart: number streaks over time
