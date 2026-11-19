/* Public, read-only trip page (/share.html?t=TOKEN). Everything from the server is escaped before it is shown. */
const token = new URLSearchParams(location.search).get("t");
const root = $("#root");
const type = p => p.trip_type || "city";
function view(p, created) {
  const days = p.days.length, b = p.budget || {};
  document.title = `${p.destination}: ${days}-day trip · Roamly`;
  root.innerHTML = `
  <header class="nav share-nav"><a class="logo" href="/" style="color:#fffaf0">${Art.brand("cream")}</a><div class="right"><button class="icon-btn" data-theme-toggle></button><a class="btn btn-sm btn-accent" href="/signup.html">Plan your own</a></div></header>
  <div class="share-hero">${Art.media(p.destination, type(p))}<div class="wrap cap"><span class="eyebrow" style="color:#fffaf0;opacity:.85">Shared trip</span><h1 class="serif">${esc(p.destination)}</h1><p>${days} days${p.hotel ? " · staying at " + esc(p.hotel) : ""}</p></div></div>
  <div class="wrap share-body">
   <section class="share-grid"><div><p class="lead" style="font-size:1.08rem">${esc(p.summary)}</p></div>
    ${b.total ? `<aside class="card infocard"><div class="eyebrow">Estimated total</div><div class="big">${Money.fmt(b.total)}</div><p class="small muted">${b.travelers || 1} traveller${(b.travelers || 1) > 1 ? "s" : ""} · about ${Money.fmt(b.per_person || b.total)} each. Estimates only.</p></aside>` : ""}</section>
   <div id="map" class="map" role="region" aria-label="Map of the trip"></div>
   <ol class="days">${p.days.map(d => `<li class="day card"><div class="dn" style="background:${TravelMap.colors[(d.day - 1) % 7]}">${d.day}</div><div class="db">
     <h3>${d.city ? `<small class="eyebrow">${esc(d.city)}</small><br>` : ""}${esc(d.title)}${d.daytrip ? ' <span class="tag">day trip</span>' : ""}</h3><p>${esc(d.text)}</p>
     <div class="stops">${d.stops.map(s => `<a class="stop" target="_blank" rel="noopener" href="${mapsLink(s.lat, s.lon)}">${Art.kind(s.kind)}${esc(s.name)}</a>`).join("")}</div></div></li>`).join("")}</ol>
   <p class="small muted" style="margin:20px 0 60px">Shared ${esc(created)}. Prices and map pins are estimates: check before you book. Map &copy; OpenStreetMap contributors.</p>
  </div>`;
  bindThemeButtons();
  TravelMap.draw($("#map"), p);
}
(async () => {
  await Money.load();
  if (!token) { root.innerHTML = `<div class="notfound"><div><h1 class="serif">?</h1><h2>This link is incomplete</h2><p class="muted" style="margin:10px 0 20px">Ask whoever sent it to share it again.</p><a class="btn btn-primary" href="/">Go to Roamly</a></div></div>`; return; }
  try { const j = await api("/api/shared/" + encodeURIComponent(token), undefined, { noRedirect: true }); view(j.plan, j.created); }
  catch (e) { root.innerHTML = `<div class="notfound"><div><h1 class="serif">404</h1><h2>${esc(e.message)}</h2><p class="muted" style="margin:10px 0 20px">The link may have been mistyped or removed.</p><a class="btn btn-primary" href="/">Go to Roamly</a></div></div>`; }
})();
