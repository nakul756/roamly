/* Trip map: numbered stops coloured by day, hotel markers, and real road routes from the public OSRM demo server
   (no key needed; falls back to straight dashed lines if it can't be reached). Used by the app and the share page. */
const TravelMap = (() => {
  const COLORS = ["#bf4b2c", "#2c5d63", "#c98d2e", "#7a4e8c", "#3a7a52", "#b3332b", "#3a6fb0"];
  const OSRM = "https://router.project-osrm.org/route/v1/driving/";
  let roadsDown = false;
  /* tile URL (with the CARTO key) comes from the server so the key lives in .env, not in the source */
  const tiles = fetch("/api/map-config").then(r => r.json()).then(j => j.tiles)
    .catch(() => "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png");

  async function road(points) {
    const key = "osrm:" + points.map(p => p.map(x => x.toFixed(4)).join(",")).join(";");
    try { const c = sessionStorage.getItem(key); if (c) return JSON.parse(c); } catch { /* storage unavailable */ }
    const ctl = new AbortController(), t = setTimeout(() => ctl.abort(), 7000);
    try {
      const r = await fetch(OSRM + points.map(p => p[1] + "," + p[0]).join(";") + "?overview=full&geometries=geojson", { signal: ctl.signal });
      const j = await r.json();
      if (j.code !== "Ok") throw new Error("no route");
      const out = { line: j.routes[0].geometry.coordinates.map(c => [c[1], c[0]]), km: j.routes[0].distance / 1000, min: j.routes[0].duration / 60 };
      try { sessionStorage.setItem(key, JSON.stringify(out)); } catch { /* quota */ }
      return out;
    } catch { roadsDown = true; return null; } finally { clearTimeout(t); }
  }

  function draw(el, plan, { roads = true, onRoad = () => {} } = {}) {
    if (el._map) el._map.remove();
    const map = L.map(el, { scrollWheelZoom: false }); el._map = map;
    L.Icon.Default.imagePath = "/vendor/leaflet/images/";
    tiles.then(url => L.tileLayer(url, { attribution: "&copy; OpenStreetMap contributors &copy; CARTO", subdomains: "abcd", maxZoom: 19, referrerPolicy: "strict-origin-when-cross-origin" }).addTo(map));
    map.on("focus", () => map.scrollWheelZoom.enable()); map.on("blur", () => map.scrollWheelZoom.disable());
    const groups = {}, all = [], used = new Map(); let n = 0;
    /* stops at (almost) the same spot would hide each other: fan them out a little so every number stays clickable */
    const spread = (lat, lon) => { const k = lat.toFixed(4) + "," + lon.toFixed(4), c = used.get(k) || 0; used.set(k, c + 1); if (!c) return [lat, lon]; const a = c * 2.4, r = 0.00012 * Math.ceil(c / 4); return [lat + r * Math.sin(a), lon + r * Math.cos(a)]; };
    plan.days.forEach(d => {
      const col = COLORS[(d.day - 1) % COLORS.length], g = L.featureGroup().addTo(map); groups[d.day] = g;
      d.stops.forEach(s => {
        n++; if (!d.daytrip) all.push([s.lat, s.lon]);   // far-away day trips would shrink the whole map into one blob
        L.marker(spread(s.lat, s.lon), { icon: L.divIcon({ className: "pin", html: `<span style="background:${col}">${n}</span>`, iconSize: [28, 28], iconAnchor: [14, 14] }) })
          .addTo(g).bindPopup(`<b>Day ${d.day}</b><br>${esc(s.name)}<br><a target="_blank" rel="noopener" href="${mapsLink(s.lat, s.lon)}">Open in Maps</a>`);
      });
      const pts = d.stops.map(s => [s.lat, s.lon]);
      if (pts.length > 1) {
        const straight = L.polyline(pts, { color: col, weight: 3, opacity: .7, dashArray: "6 8" }).addTo(g);
        if (roads && !roadsDown) road(pts).then(r => { if (!r) return; straight.remove(); L.polyline(r.line, { color: col, weight: 4, opacity: .85 }).addTo(g); onRoad(d.day, r); });
      }
    });
    (plan.hotels || []).forEach(h => { all.push([h.lat, h.lon]); L.marker([h.lat, h.lon], { icon: L.divIcon({ className: "pin hotel", html: `<span>${Art.icon("bed", 15)}</span>`, iconSize: [28, 28], iconAnchor: [14, 14] }) }).addTo(map).bindPopup(`<b>${esc(h.name)}</b><br><small>Hotel (approximate location)</small>`); });
    if (all.length) map.fitBounds(all, { padding: [32, 32], maxZoom: 15 }); else map.setView(plan.center, 12);
    setTimeout(() => map.invalidateSize(), 60);
    return { map, focusDay(d) { const g = groups[d]; if (g && g.getLayers().length) { map.fitBounds(g.getBounds(), { maxZoom: 16, padding: [40, 40] }); } }, colors: COLORS };
  }
  return { draw, COLORS, colors: COLORS };
})();
