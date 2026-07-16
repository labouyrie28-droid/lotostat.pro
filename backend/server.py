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
    content = (await file.read()).decode("utf-8", errors="ignore")
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)
    if not rows:
        raise HTTPException(status_code=400, detail="Fichier CSV vide")

    # Detect header
    header = [c.strip().lower() for c in rows[0]]
    has_header = any(k in "".join(header) for k in ["date", "boule", "num", "chance"])
    data_rows = rows[1:] if has_header else rows

    inserted = 0
    errors = 0
    docs = []
    for r in data_rows:
        try:
            if len(r) < 7:
                errors += 1
                continue
            date_str = r[0].strip()
            # Support DD/MM/YYYY and YYYY-MM-DD
            if "/" in date_str:
                dd, mm, yy = date_str.split("/")
                date_iso = f"{yy}-{mm.zfill(2)}-{dd.zfill(2)}"
            else:
                date_iso = date_str
            datetime.fromisoformat(date_iso)  # validate
            nums = [int(x) for x in r[1:6]]
            chance = int(r[6])
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
        except Exception:
            errors += 1
    if docs:
        await db.draws.insert_many(docs)
        inserted = len(docs)
    return {"inserted": inserted, "errors": errors}


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
            # Mix: 2 hot, 2 cold, 1 highest delay
            ranked_hot = sorted(range(1, 50), key=lambda n: main_freq.get(n, 0), reverse=True)
            ranked_cold = sorted(range(1, 50), key=lambda n: main_freq.get(n, 0))
            ranked_delay = sorted(range(1, 50), key=lambda n: delays[n], reverse=True)
            picked = set()
            for n in ranked_hot:
                if len(picked) >= 2: break
                picked.add(n)
            for n in ranked_cold:
                if len(picked) >= 4: break
                picked.add(n)
            for n in ranked_delay:
                if len(picked) >= 5: break
                picked.add(n)
            # fill if any collision
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


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
