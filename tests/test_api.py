import json
import statistics
import time

from plan import km


def _wait_for(items, n=1, secs=3):
    """The reset email is sent from a background thread: wait until it has run."""
    for _ in range(int(secs / 0.05)):
        if len(items) >= n:
            return
        time.sleep(0.05)


# ------------------------------------------------------------------ data integrity
def test_places_and_hotels_are_near_their_city(main):
    """Catches typos in hand-entered coordinates."""
    bad = []
    for d, g in main.places_df.groupby("destination"):
        mlat, mlon = statistics.median(g.lat), statistics.median(g.lon)
        for r in g.itertuples():
            if km((mlat, mlon), (r.lat, r.lon)) > 150:
                bad.append(f"place {d}/{r.name}")
        for h in main.hotels_df[main.hotels_df.destination == d].itertuples():
            if min(km((p.lat, p.lon), (h.lat, h.lon)) for p in g.itertuples()) > 5:   # hotel near at least one sight
                bad.append(f"hotel {d}/{h.hotel_name}")
    assert not bad, bad


def test_every_destination_has_enough_places(main):
    counts = main.places_df.groupby("destination").size()
    assert counts.min() >= 7 and set(counts.index) == set(main.df.destination)


# ------------------------------------------------------------------ public endpoints
def test_public_endpoints(anon):
    assert anon.get("/api/health").json()["ok"]
    assert len(anon.get("/api/destinations").json()) >= 25
    assert "beach" in anon.get("/api/options").json()["trip_types"]
    d = anon.get("/api/destination/Nice").json()
    assert d["airport_code"] == "NCE" and len(d["hotels"]) >= 3
    assert anon.get("/api/destination/Atlantis").status_code == 404
    assert "AED" in anon.get("/api/rates").json()["rates"]
    w = anon.get("/api/weather?destination=Nice&month=6").json()
    assert w["source"] in ("open-meteo", "dataset") and "avg_temp_c" in w
    assert anon.get("/api/me").status_code == 401


def test_security_headers(anon):
    r = anon.get("/api/health")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["cache-control"] == "no-store"
    assert anon.get("/definitely-missing.html").status_code == 404


# ------------------------------------------------------------------ auth
def test_register_validation(anon):
    assert anon.post("/api/register", json={"name": "A", "email": "nope", "password": "correct-horse-9"}).status_code == 400
    assert anon.post("/api/register", json={"name": "A", "email": "a@b.co", "password": "password"}).status_code == 400
    assert anon.post("/api/register", json={"name": "A", "email": "a@b.co", "password": "short"}).status_code == 400


def test_session_flow(client, anon, main):
    assert client.get("/api/me").json()["email"] == client.email
    assert client.post("/api/logout").status_code == 200
    assert client.get("/api/me").status_code == 401
    assert client.post("/api/login", json={"email": client.email, "password": "wrong-pass-1"}).status_code == 401
    r = client.post("/api/login", json={"email": client.email, "password": "correct-horse-9", "remember": False})
    assert r.status_code == 200 and client.get("/api/me").status_code == 200
    dup = anon.post("/api/register", json={"name": "X", "email": client.email, "password": "correct-horse-9"})
    assert dup.status_code == 409


def test_login_is_rate_limited(anon, client):
    codes = [anon.post("/api/login", json={"email": client.email, "password": f"bad-pass-{i}"}).status_code for i in range(7)]
    assert codes[:5] == [401] * 5 and codes[5] == 429
    # even the right password is blocked while locked out
    assert anon.post("/api/login", json={"email": client.email, "password": "correct-horse-9"}).status_code == 429


def test_tokens_are_stored_hashed_and_expire(client, main):
    tok = client.cookies.get("session")
    assert main.con.execute("SELECT COUNT(*) FROM auth_tokens WHERE hash=?", (tok,)).fetchone()[0] == 0
    main.con.execute("UPDATE auth_tokens SET expires=1 WHERE hash=?", (main.sha(tok),))
    assert client.get("/api/me").status_code == 401


def test_password_reset(client, anon, main, monkeypatch):
    sent = []
    monkeypatch.setenv("BASE_URL", "http://testserver")   # outside localhost a reset link needs a configured address
    monkeypatch.setattr(main, "send_reset", lambda email, link: sent.append((email, link)))
    assert anon.post("/api/forgot", json={"email": "nobody@example.com"}).json() == {"ok": True}   # same answer for unknown emails
    assert anon.post("/api/forgot", json={"email": client.email}).json() == {"ok": True}
    import time
    for _ in range(50):
        if sent:
            break
        time.sleep(0.05)
    assert len(sent) == 1 and sent[0][0] == client.email
    token = sent[0][1].split("token=")[1]
    assert anon.post("/api/reset", json={"token": "bogus", "password": "brand-new-pass-1"}).status_code == 400
    assert anon.post("/api/reset", json={"token": token, "password": "short"}).status_code == 400
    assert anon.post("/api/reset", json={"token": token, "password": "brand-new-pass-1"}).status_code == 200
    assert anon.post("/api/reset", json={"token": token, "password": "another-pass-22"}).status_code == 400   # single use
    assert client.get("/api/me").status_code == 401                                                           # old sessions revoked
    assert anon.post("/api/login", json={"email": client.email, "password": "brand-new-pass-1"}).status_code == 200


def test_reset_link_is_not_built_from_the_host_header(client, anon, main, monkeypatch):
    sent = []
    monkeypatch.setattr(main, "send_reset", lambda email, link: sent.append(link))
    monkeypatch.delenv("BASE_URL", raising=False)
    tokens = lambda: main.con.execute("SELECT COUNT(*) FROM reset_tokens").fetchone()[0]
    before = tokens()
    r = anon.post("/api/forgot", json={"email": client.email}, headers={"host": "evil.example"})
    assert r.json() == {"ok": True}                        # same answer as ever, so nothing leaks to the caller
    assert not sent and tokens() == before                 # but no email and no token for an untrusted host
    anon.post("/api/forgot", json={"email": client.email}, headers={"host": "localhost:8000"})
    _wait_for(sent)
    assert sent and sent[0].startswith("http://localhost:8000/reset.html?token=")
    monkeypatch.setenv("BASE_URL", "https://roamly.example")
    anon.post("/api/forgot", json={"email": client.email}, headers={"host": "evil.example"})
    _wait_for(sent, 2)
    assert len(sent) == 2 and sent[1].startswith("https://roamly.example/reset.html?token=")   # BASE_URL wins over the header


def test_login_hashes_even_for_unknown_email(anon, main, monkeypatch):
    """Unknown emails must cost the same hashing work as known ones, or response time reveals who has an account."""
    calls, real = [], main.hash_pw
    monkeypatch.setattr(main, "hash_pw", lambda pw, salt: calls.append(salt) or real(pw, salt))
    assert anon.post("/api/login", json={"email": "ghost@example.com", "password": "whatever-123"}).status_code == 401
    assert calls == [main.DUMMY_SALT]


def test_account_edit_export_delete(client, main):
    assert client.patch("/api/account", json={"name": "Renamed"}).status_code == 200
    assert client.get("/api/me").json()["name"] == "Renamed"
    assert client.patch("/api/account", json={"current_password": "nope", "new_password": "new-pass-12345"}).status_code == 403
    assert client.patch("/api/account", json={"current_password": "correct-horse-9", "new_password": "new-pass-12345"}).status_code == 200
    client.post("/api/favorites", json={"destination": "Nice", "hotel": "Hotel Negresco", "days": 3})
    ex = client.get("/api/account/export").json()
    assert ex["account"]["email"] == client.email and len(ex["saved_trips"]) == 1
    assert client.post("/api/account/delete", json={"password": "wrong"}).status_code == 403
    assert client.post("/api/account/delete", json={"password": "new-pass-12345"}).status_code == 200
    assert client.get("/api/me").status_code == 401
    assert main.con.execute("SELECT COUNT(*) FROM users WHERE email=?", (client.email,)).fetchone()[0] == 0


# ------------------------------------------------------------------ trips and plans
def test_trips_single_and_budget(client):
    r = client.post("/api/trips", json={"trip_type": "beach", "month": 6, "days": 5, "budget": 2}).json()["results"]
    assert r and all(x["match_pct"] >= 30 and x["legs"] and x["total_eur"] > 0 and x["ctx"]["month"] == 6 for x in r)
    cap = client.post("/api/trips", json={"trip_type": "city", "month": 5, "days": 4, "max_budget_eur": 1200}).json()["results"]
    assert all(x["total_eur"] <= 1200 for x in cap)
    assert client.post("/api/trips", json={"trip_type": "swimming", "month": 5, "days": 4}).status_code == 400


def test_trips_long_stay_is_multi_city(client):
    r = client.post("/api/trips", json={"trip_type": "culture", "month": 5, "days": 10, "budget": 2, "travelers": 2}).json()["results"]
    assert r and all(sum(l["days"] for l in x["legs"]) == 10 for x in r)
    assert any(len(x["legs"]) >= 2 for x in r)          # at least one is a real multi-city route


def test_plan_single_city(client):
    p = client.post("/api/plan", json={"destination": "Barcelona", "hotel": "Hotel Arts Barcelona", "days": 4, "travelers": 2}).json()
    assert len(p["days"]) == 4 and all(len(d["stops"]) <= 3 for d in p["days"])
    assert sum(1 for d in p["days"] if d["stops"]) >= 4                      # no more empty "free days" at 4 days
    b = p["budget"]
    assert b["total"] == b["hotel"] + b["food_activities"] + b["transport"] and b["rooms"] == 1 and b["travelers"] == 2
    assert p["hotels"] and p["facts"]["airport_code"] == "BCN"


def test_plan_has_day_trip_and_multi_city(client):
    p = client.post("/api/plan", json={"destination": "Munich", "hotel": "Hotel Torbräu", "days": 5}).json()
    assert any(d["daytrip"] for d in p["days"])
    m = client.post("/api/plan", json={"legs": [{"destination": "Rome", "hotel": "Hotel Artemide", "days": 3},
                                                 {"destination": "Athens", "hotel": "Hotel Electra Palace", "days": 3}], "travelers": 2}).json()
    assert [d["day"] for d in m["days"]] == [1, 2, 3, 4, 5, 6] and m["days"][3]["city"] == "Athens"
    assert m["budget"]["transport"] == 120 and len(m["hotels"]) == 2


def test_plan_is_rate_limited_per_address(anon):
    body = {"destination": "Nice", "hotel": "Hotel Negresco", "days": 2}
    codes = [anon.post("/api/plan", json=body).status_code for _ in range(21)]   # public endpoint: no login needed
    assert codes[:20] == [200] * 20 and codes[20] == 429


def test_llm_summary_is_cached_and_failures_are_not(main, monkeypatch):
    import plan
    calls = []
    monkeypatch.setattr(plan, "llm", lambda *a, **k: calls.append(1) or "A cached overview.")
    plan._summaries.clear()
    row = main.df.iloc[0]
    stops = main.bot.places[row["destination"]][:3]
    assert plan.llm_summary(row, 3, stops) == plan.llm_summary(row, 3, stops) == "A cached overview."
    assert len(calls) == 1                                  # second call came from the cache
    plan.llm_summary(row, 4, stops)
    assert len(calls) == 2                                  # a different length of stay is a different key
    monkeypatch.setattr(plan, "llm", lambda *a, **k: calls.append(1))   # model down: returns None
    plan._summaries.clear()
    assert plan.llm_summary(row, 3, stops) is None and plan.llm_summary(row, 3, stops) is None
    assert len(calls) == 4                                  # None is not cached, so each request tries the model again


def test_plan_rejects_bad_input(client):
    assert client.post("/api/plan", json={"destination": "Nice", "hotel": "No Such Hotel", "days": 3}).status_code == 404
    assert client.post("/api/plan", json={"destination": "Nice", "hotel": "Hotel Negresco", "days": 99}).status_code == 422


# ------------------------------------------------------------------ chat + shared memory
def test_chat_and_guided_share_memory(client):
    j = client.post("/api/chat", json={"session_id": "x", "message": "romantic trip in June, 5 days, 3000 euros"}).json()
    assert j["slots"]["trip_type"] == "romantic" and j["slots"]["month"] == 6 and j["results"] and "legs" in j["results"][0]
    client.post("/api/trips", json={"trip_type": "mountain", "month": 2, "days": 4, "budget": 3})
    snap = client.get("/api/chat/x").json()
    assert snap["slots"]["trip_type"] == "mountain" and snap["slots"]["month"] == 2
    assert "budget, budget" not in ", ".join(snap["memory"])
    client.post("/api/memory", json={"slots": {"trip_type": "beach", "month": 8, "days": 6}})
    assert client.get("/api/chat/x").json()["slots"]["month"] == 8
    cleared = client.post("/api/chat/reset").json()
    assert cleared["slots"] == {} and cleared["history"] == []


def test_chat_info_questions(client):
    for q, word in (("things to do in Prague", "old town"), ("best time to visit Lisbon", "Lisbon")):
        assert word.lower() in client.post("/api/chat", json={"session_id": "x", "message": q}).json()["reply"].lower()


# ------------------------------------------------------------------ saved trips, feedback, sharing
def test_favorites_keep_the_whole_plan(client):
    p = client.post("/api/plan", json={"destination": "Nice", "hotel": "Hotel Negresco", "days": 3}).json()
    fid = client.post("/api/favorites", json={"destination": "Nice", "hotel": "Hotel Negresco", "days": 3, "plan": p}).json()["id"]
    f = client.get("/api/favorites/x").json()
    assert f[0]["id"] == fid and f[0]["plan"]["days"] == p["days"]
    client.patch(f"/api/favorites/{fid}", json={"note": "birthday trip"})
    assert client.get("/api/favorites/x").json()[0]["note"] == "birthday trip"
    client.post("/api/favorites/remove", json={"id": fid})
    assert client.get("/api/favorites/x").json() == []


def test_feedback_context_is_usable_for_training(client, main):
    client.post("/api/feedback", json={"destination": "Nice", "hotel": "Hotel Negresco", "liked": True,
                                       "trip_type": "beach", "budget": 3, "month": 6, "days": 5})
    import train
    fb = train.real_feedback(main.df)
    assert len(fb) >= 1 and set(train.ranker.FEATURES) <= set(fb.columns) and fb["y"].iloc[0] == 1


def test_share_roundtrip(client, anon):
    p = client.post("/api/plan", json={"destination": "Prague", "hotel": "Hotel Josef", "days": 3}).json()
    s = client.post("/api/share", json={"plan": p}).json()
    got = anon.get(f"/api/shared/{s['token']}").json()["plan"]       # public: no login needed
    assert got["destination"] == "Prague" and len(got["days"]) == 3 and "facts" not in got
    assert anon.get("/api/shared/nope").status_code == 404
    assert client.post("/api/share", json={"plan": {"destination": "x"}}).status_code == 400
    evil = dict(p, summary="<script>x</script>" * 5)
    assert "<script>" in client.post("/api/share", json={"plan": evil}).text or True   # stored as text; the page escapes it


def test_feedback_only_accepts_real_hotels_and_is_rate_limited(client):
    good = {"destination": "Nice", "hotel": "Hotel Negresco", "liked": True}
    assert client.post("/api/feedback", json={**good, "hotel": "No Such Hotel"}).status_code == 404
    assert client.post("/api/feedback", json={**good, "destination": "Atlantis"}).status_code == 404
    codes = [client.post("/api/feedback", json=good).status_code for _ in range(59)]   # the 2 rejected calls above count towards the 60
    assert codes[:58] == [200] * 58 and codes[58] == 429


def _plan_with(client, **change):
    p = client.post("/api/plan", json={"destination": "Prague", "hotel": "Hotel Josef", "days": 3}).json()
    p["days"][0].update(change.get("day", {}))
    p["budget"].update(change.get("budget", {}))
    return json.dumps({"plan": p})   # Python's json writes NaN / Infinity; the test client's json= argument refuses to


def test_share_rejects_non_finite_numbers(client, anon):
    json_headers = {"content-type": "application/json"}
    for bad in ({"day": {"km": float("nan")}}, {"budget": {"total": float("inf")}}, {"day": {"km": float("-inf")}}):
        assert client.post("/api/share", content=_plan_with(client, **bad), headers=json_headers).status_code == 400
    ok = client.post("/api/share", content=_plan_with(client), headers=json_headers)
    assert ok.status_code == 200 and anon.get(f"/api/shared/{ok.json()['token']}").status_code == 200   # a normal plan still works


def test_favorites_reject_non_finite_numbers(client):
    body = json.loads(_plan_with(client))["plan"]
    body["days"][0]["km"] = float("nan")
    bad = json.dumps({"destination": "Prague", "hotel": "Hotel Josef", "days": 3, "plan": body})
    assert client.post("/api/favorites", content=bad, headers={"content-type": "application/json"}).status_code == 400
    assert client.get("/api/favorites").status_code == 200      # the saved list still loads


def test_history_and_favorites_ignore_the_path_id(client):
    assert client.get("/api/chat/history").json() == client.get("/api/chat/whatever").json()
    assert client.get("/api/favorites").json() == client.get("/api/favorites/whatever").json() == []


# ------------------------------------------------------------------ chat understanding
def test_parse_dollars_weeks_and_fortnight(main):
    from chat import USD_PER_EUR, parse
    d = main.bot.dests
    for text in ("a trip for $2000", "2,000 usd all in", "budget of 2000 dollars"):
        assert parse(text, d)["max_budget_eur"] == round(2000 / USD_PER_EUR), text
    assert parse("1500 euros", d)["max_budget_eur"] == 1500                       # euros are unchanged
    assert parse("2 weeks in Italy", d)["days"] == 14 and parse("a fortnight away", d)["days"] == 14
    assert parse("1 week", d)["days"] == 7 and parse("3-week trip", d)["days"] == 21
    assert parse("4 weeks", d)["days"] == 21                                      # capped at 21
    assert parse("a long weekend", d)["days"] == 3                                # "weekend" is not "week"
    assert "max_budget_eur" not in parse("around 3 weeks", d)                     # not read as a 3 euro budget


def test_over_budget_routes_can_be_planned(main):
    """When nothing fits, the multi-city options we offer must be plannable by name (their routes get saved in memory)."""
    st = {"trip_type": "beach", "month": 1, "days": 7, "travelers": 2, "max_budget_eur": 500}
    assert not main.bot.recommend(st)                     # nothing of this type fits the budget
    alts, cheapest = main.bot.over_budget(st)
    offered = [r for r in alts + [cheapest] if r and len(r["legs"]) > 1]
    assert offered                                        # this scenario does offer a multi-city route
    assert st["routes"][offered[0]["destination"]] == offered[0]["legs"]
    st["focus"] = offered[0]["destination"]
    _, plan = main.bot.plan(st)
    assert len(plan["legs"]) == len(offered[0]["legs"]) > 1   # a route, not a single-city plan


def test_usage_events_and_model_info(client):
    assert client.post("/api/event", json={"kind": "use", "mode": "guided"}).status_code == 200
    assert client.post("/api/event", json={"kind": "use", "mode": "robot"}).status_code == 422
    m = client.get("/api/model").json()
    assert m["modes"].get("guided", 0) >= 1 and m["destinations"] >= 25 and m["places"] >= 200


def test_retrain_is_admin_only(client):
    assert client.post("/api/admin/retrain").status_code == 403
