from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, UploadFile, File, Depends
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import io
import csv
import random
import logging
import uuid
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
    strategy: Literal["hot", "cold", "balanced", "weighted_random"]
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
    draws = await _get_all_draws(user.user_id)
    main = Counter()
    chance = Counter()
    for d in draws:
        for n in d["numbers"]:
            main[n] += 1
        chance[d["chance"]] += 1
    return {
        "total_draws": len(draws),
        "main": [{"number": n, "count": main.get(n, 0)} for n in range(1, 50)],
        "chance": [{"number": n, "count": chance.get(n, 0)} for n in range(1, 11)],
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


@api_router.get("/stats/trend")
async def stats_trend(window: int = 20, user: User = Depends(get_current_user)):
    """Compare taux récent vs global. Inspired by LotoAI-Pro v0.7 TrendIndicator."""
    draws = await _get_all_draws(user.user_id)
    total = len(draws)
    window = max(5, min(window, total)) if total else 0
    SEUIL_FIABILITE = 15
    fiable = window >= SEUIL_FIABILITE

    global_freq = Counter()
    recent_freq = Counter()
    for d in draws:
        for n in d["numbers"]:
            global_freq[n] += 1
    for d in draws[-window:] if window else []:
        for n in d["numbers"]:
            recent_freq[n] += 1

    tendances = []
    for n in range(1, 50):
        tg = (global_freq.get(n, 0) / total * 100) if total else 0.0
        tr = (recent_freq.get(n, 0) / window * 100) if window else 0.0
        tendances.append({
            "number": n,
            "taux_global": round(tg, 2),
            "taux_recent": round(tr, 2),
            "ecart": round(tr - tg, 2),
        })
    tendances.sort(key=lambda x: x["ecart"], reverse=True)
    return {
        "fenetre_recente": window,
        "seuil_fiabilite": SEUIL_FIABILITE,
        "fiable": fiable,
        "hausse": tendances[:10],
        "baisse": list(reversed(tendances[-10:])),
        "all": tendances,
    }


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
    return await cursor.to_list(200)


@api_router.delete("/grids/{grid_id}")
async def delete_grid(grid_id: str, user: User = Depends(get_current_user)):
    res = await db.saved_grids.delete_one({"id": grid_id, "user_id": user.user_id})
    return {"deleted": res.deleted_count}


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
        "chance_matches": 0,
        "rank_hist": [0] * 6,   # index = main matches (0..5)
        "hits_3plus": 0,
        "hits_5plus_chance": 0,
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
                r["rank_hist"][matches] += 1
                if chance == actual_chance:
                    r["chance_matches"] += 1
                    if matches >= 5:
                        r["hits_5plus_chance"] += 1
                if matches >= 3:
                    r["hits_3plus"] += 1

    summary = []
    for s in strategies:
        r = results[s]
        gt = r["grids_tested"] or 1
        summary.append({
            "strategy": s,
            "grids_tested": r["grids_tested"],
            "avg_main_matches": round(r["sum_main_matches"] / gt, 3),
            "chance_hit_rate": round(r["chance_matches"] / gt * 100, 2),
            "hit_3plus_rate": round(r["hits_3plus"] / gt * 100, 2),
            "rank_distribution": r["rank_hist"],
            "hits_5plus_chance": r["hits_5plus_chance"],
        })
    summary.sort(key=lambda x: x["avg_main_matches"], reverse=True)

    return {
        "total_draws": total,
        "sample_size": sample,
        "grids_per_strategy": n_grids,
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
        import asyncio as _a
        result = await _a.to_thread(resend.Emails.send, params)
        return {"status": "sent", "to": to_email, "email_id": result.get("id"), "grids": grids}
    except Exception as e:
        logger.error(f"Resend error: {e}")
        raise HTTPException(status_code=500, detail=f"Échec envoi email: {e}")


class AlertPrefs(BaseModel):
    enabled: bool = False
    strategy: Literal["hot", "cold", "balanced", "weighted_random"] = "balanced"
    grids_count: int = 3
    email: Optional[str] = None


@api_router.get("/alerts/prefs")
async def get_alert_prefs(user: User = Depends(get_current_user)):
    doc = await db.alert_prefs.find_one({"user_id": user.user_id}, {"_id": 0})
    if not doc:
        return {"enabled": False, "strategy": "balanced", "grids_count": 3, "email": user.email}
    return {
        "enabled": doc.get("enabled", False),
        "strategy": doc.get("strategy", "balanced"),
        "grids_count": doc.get("grids_count", 3),
        "email": doc.get("email") or user.email,
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
    cursor = db.alert_prefs.find({"enabled": True}, {"_id": 0})
    async for pref in cursor:
        try:
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
            import asyncio as _a
            await _a.to_thread(resend.Emails.send, params)
            logger.info(f"Auto-alert sent to {to_email}")
        except Exception as e:
            logger.error(f"Auto-alert error for {pref.get('user_id')}: {e}")


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
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler(timezone="Europe/Paris")


@app.on_event("startup")
async def _start_scheduler():
    # Run every day at 12:00 Paris time
    scheduler.add_job(_run_daily_alerts, "cron", hour=12, minute=0, id="daily_loto_alert", replace_existing=True)
    scheduler.start()
    logger.info("Scheduler started (daily alerts at 12:00 Paris)")


@app.on_event("shutdown")
async def shutdown_db_client():
    try:
        scheduler.shutdown(wait=False)
    except Exception:
        pass
    client.close()
