# LotoStat.Pro — PRD

## Problem Statement (verbatim)
> Je voudrais créer une application qui puisse analyser les statistiques des tirages loto sur les trois dernières années et proposer en fonction des tirages...

## Context
- Utilisateur a fourni une v0.7 précédente (LotoAI-Pro) construite avec ChatGPT puis Claude en stack Streamlit + SQLite.
- On repart sur une architecture moderne React + FastAPI + MongoDB tout en récupérant les concepts forts de la v0.7.

## User Personas
- **Joueur curieux** : veut visualiser des stats sur les tirages et générer des grilles.
- **Analyste amateur** : veut importer ses propres CSV, comparer tendances récentes vs global, tester des stratégies.

## Architecture
- Frontend : React 19 + Tailwind + shadcn/ui + Recharts + Framer/motion, thème dark premium.
- Backend : FastAPI + Motor (MongoDB async), auth Google via Emergent Auth (cookie httpOnly + Bearer fallback).
- Storage : MongoDB collections `users`, `user_sessions`, `draws`, `saved_grids`.

## Core Requirements
- Loto FDJ (5 numéros 1-49 + 1 chance 1-10)
- Auth Google Emergent
- Multi-utilisateur (données isolées par user_id)
- Import CSV format v0.7 (`date,n1..n5,chance`)
- Génération 3 ans de données de démo réalistes
- Analyses : fréquence, chauds/froids, retards, paires, triplets, somme, parité, écarts, tendance récent-vs-global (v0.7)
- Générateur 4 stratégies : chauds, froids, équilibrée, aléatoire pondérée
- Sauvegarde de grilles par utilisateur

## Implemented (2026-02-XX)
- Landing page + auth Google Emergent + AuthCallback
- Dashboard avec sidebar 7 vues : Overview, Historique, Statistiques, Chauds/Froids, Générateur, Mes grilles, Données
- Backend endpoints : auth, draws (list/import/demo/clear), stats (frequency/hot-cold/pairs/sum-parity/trend), grids (generate/save/list/delete), csv-template
- TrendIndicator (récent vs global) importé du v0.7 avec seuil de fiabilité
- % d'apparition sur paires/triplets (héritage v0.7)
- Avertissement statistique visible (loto = jeu indépendant)
- Bug fix : save_grid renvoyait _id ObjectId → corrigé

## Backlog / Not implemented
- **P1** Vérification pas-à-pas d'une grille contre l'historique (a-t-elle été gagnante ?)
- **P1** Comparaison de plusieurs stratégies (backtesting sur historique)
- **P2** Heatmap visuelle des paires (grille 49×49)
- **P2** Export des grilles en PDF / partage
- **P2** Import FDJ direct depuis fdj.fr (fragile — abandonné dans la v0.7 aussi)
- **P2** Notifications par email lors d'un tirage réel
