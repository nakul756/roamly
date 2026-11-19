"""Chatbot: trained intent classifier + slot extraction + persistent memory (SQLite) + the trained ranker."""
import json
import math
import re

import numpy as np

import intent
import ranker
from config import DB_DIR
from db import SafeCon
from llm import llm, mode_name
from plan import km, make_route
from rag import Retriever

DB = DB_DIR / "chat.db"
SLOT_KEYS = ("trip_type", "month", "days", "budget", "max_budget_eur", "travelers", "group", "activity", "avoid_crowds")
MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]
TYPES = {"beach": ["beach", "sea", "sun", "island", "swim"], "city": ["city", "urban", "shopping", "nightlife"],
         "culture": ["culture", "cultural", "history", "historic", "museum", "museums"], "mountain": ["mountain", "mountains", "ski", "skiing", "alps", "snow"],
         "nature": ["nature", "northern lights", "aurora", "glacier", "glaciers", "wildlife"], "romantic": ["romantic", "romance", "honeymoon", "anniversary"]}
BUDGET = {1: ["cheap", "backpack", "hostel", "affordable", "low cost", "on a budget", "budget-friendly"],
          3: ["luxury", "luxurious", "5-star", "five star", "splurge", "fancy"], 2: ["mid-range", "midrange", "moderate", "mid range"]}
SEASONS = {"summer": 7, "winter": 1, "spring": 4, "autumn": 10, "fall": 10, "christmas": 12}
GROUPS = {"solo": ["solo", "alone", "by myself", "on my own"], "couples": ["couple", "girlfriend", "boyfriend", "wife", "husband", "partner", "honeymoon"],
          "families": ["family", "kids", "children"], "friends": ["friends", "buddies"]}
BUDGET_NAME = {1: "budget", 2: "mid-range", 3: "luxury"}
AED_PER_EUR = 4.3   # approximate exchange rate
USD_PER_EUR = 1.17  # approximate, consistent with the AED rate (AED is pegged at 3.67 per dollar)
ASK = {"trip_type": "What kind of trip do you want: beach, city, culture, mountain, nature or romantic?",
       "month": "Which month are you travelling?", "days": "How many days will you stay?",
       "max_budget_eur": "What is your total budget for the trip, for everyone? For example '2000 euros' or '8000 AED', or say 'no limit'."}
INFO = [
 (["best time", "when to go", "when should", "best month", "when is the best"], lambda r: f"the best months are {r['best_months'].replace(';', ', ')}."),
 (["things to do", "to do in", "highlight", "attraction", "sights", "what to see", "see in"], lambda r: f"top things to do: {r['highlights'].replace(';', ', ')}."),
 (["weather", "temperature", "warm", "cold"], lambda r: f"around {r['avg_temp_c']}°C in the best season ({r['best_months'].replace(';', ', ')})."),
 (["food", "eat", "dish", "cuisine"], lambda r: f"try {r['must_try_food'].replace(';', ', ')}."),
 (["language", "speak"], lambda r: f"people speak {r['language']}."),
 (["currency", "money", "pay"], lambda r: f"the currency is {r['currency']}."),
 (["airport", "fly"], lambda r: f"the main airport code is {r['airport_code']}."),
 (["visa", "schengen"], lambda r: f"Schengen area: {r['schengen']}. Visa rules depend on your passport, so check official sources."),
 (["around", "transport", "metro"], lambda r: f"getting around: {r['getting_around']}."),
 (["crowd", "busy", "quiet"], lambda r: f"crowds are usually {r['crowd_level']}."),
 (["expensive", "cost", "price", "cheap"], lambda r: f"roughly €{r['daily_spend_eur']} a day for food and activities, plus hotels from about €{r['hotel_price_eur']} a night (estimates)."),
 (["tip", "advice"], lambda r: f"{r['travel_tip']}."),
]


def parse(text, dests):
    """Pull trip details out of free text."""
    t, s = text.lower(), {}
    has = lambda words: any(re.search(r"(?<!\w)" + re.escape(w) + r"(?!\w)", t) for w in words)
    for k, w in TYPES.items():
        if has(w): s["trip_type"] = k
    for k, w in BUDGET.items():
        if has(w): s["budget"] = k
    cur = r"(?:€|\$|eur|euros?|aed|dirhams?|usd|dollars?)"
    m = re.search(rf"({cur})\s*(\d[\d,]*)|(\d[\d,]*)\s*({cur})", t) or re.search(r"(?:under|below|max(?:imum)?|around|budget(?: of| is)?|up to)\s*(\d[\d,]*)(?!\s*(?:days?|nights?|weeks?|people|persons|travell?ers|adults|of us))", t)
    if m:
        g = [x for x in m.groups() if x]
        v = int(next(x for x in g if x[0].isdigit()).replace(",", ""))
        rate = AED_PER_EUR if any(x.startswith(("aed", "dirham")) for x in g) else USD_PER_EUR if any(x == "$" or x.startswith(("usd", "dollar")) for x in g) else 1
        s["max_budget_eur"] = round(v / rate)
    if re.search(r"no (budget )?limit|unlimited|flexible budget|money is no object|doesn.t matter", t): s["max_budget_eur"] = 0
    for i, n in enumerate(MONTHS):
        pat = r"\b(in|during|for|early|late|mid|of)\s+may\b" if n == "may" else rf"\b{n}\b"
        if re.search(pat, t) or (n not in ("may", "june", "july") and re.search(rf"\b{n[:3]}\b", t)): s["month"] = i + 1
    for k, v in SEASONS.items():
        if has([k]) and "month" not in s: s["month"] = v
    m = re.search(r"(\d+)\s*-?\s*(?:days?|nights?)", t)
    if m: s["days"] = max(1, min(21, int(m.group(1))))
    elif "weekend" in t: s["days"] = 3
    elif "two weeks" in t or "fortnight" in t: s["days"] = 14
    elif re.search(r"\b(a|one)\s+week\b", t): s["days"] = 7
    elif (m := re.search(r"(\d+)\s*-?\s*weeks?\b", t)): s["days"] = max(1, min(21, int(m.group(1)) * 7))
    m = re.search(r"(\d+)\s*(?:people|persons|travell?ers|adults|of us|guests)", t) or re.search(r"(?:family|group) of (\d+)", t)
    if m: s["travelers"] = int(m.group(1))
    for k, w in GROUPS.items():
        if has(w): s["group"] = k
    if s.get("group") == "solo": s["travelers"] = 1
    if s.get("group") == "couples": s.setdefault("travelers", 2)
    if has(["relax", "relaxed", "chill", "easy", "slow"]): s["activity"] = 1
    if has(["active", "adventure", "adventurous", "hike", "hiking"]): s["activity"] = 3
    if re.search(r"avoid(ing)? crowds|not crowded|less crowded|quiet|off the beaten", t): s["avoid_crowds"] = True
    for d in dests:
        if d.lower() in t: s["focus"] = d
    return s


def pretty(st):
    p = []
    if "trip_type" in st: p.append(f"{st['trip_type']} trip")
    if "month" in st: p.append(MONTHS[st["month"] - 1].capitalize())
    if "days" in st: p.append(f"{st['days']} days")
    if "budget" in st: p.append(BUDGET_NAME[st["budget"]] + " stays")
    if "travelers" in st: p.append("1 traveller" if st["travelers"] == 1 else f"{st['travelers']} travellers")
    if "group" in st: p.append(st["group"])
    if "activity" in st: p.append("relaxed pace" if st["activity"] == 1 else "active pace")
    if st.get("avoid_crowds"): p.append("avoid crowds")
    if "max_budget_eur" in st: p.append(f"total budget €{st['max_budget_eur']}" if st["max_budget_eur"] else "no budget limit")
    if "focus" in st: p.append(f"interested in {st['focus']}")
    return p


SYSTEM_PARSE = """You are the planning brain of a Europe travel assistant. Read the conversation and the user's latest message.
Return ONLY a JSON object: {"slots": {...}, "action": "...", "destination": null}
slots (include only what the user stated or changed in the latest message): trip_type (beach|city|culture|mountain|nature|romantic), month (1-12), days (1-21), budget (1=budget, 2=mid-range, 3=luxury), max_budget_eur (total budget for everyone in euros; convert AED at 4.3 AED per euro and USD at 1.17 USD per euro; 0 if the user says there is no limit), travelers (number), group (solo|couples|families|friends), activity (1=relaxed, 3=active), avoid_crowds (true/false).
action: "recommend" (wants destination suggestions or changes trip details), "plan" (wants an itinerary), "info" (asks about one destination), "forget" (reset everything), or "chat" (small talk, general travel questions, anything else).
destination: one of [DESTS] if the user means one, else null."""

SYSTEM_WRITE = """You are a friendly, concise Europe travel assistant chatting with a user (about 120 words at most, plain text, no tables).
Use ONLY the DATA given for destinations, hotels, prices and costs, and say costs are estimates. Never invent hotels, prices or places. If DATA has retrieved_passages, answer open questions from them and name the destinations they come from; if they don't cover the question, say so. For general travel advice you may use common knowledge, briefly and hedged.
If DATA lists missing_details, ask for ONE of them naturally. If DATA has recommendations, present them conversationally and say why each fits. If DATA has a plan, summarise it and mention the map. Refer back to what the user said earlier. Stay on travel topics."""


def clean(s):
    """Validate slots returned by the language model."""
    s, out = (s if isinstance(s, dict) else {}), {}
    if s.get("trip_type") in TYPES: out["trip_type"] = s["trip_type"]
    for k, lo, hi in (("month", 1, 12), ("days", 1, 21), ("budget", 1, 3), ("travelers", 1, 20), ("max_budget_eur", 0, 1000000), ("activity", 1, 3)):
        try:
            v = int(s[k])
            if lo <= v <= hi: out[k] = v
        except (KeyError, TypeError, ValueError):
            pass
    if out.get("activity") == 2: out.pop("activity")
    if s.get("group") in GROUPS: out["group"] = s["group"]
    if isinstance(s.get("avoid_crowds"), bool): out["avoid_crowds"] = s["avoid_crowds"]
    return out


class Chat:
    def __init__(self, df, places_df, bundle, hotels_df=None):
        self.df, self.bundle = df, bundle
        self.hotels = {(r.destination, r.hotel_name): (r.lat, r.lon) for r in hotels_df.itertuples()} if hotels_df is not None else {}
        self.dests = sorted(df["destination"].unique())
        self.places = {d: g.to_dict("records") for d, g in places_df.groupby("destination")}
        self.cent = {d: (sum(p['lat'] for p in g) / len(g), sum(p['lon'] for p in g) / len(g)) for d, g in self.places.items()}
        self.rag = Retriever(df, places_df)
        DB.parent.mkdir(exist_ok=True)
        self.con = SafeCon(DB)
        self.con.execute("CREATE TABLE IF NOT EXISTS sessions (sid TEXT PRIMARY KEY, state TEXT, history TEXT)")
        intent.predict("hello")   # loads (or trains) the intent model at startup

    def load(self, sid):
        r = self.con.execute("SELECT state, history FROM sessions WHERE sid=?", (sid,)).fetchone()
        return (json.loads(r[0]), json.loads(r[1])) if r else ({}, [])

    def public(self, st):
        return {k: st[k] for k in SLOT_KEYS if k in st}

    def snapshot(self, sid):
        st, hist = self.load(sid)
        return {"history": hist, "memory": pretty(st), "slots": self.public(st)}

    def set_slots(self, sid, slots):
        """Guided mode writes its choices here so chat and guided share one memory."""
        st, hist = self.load(sid)
        new = clean(slots)
        for k in SLOT_KEYS:
            if k in new:
                st[k] = new[k]
            else:
                st.pop(k, None)
        self.con.execute("INSERT OR REPLACE INTO sessions VALUES (?,?,?)", (sid, json.dumps(st), json.dumps(hist)))
        return {"memory": pretty(st), "slots": self.public(st)}

    def reset(self, sid):
        self.con.execute("DELETE FROM sessions WHERE sid=?", (sid,))

    def clean_slots(self, slots):
        return clean(slots)

    def route(self, legs, travelers=1):
        return make_route(self.df, self.places, self.hotels, legs, travelers)

    def _extra(self, i, st):
        r = self.df.iloc[i]
        months = str(r["best_months"]).split(";")
        return {"country": str(r["country"]), "description": str(r["description"]), "highlights": str(r["highlights"]).replace(";", ", "),
                "tip": str(r["travel_tip"]), "airport": str(r["airport_code"]), "hotel_price": int(r["hotel_price_eur"]),
                "in_season": bool(ranker.MONTHS[st["month"] - 1] in months), "best_months": [ranker.MONTHS.index(m) + 1 for m in months]}

    def tier(self, st):
        """Budget level from the budget amount (per person per day), unless the user named one."""
        if "budget" in st: return st["budget"]
        mx = st.get("max_budget_eur")
        if not mx: return 2
        per = mx / (st.get("travelers", 1) * st["days"])
        return 1 if per < 110 else 2 if per < 260 else 3

    def ranked(self, st):
        """Every destination/hotel row that fits the trip, best first: list of (row index, score). A city can appear
        more than once (one row per hotel tier), so recommend() can pick the best row it can afford."""
        d = self.df
        sc = ranker.score(self.bundle, st["trip_type"], self.tier(st), st["month"], st["days"], d).astype(float)
        if "group" in st: sc += 0.08 * d["best_for"].str.contains(st["group"]).to_numpy()
        if "activity" in st: sc += 0.05 * (d["activity_level"].to_numpy() == st["activity"])
        if st.get("avoid_crowds"): sc -= 0.15 * (d["crowd_level"].to_numpy() == "high")
        return [(int(i), float(sc[i])) for i in np.argsort(-sc) if sc[i] >= 0.3]

    def cost(self, i, days, n):
        r = self.df.iloc[i]
        return int((r["hotel_price_eur"] * math.ceil(n / 2) + r["daily_spend_eur"] * n) * days)

    def recommend(self, st, limit=3):
        """One city for trips up to 5 days; a multi-city route (2-3 nearby cities) for longer trips. Respects the budget."""
        st["routes"] = {}
        n, days, mx = st.get("travelers", 1), st["days"], st.get("max_budget_eur")
        label = lambda s: "great" if s >= 0.8 else "good" if s >= 0.5 else "possible"
        ctx = {"trip_type": st["trip_type"], "budget": self.tier(st), "month": st["month"], "days": days, "travelers": n}
        ranked, out = self.ranked(st), []
        if days > 5:
            for i0, s0 in ranked[:max(24, limit * 8)]:
                r0 = self.df.iloc[i0]
                if r0["destination"] in st["routes"]: continue
                legs, here = [(i0, s0)], r0["destination"]
                for _ in range(1 if days <= 8 else 2):
                    used = [x[0] for x in legs]
                    near = [(i, s) for i, s in ranked if i not in used and km(self.cent[here], self.cent[self.df.iloc[i]["destination"]]) <= 900
                            and self.df.iloc[i]["destination"] not in [self.df.iloc[u]["destination"] for u in used]]
                    if not near: break
                    legs.append(near[0])
                    here = self.df.iloc[near[0][0]]["destination"]
                k = len(legs)
                split = [days // k + (1 if j < days % k else 0) for j in range(k)]
                total = sum(self.cost(i, dd, n) for (i, _), dd in zip(legs, split)) + 60 * n * (k - 1)   # 60 EUR per person per leg: rough estimate
                if mx and total > mx: continue
                lg = [{"destination": self.df.iloc[i]["destination"], "hotel": self.df.iloc[i]["hotel_name"], "days": dd} for (i, _), dd in zip(legs, split)]
                st["routes"][r0["destination"]] = lg
                avg = sum(s for _, s in legs) / k
                out.append({"destination": r0["destination"], "trip_type": r0["trip_type"], "days": days, "hotel": r0["hotel_name"], "total_eur": total,
                            "fit": label(avg), "match_pct": min(100, round(avg * 100)), "legs": lg, "ctx": ctx, **self._extra(i0, st),
                            "route": " → ".join(f"{l['destination']} {l['days']}d" for l in lg)})
                if len(out) == limit: break
            return out
        seen = set()
        for i, s in ranked:
            r = self.df.iloc[i]
            total = self.cost(i, days, n)
            if (mx and total > mx) or r["destination"] in seen: continue
            seen.add(r["destination"])
            lg = [{"destination": r["destination"], "hotel": r["hotel_name"], "days": days}]
            out.append({"destination": r["destination"], "trip_type": r["trip_type"], "days": days, "hotel": r["hotel_name"], "total_eur": total,
                        "fit": label(s), "match_pct": min(100, round(s * 100)), "legs": lg, "ctx": ctx, "route": None, **self._extra(i, st)})
            if len(out) == limit: break
        return out

    def over_budget(self, st):
        """Nothing of the chosen type fits the budget. Returns (alternatives in budget, cheapest option of the chosen type or None).
        Alternatives are the best in-budget pick for each OTHER trip type, best fit first."""
        mx, t = st["max_budget_eur"], st["trip_type"]
        # recommend() fills st["routes"] on the copy it is given, so keep each copy's routes and merge the ones we offer into st
        sub = {**st, "max_budget_eur": 0}
        pricey = self.recommend(sub, limit=12)
        cheapest = min(pricey, key=lambda r: r["total_eur"]) if pricey else None
        routes = {cheapest["destination"]: sub["routes"][cheapest["destination"]]} if cheapest and cheapest["destination"] in sub["routes"] else {}
        alts, alt_routes = [], {}
        for other in TYPES:
            if other != t:
                sub = {**st, "trip_type": other}
                got = self.recommend(sub, limit=1)
                if got:
                    alts.append(got[0])
                    alt_routes[got[0]["destination"]] = sub["routes"].get(got[0]["destination"])
        alts.sort(key=lambda r: -r["match_pct"])
        alts = alts[:3]
        for r in alts:   # the alternatives win a name clash: they are what is listed first and what "plan" defaults to
            if alt_routes.get(r["destination"]): routes[r["destination"]] = alt_routes[r["destination"]]
        st.setdefault("routes", {}).update(routes)
        return alts, cheapest

    def over_budget_text(self, st, alts, cheapest):
        t, mx = st["trip_type"], st["max_budget_eur"]
        text = f"A {t} trip of {st['days']} days is more than €{mx} here."
        if alts:
            text += " Within your budget I'd look at:\n" + "\n".join(
                f"{i}. {r['route'] or r['destination'] + ', staying at ' + r['hotel']} ({r['trip_type']}): about €{r['total_eur']} in total" for i, r in enumerate(alts, 1))
        if cheapest:
            text += (f"\nOr keep {t}: the cheapest I have is {cheapest['route'] or cheapest['destination']} at about €{cheapest['total_eur']}. "
                     f"Want me to use a budget of €{cheapest['total_eur']} instead, or fewer days?")
        return text

    def trip(self, st):
        for k in ("trip_type", "month", "days", "max_budget_eur"):
            if k not in st:
                known = pretty(st)
                return ("Got it: " + ", ".join(known) + ". " if known else "") + ASK[k], None
        res, note = self.recommend(st), ""
        if not res and st.get("max_budget_eur"):   # nothing fits: offer other styles in budget, or the same style for more money
            alts, cheapest = self.over_budget(st)
            if alts or cheapest:
                if alts: st["last_top"] = alts[0]["destination"]; st["hotels"] = {r["destination"]: r["hotel"] for r in alts}
                return self.over_budget_text(st, alts, cheapest), alts or None
        if not res:
            return "Nothing in my list fits that month and trip type yet. Try another month, or tell me a different kind of trip.", None
        st.pop("focus", None); st["last_top"] = res[0]["destination"]; st["hotels"] = {r["destination"]: r["hotel"] for r in res}
        who = f" for {st['travelers']} travellers" if st.get("travelers", 1) > 1 else ""
        lines = [f"{i}. {r['route'] or r['destination'] + ', staying at ' + r['hotel']}: about €{r['total_eur']} in total{who}, {r['fit']} fit" for i, r in enumerate(res, 1)]
        return (f"Here are my top picks for {', '.join(pretty(st))}{note}:\n" + "\n".join(lines) +
                "\nSay 'plan " + res[0]["destination"] + "' for a day-by-day itinerary, or tell me what to change."), res

    def info(self, msg, dest):
        if not dest: return "Which destination do you mean? I know " + ", ".join(self.dests) + "."
        r, t = self.df[self.df.destination == dest].iloc[0], msg.lower()
        for words, fn in INFO:
            if any(re.search(r"\b" + w, t) for w in words): return f"{dest}: " + fn(r)
        return f"{dest}: {r['description']} Tip: {r['travel_tip']}."

    def plan(self, st):
        dest = st.get("focus") or st.get("last_top")
        if not dest: return "Which destination should I plan? Tell me a trip type and month first, or name a place.", None
        n = st.get("travelers", 1)
        legs = st.get("routes", {}).get(dest)
        if legs:   # multi-city route
            plan = self.route(legs, n)
            return f"Here is a {len(plan['days'])}-day route: {plan['destination']}. The stops are on the map.", plan
        rows = self.df[self.df.destination == dest]
        hotel = st.get("hotels", {}).get(dest)
        row = rows[rows.hotel_name == hotel].iloc[0] if hotel and (rows.hotel_name == hotel).any() else rows.iloc[int((rows.budget_level - self.tier(st) if "days" in st else rows.budget_level - st.get("budget", 2)).abs().argmin())]
        days = st.get("days", 3)
        plan = self.route([{"destination": dest, "hotel": row["hotel_name"], "days": days}], n)
        return f"Here is a {days}-day plan for {dest}. The stops are on the map.", plan

    def reply_rules(self, sid, msg):
        st, hist = self.load(sid)
        it, _ = intent.predict(msg)
        slots = parse(msg, self.dests)
        focus = slots.pop("focus", None)
        known_dest = focus or st.get("focus") or st.get("last_top")
        if slots and it in ("greet", "thanks", "fallback"): it = "trip"
        if it == "plan" and slots and not known_dest: it = "trip"
        if it == "trip" and focus and not slots: it = "info"
        if it == "forget": st = {}
        else:
            st.update(slots)
            if focus: st["focus"] = focus
        res = plan = None
        if it == "forget": text = "Okay, I cleared everything. Where would you like to go next?"
        elif it == "memory": text = ("Here is what I remember: " + ", ".join(pretty(st)) + ".") if pretty(st) else "I don't know anything about your trip yet. Tell me what you're after."
        elif it == "info": text = self.info(msg, focus or st.get("focus") or st.get("last_top"))
        elif it == "plan": text, plan = self.plan(st)
        elif it == "trip": text, res = self.trip(st)
        elif it == "greet": text = "Hi! I'm your Europe trip assistant. Tell me what you're after, for example: 'a relaxed beach trip in June for 5 days'."
        elif it == "thanks": text = "You're welcome! Ask me anything else about your trip."
        else: text = "I didn't quite get that. Tell me a trip type, month and number of days, or ask about a place (food, weather, language...)."
        hist = (hist + [{"role": "user", "text": msg}, {"role": "bot", "text": text}])[-30:]
        self.con.execute("INSERT OR REPLACE INTO sessions VALUES (?,?,?)", (sid, json.dumps(st), json.dumps(hist)))
        self.con.commit()
        return {"reply": text, "results": res, "plan": plan, "memory": pretty(st), "slots": self.public(st), "intent": it}

    def mode(self):
        return mode_name()

    def reply(self, sid, msg):
        if self.mode().startswith("rule"):
            return self.reply_rules(sid, msg)
        return self.reply_llm(sid, msg) or self.reply_rules(sid, msg)   # falls back if the model is down

    def reply_llm(self, sid, msg):
        """The language model reads the conversation, we run our trained models for facts, then it writes the reply."""
        st, hist = self.load(sid)
        ctx = [{"role": "user" if h["role"] == "user" else "assistant", "content": h["text"]} for h in hist[-10:]]
        memory = {k: v for k, v in st.items() if k != "hotels"}
        raw = llm(SYSTEM_PARSE.replace("[DESTS]", ", ".join(self.dests)) + "\nCurrent memory: " + json.dumps(memory),
                  ctx + [{"role": "user", "content": msg}], 300, json_mode=True, temperature=0)
        try:
            j = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
        except Exception:
            return None
        action = j.get("action") if j.get("action") in ("recommend", "plan", "info", "forget", "chat") else "chat"
        dest = j.get("destination") if j.get("destination") in self.dests else None
        if action == "forget":
            st = {}
        else:
            st.update(clean(j.get("slots")))
            if dest: st["focus"] = dest
        data, res, plan = {"user_preferences": pretty(st)}, None, None
        if action == "recommend":
            missing = [k for k in ("trip_type", "month", "days", "max_budget_eur") if k not in st]
            if missing:
                data["missing_details"] = missing
                action = "chat"
            else:
                res = self.recommend(st)
                st.pop("focus", None)
                if not res and st.get("max_budget_eur"):
                    alts, cheapest = self.over_budget(st)
                    res = alts
                    data["note_budget"] = "the chosen trip type does not fit the budget; offer the in_budget_alternatives (other trip types) and ask if they want the same type at the higher cheapest_same_type cost or fewer days"
                    data["in_budget_alternatives"] = [{k: r[k] for k in ("destination", "trip_type", "route", "hotel", "total_eur")} for r in alts]
                    data["cheapest_same_type"] = {k: cheapest[k] for k in ("destination", "route", "total_eur")} if cheapest else None
                if res:
                    st["last_top"], st["hotels"] = res[0]["destination"], {r["destination"]: r["hotel"] for r in res}
                data["recommendations"] = [{k: r[k] for k in ("destination", "route", "days", "hotel", "total_eur", "fit")} for r in res] if res else "no match found"
                data["note"] = "costs are rough estimates; multi-city totals include a rough inter-city transport estimate"
        elif action == "plan":
            text, plan = self.plan(st)
            data["plan"] = {"destination": plan["destination"], "hotel": plan["hotel"], "days": [d["text"] for d in plan["days"]]} if plan else text
        if action in ("chat", "info", "recommend"):   # RAG: ground open questions in the closest dataset passages
            hits = self.rag.search(msg, k=4, destination=(dest or st.get("focus")) if action == "info" else None)
            if hits:
                data["retrieved_passages"] = [{"destination": h["destination"], "text": h["text"]} for h in hits]
        if action == "info":
            d = dest or st.get("focus") or st.get("last_top")
            if d:
                r = self.df[self.df.destination == d].iloc[0]
                data["facts"] = {"destination": d, **{k: str(r[k]) for k in ("description", "best_months", "avg_temp_c", "crowd_level", "must_try_food", "language", "currency", "airport_code", "schengen", "getting_around", "travel_tip", "daily_spend_eur")}}
        sources = [{"destination": p["destination"], "text": p["text"]} for p in data.get("retrieved_passages", [])]
        text = llm(SYSTEM_WRITE, ctx + [{"role": "user", "content": msg + "\n\nDATA: " + json.dumps(data, ensure_ascii=False, default=str)}], 500)
        if not text:
            return None
        hist = (hist + [{"role": "user", "text": msg}, {"role": "bot", "text": text}])[-30:]
        self.con.execute("INSERT OR REPLACE INTO sessions VALUES (?,?,?)", (sid, json.dumps(st), json.dumps(hist)))
        self.con.commit()
        return {"reply": text, "results": res, "plan": plan, "memory": pretty(st), "slots": self.public(st), "intent": action, "sources": sources}
