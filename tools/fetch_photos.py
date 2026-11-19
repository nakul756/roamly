"""Downloads one real photo per destination from Wikimedia Commons (free, no API key) into
frontend/images/destinations/<slug>.jpg and writes the licence/author of each photo to CREDITS.md.
Only openly licensed photos (Creative Commons or public domain) are kept. The app shows a photo automatically when
its file exists, and the drawn illustration otherwise.

    pip install pillow
    python tools/fetch_photos.py                 # all destinations
    python tools/fetch_photos.py Nice Prague     # just these

NOTE: written without internet access in the build environment, so it has not been run end to end. Wikipedia's lead
image is sometimes a map or a logo: look at the results and delete any you don't like (the illustration returns).
Attribution is required by most of these licences, so keep CREDITS.md and the "Photo credits" link in the footer."""
import io
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    sys.exit("Please run:  pip install pillow")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "frontend" / "images" / "destinations"
sys.path.insert(0, str(ROOT / "backend"))
import seed  # noqa: E402

UA = {"User-Agent": "travel-ai-class-project/1.0 (educational; contact: set-your-email)"}
WIKI_TITLE = {"Tromso": "Tromsø", "Krakow": "Kraków", "Reykjavik": "Reykjavík", "Amalfi Coast": "Amalfi Coast", "Palma de Mallorca": "Palma de Mallorca",
              "Lagos": "Lagos, Portugal", "Split": "Split, Croatia", "Santorini": "Oia, Greece"}   # plain names hit the wrong place or a disambiguation page
OK_LICENCE = re.compile(r"^(CC[ -]BY|CC0|Public domain|PD)", re.I)


def polite(fn, *args):
    """Call fn, and when Wikimedia answers 429 (too many requests) wait as long as it asks, then retry."""
    for attempt in range(5):
        try:
            return fn(*args)
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == 4:
                raise
            wait = int(e.headers.get("Retry-After") or 30) + 5 * attempt
            print(f"      rate limited, waiting {wait}s")
            time.sleep(wait)


def get_json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return json.load(r)


def lead_image(title):
    q = urllib.parse.urlencode({"action": "query", "titles": title, "prop": "pageimages", "piprop": "name", "redirects": 1, "format": "json"})
    page = next(iter(get_json("https://en.wikipedia.org/w/api.php?" + q)["query"]["pages"].values()))
    return page.get("pageimage")


def licence(filename):
    q = urllib.parse.urlencode({"action": "query", "titles": "File:" + filename, "prop": "imageinfo", "iiprop": "extmetadata", "format": "json"})
    page = next(iter(get_json("https://commons.wikimedia.org/w/api.php?" + q)["query"]["pages"].values()))
    meta = page["imageinfo"][0]["extmetadata"]
    strip = lambda s: re.sub(r"<[^>]+>", "", s or "").strip()
    return strip(meta.get("LicenseShortName", {}).get("value")), strip(meta.get("Artist", {}).get("value")) or "unknown author"


def download(filename, path):
    url = "https://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(filename) + "?width=1000"
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        img = Image.open(io.BytesIO(r.read())).convert("RGB")
    img.thumbnail((1000, 1000))
    img.save(path, "JPEG", quality=82, optimize=True)


def slug(n):
    return re.sub(r"[^a-z0-9]+", "-", n.lower()).strip("-")


def main(only):
    OUT.mkdir(parents=True, exist_ok=True)
    names = sorted(seed.load_destinations()["destination"].unique())
    rows = []
    credits = OUT / "CREDITS.md"
    credited = {l.split("|")[1].strip() for l in credits.read_text(encoding="utf-8").splitlines()
                if l.startswith("| ") and not l.startswith("| Place")} if credits.exists() else set()
    for name in names:
        if only and name not in only:
            continue
        have = (OUT / f"{slug(name)}.jpg").exists()
        if not only and have and name in credited:
            continue                      # done; name a city on the command line to redo it
        time.sleep(2)                     # be gentle with Wikimedia
        try:
            fn = polite(lead_image, WIKI_TITLE.get(name, name))
            if not fn or not fn.lower().endswith((".jpg", ".jpeg")):
                print(f"skip  {name}: lead image is {fn!r} (not a photo)")
                continue
            lic, author = polite(licence, fn)
            if not OK_LICENCE.match(lic):
                print(f"skip  {name}: licence {lic!r} not allowed")
                continue
            if not (have and not only):   # a photo without a credit row only needs its credit written, not a new download
                polite(download, fn, OUT / f"{slug(name)}.jpg")
            rows.append(f"| {name} | {author} | {lic} | https://commons.wikimedia.org/wiki/File:{urllib.parse.quote(fn.replace(' ', '_'))} |")
            print(f"ok    {name}: {fn} ({lic})")
        except Exception as e:
            print(f"FAIL  {name}: {e}")
    if rows:
        head = "# Photo credits\n\nPhotos from Wikimedia Commons under the licences shown. Illustrations elsewhere are drawn in code.\n\n| Place | Author | Licence | Source |\n|---|---|---|---|\n"
        old = [l for l in credits.read_text(encoding="utf-8").splitlines() if l.startswith("| ") and not l.startswith("| Place") and l.split("|")[1].strip() not in {r.split("|")[1].strip() for r in rows}] if credits.exists() else []
        credits.write_text(head + "\n".join(old + rows) + "\n", encoding="utf-8")
        print(f"\nWrote {len(rows)} photos and updated CREDITS.md")


if __name__ == "__main__":
    main(set(sys.argv[1:]))
