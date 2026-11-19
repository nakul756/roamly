# Roamly (v7)

Plan a Europe trip around your month, length and budget. Describe it in a chat or tap through guided options (both share
one memory), compare ranked destinations with honest cost estimates, then get a day-by-day itinerary with road routes,
weather, a budget breakdown, flight and hotel links, a calendar file and a shareable link.

## Run it
```bash
pip install -r requirements.txt
cd backend
python -m uvicorn main:app --port 8000      # or double-click run.bat (Windows) / ./run.sh (macOS, Linux)
```
Open http://127.0.0.1:8000. The first start builds the database and trains the ranking model (about 15 seconds).
Docker: `docker build -t roamly . && docker run -p 8000:8000 -v travel-data:/data roamly`.
Interactive API docs: http://127.0.0.1:8000/docs. Tests: `pip install -r requirements-dev.txt && python -m pytest tests`.

## Settings (all optional)
Copy `.env.example` to `.env`. No key is needed to run the app. See that file for every option:
language model (free: `LLM_BASE_URL` + `LLM_API_KEY` for Groq or OpenRouter, or a local Ollama; paid: `ANTHROPIC_API_KEY`), `ADMIN_EMAIL` (can retrain from Settings),
`COOKIE_SECURE` and `BASE_URL` for deployment, `SMTP_*` for password-reset emails (without them the reset link is printed
in the server console), `TRAVEL_DATA_DIR` for where the databases live.
Free services used with no key: Open-Meteo (weather), open.er-api.com (exchange rates), OSRM demo server (road routes),
OpenStreetMap (map tiles). Each has a fallback if it can't be reached, except map tiles.

## What's in the box
| Area | What it does |
|---|---|
| Two ways to plan | **Chat** and **Guided** write to the same memory (`/api/memory`, `/api/trips`). Usage of each is counted and shown in About. |
| Ranking | Gradient-boosted model scores every destination/hotel. Trips over 5 days become multi-city routes. Costs scale with travellers and rooms. |
| Itinerary | Stops are clustered by area per day, far sights become a day trip, budget split (hotels, food, city-to-city travel), weather, facts, map with road routes, hotel pins. |
| Share and export | Public read-only link (`/share.html`), `.ics` calendar file, copy as text, print, Google Flights / Booking.com links (use your home airport from Settings). |
| Accounts | Sign up, log in (remember me), forgot / reset password, change password, change name, download all your data, delete account. Sessions expire, tokens are stored hashed, logins and sign-ups are rate-limited. |
| Learning | Every thumbs-up/down is stored with the trip's type, budget, month and length. `python train.py` (or the admin button) blends them into training once there are 20+. |
| Design | Warm paper-and-ink look with drawn destination illustrations (`frontend/js/art.js`), light and dark themes, works on phones, built with labels, roles and focus styles for keyboard and screen-reader use (not yet audited with a real screen reader), offline fonts and map library. |
| Pages | Landing (with a live try-it), login, signup, forgot, reset, app, shared trip, privacy, 404. |

## Folder tour
```
backend/   main.py (API) chat.py (assistant) plan.py (itineraries) ranker.py + train.py (model) seed.py (data) intent.py
           db.py (thread-safe SQLite) llm.py (language model calls) ratelimit.py config.py
data/      europe_travel_dataset_v2.csv  (databases are created here)
frontend/  *.html  css/  js/ (art.js illustrations, app.js planner, map.js)  fonts/  vendor/leaflet/
tools/     fetch_photos.py (Wikimedia photos)  generate_images.ipynb (optional AI images)
tests/     22 tests: API, auth, rate limits, plans, sharing, data sanity checks
```

## Data you should know about
- **Places:** about 350 places across 40 cities, each with a type and approximate coordinates. Hotel pins are approximate too (about 1 km).
  The test suite checks every pin is near its city, but please spot-check before publishing.
- **Hotels:** 43 rows from the original dataset, 26 added in v6 (`NEW_HOTELS` in `seed.py`) and 39 added in v7 for 13 cheaper, lesser-known cities (`backend/extra_data.py`). All prices, hotel names and coordinates are approximate.
  All prices are estimates and marked unverified. Chamonix still has only a luxury option.
- **Model:** trained on simulated travellers, so its scores show how well it learned the simulator's rules, not real preferences.
  Real feedback fixes that over time. The About page says this too.
- **Photos:** none bundled; the illustrations are used. Drop `<slug>.jpg` files into `frontend/images/destinations/` or run `tools/fetch_photos.py`.

## Not included (on purpose or for lack of a key)
Booking and live prices or availability (needs a paid partner API), email verification at sign-up, social login,
languages other than English, push notifications. Rate limits are per process: run several server workers and you need Redis.

## Verified and not verified
Verified in the build environment: all 22 tests pass; every page was walked through in a real browser (desktop and a phone-sized screen,
light and dark) with no script errors; plans, sharing, password reset (console link), account export and delete work.
**Not verified** because the build environment had no internet: live weather, live exchange rates, road routes from OSRM, map tiles,
`tools/fetch_photos.py`, SMTP email sending, and the Docker image. Each has a fallback or is plain standard code, but try them once on your machine.
