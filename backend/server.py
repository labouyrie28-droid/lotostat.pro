from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, UploadFile, File, Depends
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os
import io
import csv
import zipfile
import random
import logging
import uuid
import asyncio
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime, timezone, timedelta
from collections import Counter
import httpx

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

app = FastAPI()
api_router = APIRouter(prefix="/api")

# --------- Models ---------

class User(BaseModel):
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Draw(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    date: str  # ISO YYYY-MM-DD
    numbers: List[int]  # 5 numbers, 1-49
    chance: int  # 1-10


class SavedGrid(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    strategy: str
    numbers: List[int]
    chance: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GenerateGridRequest(BaseModel):
    strategy: Literal["hot", "cold", "balanced", "weighted_random", "credible_top5"]
    count: int = 1


class SaveGridRequest(BaseModel):
    strategy: str
    numbers: List[int]
    chance: int


# --------- Auth Helper ---------

async def get_current_user(request: Request) -> User:
    # REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    session_token = request.cookies.get("session_token")
    if not session_token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            session_token = auth_header.replace("Bearer ", "")
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session_doc = await db.user_sessions.find_one({"session_token": session_token}, {"_id": 0})
    if not session_doc:
        raise HTTPException(status_code=401, detail="Invalid session")

    expires_at = session_doc["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")

    user_doc = await db.users.find_one({"user_id": session_doc["user_id"]}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=401, detail="User not found")

    # Enforce whitelist on every request (private mode)
    allowed = [e.strip().lower() for e in os.environ.get("ALLOWED_EMAILS", "").split(",") if e.strip()]
    if allowed and user_doc.get("email", "").lower() not in allowed:
        raise HTTPException(status_code=403, detail="Accès refusé (mode privé)")

    return User(**user_doc)


# --------- Auth Endpoints ---------

class SessionRequest(BaseModel):
    session_id: str


@api_router.post("/auth/session")
async def create_session(payload: SessionRequest, response: Response):
    # REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    async with httpx.AsyncClient(timeout=15) as http:
        r = await http.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": payload.session_id},
        )
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid session_id")
    data = r.json()
    email = data["email"]
    name = data.get("name", email)
    picture = data.get("picture")
    session_token = data["session_token"]

    # Access control: private mode — only whitelisted emails can log in.
    # Whitelist is a comma-separated list in ALLOWED_EMAILS env var.
    # Leave empty to allow anyone.
    allowed = [e.strip().lower() for e in os.environ.get("ALLOWED_EMAILS", "").split(",") if e.strip()]
    if allowed and email.lower() not in allowed:
        raise HTTPException(status_code=403, detail="Accès refusé. Cette application est actuellement en mode privé.")

    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        user_id = existing["user_id"]
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": {"name": name, "picture": picture}}
        )
    else:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        await db.users.insert_one({
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # Auto-load the official FDJ dataset on first login (user has no draws yet)
    existing_draws = await db.draws.count_documents({"user_id": user_id})
    if existing_draws == 0:
        try:
            await _load_official_for_user(user_id)
        except Exception as e:
            logger.warning(f"Could not auto-load official dataset for {email}: {e}")

    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=7 * 24 * 3600,
    )

    return {"user_id": user_id, "email": email, "name": name, "picture": picture}


@api_router.get("/auth/me")
async def me(user: User = Depends(get_current_user)):
    return {"user_id": user.user_id, "email": user.email, "name": user.name, "picture": user.picture}


@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    session_token = request.cookies.get("session_token")
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    response.delete_cookie("session_token", path="/", samesite="none", secure=True)
    return {"ok": True}


# --------- Draws Endpoints ---------

def _valid_draw(nums: List[int], chance: int) -> bool:
    if not (len(nums) == 5 and all(1 <= n <= 49 for n in nums) and len(set(nums)) == 5):
        return False
    if not (1 <= chance <= 10):
        return False
    return True


@api_router.get("/draws")
async def list_draws(user: User = Depends(get_current_user), limit: int = 500):
    cursor = db.draws.find({"user_id": user.user_id}, {"_id": 0}).sort("date", -1).limit(limit)
    return await cursor.to_list(limit)


@api_router.delete("/draws")
async def clear_draws(user: User = Depends(get_current_user)):
    res = await db.draws.delete_many({"user_id": user.user_id})
    return {"deleted": res.deleted_count}


@api_router.post("/draws/generate-demo")
async def generate_demo(user: User = Depends(get_current_user)):
    # Clear existing then generate ~3 years of realistic data (Mon/Wed/Sat draws)
    await db.draws.delete_many({"user_id": user.user_id})
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=365 * 3)
    draws = []
    d = start
    # Slight bias: some numbers appear a bit more often to make stats interesting
    hot_bias = {7, 13, 22, 27, 31, 41, 46}
    weights = [1.0] * 50
    for n in hot_bias:
        weights[n] = 1.6
    while d <= today:
        # Draw days: Monday(0), Wednesday(2), Saturday(5)
        if d.weekday() in (0, 2, 5):
            nums = set()
            while len(nums) < 5:
                pick = random.choices(range(1, 50), weights=weights[1:50])[0]
                nums.add(pick)
            chance = random.randint(1, 10)
            draws.append({
                "id": str(uuid.uuid4()),
                "user_id": user.user_id,
                "date": d.isoformat(),
                "numbers": sorted(list(nums)),
                "chance": chance,
            })
        d += timedelta(days=1)
    if draws:
        await db.draws.insert_many(draws)
    return {"inserted": len(draws)}


@api_router.post("/draws/load-official")
async def load_official_dataset(user: User = Depends(get_current_user)):
    """Import the bundled official FDJ dataset (1048 draws Nov 2019 → July 2026)."""
    result = await _load_official_for_user(user.user_id)
    return result


async def _load_official_for_user(user_id: str) -> dict:
    """Internal helper: load the bundled official FDJ CSV into a user's draws collection."""
    official_path = ROOT_DIR / "data" / "loto_fdj_official.csv"
    if not official_path.exists():
        raise HTTPException(status_code=500, detail="Dataset officiel introuvable")

    with open(official_path, "rb") as f:
        raw = f.read()
    content = None
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            content = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if content is None:
        raise HTTPException(status_code=500, detail="Encodage dataset non reconnu")

    # Clear existing draws for the user first
    await db.draws.delete_many({"user_id": user_id})

    reader = csv.DictReader(io.StringIO(content), delimiter=";")
    docs = []
    errors = 0
    for row in reader:
        try:
            date_iso = datetime.strptime(row["date_de_tirage"].strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
            nums = sorted([int(row[f"boule_{i}"]) for i in range(1, 6)])
            chance = int(row["numero_chance"])
            if not _valid_draw(nums, chance):
                errors += 1
                continue
            docs.append({
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "date": date_iso,
                "numbers": nums,
                "chance": chance,
            })
        except Exception:
            errors += 1
    if docs:
        await db.draws.insert_many(docs)
    return {
        "inserted": len(docs),
        "errors": errors,
        "period": {"from": min(d["date"] for d in docs) if docs else None,
                   "to": max(d["date"] for d in docs) if docs else None},
    }

async def _fetch_latest_official_rows() -> List[dict]:
    """Télécharge l'historique officiel FDJ (mis à jour après chaque tirage)
    et retourne les tirages sous forme de liste triée par date croissante."""
    async with httpx.AsyncClient(timeout=30) as http:
        r = await http.get( f"https://media.fdj.fr/static-draws/csv/loto/loto_201911.zip?t={int(datetime.now(timezone.utc).timestamp())}", headers={"Cache-Control": "no-cache"}, )
        r.raise_for_status()
        content_bytes = r.content

    with zipfile.ZipFile(io.BytesIO(content_bytes)) as zf:
        csv_name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
        raw = zf.read(csv_name)

    content = None
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            content = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if content is None:
        return []

    reader = csv.DictReader(io.StringIO(content), delimiter=";")
    rows = []
    for row in reader:
        try:
            date_iso = datetime.strptime(row["date_de_tirage"].strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
            nums = sorted([int(row[f"boule_{i}"]) for i in range(1, 6)])
            chance = int(row["numero_chance"])
            if not _valid_draw(nums, chance):
                continue
            rows.append({"date": date_iso, "numbers": nums, "chance": chance})
        except Exception:
            continue
    rows.sort(key=lambda d: d["date"])
    return rows


async def _run_draw_sync():
    """S'exécute chaque soir. Les soirs de tirage (lun/mer/sam), télécharge
    les résultats officiels FDJ et ajoute le nouveau tirage à l'historique
    de chaque utilisateur qui a déjà des tirages enregistrés."""
    today = datetime.now(timezone.utc).date()
    if today.weekday() not in (0, 2, 5):
        return
    try:
        official_rows = await _fetch_latest_official_rows()
    except Exception as e:
        logger.error(f"Draw sync: failed to fetch FDJ data: {e}")
        return
    if not official_rows:
        return
    latest_rows = official_rows[-5:]

    user_ids = await db.draws.distinct("user_id")
    for uid in user_ids:
        try:
            existing_dates = set(await db.draws.distinct("date", {"user_id": uid}))
            to_insert = [
                {"id": str(uuid.uuid4()), "user_id": uid, **row}
                for row in latest_rows if row["date"] not in existing_dates
            ]
            if to_insert:
                await db.draws.insert_many(to_insert)
                logger.info(f"Draw sync: added {len(to_insert)} new draw(s) for user {uid}")
        except Exception as e:
            logger.error(f"Draw sync error for user {uid}: {e}")


@api_router.post("/draws/import-csv")
async def import_csv(file: UploadFile = File(...), user: User = Depends(get_current_user)):
    raw = await file.read()
    # Try multiple encodings (FDJ uses latin-1/cp1252 sometimes)
    content = None
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            content = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if content is None:
        raise HTTPException(status_code=400, detail="Encodage du fichier non reconnu")

    # Auto-detect delimiter (FDJ uses ';', v0.7 template uses ',')
    sample = content[:2000]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","

    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    fieldnames = reader.fieldnames or []
    if not fieldnames:
        raise HTTPException(status_code=400, detail="Fichier CSV vide")

    # Column aliases (case-insensitive) — supports FDJ official format & v0.7 template
    date_aliases = ["date_de_tirage", "date"]
    number_aliases = [
        ["boule_1", "boule1", "n1", "num1"],
        ["boule_2", "boule2", "n2", "num2"],
        ["boule_3", "boule3", "n3", "num3"],
        ["boule_4", "boule4", "n4", "num4"],
        ["boule_5", "boule5", "n5", "num5"],
    ]
    chance_aliases = ["numero_chance", "numchance", "chance", "n_chance"]

    lower_map = {f.lower().strip(): f for f in fieldnames}
    def find(aliases):
        for a in aliases:
            if a in lower_map:
                return lower_map[a]
        return None

    date_col = find(date_aliases)
    num_cols = [find(a) for a in number_aliases]
    chance_col = find(chance_aliases)

    if not date_col or not all(num_cols) or not chance_col:
        raise HTTPException(
            status_code=400,
            detail=f"Colonnes attendues introuvables. Colonnes trouvées: {fieldnames[:20]}. "
                   "Formats acceptés: FDJ officiel (date_de_tirage;boule_1..5;numero_chance) ou template v0.7 (date,n1..n5,chance)."
        )

    def parse_date(raw_date):
        raw_date = raw_date.strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"):
            try:
                return datetime.strptime(raw_date, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    inserted = 0
    errors = 0
    docs = []
    seen_dates = set()
    # Load existing dates to avoid duplicates
    existing_cursor = db.draws.find({"user_id": user.user_id}, {"_id": 0, "date": 1})
    async for d in existing_cursor:
        seen_dates.add(d["date"])

    for row in reader:
        try:
            date_iso = parse_date(row[date_col])
            if not date_iso:
                errors += 1
                continue
            if date_iso in seen_dates:
                continue  # skip duplicate
            nums = [int(row[c]) for c in num_cols]
            chance = int(row[chance_col])
            if not _valid_draw(nums, chance):
                errors += 1
                continue
            docs.append({
                "id": str(uuid.uuid4()),
                "user_id": user.user_id,
                "date": date_iso,
                "numbers": sorted(nums),
                "chance": chance,
            })
            seen_dates.add(date_iso)
        except Exception:
            errors += 1
    if docs:
        await db.draws.insert_many(docs)
        inserted = len(docs)
    return {"inserted": inserted, "errors": errors, "format_detected": "FDJ" if delimiter == ";" else "template"}


# --------- Stats Endpoints ---------

async def _get_all_draws(user_id: str) -> List[dict]:
    cursor = db.draws.find({"user_id": user_id}, {"_id": 0}).sort("date", 1)
    return await cursor.to_list(10000)


@api_router.get("/stats/frequency")
async def stats_frequency(user: User = Depends(get_current_user)):
    import math
    draws = await _get_all_draws(user.user_id)
    total = len(draws)
    main = Counter()
    chance = Counter()
    for d in draws:
        for n in d["numbers"]:
            main[n] += 1
        chance[d["chance"]] += 1

    # Rigueur : chi² sur les 49 numéros (48 degrés de liberté)
    expected_main = 5 * total / 49 if total else 0
    sigma_main = math.sqrt(total * (5/49) * (44/49)) if total else 0
    chi2_main = sum((main.get(n, 0) - expected_main) ** 2 / expected_main for n in range(1, 50)) if expected_main > 0 else 0

    # Idem pour la chance (10 numéros, 9 dof)
    expected_chance = total / 10 if total else 0
    sigma_chance = math.sqrt(total * (1/10) * (9/10)) if total else 0
    chi2_chance = sum((chance.get(n, 0) - expected_chance) ** 2 / expected_chance for n in range(1, 11)) if expected_chance > 0 else 0

    return {
        "total_draws": total,
        "main": [{"number": n, "count": main.get(n, 0)} for n in range(1, 50)],
        "chance": [{"number": n, "count": chance.get(n, 0)} for n in range(1, 11)],
        "main_stats": {
            "expected": round(expected_main, 1),
            "sigma": round(sigma_main, 1),
            "chi2": round(chi2_main, 2),
            "chi2_threshold_5pct": 65.17,  # dof=48, alpha=0.05
            "biased": chi2_main > 65.17,
        },
        "chance_stats": {
            "expected": round(expected_chance, 1),
            "sigma": round(sigma_chance, 1),
            "chi2": round(chi2_chance, 2),
            "chi2_threshold_5pct": 16.92,  # dof=9, alpha=0.05
            "biased": chi2_chance > 16.92,
        },
    }


@api_router.get("/stats/hot-cold")
async def stats_hot_cold(user: User = Depends(get_current_user)):
    draws = await _get_all_draws(user.user_id)
    main = Counter()
    for d in draws:
        for n in d["numbers"]:
            main[n] += 1
    ranked = sorted(range(1, 50), key=lambda n: main.get(n, 0), reverse=True)
    hot = ranked[:10]
    cold = ranked[-10:]

    # Delays (retards): draws since last appearance
    last_seen = {n: None for n in range(1, 50)}
    for idx, d in enumerate(draws):
        for n in d["numbers"]:
            last_seen[n] = idx
    total = len(draws)
    delays = []
    for n in range(1, 50):
        if last_seen[n] is None:
            delays.append((n, total))
        else:
            delays.append((n, total - 1 - last_seen[n]))
    delays_sorted = sorted(delays, key=lambda x: x[1], reverse=True)
    top_delays = [{"number": n, "delay": d} for n, d in delays_sorted[:10]]

    return {
        "hot": hot,
        "cold": cold,
        "top_delays": top_delays,
        "all_delays": [{"number": n, "delay": d} for n, d in delays],
    }


@api_router.get("/stats/pairs")
async def stats_pairs(user: User = Depends(get_current_user)):
    draws = await _get_all_draws(user.user_id)
    total = len(draws)
    pairs = Counter()
    triplets = Counter()
    for d in draws:
        nums = sorted(d["numbers"])
        for i in range(len(nums)):
            for j in range(i + 1, len(nums)):
                pairs[(nums[i], nums[j])] += 1
                for k in range(j + 1, len(nums)):
                    triplets[(nums[i], nums[j], nums[k])] += 1
    top_pairs = [
        {"a": a, "b": b, "count": c, "percent": round(c / total * 100, 2) if total else 0.0}
        for (a, b), c in pairs.most_common(20)
    ]
    top_triplets = [
        {"a": a, "b": b, "c": c, "count": cnt, "percent": round(cnt / total * 100, 2) if total else 0.0}
        for (a, b, c), cnt in triplets.most_common(15)
    ]
    return {"total_draws": total, "top_pairs": top_pairs, "top_triplets": top_triplets}


@api_router.get("/stats/credible-pool")
async def credible_pool(count: int = 8, user: User = Depends(get_current_user)):
    """Retourne les `count` numéros qui apparaissent le plus dans les grilles crédibles.
    Utile pour pré-remplir le pool du Système Réducteur avec des numéros 'crédibles'.
    Méthode : génère 50 grilles crédibles via credible_top5, compte la fréquence de chaque
    numéro, retourne les top `count` (avec fallback fréquence historique si égalité)."""
    import math
    from itertools import combinations as _c
    draws = await _get_all_draws(user.user_id)
    if not draws:
        raise HTTPException(400, "Aucun tirage. Charge le dataset FDJ.")
    count = max(6, min(count, 12))

    # Réutilise la logique credible_top5 en mode batch (5 runs de top-5 = 25 grilles échantillons)
    main_freq = Counter()
    for d in draws:
        for n in d["numbers"]:
            main_freq[n] += 1
    all_sums = [sum(d["numbers"]) for d in draws]
    hist_sum_mean = sum(all_sums) / len(all_sums)
    hist_sum_sigma = math.sqrt(sum((s - hist_sum_mean) ** 2 for s in all_sums) / len(all_sums)) or 1
    even_counts = [sum(1 for n in d["numbers"] if n % 2 == 0) for d in draws]
    hist_even_mean = sum(even_counts) / len(even_counts)

    def cred(nums):
        s = sum(nums)
        evens = sum(1 for n in nums if n % 2 == 0)
        sum_score = math.exp(-((s - hist_sum_mean) ** 2) / (2 * hist_sum_sigma ** 2))
        parity_score = math.exp(-((evens - hist_even_mean) ** 2) / 2.42)
        spread = len({(n - 1) // 10 for n in nums}) / 5.0
        sorted_n = sorted(nums)
        consec = sum(1 for i in range(4) if sorted_n[i+1] - sorted_n[i] == 1)
        return sum_score * parity_score * spread * max(0, 1 - consec * 0.15)

    weights_main = {n: main_freq.get(n, 0) + 1 for n in range(1, 50)}
    number_appearance = Counter()
    for _run in range(10):
        candidates = []
        seen = set()
        for _ in range(20):
            pool_local = list(weights_main.keys())
            weights_local = [weights_main[n] for n in pool_local]
            chosen = set()
            while len(chosen) < 5 and pool_local:
                n = random.choices(pool_local, weights=weights_local, k=1)[0]
                chosen.add(n)
                idx = pool_local.index(n)
                pool_local.pop(idx)
                weights_local.pop(idx)
            key = tuple(sorted(chosen))
            if key in seen: continue
            seen.add(key)
            candidates.append((cred(list(chosen)), list(chosen)))
        candidates.sort(reverse=True)
        for _, nums in candidates[:5]:
            for n in nums:
                number_appearance[n] += 1

    # Sort by appearance, tie-break by historical frequency
    ranked = sorted(range(1, 50), key=lambda n: (number_appearance[n], main_freq.get(n, 0)), reverse=True)
    return {"pool": sorted(ranked[:count]), "count": count}


@api_router.get("/stats/trend")
async def stats_trend(window: int = 100, user: User = Depends(get_current_user)):
    """
    Récent vs global. Rigueur statistique renforcée :
    - Seuil de fiabilité minimum : 200 tirages (1 an environ) au lieu de 15
    - Correction de Bonferroni sur 49 tests simultanés
    - Retourne seuil_bruit_pct = ± seuil sous lequel l'écart est considéré comme bruit
    """
    import math
    draws = await _get_all_draws(user.user_id)
    total = len(draws)
    window = max(5, min(window, total)) if total else 0
    SEUIL_FIABILITE = 200
    fiable = window >= SEUIL_FIABILITE

    global_freq = Counter()
    recent_freq = Counter()
    for d in draws:
        for n in d["numbers"]:
            global_freq[n] += 1
    for d in draws[-window:] if window else []:
        for n in d["numbers"]:
            recent_freq[n] += 1

    # Écart-type sous hypothèse d'indépendance : sqrt(p*(1-p)/N) * 100 en points de %
    # avec p = 5/49 = 0.102
    p = 5 / 49
    sigma_pct = (math.sqrt(p * (1 - p) / window) * 100) if window else 0
    # Correction Bonferroni : 49 tests simultanés à 5% -> chaque test à 0.1% -> z ~ 3.29
    seuil_bruit = 3.29 * sigma_pct

    tendances = []
    for n in range(1, 50):
        tg = (global_freq.get(n, 0) / total * 100) if total else 0.0
        tr = (recent_freq.get(n, 0) / window * 100) if window else 0.0
        ecart = tr - tg
        significatif = abs(ecart) > seuil_bruit
        tendances.append({
            "number": n,
            "taux_global": round(tg, 2),
            "taux_recent": round(tr, 2),
            "ecart": round(ecart, 2),
            "significatif": significatif,
        })
    tendances.sort(key=lambda x: x["ecart"], reverse=True)
    return {
        "fenetre_recente": window,
        "seuil_fiabilite": SEUIL_FIABILITE,
        "fiable": fiable,
        "seuil_bruit_pct": round(seuil_bruit, 2),
        "sigma_pct": round(sigma_pct, 2),
        "hausse": tendances[:10],
        "baisse": list(reversed(tendances[-10:])),
        "all": tendances,
    }


@api_router.post("/draws/sync-latest")
async def sync_latest_official(user: User = Depends(get_current_user)):
    """Déclenche manuellement une synchronisation avec les résultats officiels FDJ."""
    official_rows = await _fetch_latest_official_rows()
    if not official_rows:
        raise HTTPException(status_code=502, detail="Impossible de récupérer les données FDJ")
    existing_dates = set(await db.draws.distinct("date", {"user_id": user.user_id}))
    to_insert = [
        {"id": str(uuid.uuid4()), "user_id": user.user_id, **row}
        for row in official_rows[-10:] if row["date"] not in existing_dates
    ]
    if to_insert:
        await db.draws.insert_many(to_insert)
    return {"inserted": len(to_insert), "latest_official_date": official_rows[-1]["date"]}
    
@api_router.get("/draws/csv-template")
async def csv_template():
    """Template CSV compatible avec le format LotoAI Pro v0.7."""
    from fastapi.responses import PlainTextResponse
    sample = (
        "date,n1,n2,n3,n4,n5,chance\n"
        "2024-01-06,7,13,22,31,46,5\n"
        "2024-01-08,3,17,24,28,41,2\n"
        "2024-01-10,9,15,23,36,44,7\n"
    )
    return PlainTextResponse(content=sample, headers={
        "Content-Disposition": "attachment; filename=loto_template.csv"
    })


@api_router.get("/stats/sum-parity")
async def stats_sum_parity(user: User = Depends(get_current_user)):
    draws = await _get_all_draws(user.user_id)
    sums = []
    parity_counts = Counter()  # number of even numbers per draw (0..5)
    gaps = []
    for d in draws:
        nums = sorted(d["numbers"])
        s = sum(nums)
        sums.append(s)
        even = sum(1 for x in nums if x % 2 == 0)
        parity_counts[even] += 1
        for i in range(len(nums) - 1):
            gaps.append(nums[i + 1] - nums[i])
    # Sum distribution bins
    bins = [0] * 12  # 0..300 in bins of 25
    for s in sums:
        idx = min(11, s // 25)
        bins[idx] += 1
    sum_hist = [{"range": f"{i*25}-{i*25+24}", "count": bins[i]} for i in range(12)]

    parity_dist = [{"even_count": k, "count": parity_counts.get(k, 0)} for k in range(6)]

    gap_counter = Counter(gaps)
    gap_dist = [{"gap": g, "count": gap_counter[g]} for g in sorted(gap_counter.keys())]

    return {
        "sum_min": min(sums) if sums else 0,
        "sum_max": max(sums) if sums else 0,
        "sum_avg": round(sum(sums) / len(sums), 1) if sums else 0,
        "sum_distribution": sum_hist,
        "parity_distribution": parity_dist,
        "gap_distribution": gap_dist,
    }


# --------- Grid Generator ---------

@api_router.post("/grids/generate")
async def generate_grid(payload: GenerateGridRequest, user: User = Depends(get_current_user)):
    draws = await _get_all_draws(user.user_id)
    if not draws:
        raise HTTPException(status_code=400, detail="Aucun tirage. Générez les données de démo ou importez un CSV.")

    main_freq = Counter()
    chance_freq = Counter()
    last_seen = {n: None for n in range(1, 50)}
    for idx, d in enumerate(draws):
        for n in d["numbers"]:
            main_freq[n] += 1
            last_seen[n] = idx
        chance_freq[d["chance"]] += 1
    total = len(draws)
    delays = {n: (total if last_seen[n] is None else total - 1 - last_seen[n]) for n in range(1, 50)}

    def pick_by_weights(weights_map, k):
        pool = list(weights_map.keys())
        weights = [max(0.01, weights_map[n]) for n in pool]
        chosen = set()
        # Sample without replacement using weighted random
        while len(chosen) < k and pool:
            n = random.choices(pool, weights=weights, k=1)[0]
            chosen.add(n)
            idx_n = pool.index(n)
            pool.pop(idx_n)
            weights.pop(idx_n)
        return sorted(chosen)

    # --- Credible Top-5 strategy: generate 10 weighted_random candidates,
    #     score them by "statistical credibility" (proximity to real-draw patterns), keep top 5.
    if payload.strategy == "credible_top5":
        import math
        # Historical distributions used to score credibility
        all_sums = [sum(d["numbers"]) for d in draws]
        hist_sum_mean = sum(all_sums) / len(all_sums) if all_sums else 125
        hist_sum_sigma = math.sqrt(sum((s - hist_sum_mean) ** 2 for s in all_sums) / max(1, len(all_sums))) if all_sums else 30

        even_counts = [sum(1 for n in d["numbers"] if n % 2 == 0) for d in draws]
        hist_even_mean = sum(even_counts) / len(even_counts) if even_counts else 2.5
        hist_even_sigma = 1.1  # theoretical std for binomial

        weights_main = {n: main_freq.get(n, 0) + 1 for n in range(1, 50)}
        weights_chance = {n: chance_freq.get(n, 0) + 1 for n in range(1, 11)}

        def credibility(nums):
            s = sum(nums)
            evens = sum(1 for n in nums if n % 2 == 0)
            # 1. Sum near historical mean (Gaussian score)
            sum_score = math.exp(-((s - hist_sum_mean) ** 2) / (2 * hist_sum_sigma ** 2))
            # 2. Parity near historical mean
            parity_score = math.exp(-((evens - hist_even_mean) ** 2) / (2 * hist_even_sigma ** 2))
            # 3. Range spread: check how many of the 5 decades are covered
            decades = {(n - 1) // 10 for n in nums}
            spread_score = len(decades) / 5.0
            # 4. Frequency likelihood: mean normalized frequency
            freq_score = sum(main_freq.get(n, 0) / max(1, sum(main_freq.values())) for n in nums)
            # 5. Avoid consecutive-heavy grids
            sorted_nums = sorted(nums)
            consec = sum(1 for i in range(4) if sorted_nums[i + 1] - sorted_nums[i] == 1)
            consec_penalty = max(0, 1 - consec * 0.15)
            return sum_score * parity_score * spread_score * consec_penalty * (1 + freq_score)

        POOL_SIZE = 10
        TOP_N = 5
        candidates = []
        seen = set()
        attempts = 0
        while len(candidates) < POOL_SIZE and attempts < POOL_SIZE * 4:
            attempts += 1
            nums = pick_by_weights(weights_main, 5)
            key = tuple(nums)
            if key in seen:
                continue
            seen.add(key)
            chance_n = pick_by_weights(weights_chance, 1)[0]
            score = credibility(nums)
            # Clamp to [0, 1] for consistent % display in UI
            score = max(0.0, min(1.0, score))
            candidates.append({
                "numbers": nums,
                "chance": chance_n,
                "score": round(score, 4),
                "sum": sum(nums),
                "evens": sum(1 for n in nums if n % 2 == 0),
            })
        candidates.sort(key=lambda x: x["score"], reverse=True)
        top = candidates[:TOP_N]
        for g in top:
            g["strategy"] = "credible_top5"
        return {
            "grids": top,
            "pool_size": len(candidates),
            "credibility_stats": {
                "hist_sum_mean": round(hist_sum_mean, 1),
                "hist_sum_sigma": round(hist_sum_sigma, 1),
                "hist_even_mean": round(hist_even_mean, 2),
            },
        }

    grids = []
    for _ in range(max(1, min(10, payload.count))):
        if payload.strategy == "hot":
            weights_main = {n: (main_freq.get(n, 0) ** 2) + 1 for n in range(1, 50)}
            weights_chance = {n: (chance_freq.get(n, 0) ** 2) + 1 for n in range(1, 11)}
        elif payload.strategy == "cold":
            max_m = max(main_freq.values()) if main_freq else 1
            max_c = max(chance_freq.values()) if chance_freq else 1
            weights_main = {n: (max_m - main_freq.get(n, 0) + 1) ** 2 for n in range(1, 50)}
            weights_chance = {n: (max_c - chance_freq.get(n, 0) + 1) ** 2 for n in range(1, 11)}
        elif payload.strategy == "balanced":
            # Mix: 2 chauds + 2 froids + 1 en retard, avec variation via sampling
            ranked_hot = sorted(range(1, 50), key=lambda n: main_freq.get(n, 0), reverse=True)
            ranked_cold = sorted(range(1, 50), key=lambda n: main_freq.get(n, 0))
            ranked_delay = sorted(range(1, 50), key=lambda n: delays[n], reverse=True)
            picked = set()
            # 2 from top-8 hot
            hot_pool = [n for n in ranked_hot[:8] if n not in picked]
            picked.update(random.sample(hot_pool, min(2, len(hot_pool))))
            # 2 from top-8 cold
            cold_pool = [n for n in ranked_cold[:8] if n not in picked]
            picked.update(random.sample(cold_pool, min(2, len(cold_pool))))
            # 1 from top-5 delay
            delay_pool = [n for n in ranked_delay[:5] if n not in picked]
            if delay_pool:
                picked.add(random.choice(delay_pool))
            while len(picked) < 5:
                picked.add(random.randint(1, 49))
            weights_main = None
            weights_chance = {n: (chance_freq.get(n, 0) + 1) for n in range(1, 11)}
            main_nums = sorted(picked)
        else:  # weighted_random
            weights_main = {n: main_freq.get(n, 0) + 1 for n in range(1, 50)}
            weights_chance = {n: chance_freq.get(n, 0) + 1 for n in range(1, 11)}

        if payload.strategy != "balanced":
            main_nums = pick_by_weights(weights_main, 5)
        chance_num = pick_by_weights(weights_chance, 1)[0]
        grids.append({"numbers": main_nums, "chance": chance_num, "strategy": payload.strategy})

    return {"grids": grids}


# --------- Wheel / Système Réducteur ---------

class WheelRequest(BaseModel):
    numbers: List[int]  # pool of K numbers (6..12)
    target_matches: int = 3  # 3, 4 or 5
    chance: Optional[int] = None  # optional single chance number for all tickets


@api_router.post("/grids/wheel")
async def wheel_system(payload: WheelRequest, user: User = Depends(get_current_user)):
    """
    Système Réducteur (Covering Design).
    Génère la couverture minimale : si au moins `target_matches` des 5 numéros tirés
    sont dans le pool de K numéros, alors au moins une des grilles retournées est
    GARANTIE d'avoir target_matches+ bons numéros.
    Algorithme : greedy set-cover (approximation ~ln(n) du minimum optimal).
    Références : Steiner (1853), Erdős, La Jolla Covering Repository.
    """
    from itertools import combinations
    from math import comb

    pool = sorted(set(payload.numbers))
    K = len(pool)
    t = payload.target_matches

    if K != len(payload.numbers):
        raise HTTPException(400, "Les numéros du pool doivent être uniques")
    if K < 6 or K > 12:
        raise HTTPException(400, "Le pool doit contenir entre 6 et 12 numéros")
    if t not in (3, 4, 5):
        raise HTTPException(400, "target_matches doit être 3, 4 ou 5")
    if t > K:
        raise HTTPException(400, "target_matches ne peut pas dépasser la taille du pool")
    if any(n < 1 or n > 49 for n in pool):
        raise HTTPException(400, "Les numéros doivent être entre 1 et 49")
    if payload.chance is not None and not (1 <= payload.chance <= 10):
        raise HTTPException(400, "Chance entre 1 et 10")
    # Guard: t=5 on a large pool blows up (up to C(12,5)=792 tickets ≈ 1742€)
    if t == 5 and K > 8:
        raise HTTPException(400, "Pour target 5+, limite le pool à 8 numéros max (sinon >100 grilles).")

    MAX_TICKETS = 100  # safety cap to avoid runaway output

    def _compute_cover():
        """Blocking CPU work — offloaded to a thread to keep event loop free."""
        to_cover = set(combinations(pool, t))
        candidates = list(combinations(pool, 5))
        selected_local = []
        uncovered = set(to_cover)
        iterations = 0
        while uncovered and iterations < MAX_TICKETS:
            iterations += 1
            best_ticket = None
            best_cover = frozenset()
            for c in candidates:
                covered_by_c = frozenset(combinations(c, t)) & uncovered
                if len(covered_by_c) > len(best_cover):
                    best_cover = covered_by_c
                    best_ticket = c
            if best_ticket is None:
                break
            selected_local.append(list(best_ticket))
            uncovered -= best_cover
        return selected_local, len(uncovered) == 0

    selected, complete = await asyncio.to_thread(_compute_cover)

    # Attach chance number
    chance_num = payload.chance if payload.chance is not None else random.randint(1, 10)
    tickets = [{"numbers": list(t), "chance": chance_num} for t in selected]

    # Probability that at least `t` of the drawn 5 fall inside our pool of K
    p_pool_has_t_plus = sum(
        comb(K, k) * comb(49 - K, 5 - k) for k in range(t, 6)
    ) / comb(49, 5)

    # Also: baseline probability of a single random ticket getting t+ matches
    p_single_random_tplus = sum(
        comb(5, k) * comb(44, 5 - k) for k in range(t, 6)
    ) / comb(49, 5)

    return {
        "pool": pool,
        "pool_size": K,
        "target_matches": t,
        "tickets": tickets,
        "tickets_count": len(tickets),
        "cost_euros": round(len(tickets) * FDJ_GRID_COST, 2),
        "chance": chance_num,
        "p_pool_covers_pct": round(p_pool_has_t_plus * 100, 3),
        "p_single_random_pct": round(p_single_random_tplus * 100, 3),
        "improvement_factor": round(p_pool_has_t_plus / p_single_random_tplus, 2) if p_single_random_tplus > 0 else 0,
    }


@api_router.post("/grids/save")
async def save_grid(payload: SaveGridRequest, user: User = Depends(get_current_user)):
    if not _valid_draw(payload.numbers, payload.chance):
        raise HTTPException(status_code=400, detail="Grille invalide")
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user.user_id,
        "strategy": payload.strategy,
        "numbers": sorted(payload.numbers),
        "chance": payload.chance,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.saved_grids.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api_router.get("/grids")
async def list_grids(user: User = Depends(get_current_user)):
    cursor = db.saved_grids.find({"user_id": user.user_id}, {"_id": 0}).sort("created_at", -1).limit(200)
    grids = await cursor.to_list(200)
    all_draws = await _get_all_draws(user.user_id)  # sorted asc by date
    for g in grids:
        created_date = g["created_at"][:10]
        target_draw = None
        is_historical = False
        # Prefer the first draw on/after created_at (the "next" draw after save)
        for d in all_draws:
            if d["date"] >= created_date:
                target_draw = d
                break
        # Fallback: if no draw is on/after the save date (typical when the dataset
        # is historical only), compare against the most recent draw as a "historical simulation"
        if target_draw is None and all_draws:
            target_draw = all_draws[-1]
            is_historical = True
        if target_draw:
            actual_set = set(target_draw["numbers"])
            main_matches = len(actual_set & set(g["numbers"]))
            chance_match = target_draw["chance"] == g["chance"]
            g["result"] = {
                "target_date": target_draw["date"],
                "target_numbers": target_draw["numbers"],
                "target_chance": target_draw["chance"],
                "main_matches": main_matches,
                "chance_match": chance_match,
                "rank_label": _payout_rank(main_matches, chance_match),
                "is_historical": is_historical,
            }
        else:
            g["result"] = None
    return grids


def _payout_rank(main_matches: int, chance_match: bool) -> str:
    """FDJ Loto rank label based on matches."""
    if main_matches == 5 and chance_match: return "Rang 1 · Jackpot"
    if main_matches == 5: return "Rang 2"
    if main_matches == 4 and chance_match: return "Rang 3"
    if main_matches == 4: return "Rang 4"
    if main_matches == 3 and chance_match: return "Rang 5"
    if main_matches == 3: return "Rang 6"
    if main_matches == 2 and chance_match: return "Rang 7"
    if main_matches == 2: return "Rang 8"
    if chance_match: return "Rang 9 · N° Chance"
    return "Perdu"


# FDJ Loto average payouts (in euros). Rang 1 is variable — use realistic average.
FDJ_PAYOUTS = {
    "Rang 1 · Jackpot": 5_000_000.0,
    "Rang 2": 100_000.0,
    "Rang 3": 1_000.0,
    "Rang 4": 50.0,
    "Rang 5": 20.0,
    "Rang 6": 10.0,
    "Rang 7": 5.0,
    "Rang 8": 2.20,
    "Rang 9 · N° Chance": 2.20,
    "Perdu": 0.0,
}
FDJ_GRID_COST = 2.20  # cost per grid in euros


def _grid_payout(main_matches: int, chance_match: bool) -> float:
    return FDJ_PAYOUTS.get(_payout_rank(main_matches, chance_match), 0.0)


class VerifyGridRequest(BaseModel):
    numbers: List[int]
    chance: int


class VerifyBatchRequest(BaseModel):
    grids: List[VerifyGridRequest]


@api_router.post("/grids/verify-batch")
async def verify_batch(payload: VerifyBatchRequest, user: User = Depends(get_current_user)):
    """Verify multiple grids at once and compare their historical performance."""
    if not payload.grids:
        raise HTTPException(status_code=400, detail="Au moins une grille est requise")
    if len(payload.grids) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 grilles à la fois")

    for i, g in enumerate(payload.grids):
        if not _valid_draw(g.numbers, g.chance):
            raise HTTPException(status_code=400, detail=f"Grille #{i+1} invalide")

    draws = await _get_all_draws(user.user_id)
    total = len(draws)
    if total == 0:
        raise HTTPException(status_code=400, detail="Aucun tirage. Chargez le dataset FDJ officiel.")

    results = []
    for i, g in enumerate(payload.grids):
        grid_set = set(g.numbers)
        dist = [0] * 6
        chance_hits = 0
        combined_5_chance = 0
        total_matches = 0  # sum of main matches across all draws
        rank_counts = {r: 0 for r in ["Rang 1 · Jackpot", "Rang 2", "Rang 3", "Rang 4", "Rang 5",
                                       "Rang 6", "Rang 7", "Rang 8", "Rang 9 · N° Chance", "Perdu"]}
        gross_gain = 0.0
        for d in draws:
            matches = len(grid_set & set(d["numbers"]))
            chance_match = d["chance"] == g.chance
            dist[matches] += 1
            total_matches += matches
            if chance_match:
                chance_hits += 1
                if matches == 5:
                    combined_5_chance += 1
            rank = _payout_rank(matches, chance_match)
            rank_counts[rank] += 1
            gross_gain += _grid_payout(matches, chance_match)

        results.append({
            "index": i,
            "grid": {"numbers": sorted(g.numbers), "chance": g.chance},
            "distribution": [{"main_matches": k, "count": dist[k]} for k in range(6)],
            "chance_hits": chance_hits,
            "combined_5_and_chance": combined_5_chance,
            "avg_main_matches": round(total_matches / total, 3) if total else 0,
            "gross_gain": round(gross_gain, 2),
            "hit_3plus": dist[3] + dist[4] + dist[5],
            "hit_2plus": dist[2] + dist[3] + dist[4] + dist[5],
            "per_rank": [{"rank": r, "count": c} for r, c in rank_counts.items() if c > 0],
        })

    # Best-in-class rankings
    best = {
        "by_avg": max(results, key=lambda x: x["avg_main_matches"])["index"],
        "by_gain": max(results, key=lambda x: x["gross_gain"])["index"],
        "by_hits_3plus": max(results, key=lambda x: x["hit_3plus"])["index"],
    }

    return {
        "total_draws": total,
        "grids_count": len(results),
        "results": results,
        "best": best,
    }


@api_router.post("/grids/verify")
async def verify_grid(payload: VerifyGridRequest, user: User = Depends(get_current_user)):
    """
    Verify an arbitrary grid against the full user history.
    Returns: distribution of main matches (0..5), chance hit rate, and best historical hits.
    """
    if not _valid_draw(payload.numbers, payload.chance):
        raise HTTPException(status_code=400, detail="Grille invalide : 5 numéros uniques (1-49) + 1 chance (1-10)")

    draws = await _get_all_draws(user.user_id)
    total = len(draws)
    if total == 0:
        raise HTTPException(status_code=400, detail="Aucun tirage. Importez d'abord un CSV ou générez la démo.")

    grid_set = set(payload.numbers)
    dist = [0] * 6  # 0..5 main matches
    chance_hits = 0
    combined_5_chance = 0
    per_rank = {r: 0 for r in ["Rang 1 · Jackpot", "Rang 2", "Rang 3", "Rang 4", "Rang 5",
                                "Rang 6", "Rang 7", "Rang 8", "Rang 9 · N° Chance", "Perdu"]}
    best_hits = []  # (matches, chance_match, draw)

    for d in draws:
        matches = len(grid_set & set(d["numbers"]))
        chance_match = d["chance"] == payload.chance
        dist[matches] += 1
        if chance_match:
            chance_hits += 1
        if matches == 5 and chance_match:
            combined_5_chance += 1
        rank = _payout_rank(matches, chance_match)
        per_rank[rank] += 1
        if matches >= 3 or (matches >= 2 and chance_match):
            best_hits.append({
                "date": d["date"],
                "numbers": d["numbers"],
                "chance": d["chance"],
                "main_matches": matches,
                "chance_match": chance_match,
                "rank": rank,
            })

    best_hits.sort(key=lambda x: (x["main_matches"], x["chance_match"]), reverse=True)
    return {
        "total_draws": total,
        "grid": {"numbers": sorted(payload.numbers), "chance": payload.chance},
        "distribution": [{"main_matches": i, "count": dist[i]} for i in range(6)],
        "chance_hits": chance_hits,
        "combined_5_and_chance": combined_5_chance,
        "per_rank": [{"rank": k, "count": v} for k, v in per_rank.items() if v > 0],
        "best_hits": best_hits[:20],
    }


@api_router.delete("/grids/{grid_id}")
async def delete_grid(grid_id: str, user: User = Depends(get_current_user)):
    res = await db.saved_grids.delete_one({"id": grid_id, "user_id": user.user_id})
    return {"deleted": res.deleted_count}


# --------- Share ---------

class ShareCreateRequest(BaseModel):
    grid_id: str


class ShareByEmailRequest(BaseModel):
    grid_id: str
    to_email: str
    message: Optional[str] = None


@api_router.post("/grids/share")
async def create_share(payload: ShareCreateRequest, user: User = Depends(get_current_user)):
    """Create a public share link (no auth) for a saved grid."""
    grid = await db.saved_grids.find_one({"id": payload.grid_id, "user_id": user.user_id}, {"_id": 0})
    if not grid:
        raise HTTPException(404, "Grille introuvable")
    # Check for existing share to avoid duplicates
    existing = await db.grid_shares.find_one({"grid_id": payload.grid_id, "owner_id": user.user_id}, {"_id": 0})
    if existing:
        return {"token": existing["token"], "created_at": existing["created_at"]}
    token = uuid.uuid4().hex[:12]
    await db.grid_shares.insert_one({
        "token": token,
        "grid_id": payload.grid_id,
        "owner_id": user.user_id,
        "owner_name": user.name,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"token": token, "created_at": datetime.now(timezone.utc).isoformat()}


@api_router.get("/share/{token}")
async def get_shared_grid(token: str):
    """Public endpoint (no auth) — returns a grid via share token."""
    share = await db.grid_shares.find_one({"token": token}, {"_id": 0})
    if not share:
        raise HTTPException(404, "Lien de partage invalide ou expiré")
    grid = await db.saved_grids.find_one({"id": share["grid_id"]}, {"_id": 0})
    if not grid:
        raise HTTPException(404, "La grille partagée n'existe plus")
    return {
        "numbers": grid["numbers"],
        "chance": grid["chance"],
        "strategy": grid["strategy"],
        "created_at": grid["created_at"],
        "shared_by": share.get("owner_name", "Un joueur"),
        "shared_at": share["created_at"],
    }


@api_router.post("/grids/share-email")
async def share_by_email(payload: ShareByEmailRequest, user: User = Depends(get_current_user)):
    """Share a saved grid by email via Resend."""
    if not RESEND_API_KEY or not resend:
        raise HTTPException(503, "Service email non configuré. Ajoutez RESEND_API_KEY dans backend/.env.")
    grid = await db.saved_grids.find_one({"id": payload.grid_id, "user_id": user.user_id}, {"_id": 0})
    if not grid:
        raise HTTPException(404, "Grille introuvable")
    # Simple email regex
    import re
    if not re.match(r"^[\w\.\-\+]+@[\w\-]+\.[\w\.\-]+$", payload.to_email):
        raise HTTPException(400, "Adresse email invalide")

    balls_html = ""
    for n in grid["numbers"]:
        balls_html += (
            f'<span style="display:inline-block;width:34px;height:34px;line-height:34px;border-radius:50%;'
            f'background:#111;color:#fff;font-family:monospace;font-weight:600;text-align:center;margin-right:6px;'
            f'border:1px solid #333;">{n}</span>'
        )
    balls_html += (
        f'<span style="display:inline-block;width:34px;height:34px;line-height:34px;border-radius:50%;'
        f'background:rgba(245,158,11,0.15);color:#F59E0B;font-family:monospace;font-weight:700;text-align:center;'
        f'margin-left:6px;border:2px solid #F59E0B;">{grid["chance"]}</span>'
    )
    message_html = f'<p style="color:#333;font-style:italic;">"{payload.message}"</p>' if payload.message else ""
    html = f"""
    <html><body style="font-family:Arial,sans-serif;background:#f5f5f5;padding:32px;margin:0;">
      <table style="max-width:560px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;">
        <tr><td>
          <div style="font-size:12px;color:#F59E0B;text-transform:uppercase;letter-spacing:3px;margin-bottom:8px;">LotoStat.Pro</div>
          <h1 style="font-size:22px;margin:0 0 8px 0;color:#111;">{user.name} vous partage une grille</h1>
          {message_html}
          <div style="margin:24px 0;">{balls_html}</div>
          <p style="font-size:12px;color:#888;">Stratégie : {grid["strategy"]}</p>
        </td></tr>
      </table>
    </body></html>
    """
    try:
        result = await asyncio.to_thread(resend.Emails.send, {
            "from": SENDER_EMAIL,
            "to": [payload.to_email],
            "subject": f"🎯 {user.name} vous partage une grille Loto",
            "html": html,
        })
        return {"status": "sent", "to": payload.to_email, "email_id": result.get("id")}
    except Exception as e:
        logger.error(f"Share-email error: {e}")
        raise HTTPException(500, f"Échec envoi : {e}")


# --------- Health ---------

@api_router.get("/")
async def root():
    return {"message": "LotoStat Pro API"}


# --------- Heatmap ---------

@api_router.get("/stats/heatmap")
async def stats_heatmap(user: User = Depends(get_current_user)):
    """Full 49x49 pair co-occurrence matrix for visual heatmap."""
    draws = await _get_all_draws(user.user_id)
    total = len(draws)
    matrix = [[0] * 50 for _ in range(50)]  # 1-indexed, ignore row/col 0
    for d in draws:
        nums = sorted(d["numbers"])
        for i in range(len(nums)):
            for j in range(i + 1, len(nums)):
                a, b = nums[i], nums[j]
                matrix[a][b] += 1
                matrix[b][a] += 1
    max_val = 0
    for r in range(1, 50):
        for c in range(1, 50):
            if r != c and matrix[r][c] > max_val:
                max_val = matrix[r][c]
    # Compact payload: list of {a, b, count} for a<b only (upper triangle)
    pairs = []
    for a in range(1, 50):
        for b in range(a + 1, 50):
            pairs.append({"a": a, "b": b, "count": matrix[a][b]})
    return {"total_draws": total, "max": max_val, "pairs": pairs}


# --------- Backtesting ---------

class BacktestRequest(BaseModel):
    grids_per_strategy: int = 20
    sample_size: int = 100  # how many past draws to test against


def _pick_by_weights(weights_map: dict, k: int) -> List[int]:
    pool = list(weights_map.keys())
    weights = [max(0.01, weights_map[n]) for n in pool]
    chosen = set()
    while len(chosen) < k and pool:
        n = random.choices(pool, weights=weights, k=1)[0]
        chosen.add(n)
        idx_n = pool.index(n)
        pool.pop(idx_n)
        weights.pop(idx_n)
    return sorted(chosen)


def _generate_grids_from_history(history: List[dict], strategy: str, n_grids: int):
    """Generate N grids using stats computed on `history` only (no lookahead)."""
    main_freq = Counter()
    chance_freq = Counter()
    last_seen = {n: None for n in range(1, 50)}
    for idx, d in enumerate(history):
        for n in d["numbers"]:
            main_freq[n] += 1
            last_seen[n] = idx
        chance_freq[d["chance"]] += 1
    total = len(history)
    delays = {n: (total if last_seen[n] is None else total - 1 - last_seen[n]) for n in range(1, 50)}

    grids = []
    for _ in range(n_grids):
        if strategy == "hot":
            wm = {n: (main_freq.get(n, 0) ** 2) + 1 for n in range(1, 50)}
            wc = {n: (chance_freq.get(n, 0) ** 2) + 1 for n in range(1, 11)}
            nums = _pick_by_weights(wm, 5)
        elif strategy == "cold":
            max_m = max(main_freq.values()) if main_freq else 1
            max_c = max(chance_freq.values()) if chance_freq else 1
            wm = {n: (max_m - main_freq.get(n, 0) + 1) ** 2 for n in range(1, 50)}
            wc = {n: (max_c - chance_freq.get(n, 0) + 1) ** 2 for n in range(1, 11)}
            nums = _pick_by_weights(wm, 5)
        elif strategy == "balanced":
            rh = sorted(range(1, 50), key=lambda n: main_freq.get(n, 0), reverse=True)
            rc = sorted(range(1, 50), key=lambda n: main_freq.get(n, 0))
            rd = sorted(range(1, 50), key=lambda n: delays[n], reverse=True)
            picked = set()
            hot_pool = [n for n in rh[:8] if n not in picked]
            picked.update(random.sample(hot_pool, min(2, len(hot_pool))))
            cold_pool = [n for n in rc[:8] if n not in picked]
            picked.update(random.sample(cold_pool, min(2, len(cold_pool))))
            delay_pool = [n for n in rd[:5] if n not in picked]
            if delay_pool:
                picked.add(random.choice(delay_pool))
            while len(picked) < 5:
                picked.add(random.randint(1, 49))
            nums = sorted(picked)
            wc = {n: (chance_freq.get(n, 0) + 1) for n in range(1, 11)}
        elif strategy == "weighted_random":
            wm = {n: main_freq.get(n, 0) + 1 for n in range(1, 50)}
            wc = {n: chance_freq.get(n, 0) + 1 for n in range(1, 11)}
            nums = _pick_by_weights(wm, 5)
        else:  # pure random baseline
            nums = sorted(random.sample(range(1, 50), 5))
            wc = {n: 1 for n in range(1, 11)}
        chance = _pick_by_weights(wc, 1)[0]
        grids.append((nums, chance))
    return grids


@api_router.post("/backtest")
async def backtest(payload: BacktestRequest, user: User = Depends(get_current_user)):
    """
    For each strategy, walk-forward through the last N draws:
    - At step k, use draws[0..k] as known history to generate grids
    - Score the grids against draws[k+1] (main matches, chance match)
    Returns average matches per grid + rank distribution counts.
    """
    draws = await _get_all_draws(user.user_id)
    total = len(draws)
    if total < 30:
        raise HTTPException(status_code=400, detail="Il faut au moins 30 tirages pour un backtest fiable.")

    sample = max(20, min(payload.sample_size, total - 20))
    n_grids = max(5, min(payload.grids_per_strategy, 50))
    # Test window: last `sample` draws (predict each from the ones before)
    start_idx = total - sample

    strategies = ["hot", "cold", "balanced", "weighted_random", "random"]
    results = {s: {
        "grids_tested": 0,
        "sum_main_matches": 0,
        "sum_main_matches_sq": 0,  # for std dev
        "chance_matches": 0,
        "rank_hist": [0] * 6,
        "hits_3plus": 0,
        "hits_5plus_chance": 0,
        "gross_gains": 0.0,
    } for s in strategies}

    for k in range(start_idx, total - 1):
        history = draws[: k + 1]
        actual = draws[k + 1]
        actual_set = set(actual["numbers"])
        actual_chance = actual["chance"]
        for s in strategies:
            grids = _generate_grids_from_history(history, s, n_grids)
            for (nums, chance) in grids:
                matches = len(actual_set & set(nums))
                r = results[s]
                r["grids_tested"] += 1
                r["sum_main_matches"] += matches
                r["sum_main_matches_sq"] += matches * matches
                r["rank_hist"][matches] += 1
                if chance == actual_chance:
                    r["chance_matches"] += 1
                    if matches >= 5:
                        r["hits_5plus_chance"] += 1
                if matches >= 3:
                    r["hits_3plus"] += 1
                r["gross_gains"] += _grid_payout(matches, chance == actual_chance)

    import math
    # Espérance théorique du hasard pur : 5 * 5/49
    theoretical_avg = 5 * 5 / 49
    summary = []
    for s in strategies:
        r = results[s]
        gt = r["grids_tested"] or 1
        avg = r["sum_main_matches"] / gt
        var = (r["sum_main_matches_sq"] / gt) - (avg ** 2)
        std_err = math.sqrt(max(var, 0) / gt)  # standard error of the mean
        ci95 = 1.96 * std_err
        # Est-ce que la stratégie bat le hasard pur ?
        beats_random = (avg - ci95) > theoretical_avg
        cost = r["grids_tested"] * FDJ_GRID_COST
        net = r["gross_gains"] - cost
        roi = (net / cost * 100) if cost else 0.0
        summary.append({
            "strategy": s,
            "grids_tested": r["grids_tested"],
            "avg_main_matches": round(avg, 3),
            "ci95": round(ci95, 3),
            "beats_random": beats_random,
            "chance_hit_rate": round(r["chance_matches"] / gt * 100, 2),
            "hit_3plus_rate": round(r["hits_3plus"] / gt * 100, 2),
            "rank_distribution": r["rank_hist"],
            "hits_5plus_chance": r["hits_5plus_chance"],
            "gross_gains": round(r["gross_gains"], 2),
            "total_cost": round(cost, 2),
            "net_gains": round(net, 2),
            "roi_percent": round(roi, 2),
        })
    summary.sort(key=lambda x: x["avg_main_matches"], reverse=True)

    return {
        "total_draws": total,
        "sample_size": sample,
        "grids_per_strategy": n_grids,
        "grid_cost": FDJ_GRID_COST,
        "payout_table": FDJ_PAYOUTS,
        "theoretical_avg": round(theoretical_avg, 3),
        "any_beats_random": any(s["beats_random"] for s in summary),
        "strategies": summary,
    }


# --------- Email Alerts (Resend) ---------

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")

try:
    import resend  # type: ignore
    if RESEND_API_KEY:
        resend.api_key = RESEND_API_KEY
except ImportError:
    resend = None


def _next_draw_date(from_date: Optional[datetime] = None) -> datetime:
    """Next Loto FDJ draw day: Mon(0), Wed(2), Sat(5)."""
    d = (from_date or datetime.now(timezone.utc)).date()
    for i in range(1, 8):
        cand = d + timedelta(days=i)
        if cand.weekday() in (0, 2, 5):
            return datetime.combine(cand, datetime.min.time(), tzinfo=timezone.utc)
    return datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc)


def _render_email_html(user_name: str, draw_date: str, grids: List[dict]) -> str:
    rows = ""
    for i, g in enumerate(grids, 1):
        balls_html = ""
        for n in g["numbers"]:
            balls_html += (
                f'<span style="display:inline-block;width:34px;height:34px;line-height:34px;'
                f'border-radius:50%;background:#111;color:#fff;font-family:monospace;font-weight:600;'
                f'text-align:center;margin-right:6px;border:1px solid #333;">{n}</span>'
            )
        balls_html += (
            f'<span style="display:inline-block;width:34px;height:34px;line-height:34px;border-radius:50%;'
            f'background:rgba(245,158,11,0.15);color:#F59E0B;font-family:monospace;font-weight:700;'
            f'text-align:center;margin-left:6px;border:2px solid #F59E0B;">{g["chance"]}</span>'
        )
        rows += (
            f'<tr><td style="padding:16px 0;border-top:1px solid #eee;">'
            f'<div style="font-size:12px;color:#888;text-transform:uppercase;letter-spacing:2px;margin-bottom:8px;">'
            f'Grille #{i} · {g.get("strategy", "")}</div>{balls_html}</td></tr>'
        )
    return f"""
    <html><body style="font-family:Arial,sans-serif;background:#f5f5f5;padding:32px;margin:0;">
      <table style="max-width:560px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;">
        <tr><td>
          <div style="font-size:12px;color:#F59E0B;text-transform:uppercase;letter-spacing:3px;margin-bottom:8px;">LotoStat.Pro</div>
          <h1 style="font-size:24px;margin:0 0 8px 0;color:#111;">Prochain tirage : {draw_date}</h1>
          <p style="color:#555;margin:0 0 24px 0;">Bonjour {user_name}, voici vos grilles suggérées.</p>
        </td></tr>
        {rows}
        <tr><td style="padding-top:24px;border-top:1px solid #eee;">
          <p style="font-size:11px;color:#999;line-height:1.6;">
            Rappel : les tirages du Loto sont indépendants. Aucune méthode ne permet de prédire un tirage.
            Ces grilles sont générées à partir de l'analyse statistique de l'historique passé.
          </p>
        </td></tr>
      </table>
    </body></html>
    """


class SendAlertRequest(BaseModel):
    email: Optional[str] = None  # override; default = user.email
    strategy: Literal["hot", "cold", "balanced", "weighted_random"] = "balanced"
    grids_count: int = 3


@api_router.get("/alerts/next-draw")
async def next_draw(user: User = Depends(get_current_user)):
    nd = _next_draw_date()
    return {
        "next_draw_date": nd.date().isoformat(),
        "day_name": ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"][nd.weekday()],
        "resend_configured": bool(RESEND_API_KEY and resend),
    }


@api_router.post("/alerts/send")
async def send_alert(payload: SendAlertRequest, user: User = Depends(get_current_user)):
    if not RESEND_API_KEY or not resend:
        raise HTTPException(status_code=503, detail="Service email non configuré. Ajoutez RESEND_API_KEY dans le .env.")

    draws = await _get_all_draws(user.user_id)
    if not draws:
        raise HTTPException(status_code=400, detail="Aucun tirage. Générez les données de démo ou importez un CSV.")

    generated = _generate_grids_from_history(draws, payload.strategy, max(1, min(10, payload.grids_count)))
    grids = [{"numbers": n, "chance": c, "strategy": payload.strategy} for (n, c) in generated]

    nd = _next_draw_date()
    html = _render_email_html(user.name, nd.date().isoformat(), grids)
    to_email = payload.email or user.email

    params = {
        "from": SENDER_EMAIL,
        "to": [to_email],
        "subject": f"🎯 LotoStat.Pro — Vos grilles pour le tirage du {nd.date().isoformat()}",
        "html": html,
    }
    try:
        result = await asyncio.to_thread(resend.Emails.send, params)
        return {"status": "sent", "to": to_email, "email_id": result.get("id"), "grids": grids}
    except Exception as e:
        logger.error(f"Resend error: {e}")
        raise HTTPException(status_code=500, detail=f"Échec envoi email: {e}")


class AlertPrefs(BaseModel):
    enabled: bool = False
    strategy: Literal["hot", "cold", "balanced", "weighted_random"] = "balanced"
    grids_count: int = 3
    email: Optional[str] = None
    results_enabled: bool = False


@api_router.get("/alerts/prefs")
async def get_alert_prefs(user: User = Depends(get_current_user)):
    doc = await db.alert_prefs.find_one({"user_id": user.user_id}, {"_id": 0})
    if not doc:
        return {"enabled": False, "strategy": "balanced", "grids_count": 3, "email": user.email, "results_enabled": False}
    return {
        "enabled": doc.get("enabled", False),
        "strategy": doc.get("strategy", "balanced"),
        "grids_count": doc.get("grids_count", 3),
        "email": doc.get("email") or user.email,
        "results_enabled": doc.get("results_enabled", False),
    }


@api_router.post("/alerts/prefs")
async def set_alert_prefs(payload: AlertPrefs, user: User = Depends(get_current_user)):
    await db.alert_prefs.update_one(
        {"user_id": user.user_id},
        {"$set": {
            "user_id": user.user_id,
            "enabled": payload.enabled,
            "strategy": payload.strategy,
            "grids_count": max(1, min(10, payload.grids_count)),
            "email": payload.email or user.email,
            "results_enabled": payload.results_enabled,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True,
    )
    return {"ok": True}


async def _run_daily_alerts():
    """Run every day. If it's a Loto draw day (Mon/Wed/Sat), send alerts to opted-in users."""
    today = datetime.now(timezone.utc).date()
    if today.weekday() not in (0, 2, 5):
        return
    if not RESEND_API_KEY or not resend:
        logger.info("Daily alert skipped: Resend not configured")
        return
    today_iso = today.isoformat()
    cursor = db.alert_prefs.find({"enabled": True}, {"_id": 0})
    async for pref in cursor:
        try:
            # Idempotency: skip if already sent today for this user
            already = await db.alert_sent_log.find_one({
                "user_id": pref["user_id"],
                "date": today_iso,
                "type": {"$ne": "results"},
            })
            if already:
                continue

            user_doc = await db.users.find_one({"user_id": pref["user_id"]}, {"_id": 0})
            if not user_doc:
                continue
            draws = await _get_all_draws(pref["user_id"])
            if not draws:
                continue
            generated = _generate_grids_from_history(
                draws, pref.get("strategy", "balanced"), pref.get("grids_count", 3),
            )
            grids = [{"numbers": n, "chance": c, "strategy": pref.get("strategy", "balanced")} for (n, c) in generated]
            nd = _next_draw_date()
            html = _render_email_html(user_doc.get("name", "joueur"), nd.date().isoformat(), grids)
            to_email = pref.get("email") or user_doc["email"]
            params = {
                "from": SENDER_EMAIL,
                "to": [to_email],
                "subject": f"🎯 LotoStat.Pro — Vos grilles pour le tirage du {nd.date().isoformat()}",
                "html": html,
            }
            await asyncio.to_thread(resend.Emails.send, params)
            await db.alert_sent_log.insert_one({
                "user_id": pref["user_id"],
                "date": today_iso,
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "to": to_email,
                "type": "grids",
            })
            logger.info(f"Auto-alert sent to {to_email}")
        except Exception as e:
            logger.error(f"Auto-alert error for {pref.get('user_id')}: {e}")


def _render_results_email_html(user_name: str, draw: dict, grids_with_results: list, total_won: float, total_cost: float) -> str:
    """Render the 'grid results' email HTML after a draw."""
    balls_actual = ""
    for n in draw["numbers"]:
        balls_actual += (
            f'<span style="display:inline-block;width:36px;height:36px;line-height:36px;'
            f'border-radius:50%;background:#F59E0B;color:#111;font-family:monospace;font-weight:700;'
            f'text-align:center;margin-right:6px;">{n}</span>'
        )
    balls_actual += (
        f'<span style="display:inline-block;width:36px;height:36px;line-height:36px;border-radius:50%;'
        f'background:#111;color:#F59E0B;font-family:monospace;font-weight:700;'
        f'text-align:center;margin-left:8px;border:2px solid #F59E0B;">{draw["chance"]}</span>'
    )

    rows = ""
    for i, g in enumerate(grids_with_results, 1):
        actual_set = set(draw["numbers"])
        balls_html = ""
        for n in g["numbers"]:
            hit = n in actual_set
            balls_html += (
                f'<span style="display:inline-block;width:32px;height:32px;line-height:32px;'
                f'border-radius:50%;background:{"#10B981" if hit else "#222"};color:#fff;font-family:monospace;font-weight:600;'
                f'text-align:center;margin-right:5px;border:1px solid {"#10B981" if hit else "#333"};">{n}</span>'
            )
        chance_hit = g["chance"] == draw["chance"]
        balls_html += (
            f'<span style="display:inline-block;width:32px;height:32px;line-height:32px;border-radius:50%;'
            f'background:{"#10B981" if chance_hit else "#111"};color:#fff;font-family:monospace;font-weight:700;'
            f'text-align:center;margin-left:6px;border:2px solid {"#10B981" if chance_hit else "#F59E0B"};">{g["chance"]}</span>'
        )
        payout = g["payout"]
        payout_color = "#10B981" if payout > 0 else "#666"
        payout_txt = f"{payout:,.2f} €".replace(",", " ") if payout > 0 else "—"
        rows += (
            f'<tr><td style="padding:14px 0;border-top:1px solid #eee;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">'
            f'<span style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:2px;">'
            f'Grille #{i} · {g["main_matches"]}/5 + {"chance" if chance_hit else "0 ch."}</span>'
            f'<span style="font-size:14px;font-weight:700;color:{payout_color};font-family:monospace;">{payout_txt}</span>'
            f'</div>{balls_html}'
            f'<div style="font-size:10px;color:#999;margin-top:6px;">{g["rank_label"]}</div>'
            f'</td></tr>'
        )

    net = total_won - total_cost
    net_color = "#10B981" if net > 0 else ("#EF4444" if net < 0 else "#666")
    net_prefix = "+" if net > 0 else ""
    return f"""
    <html><body style="font-family:Arial,sans-serif;background:#f5f5f5;padding:32px;margin:0;">
      <table style="max-width:600px;margin:0 auto;background:#fff;border-radius:12px;padding:32px;">
        <tr><td>
          <div style="font-size:12px;color:#F59E0B;text-transform:uppercase;letter-spacing:3px;margin-bottom:8px;">LotoStat.Pro · Résultats</div>
          <h1 style="font-size:22px;margin:0 0 8px 0;color:#111;">Tirage du {draw["date"]}</h1>
          <p style="color:#555;margin:0 0 20px 0;font-size:14px;">Bonjour {user_name}, voici le bilan de vos grilles.</p>
          <div style="padding:16px;background:#0d0d10;border-radius:8px;margin-bottom:24px;">
            <div style="font-size:10px;color:#666;text-transform:uppercase;letter-spacing:2px;margin-bottom:10px;">Tirage officiel</div>
            {balls_actual}
          </div>
          <div style="display:flex;gap:8px;margin-bottom:20px;">
            <div style="flex:1;padding:12px;background:#f9f9f9;border-radius:6px;text-align:center;">
              <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:1px;">Coût</div>
              <div style="font-size:16px;font-weight:700;color:#111;font-family:monospace;">{total_cost:.2f} €</div>
            </div>
            <div style="flex:1;padding:12px;background:#f9f9f9;border-radius:6px;text-align:center;">
              <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:1px;">Gains</div>
              <div style="font-size:16px;font-weight:700;color:#10B981;font-family:monospace;">{total_won:.2f} €</div>
            </div>
            <div style="flex:1;padding:12px;background:#f9f9f9;border-radius:6px;text-align:center;">
              <div style="font-size:10px;color:#888;text-transform:uppercase;letter-spacing:1px;">Net</div>
              <div style="font-size:16px;font-weight:700;color:{net_color};font-family:monospace;">{net_prefix}{net:.2f} €</div>
            </div>
          </div>
        </td></tr>
        {rows}
        <tr><td style="padding-top:24px;border-top:1px solid #eee;">
          <p style="font-size:11px;color:#999;line-height:1.6;">
            Le loto reste un jeu de hasard. Gains basés sur les rangs FDJ moyens (le Rang 1 est variable).
          </p>
        </td></tr>
      </table>
    </body></html>
    """


async def _run_results_alerts():
    """Run every day. Day after a Loto draw (Tue/Thu/Sun), send RESULT emails
    to opted-in users showing how their saved grids performed."""
    today = datetime.now(timezone.utc).date()
    # Day AFTER draw: Tue(1), Thu(3), Sun(6)
    if today.weekday() not in (1, 3, 6):
        return
    if not RESEND_API_KEY or not resend:
        logger.info("Results alert skipped: Resend not configured")
        return
    today_iso = today.isoformat()
    cursor = db.alert_prefs.find({"results_enabled": True}, {"_id": 0})
    async for pref in cursor:
        try:
            user_doc = await db.users.find_one({"user_id": pref["user_id"]}, {"_id": 0})
            if not user_doc:
                continue

            # Find latest draw for that user
            draws = await _get_all_draws(pref["user_id"])
            if not draws:
                continue
            latest = draws[-1]  # already sorted asc
            draw_date = latest["date"]

            # Idempotency: skip if already sent for this draw
            already = await db.alert_sent_log.find_one({
                "user_id": pref["user_id"],
                "type": "results",
                "draw_date": draw_date,
            })
            if already:
                continue

            # Get user's saved grids, only those created on or before the draw date
            grids_cursor = db.saved_grids.find(
                {"user_id": pref["user_id"]},
                {"_id": 0},
            )
            saved = await grids_cursor.to_list(500)
            eligible = [g for g in saved if g.get("created_at", "")[:10] <= draw_date]
            if not eligible:
                continue

            grids_with_results = []
            total_won = 0.0
            actual_set = set(latest["numbers"])
            for g in eligible:
                main_matches = len(actual_set & set(g["numbers"]))
                chance_match = latest["chance"] == g["chance"]
                rank_label = _payout_rank(main_matches, chance_match)
                payout = _grid_payout(main_matches, chance_match)
                total_won += payout
                grids_with_results.append({
                    "numbers": g["numbers"],
                    "chance": g["chance"],
                    "main_matches": main_matches,
                    "chance_match": chance_match,
                    "rank_label": rank_label,
                    "payout": payout,
                })
            total_cost = len(eligible) * FDJ_GRID_COST

            html = _render_results_email_html(
                user_doc.get("name", "joueur"), latest, grids_with_results, total_won, total_cost,
            )
            to_email = pref.get("email") or user_doc["email"]
            params = {
                "from": SENDER_EMAIL,
                "to": [to_email],
                "subject": f"🎯 LotoStat.Pro — Résultats du tirage du {draw_date}",
                "html": html,
            }
            await asyncio.to_thread(resend.Emails.send, params)
            await db.alert_sent_log.insert_one({
                "user_id": pref["user_id"],
                "date": today_iso,
                "sent_at": datetime.now(timezone.utc).isoformat(),
                "to": to_email,
                "type": "results",
                "draw_date": draw_date,
            })
            logger.info(f"Results email sent to {to_email} for draw {draw_date}")
        except Exception as e:
            logger.error(f"Results email error for {pref.get('user_id')}: {e}")


@api_router.post("/alerts/send-results")
async def send_results_now(user: User = Depends(get_current_user)):
    """Manually trigger a 'results' email for the current user against the latest draw."""
    if not RESEND_API_KEY or not resend:
        raise HTTPException(status_code=503, detail="Service email non configuré.")
    draws = await _get_all_draws(user.user_id)
    if not draws:
        raise HTTPException(status_code=400, detail="Aucun tirage. Importez d'abord un CSV FDJ.")
    latest = draws[-1]
    saved = await db.saved_grids.find({"user_id": user.user_id}, {"_id": 0}).to_list(500)
    eligible = [g for g in saved if g.get("created_at", "")[:10] <= latest["date"]]
    if not eligible:
        raise HTTPException(status_code=400, detail="Aucune grille sauvegardée avant le dernier tirage.")

    grids_with_results = []
    total_won = 0.0
    actual_set = set(latest["numbers"])
    for g in eligible:
        main_matches = len(actual_set & set(g["numbers"]))
        chance_match = latest["chance"] == g["chance"]
        payout = _grid_payout(main_matches, chance_match)
        total_won += payout
        grids_with_results.append({
            "numbers": g["numbers"],
            "chance": g["chance"],
            "main_matches": main_matches,
            "chance_match": chance_match,
            "rank_label": _payout_rank(main_matches, chance_match),
            "payout": payout,
        })
    total_cost = len(eligible) * FDJ_GRID_COST

    prefs = await db.alert_prefs.find_one({"user_id": user.user_id}, {"_id": 0}) or {}
    to_email = prefs.get("email") or user.email
    html = _render_results_email_html(user.name, latest, grids_with_results, total_won, total_cost)
    params = {
        "from": SENDER_EMAIL,
        "to": [to_email],
        "subject": f"🎯 LotoStat.Pro — Résultats du tirage du {latest['date']}",
        "html": html,
    }
    try:
        result = await asyncio.to_thread(resend.Emails.send, params)
        return {
            "status": "sent",
            "to": to_email,
            "email_id": result.get("id"),
            "grids_count": len(eligible),
            "total_won": total_won,
            "total_cost": total_cost,
            "draw_date": latest["date"],
        }
    except Exception as e:
        logger.error(f"Manual results email error: {e}")
        raise HTTPException(status_code=500, detail=f"Échec envoi email: {e}")


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# --------- Scheduler ---------
scheduler = AsyncIOScheduler(timezone="Europe/Paris")


@app.on_event("startup")
async def _start_scheduler():
    # Grids alert: every day at 12:00 Paris (sends only on draw days Mon/Wed/Sat)
    scheduler.add_job(_run_daily_alerts, "cron", hour=12, minute=0, id="daily_loto_alert", replace_existing=True)
    # Results alert: every day at 09:00 Paris (sends only on Tue/Thu/Sun, day after a draw)
    scheduler.add_job(_run_results_alerts, "cron", hour=9, minute=0, id="results_loto_alert", replace_existing=True)
    scheduler.add_job(_run_draw_sync, "cron", hour=21, minute=30, id="draw_sync", replace_existing=True)
    scheduler.start()
    logger.info("Scheduler started (grids @12:00 · results @09:00 Paris)")


@app.on_event("shutdown")
async def shutdown_db_client():
    try:
        scheduler.shutdown(wait=False)
    except Exception:
        pass
    client.close()
