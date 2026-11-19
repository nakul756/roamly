"""Itinerary builder. Stops and coordinates always come from the database, so the map is reliable.
Stops are grouped into days by proximity (nearest-neighbour path from the hotel), far-away sights become a
separate day trip, and every plan carries a budget breakdown and "know before you go" facts.
If a language model is configured, it writes the overview paragraph; otherwise a template is used."""
import math
import threading

from llm import llm

TRANSPORT_PER_LEG_EUR = 60      # rough per-person cost of an inter-city leg
DAY_TRIP_KM = 40                # sights farther than this from the city centre become a day trip
KIND_LABEL = {"sight": "sight", "museum": "museum", "food": "food", "market": "market", "nature": "nature",
              "view": "viewpoint", "beach": "beach", "park": "park", "nightlife": "evening"}


def km(a, b):
    """Distance in km between two (lat, lon) points."""
    (la1, lo1), (la2, lo2), p = a, b, math.pi / 180
    h = math.sin((la2 - la1) * p / 2) ** 2 + math.cos(la1 * p) * math.cos(la2 * p) * math.sin((lo2 - lo1) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


def _centre(stops):
    return (sum(s["lat"] for s in stops) / len(stops), sum(s["lon"] for s in stops) / len(stops))


def _order(stops, start):
    """Nearest-neighbour path through the stops, beginning at `start`."""
    left, path, here = list(stops), [], start
    while left:
        nxt = min(left, key=lambda s: km(here, (s["lat"], s["lon"])))
        left.remove(nxt)
        path.append(nxt)
        here = (nxt["lat"], nxt["lon"])
    return path


def _cluster(stops, k):
    """Groups stops into k geographic clusters of near-equal size (k-means with a size cap), so each day stays in one area."""
    pts = [(s["lat"], s["lon"]) for s in stops]
    cap = -(-len(stops) // k)                       # ceiling division: 8 stops over 3 days -> at most 3 per day
    cents = [pts[0]]
    while len(cents) < k:                           # farthest-first start gives well-spread initial centres
        cents.append(max(pts, key=lambda p: min(km(p, c) for c in cents)))
    groups = []
    for _ in range(15):
        groups = [[] for _ in range(k)]
        for i in sorted(range(len(pts)), key=lambda i: min(km(pts[i], c) for c in cents)):
            for j in sorted(range(k), key=lambda j: km(pts[i], cents[j])):
                if len(groups[j]) < cap:
                    groups[j].append(i)
                    break
        new = [(sum(pts[i][0] for i in g) / len(g), sum(pts[i][1] for i in g) / len(g)) if g else cents[j] for j, g in enumerate(groups)]
        if new == cents:
            break
        cents = new
    return [[stops[i] for i in g] for g in groups if g]


def _path_km(stops):
    return round(sum(km((a["lat"], a["lon"]), (b["lat"], b["lon"])) for a, b in zip(stops, stops[1:])), 1)


def _stop(s):
    return {"name": s["name"], "lat": s["lat"], "lon": s["lon"], "kind": s.get("kind", "sight")}


def _text(stops, food, first=False, hotel="", last=False, code="", flex=None):
    if not stops:
        t = f"Free day: {flex}, or revisit a favourite spot."
    elif len(stops) == 1:
        t = f"Take your time at {stops[0]['name']}."
    else:
        slots = ["Morning", "Afternoon", "Evening"]
        t = " ".join(f"{slots[i]}: {s['name']}." for i, s in enumerate(stops[:3]))
    t += f" Try {food}."
    if first:
        t = f"Check in at {hotel}. " + t
    if last:
        t += f" Fly home from {code} when you are ready."
    return t


_summaries, _summaries_lock = {}, threading.Lock()   # (destination, hotel, days) -> overview; only real model answers are kept
SUMMARY_CACHE_MAX = 500


def llm_summary(row, days, stops):
    key = (row["destination"], row["hotel_name"], days)
    with _summaries_lock:
        if key in _summaries:
            return _summaries[key]
    prompt = (f"Write a friendly overview of about 80 words for a {days}-day trip to {row['destination']}, {row['country']}. "
              f"Stay at {row['hotel_name']}. Mention only these places: {', '.join(s['name'] for s in stops)}. "
              f"Highlights: {row['highlights']}. Tip: {row['travel_tip']}. Do not invent other places, prices or facts.")
    text = llm("You write short, warm travel overviews in plain text.", [{"role": "user", "content": prompt}], 300, timeout=30)
    if text:   # a failure (None) is not cached, so the next request tries the model again
        with _summaries_lock:
            if len(_summaries) >= SUMMARY_CACHE_MAX:
                _summaries.pop(next(iter(_summaries)))   # oldest first
            _summaries[key] = text
    return text


def facts(row):
    return {"country": str(row["country"]), "currency": str(row["currency"]), "language": str(row["language"]),
            "airport_code": str(row["airport_code"]), "schengen": str(row["schengen"]), "getting_around": str(row["getting_around"]),
            "tip": str(row["travel_tip"]), "food": [f.strip() for f in str(row["must_try_food"]).split(";")],
            "best_months": [m for m in str(row["best_months"]).split(";")], "avg_temp_c": int(row["avg_temp_c"]),
            "crowd_level": str(row["crowd_level"]), "trip_type": str(row["trip_type"])}


def budget(row, days, travelers):
    rooms = math.ceil(travelers / 2)
    hotel = int(row["hotel_price_eur"]) * rooms * days
    food = int(row["daily_spend_eur"]) * travelers * days
    return {"hotel": hotel, "food_activities": food, "transport": 0, "total": hotel + food,
            "travelers": travelers, "rooms": rooms, "per_person": round((hotel + food) / travelers)}


def make_plan(row, days, stops, travelers=1, hotel_xy=None, with_summary=True, final=True):
    """One-city plan. `stops` are dicts with name, lat, lon, kind (best first)."""
    centre = _centre(stops)
    start = tuple(hotel_xy) if hotel_xy else centre
    far = [s for s in stops if km(centre, (s["lat"], s["lon"])) > DAY_TRIP_KM]
    local = [s for s in stops if s not in far]
    trip_slot = (days - 1 if days >= 4 else days) if far and days >= 2 else 0   # which day number is the day trip
    n_local = days - (1 if trip_slot else 0)
    local = local[:3 * n_local]
    groups = _cluster(local, min(n_local, len(local))) if local else []
    # visit the clusters nearest the hotel first, chaining from one cluster to the next; each day's stops are ordered from the hotel
    ordered, here, left = [], start, list(groups)
    while left:
        nxt = min(left, key=lambda g: km(here, _centre(g)))
        left.remove(nxt)
        ordered.append(_order(nxt, start))
        here = _centre(nxt)
    ordered += [[] for _ in range(n_local - len(ordered))]          # leftover days are free days
    foods = [f.strip() for f in str(row["must_try_food"]).split(";")]
    highlights = [h.strip() for h in str(row["highlights"]).split(";")]
    plan_days, k = [], 0
    for d in range(1, days + 1):
        if d == trip_slot:
            day_stops, daytrip = _order(far, centre)[:3], True
        else:
            day_stops, daytrip = ordered[k], False
            k += 1
        text = _text(day_stops, foods[(d - 1) % len(foods)], first=d == 1, hotel=row["hotel_name"], last=(d == days and days > 1 and final),
                     code=row["airport_code"], flex=highlights[(d - 1) % len(highlights)])
        if daytrip:
            text = "Day trip. " + text
        title = " & ".join(s["name"] for s in day_stops[:2]) if day_stops else "Free day"
        plan_days.append({"day": d, "title": title, "text": text, "stops": [_stop(s) for s in day_stops],
                          "km": _path_km(day_stops), "daytrip": daytrip})
    summary = llm_summary(row, days, stops) if with_summary else None
    source = "llm" if summary else "template"
    if not summary:
        summary = f"{days} days in {row['destination']}. {row['description']} Tip: {row['travel_tip']}."
    return {"destination": row["destination"], "hotel": row["hotel_name"], "summary": summary, "source": source, "days": plan_days,
            "center": [centre[0], centre[1]], "hotels": [{"name": row["hotel_name"], "lat": start[0], "lon": start[1], "city": row["destination"], "approx": True}] if hotel_xy else [],
            "budget": budget(row, days, travelers), "facts": facts(row), "legs": None}


def make_route(df, places, hotels, legs, travelers=1):
    """Plan for one or more cities. legs = [{destination, hotel, days}]. `places` maps city -> stop dicts,
    `hotels` maps (city, hotel) -> (lat, lon)."""
    ps, rows = [], []
    for l in legs:
        row = df[(df.destination == l["destination"]) & (df.hotel_name == l["hotel"])].iloc[0]
        rows.append(row)
        ps.append(make_plan(row, l["days"], places[l["destination"]], travelers, hotels.get((l["destination"], l["hotel"])),
                            with_summary=len(legs) == 1, final=len(ps) == len(legs) - 1))
    if len(legs) == 1:
        ps[0]["legs"] = legs
        return ps[0]
    days = []
    for j, (p, l) in enumerate(zip(ps, legs)):
        for k, d in enumerate(p["days"]):
            days.append({**d, "day": len(days) + 1, "city": l["destination"],
                         "text": ("Travel to " + l["destination"] + ". " if j and not k else "") + d["text"]})
    b = {k: sum(p["budget"][k] for p in ps) for k in ("hotel", "food_activities")}
    b["transport"] = TRANSPORT_PER_LEG_EUR * travelers * (len(legs) - 1)
    b["total"] = b["hotel"] + b["food_activities"] + b["transport"]
    b.update(travelers=travelers, rooms=ps[0]["budget"]["rooms"], per_person=round(b["total"] / travelers))
    c = [p["center"] for p in ps]
    names = " → ".join(l["destination"] for l in legs)
    return {"destination": names, "hotel": legs[0]["hotel"], "source": "template", "days": days, "budget": b,
            "summary": f"{len(days)} days across {len(legs)} cities: " + "; ".join(f"{l['days']} days in {l['destination']}" for l in legs) + ". Inter-city transport is a rough estimate.",
            "center": [sum(x[0] for x in c) / len(c), sum(x[1] for x in c) / len(c)], "hotels": [h for p in ps for h in p["hotels"]],
            "facts": ps[0]["facts"], "legs": legs, "city_facts": {l["destination"]: p["facts"] for l, p in zip(legs, ps)}}
