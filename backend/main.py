"""Roamly backend (FastAPI). Run from this folder:  python -m uvicorn main:app --port 8000
Everything is documented at http://localhost:8000/docs once it is running."""
import hashlib
import json
import logging
import math
import os
import re
import secrets
import smtplib
import sqlite3
import threading
import time
import urllib.parse
import urllib.request
from datetime import date, timedelta
from email.message import EmailMessage
from typing import List, Optional

import joblib
import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import config
import imagegen
import intent
import ranker
import seed
from chat import Chat
from ratelimit import Limiter

log = logging.getLogger("travel")
MONTHS = ranker.MONTHS
seed.ensure()                                   # creates / upgrades data/travel.db
_con = sqlite3.connect(seed.DB)
df = pd.read_sql("SELECT * FROM destinations", _con)
places_df = pd.read_sql("SELECT * FROM places ORDER BY destination, ord", _con)
hotels_df = pd.read_sql("SELECT * FROM hotels", _con)
_con.close()
TYPES = sorted(df["trip_type"].unique())
CENTRE = {d: (g.lat.mean(), g.lon.mean()) for d, g in places_df.groupby("destination")}
bundle = ranker.load()                          # trains on first run if models/ranker.joblib is missing
bot = Chat(df, places_df, bundle, hotels_df)
con = bot.con
limiter = Limiter()
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").strip().lower()

app = FastAPI(title="Roamly", docs_url="/docs")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.update({"X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "Referrer-Policy": "strict-origin-when-cross-origin",
                         "Permissions-Policy": "microphone=(self), camera=(), geolocation=()"})
    if request.url.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    elif request.url.path.endswith((".js", ".css", ".html", ".webmanifest")) or request.url.path == "/":
        resp.headers["Cache-Control"] = "no-cache"   # always revalidate (cheap 304), so a new art.js can't be paired with an old landing.js
    return resp


# ---------------------------------------------------------------- tables (created or upgraded on start)
con.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, name TEXT, pw TEXT, salt TEXT)")
con.add_column("users", "created", "TEXT")
con.execute("CREATE TABLE IF NOT EXISTS auth_tokens (hash TEXT PRIMARY KEY, uid INTEGER, expires INTEGER)")
con.execute("CREATE TABLE IF NOT EXISTS reset_tokens (hash TEXT PRIMARY KEY, uid INTEGER, expires INTEGER)")
con.execute("CREATE TABLE IF NOT EXISTS favorites (id INTEGER PRIMARY KEY AUTOINCREMENT, sid TEXT, destination TEXT, hotel TEXT, days INTEGER)")
for c_, d_ in (("plan", "TEXT"), ("note", "TEXT"), ("created", "TEXT")):
    con.add_column("favorites", c_, d_)
con.execute("CREATE TABLE IF NOT EXISTS feedback (sid TEXT, destination TEXT, hotel TEXT, liked INTEGER)")
for c_, d_ in (("trip_type", "TEXT"), ("budget", "INTEGER"), ("month", "INTEGER"), ("days", "INTEGER"), ("ts", "TEXT")):
    con.add_column("feedback", c_, d_)
con.execute("CREATE TABLE IF NOT EXISTS events (uid INTEGER, kind TEXT, mode TEXT, ts DATETIME DEFAULT CURRENT_TIMESTAMP)")
con.execute("CREATE TABLE IF NOT EXISTS shares (token TEXT PRIMARY KEY, uid INTEGER, plan TEXT, created TEXT)")


# ---------------------------------------------------------------- auth
def now():
    return int(time.time())


def sha(x):
    return hashlib.sha256(x.encode()).hexdigest()


def hash_pw(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000).hex()


DUMMY_SALT = secrets.token_hex(16)   # lets login hash a password even when the email is unknown, so both paths take the same time


def ip_of(request: Request):
    return request.client.host if request.client else "?"


def auth(request: Request):
    """Returns (id, name, email) of the logged-in user, or 401. Only a hash of the session token is stored."""
    t = request.cookies.get("session")
    r = con.execute("SELECT u.id, u.name, u.email FROM auth_tokens k JOIN users u ON u.id = k.uid WHERE k.hash=? AND k.expires>?",
                    (sha(t), now())).fetchone() if t else None
    if not r:
        raise HTTPException(401, "Please log in")
    return r


def start_session(resp: Response, uid: int, remember: bool = True):
    tok, days = secrets.token_urlsafe(32), 30 if remember else 1
    con.execute("DELETE FROM auth_tokens WHERE expires<?", (now(),))
    con.execute("INSERT INTO auth_tokens VALUES (?,?,?)", (sha(tok), uid, now() + days * 86400))
    resp.set_cookie("session", tok, httponly=True, samesite="lax", secure=os.getenv("COOKIE_SECURE") == "1",
                    max_age=days * 86400 if remember else None)


WEAK = {"password", "password1", "12345678", "123456789", "qwertyui", "11111111", "iloveyou", "letmein1"}


def check_password(pw, email=""):
    if len(pw) < 8:
        raise HTTPException(400, "Use at least 8 characters")
    if pw.lower() in WEAK or pw.lower() == email.lower():
        raise HTTPException(400, "That password is too easy to guess")


def valid_email(e):
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", e)) and len(e) <= 120


class Reg(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    email: str = Field(max_length=120)
    password: str = Field(min_length=1, max_length=100)
    remember: bool = True


class Login(BaseModel):
    email: str
    password: str
    remember: bool = True


@app.post("/api/register")
def register(b: Reg, request: Request, resp: Response):
    if not limiter.allow(f"reg:{ip_of(request)}", 10, 3600):
        raise HTTPException(429, "Too many sign-ups from this network. Try again later.")
    email = b.email.strip().lower()
    if not valid_email(email):
        raise HTTPException(400, "Enter a valid email address")
    check_password(b.password, email)
    salt = secrets.token_hex(16)
    try:
        cur = con.execute("INSERT INTO users (email, name, pw, salt, created) VALUES (?,?,?,?,?)",
                          (email, b.name.strip(), hash_pw(b.password, salt), salt, date.today().isoformat()))
    except sqlite3.IntegrityError:
        raise HTTPException(409, "That email is already registered. Try logging in.")
    start_session(resp, cur.lastrowid, b.remember)
    return {"name": b.name.strip()}


@app.post("/api/login")
def login(b: Login, request: Request, resp: Response):
    email = b.email.strip().lower()
    k1, k2 = f"fail:{ip_of(request)}:{email}", f"failip:{ip_of(request)}"
    if limiter.count(k1, 600) >= 5 or limiter.count(k2, 600) >= 30:
        raise HTTPException(429, "Too many failed attempts. Wait a few minutes and try again.")
    r = con.execute("SELECT id, name, pw, salt FROM users WHERE email=?", (email,)).fetchone()
    good = hash_pw(b.password, r[3] if r else DUMMY_SALT)   # always hashed: an unknown email must not answer faster
    if not r or not secrets.compare_digest(good, r[2]):
        limiter.add(k1, 600)
        limiter.add(k2, 600)
        raise HTTPException(401, "Wrong email or password")
    limiter.clear(k1)
    start_session(resp, r[0], b.remember)
    return {"name": r[1]}


@app.post("/api/logout")
def logout(request: Request, resp: Response):
    t = request.cookies.get("session")
    if t:
        con.execute("DELETE FROM auth_tokens WHERE hash=?", (sha(t),))
    resp.delete_cookie("session")
    return {"ok": True}


@app.get("/api/me")
def me(u=Depends(auth)):
    created = con.execute("SELECT created FROM users WHERE id=?", (u[0],)).fetchone()[0]
    return {"name": u[1], "email": u[2], "since": created, "admin": bool(ADMIN_EMAIL) and u[2] == ADMIN_EMAIL}


def send_reset(email: str, link: str):
    """Emails the reset link when SMTP_HOST / SMTP_USER / SMTP_PASSWORD are set; otherwise prints it to the server
    console (handy while developing)."""
    host = os.getenv("SMTP_HOST")
    if not host:
        log.warning("PASSWORD RESET LINK for %s: %s", email, link)
        print(f"\n  PASSWORD RESET LINK for {email}:\n  {link}\n")
        return
    m = EmailMessage()
    m["Subject"], m["From"], m["To"] = "Reset your Roamly password", os.getenv("SMTP_FROM", os.getenv("SMTP_USER")), email
    m.set_content(f"Someone asked to reset the password for this account.\n\nOpen this link within one hour:\n{link}\n\nIf it was not you, ignore this email.")
    try:
        with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=15) as s:
            s.starttls()
            s.login(os.getenv("SMTP_USER", ""), os.getenv("SMTP_PASSWORD", ""))
            s.send_message(m)
    except Exception:
        log.exception("could not send reset email")


class Forgot(BaseModel):
    email: str = Field(max_length=120)


class Reset(BaseModel):
    token: str = Field(max_length=100)
    password: str = Field(min_length=1, max_length=100)


def reset_base_url(request: Request):
    """Address used in reset links. BASE_URL when set. Otherwise the request's own address, but only on localhost: the Host
    header is attacker-controlled, so trusting it elsewhere would let anyone mail a victim a link to their own server."""
    if os.getenv("BASE_URL"):
        return os.environ["BASE_URL"].rstrip("/")
    if request.url.hostname in ("localhost", "127.0.0.1", "::1"):
        return str(request.base_url).rstrip("/")
    return None


@app.post("/api/forgot")
def forgot(b: Forgot, request: Request):
    email = b.email.strip().lower()
    if not limiter.allow(f"forgot:{ip_of(request)}", 5, 3600):
        raise HTTPException(429, "Too many requests. Try again later.")
    r = con.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
    if r:   # the answer is identical whether or not the account exists, so it can't be used to look up emails
        base = reset_base_url(request)
        if not base:
            log.warning("Password reset for %s NOT sent: set BASE_URL (the Host header %r is not trusted for links)", email, request.headers.get("host"))
            return {"ok": True}
        tok = secrets.token_urlsafe(32)
        con.execute("INSERT INTO reset_tokens VALUES (?,?,?)", (sha(tok), r[0], now() + 3600))
        threading.Thread(target=send_reset, args=(email, f"{base}/reset.html?token={tok}"), daemon=True).start()
    return {"ok": True}


@app.post("/api/reset")
def reset(b: Reset):
    r = con.execute("SELECT uid FROM reset_tokens WHERE hash=? AND expires>?", (sha(b.token), now())).fetchone()
    if not r:
        raise HTTPException(400, "This reset link is invalid or has expired. Request a new one.")
    email = con.execute("SELECT email FROM users WHERE id=?", (r[0],)).fetchone()[0]
    check_password(b.password, email)
    salt = secrets.token_hex(16)
    con.execute("UPDATE users SET pw=?, salt=? WHERE id=?", (hash_pw(b.password, salt), salt, r[0]))
    con.execute("DELETE FROM reset_tokens WHERE uid=?", (r[0],))
    con.execute("DELETE FROM auth_tokens WHERE uid=?", (r[0],))   # log out everywhere
    return {"ok": True}


class AccountEdit(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=60)
    current_password: Optional[str] = Field(default=None, max_length=100)
    new_password: Optional[str] = Field(default=None, max_length=100)


def verify_pw(uid, pw):
    r = con.execute("SELECT pw, salt FROM users WHERE id=?", (uid,)).fetchone()
    return bool(pw) and secrets.compare_digest(hash_pw(pw, r[1]), r[0])


@app.patch("/api/account")
def account_edit(b: AccountEdit, request: Request, u=Depends(auth)):
    if b.name:
        con.execute("UPDATE users SET name=? WHERE id=?", (b.name.strip(), u[0]))
    if b.new_password:
        if not limiter.allow(f"pw:{u[0]}", 5, 600):
            raise HTTPException(429, "Too many attempts. Try again in a few minutes.")
        if not verify_pw(u[0], b.current_password):
            raise HTTPException(403, "Your current password is wrong")
        check_password(b.new_password, u[2])
        salt = secrets.token_hex(16)
        con.execute("UPDATE users SET pw=?, salt=? WHERE id=?", (hash_pw(b.new_password, salt), salt, u[0]))
        keep = sha(request.cookies.get("session", ""))
        con.execute("DELETE FROM auth_tokens WHERE uid=? AND hash<>?", (u[0], keep))   # other devices are logged out
    return {"ok": True}


class Pw(BaseModel):
    password: str = Field(max_length=100)


@app.post("/api/account/delete")
def account_delete(b: Pw, resp: Response, u=Depends(auth)):
    if not limiter.allow(f"del:{u[0]}", 5, 600) or not verify_pw(u[0], b.password):
        raise HTTPException(403, "Wrong password")
    sid = f"u{u[0]}"
    for sql in ("DELETE FROM favorites WHERE sid=?", "DELETE FROM feedback WHERE sid=?", "DELETE FROM sessions WHERE sid=?"):
        con.execute(sql, (sid,))
    for t in ("auth_tokens", "reset_tokens", "events", "shares"):
        con.execute(f"DELETE FROM {t} WHERE uid=?", (u[0],))
    con.execute("DELETE FROM users WHERE id=?", (u[0],))
    resp.delete_cookie("session")
    return {"ok": True}


@app.get("/api/account/export")
def account_export(u=Depends(auth)):
    sid = f"u{u[0]}"
    favs = con.execute("SELECT destination, hotel, days, note, created, plan FROM favorites WHERE sid=?", (sid,)).fetchall()
    fb = con.execute("SELECT destination, hotel, liked, trip_type, budget, month, days, ts FROM feedback WHERE sid=?", (sid,)).fetchall()
    snap = bot.snapshot(sid)
    return {"account": {"name": u[1], "email": u[2]}, "memory": snap["memory"], "chat_history": snap["history"],
            "saved_trips": [{"destination": f[0], "hotel": f[1], "days": f[2], "note": f[3], "saved": f[4], "plan": json.loads(f[5]) if f[5] else None} for f in favs],
            "feedback": [dict(zip(("destination", "hotel", "liked", "trip_type", "budget", "month", "days", "time"), x)) for x in fb]}


# ---------------------------------------------------------------- destinations, trips, plans
@app.get("/api/options")
def options():
    return {"trip_types": TYPES}


@app.get("/api/destinations")
def destinations():
    """Public list used by the landing page."""
    out = []
    for d, g in df.groupby("destination", sort=True):
        r = g.iloc[0]
        out.append({"destination": d, "country": str(r["country"]), "trip_type": str(r["trip_type"]),
                    "best_months": [MONTHS.index(m) + 1 for m in str(r["best_months"]).split(";")],
                    "from_per_day_eur": int((g["hotel_price_eur"].min() + r["daily_spend_eur"])),
                    "highlights": str(r["highlights"]).split(";")[:3], "description": str(r["description"])})
    return out


@app.get("/api/destination/{name}")
def destination(name: str):
    rows = df[df.destination == name]
    if rows.empty:
        raise HTTPException(404, "Unknown destination")
    r = rows.iloc[0]
    return {"destination": name, "country": str(r["country"]), "trip_type": str(r["trip_type"]),
            "best_months": [MONTHS.index(m) + 1 for m in r["best_months"].split(";")], "avg_temp_c": int(r["avg_temp_c"]),
            "crowd_level": str(r["crowd_level"]), "activity_level": int(r["activity_level"]), "rating": float(r["rating"]),
            "daily_spend_eur": int(r["daily_spend_eur"]), "currency": str(r["currency"]), "language": str(r["language"]),
            "airport_code": str(r["airport_code"]), "schengen": str(r["schengen"]),
            "hotels": [{"name": str(h.hotel_name), "price": int(h.hotel_price_eur), "category": str(h.hotel_category)} for h in rows.itertuples()]}


class Trip(BaseModel):
    trip_type: str
    budget: int = Field(ge=1, le=3)   # 1 budget, 2 mid-range, 3 luxury
    month: int = Field(ge=1, le=12)
    days: int = Field(ge=1, le=21)


@app.post("/api/recommend")
def recommend(trip: Trip):
    """Simple single-city ranking (kept for compatibility). The app uses /api/trips."""
    scores = ranker.score(bundle, trip.trip_type, trip.budget, trip.month, trip.days, df)
    results, seen = [], set()
    for i in np.argsort(-scores):
        r = df.iloc[i]
        if scores[i] < 0.3:
            break
        if r["destination"] in seen:
            continue
        seen.add(r["destination"])
        results.append({"destination": r["destination"], "country": r["country"], "trip_type": r["trip_type"],
                        "best_months": r["best_months"].replace(";", ", "), "match_pct": round(float(scores[i]) * 100),
                        "in_season": MONTHS[trip.month - 1] in r["best_months"].split(";"), "hotel": r["hotel_name"],
                        "hotel_category": r["hotel_category"], "hotel_price_eur": int(r["hotel_price_eur"]),
                        "estimated_cost_eur": int(r["cost_per_day_total_eur"] * trip.days),
                        "highlights": r["highlights"].replace(";", ", "), "description": r["description"], "tip": r["travel_tip"]})
        if len(results) == 5:
            break
    return {"results": results}


class TripReq(BaseModel):
    trip_type: str
    month: int = Field(ge=1, le=12)
    days: int = Field(ge=1, le=21)
    budget: Optional[int] = Field(default=None, ge=1, le=3)
    max_budget_eur: Optional[int] = Field(default=None, ge=0, le=1_000_000)
    travelers: int = Field(default=1, ge=1, le=20)
    group: Optional[str] = None
    activity: Optional[int] = Field(default=None, ge=1, le=3)
    avoid_crowds: bool = False
    sync: bool = True   # also store these choices as the chat's memory


@app.post("/api/trips")
def trips(t: TripReq, request: Request):
    """Guided mode: same engine as the chat, so results (budget, multi-city routes, match %) are identical."""
    if t.trip_type not in TYPES:
        raise HTTPException(400, "Unknown trip type")
    if not limiter.allow(f"trips:{ip_of(request)}", 60, 60):
        raise HTTPException(429, "Slow down a little")
    slots = {k: v for k, v in t.model_dump(exclude={"sync"}).items() if v not in (None, False)}
    st = bot.clean_slots(slots)
    res = bot.recommend(st, limit=5)
    if t.sync and request.cookies.get("session"):
        try:
            bot.set_slots(f"u{auth(request)[0]}", slots)
        except HTTPException:
            pass
    return {"results": res, "slots": bot.public(st)}


class Leg(BaseModel):
    destination: str
    hotel: str
    days: int = Field(ge=1, le=21)


class PlanReq(BaseModel):
    destination: Optional[str] = None
    hotel: Optional[str] = None
    days: Optional[int] = Field(default=None, ge=1, le=21)
    legs: Optional[List[Leg]] = Field(default=None, max_length=4)
    travelers: int = Field(default=1, ge=1, le=20)


@app.post("/api/plan")
def plan(req: PlanReq, request: Request):
    if not limiter.allow(f"plan:{ip_of(request)}", 20, 60):   # public and may call the language model, so it is limited per address
        raise HTTPException(429, "Slow down a little")
    legs = [l.model_dump() for l in req.legs] if req.legs else [{"destination": req.destination, "hotel": req.hotel, "days": req.days or 3}]
    if sum(l["days"] for l in legs) > 28:
        raise HTTPException(400, "Plans are limited to 28 days")
    for l in legs:
        if df[(df.destination == l["destination"]) & (df.hotel_name == l["hotel"])].empty or l["destination"] not in bot.places:
            raise HTTPException(404, "Unknown destination or hotel")
    return bot.route(legs, req.travelers)


# ---------------------------------------------------------------- weather and currency (free, no API keys; cached)
_cache, _cache_lock = {}, threading.Lock()
WMO = {0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Overcast", 45: "Fog", 48: "Fog", 51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
       61: "Light rain", 63: "Rain", 65: "Heavy rain", 71: "Light snow", 73: "Snow", 75: "Heavy snow", 80: "Showers", 81: "Showers", 82: "Heavy showers",
       95: "Thunderstorm", 96: "Thunderstorm", 99: "Thunderstorm"}


def fetch_json(url, timeout=6):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "travel-ai-class-project"}), timeout=timeout) as r:
        return json.load(r)


def cached(key, ttl, fn):
    with _cache_lock:
        hit = _cache.get(key)
        if hit and hit[0] > time.time():
            return hit[1]
    val = fn()
    with _cache_lock:
        _cache[key] = (time.time() + ttl, val)
    return val


@app.get("/api/weather")
def weather(destination: str, month: int = 0):
    """7-day forecast plus the average for the chosen month last year (Open-Meteo). Falls back to the dataset's
    average temperature when the service can't be reached."""
    if destination not in CENTRE:
        raise HTTPException(404, "Unknown destination")
    lat, lon = CENTRE[destination]
    month = month if 1 <= month <= 12 else date.today().month

    def load():
        out = {"destination": destination, "month": month, "forecast": [], "climate": None, "source": "dataset",
               "avg_temp_c": int(df[df.destination == destination].iloc[0]["avg_temp_c"])}
        try:
            f = fetch_json(f"https://api.open-meteo.com/v1/forecast?latitude={lat:.3f}&longitude={lon:.3f}&timezone=auto&forecast_days=7"
                           "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weathercode")["daily"]
            out["forecast"] = [{"date": d, "max": round(a), "min": round(b), "rain_pct": p, "label": WMO.get(c, "Mixed")}
                               for d, a, b, p, c in zip(f["time"], f["temperature_2m_max"], f["temperature_2m_min"], f["precipitation_probability_max"], f["weathercode"])]
            out["source"] = "open-meteo"
        except Exception:
            pass
        try:
            y = date.today().year - 1
            start = date(y, month, 1)
            end = (date(y + (month == 12), month % 12 + 1, 1)) - timedelta(days=1)
            a = fetch_json(f"https://archive-api.open-meteo.com/v1/archive?latitude={lat:.3f}&longitude={lon:.3f}&start_date={start}&end_date={end}"
                           "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum&timezone=auto")["daily"]
            mx, mn, pr = [x for x in a["temperature_2m_max"] if x is not None], [x for x in a["temperature_2m_min"] if x is not None], [x for x in a["precipitation_sum"] if x is not None]
            if mx and mn:
                out["climate"] = {"avg_max": round(sum(mx) / len(mx)), "avg_min": round(sum(mn) / len(mn)), "rainy_days": sum(1 for x in pr if x >= 1), "year": y}
                out["source"] = "open-meteo"
        except Exception:
            pass
        return out
    return cached(("w", destination, month), 6 * 3600, load)


FALLBACK_RATES = {"EUR": 1.0, "AED": 4.3, "USD": 1.15, "GBP": 0.86, "SAR": 4.3, "INR": 95.0}


@app.get("/api/rates")
def rates():
    """EUR-based exchange rates from open.er-api.com (free, no key). Falls back to rough fixed values."""
    def load():
        try:
            r = fetch_json("https://open.er-api.com/v6/latest/EUR")["rates"]
            return {"base": "EUR", "rates": {k: round(float(r[k]), 4) for k in FALLBACK_RATES if k in r}, "source": "live"}
        except Exception:
            return {"base": "EUR", "rates": FALLBACK_RATES, "source": "approximate"}
    return cached("rates", 12 * 3600, load)


# ---------------------------------------------------------------- chat
class ChatReq(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=500)


@app.post("/api/chat")
def chat(req: ChatReq, u=Depends(auth)):
    if not limiter.allow(f"chat:{u[0]}", 40, 60):
        raise HTTPException(429, "You are sending messages very quickly. Wait a moment.")
    return bot.reply(f"u{u[0]}", req.message)


@app.get("/api/chat/history")
def chat_history(u=Depends(auth)):
    return bot.snapshot(f"u{u[0]}")


@app.get("/api/chat/{sid}")
def chat_history_legacy(sid: str, u=Depends(auth)):
    """Old alias of /api/chat/history. The server ignores {sid}: the history always belongs to the logged-in user."""
    return bot.snapshot(f"u{u[0]}")


@app.post("/api/chat/reset")
def chat_reset(u=Depends(auth)):
    bot.reset(f"u{u[0]}")
    return bot.snapshot(f"u{u[0]}")


class Slots(BaseModel):
    slots: dict


@app.post("/api/memory")
def memory(b: Slots, u=Depends(auth)):
    return bot.set_slots(f"u{u[0]}", b.slots)


# ---------------------------------------------------------------- saved trips, feedback, usage
class Fav(BaseModel):
    session_id: str = Field(default="", max_length=64)
    destination: str = Field(max_length=120)
    hotel: str = Field(max_length=120)
    days: int = Field(default=3, ge=1, le=28)
    plan: Optional[dict] = None
    note: Optional[str] = Field(default=None, max_length=500)


class Note(BaseModel):
    note: str = Field(max_length=500)


class Rm(BaseModel):
    session_id: str = Field(default="", max_length=64)
    id: int


class Fb(BaseModel):
    session_id: str = Field(default="", max_length=64)
    destination: str
    hotel: str
    liked: bool
    trip_type: Optional[str] = None
    budget: Optional[int] = Field(default=None, ge=1, le=3)
    month: Optional[int] = Field(default=None, ge=1, le=12)
    days: Optional[int] = Field(default=None, ge=1, le=28)


class Ev(BaseModel):
    kind: str = Field(pattern="^(use|switch)$")
    mode: str = Field(pattern="^(chat|guided)$")


@app.post("/api/favorites")
def fav_add(f: Fav, u=Depends(auth)):
    try:
        plan_json = json.dumps(f.plan, allow_nan=False) if f.plan else None   # NaN/Infinity would make the saved-trips list fail to load later
    except ValueError:
        raise HTTPException(400, "That plan could not be saved")
    if plan_json and len(plan_json) > 200_000:
        raise HTTPException(413, "Plan is too large")
    cur = con.execute("INSERT INTO favorites (sid, destination, hotel, days, plan, note, created) VALUES (?,?,?,?,?,?,?)",
                      (f"u{u[0]}", f.destination, f.hotel, f.days, plan_json, f.note, date.today().isoformat()))
    return {"ok": True, "id": cur.lastrowid}


@app.get("/api/favorites")
def fav_list(u=Depends(auth)):
    rows = con.execute("SELECT id, destination, hotel, days, note, created, plan FROM favorites WHERE sid=? ORDER BY id DESC", (f"u{u[0]}",)).fetchall()
    return [{"id": r[0], "destination": r[1], "hotel": r[2], "days": r[3], "note": r[4] or "", "created": r[5], "plan": json.loads(r[6]) if r[6] else None} for r in rows]


@app.get("/api/favorites/{sid}")
def fav_list_legacy(sid: str, u=Depends(auth)):
    """Old alias of /api/favorites. The server ignores {sid}: saved trips always belong to the logged-in user."""
    return fav_list(u)


@app.patch("/api/favorites/{fid}")
def fav_note(fid: int, n: Note, u=Depends(auth)):
    con.execute("UPDATE favorites SET note=? WHERE id=? AND sid=?", (n.note, fid, f"u{u[0]}"))
    return {"ok": True}


@app.post("/api/favorites/remove")
def fav_remove(r: Rm, u=Depends(auth)):
    con.execute("DELETE FROM favorites WHERE id=? AND sid=?", (r.id, f"u{u[0]}"))
    return {"ok": True}


@app.post("/api/feedback")
def feedback(f: Fb, u=Depends(auth)):
    if not limiter.allow(f"fb:{u[0]}", 60, 3600):   # feedback is blended into training, so one account must not be able to flood it
        raise HTTPException(429, "Too much feedback in a short time. Try again later.")
    if df[(df.destination == f.destination) & (df.hotel_name == f.hotel)].empty:
        raise HTTPException(404, "Unknown destination or hotel")
    con.execute("INSERT INTO feedback (sid, destination, hotel, liked, trip_type, budget, month, days, ts) VALUES (?,?,?,?,?,?,?,?,?)",
                (f"u{u[0]}", f.destination, f.hotel, int(f.liked), f.trip_type, f.budget, f.month, f.days, date.today().isoformat()))
    return {"ok": True}


@app.post("/api/event")
def event(e: Ev, u=Depends(auth)):
    """Logs which planning mode people use (kind='use') or switch to (kind='switch')."""
    con.execute("INSERT INTO events (uid, kind, mode) VALUES (?,?,?)", (u[0], e.kind, e.mode))
    return {"ok": True}


# ---------------------------------------------------------------- sharing (public, read-only links)
def finite(x):
    """float(x), refusing NaN and infinity: they are valid in JSON input but crash JSON output and int()."""
    x = float(x)
    if not math.isfinite(x):
        raise ValueError("non-finite number")
    return x


def clean_plan(p: dict) -> dict:
    """Keeps only the fields the share page uses, so arbitrary data can't be stored behind a public link."""
    try:
        days = [{"day": int(d["day"]), "title": str(d.get("title", ""))[:120], "text": str(d["text"])[:600], "city": str(d.get("city", ""))[:60],
                 "daytrip": bool(d.get("daytrip")), "km": finite(d.get("km", 0)),
                 "stops": [{"name": str(s["name"])[:100], "lat": finite(s["lat"]), "lon": finite(s["lon"]), "kind": str(s.get("kind", "sight"))[:12]} for s in d["stops"]][:6]}
                for d in p["days"]][:28]
        out = {"destination": str(p["destination"])[:160], "hotel": str(p.get("hotel", ""))[:120], "summary": str(p.get("summary", ""))[:1500],
               "days": days, "center": [finite(p["center"][0]), finite(p["center"][1])],
               "hotels": [{"name": str(h["name"])[:120], "lat": finite(h["lat"]), "lon": finite(h["lon"]), "city": str(h.get("city", ""))[:60]} for h in p.get("hotels", [])][:6],
               "budget": {k: int(finite(v)) for k, v in p.get("budget", {}).items() if isinstance(v, (int, float))},
               "trip_type": str(p.get("facts", {}).get("trip_type", "city"))[:20]}
    except (KeyError, TypeError, ValueError, IndexError, OverflowError):
        raise HTTPException(400, "That plan could not be shared")
    if not days:
        raise HTTPException(400, "That plan could not be shared")
    return out


class ShareReq(BaseModel):
    plan: dict


@app.post("/api/share")
def share(b: ShareReq, u=Depends(auth)):
    if not limiter.allow(f"share:{u[0]}", 30, 3600):
        raise HTTPException(429, "Too many share links created. Try again later.")
    tok = secrets.token_urlsafe(9)
    con.execute("INSERT INTO shares VALUES (?,?,?,?)", (tok, u[0], json.dumps(clean_plan(b.plan)), date.today().isoformat()))
    return {"token": tok, "path": f"/share.html?t={tok}"}


@app.get("/api/shared/{token}")
def shared(token: str):
    r = con.execute("SELECT plan, created FROM shares WHERE token=?", (token[:40],)).fetchone()
    if not r:
        raise HTTPException(404, "This link does not exist or was removed")
    return {"plan": json.loads(r[0]), "created": r[1]}


# ---------------------------------------------------------------- model info, retraining, health
@app.get("/api/model")
def model_info():
    fb = dict(con.execute("SELECT liked, COUNT(*) FROM feedback GROUP BY liked").fetchall())
    ctx = con.execute("SELECT COUNT(*) FROM feedback WHERE trip_type IS NOT NULL AND month IS NOT NULL").fetchone()[0]
    try:
        metrics = json.load(open(config.MODELS / "metrics.json"))
    except Exception:
        metrics = {}
    return {"intent_accuracy": intent._bundle["accuracy"], "ranker": metrics, "likes": fb.get(1, 0), "dislikes": fb.get(0, 0), "chat_mode": bot.mode(),
            "feedback_with_context": ctx, "destinations": int(df.destination.nunique()), "hotels": len(df), "places": len(places_df),
            "modes": dict(con.execute("SELECT mode, COUNT(*) FROM events WHERE kind='use' GROUP BY mode").fetchall())}


_retraining = threading.Lock()


@app.post("/api/admin/retrain")
def retrain(u=Depends(auth)):
    """Retrains the ranker (blending in real thumbs-up/down). Only the account whose email is ADMIN_EMAIL can call it."""
    if not ADMIN_EMAIL or u[2] != ADMIN_EMAIL:
        raise HTTPException(403, "Admins only")
    if not _retraining.acquire(blocking=False):
        raise HTTPException(409, "A retrain is already running")
    try:
        import train
        train.main(use_feedback=True)
        bot.bundle = joblib.load(ranker.MODEL_PATH)
        global bundle
        bundle = bot.bundle
    finally:
        _retraining.release()
    return model_info()


@app.get("/api/health")
def health():
    return {"ok": True, "destinations": int(df.destination.nunique())}


@app.get("/images/destinations/{name}.jpg")
def destination_image(name: str):
    """Picture for a city: a photo dropped into frontend/images/destinations wins, otherwise one generated by xAI
    (once, then cached). 404 means "no picture", and the page keeps its drawn illustration."""
    rows = df[df.destination.map(imagegen.slug) == name]
    if rows.empty:
        raise HTTPException(404)
    photo = config.FRONTEND / "images" / "destinations" / f"{name}.jpg"
    path = photo if photo.exists() else imagegen.get(rows.iloc[0]["destination"], str(rows.iloc[0]["country"]), str(rows.iloc[0]["trip_type"]))
    if not path:
        raise HTTPException(404)
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=2592000"})


@app.get("/api/map-config")
def map_config():
    """Tile URL for the browser map. The CARTO key is public by nature (it ships to the browser), so it is
    read from the environment here instead of being hard-coded in the frontend."""
    key = os.getenv("CARTO_API_KEY", "").strip()
    url = os.getenv("MAP_TILE_URL", "").strip() or "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
    if key:
        url = url.replace("{key}", key) if "{key}" in url else url + ("&" if "?" in url else "?") + "key=" + key
    return {"tiles": url}


app.mount("/", StaticFiles(directory=config.FRONTEND, html=True), name="frontend")
