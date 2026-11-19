const LOGO = `${Art.brand()}`;
$("#logo").innerHTML = LOGO; $("#flogo").innerHTML = LOGO;
bindThemeButtons();
$$("[data-art]").forEach(el => { const [n, t] = el.dataset.art.split("|"); el.outerHTML = Art.media(n, t); });

const FEATURES = [
  ["thumbup", "A predicted match", "Every result gets a fit score from a model trained on thousands of simulated travellers and retrained from real thumbs-up and thumbs-down."],
  ["calendar", "Costs that add up", "Hotel nights, food and activities and city-to-city travel, split by travellers and rooms."],
  ["map", "Multi-city routes", "Stays of more than five days combine nearby cities automatically, with the days split between them."],
  ["pin", "Real road routes", "See each day's stops on the map with road distances, and open any stop in Maps."],
  ["sun", "Weather that matters", "A 7-day forecast plus what the month was like last year, so you know what to pack."],
  ["share", "Share or sync", "Send a read-only link to your travel partners or add the whole plan to your calendar."],
  ["compare", "Your currency", "Switch between euros, dirhams, dollars, pounds, riyals and rupees with live rates."],
  ["lock", "Private by default", "Download or delete everything we store about you from Settings, any time."],
];
$("#features").innerHTML = FEATURES.map(([i, t, p]) => `<div class="card feature"><div class="ic">${Art.icon(i, 22)}</div><h3>${t}</h3><p>${p}</p></div>`).join("");

api("/api/model", undefined, { noRedirect: true }).then(m => {
  const v = [m.destinations, m.places, m.hotels];
  $$("#facts dt").forEach((d, i) => d.textContent = v[i]);
}).catch(() => {});

/* try it */
const TRY = { type: null, budget: 2 };
$("#tMonth").innerHTML = MON.map((m, i) => `<option value="${i + 1}">${m}</option>`).join(""); $("#tMonth").value = new Date().getMonth() + 1;
$("#tBud").innerHTML = [[1, "Budget"], [2, "Mid-range"], [3, "Luxury"]].map(([v, l]) => `<button class="pill" data-b="${v}" aria-pressed="${v === 2}">${l}</button>`).join("");
let TYPES = ["beach", "city", "culture", "mountain", "nature", "romantic"];
const drawTypes = () => $("#tTypes").innerHTML = TYPES.map(t => `<button class="pill" data-t="${t}" aria-pressed="${TRY.type === t}">${Art.icon(t)}${t[0].toUpperCase() + t.slice(1)}</button>`).join("");
api("/api/options", undefined, { noRedirect: true }).then(o => { TYPES = o.trip_types; drawTypes(); }).catch(() => {}); drawTypes();
async function runTry() {
  if (!TRY.type) return;
  const out = $("#tOut"); out.innerHTML = `<p class="muted"><span class="spin"></span> Finding matches</p>`;
  try {
    const j = await api("/api/trips", { trip_type: TRY.type, month: +$("#tMonth").value, days: +$("#tDays").value, budget: TRY.budget, sync: false }, { noRedirect: true });
    out.innerHTML = j.results.length ? j.results.slice(0, 3).map(r => `<div class="mini">${Art.media(r.destination, r.trip_type)}<div><h4>${esc(r.destination)}${r.route ? ` <small class="muted">route</small>` : ""}</h4><p>${esc(r.route || r.hotel)}<br>about ${Money.fmt(r.total_eur)} for ${r.days} days</p></div><div class="pct">${Math.min(99, r.match_pct)}%<small>${Season.of(+$("#tMonth").value, r.best_months).t.toLowerCase()}</small></div></div>`).join("") +
      `<a class="btn btn-accent" href="/signup.html" style="justify-self:start;margin-top:6px">Plan this trip ${Art.icon("arrow")}</a>`
      : `<p class="muted">Nothing fits that combination well. Try another month or a different budget level.</p>`;
  } catch (e) { out.innerHTML = `<p class="muted">${esc(e.message)}</p>`; }
}
$("#tTypes").onclick = e => { const b = e.target.closest("[data-t]"); if (b) { TRY.type = b.dataset.t; drawTypes(); runTry(); } };
$("#tBud").onclick = e => { const b = e.target.closest("[data-b]"); if (b) { TRY.budget = +b.dataset.b; $$("#tBud .pill").forEach(x => x.setAttribute("aria-pressed", x === b)); runTry(); } };
$("#tMonth").onchange = $("#tDays").onchange = runTry;

/* destinations */
let ALL = [], FILTER = "all";
const drawGrid = () => {
  const list = ALL.filter(d => FILTER === "all" || d.trip_type === FILTER);
  $("#dGrid").innerHTML = list.map(d => `<a class="card dcard" href="/signup.html">${Art.media(d.destination, d.trip_type)}<div class="body"><h3>${esc(d.destination)}</h3>
   <div class="meta"><span>${esc(d.country)}</span><span>from ${Money.fmt(d.from_per_day_eur)} / day</span></div>
   <div class="tags"><span class="tag">${MO[d.best_months[0] - 1]}${d.best_months.length > 1 ? " to " + MO[d.best_months.at(-1) - 1] : ""}</span>${d.highlights.slice(0, 2).map(h => `<span class="tag">${esc(h)}</span>`).join("")}</div></div></a>`).join("");
};
api("/api/destinations", undefined, { noRedirect: true }).then(async d => {
  await Money.load(); ALL = d;
  const types = ["all", ...new Set(d.map(x => x.trip_type))];
  $("#dFilters").innerHTML = types.map(t => `<button class="pill" data-f="${t}" aria-pressed="${t === "all"}">${t === "all" ? "All" : Art.icon(t) + t[0].toUpperCase() + t.slice(1)}</button>`).join("");
  $("#dFilters").onclick = e => { const b = e.target.closest("[data-f]"); if (!b) return; FILTER = b.dataset.f; $$("#dFilters .pill").forEach(x => x.setAttribute("aria-pressed", x === b)); drawGrid(); };
  drawGrid();
}).catch(() => { $("#dGrid").innerHTML = `<p class="muted">Start the server to see destinations.</p>`; });
Money.load();
