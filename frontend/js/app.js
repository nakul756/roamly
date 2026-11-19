/* Roamly planner. Part 1: setup, chat, guided mode, results. Part 2 (below): itinerary, saved, compare, settings. */
const sid = localStorage.sid || (localStorage.sid = crypto.randomUUID());
const state = { me: null, results: [], cmp: [], plan: null, planCtx: {}, mode: localStorage.mode === "guided" ? "guided" : "chat", busy: false, types: ["beach", "city", "culture", "mountain", "nature", "romantic"], mapH: null };
const G = { trip_type: null, month: new Date().getMonth() + 1, days: 5, budget: null, travelers: 1, activity: null, avoid_crowds: false, total: "" };
const cap = s => s[0].toUpperCase() + s.slice(1);
const ev = (kind, mode) => api("/api/event", { kind, mode }).catch(() => {});
const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;
const $log = $("#log");

/* ---------- static bits ---------- */
$("#logo").innerHTML = `${Art.brand()}`;
$("#mChat").innerHTML = Art.icon("send") + "Chat"; $("#mGuided").innerHTML = Art.icon("sliders") + "Guided";
$("#mic").innerHTML = Art.icon("mic", 19); $("#sClose").innerHTML = Art.icon("close", 19);
$("#trMinus").innerHTML = Art.icon("minus", 16); $("#trPlus").innerHTML = Art.icon("plus", 16);
$("#surprise").innerHTML = Art.icon("dice") + "Surprise me"; $("#sExport").innerHTML = Art.icon("download") + "Download my data";
$("#f .send").innerHTML = Art.icon("send");
bindThemeButtons();

/* ---------- tabs ---------- */
const TABS = [["results", "Results"], ["plan", "Itinerary"], ["saved", "Saved"], ["compare", "Compare"]];
function drawTabs(active) {
  const badge = { results: state.results.length, compare: state.cmp.length };
  $("#tabs").innerHTML = TABS.map(([id, l]) => `<button role="tab" data-t="${id}" aria-selected="${id === active}">${l}${badge[id] ? `<span class="n">${badge[id]}</span>` : ""}</button>`).join("");
}
function tab(n) {
  $$(".tab").forEach(d => d.hidden = d.id !== n); drawTabs(n); state.tab = n;
  if (n === "saved") loadSaved(); if (n === "compare") renderCompare();
  if (n === "plan" && state.mapH) setTimeout(() => state.mapH.map.invalidateSize(), 60);
}
$("#tabs").onclick = e => { const b = e.target.closest("[data-t]"); if (b) tab(b.dataset.t); };

/* ---------- mode switch ---------- */
function setMode(m, init) {
  state.mode = m; localStorage.mode = m;
  $("#chatView").hidden = m !== "chat"; $("#guidedView").hidden = m !== "guided";
  $("#mChat").setAttribute("aria-selected", m === "chat"); $("#mGuided").setAttribute("aria-selected", m === "guided");
  if (!init) ev("switch", m);
}
$("#mChat").onclick = () => setMode("chat"); $("#mGuided").onclick = () => setMode("guided");

/* ---------- memory chips + sync between chat and guided ---------- */
const drawMem = list => $("#mem").innerHTML = list && list.length ? list.map(x => `<span>${esc(x)}</span>`).join("") : "<small>Your preferences will appear here as we talk.</small>";
function applySlots(s) {
  if (!s) return;
  Object.assign(G, { trip_type: s.trip_type || null, month: s.month || G.month, days: s.days || G.days, budget: s.budget || null, travelers: s.travelers || 1, activity: s.activity || null, avoid_crowds: !!s.avoid_crowds,
    total: s.max_budget_eur ? String(Math.round(s.max_budget_eur * Money.rate())) : "" });
  drawGuided();
}

/* ---------- chat ---------- */
function addMsg(role, text) {
  const d = document.createElement("div"); d.className = "msg " + role;
  d.innerHTML = (role === "bot" ? `<span class="av" aria-hidden="true"><img src="/images/brand/roamly-mark-96.png" alt=""></span>` : "") + `<div class="bub"></div>`; $(".bub", d).textContent = text;
  $log.append(d); $log.scrollTop = $log.scrollHeight; return d;
}
/* RAG: show which dataset passages the answer was grounded in */
function addSources(msgEl, sources) {
  if (!sources || !sources.length) return;
  const d = document.createElement("details"); d.className = "sources small muted";
  d.innerHTML = `<summary>Sources (${sources.length})</summary>` + sources.map(s => `<p><b>${esc(s.destination)}</b>: ${esc(s.text)}</p>`).join("");
  $(".bub", msgEl).append(d);
}
const typing = () => { const d = addMsg("bot", ""); $(".bub", d).innerHTML = `<span class="dots" aria-label="Typing"><i></i><i></i><i></i></span>`; return d; };
function chips(list) { $("#sugg").innerHTML = list.map(([label, msg]) => `<button class="pill" data-m="${esc(msg || label)}">${esc(label)}</button>`).join(""); }
$("#sugg").onclick = e => { const b = e.target.closest("[data-m]"); if (b) send(b.dataset.m); };
const surpriseMsg = () => { const r = a => a[Math.floor(Math.random() * a.length)]; return `${r(state.types)} trip in ${r(MON)}, ${r([3, 4, 5, 7, 8])} days, ${r(["cheap", "mid-range", "luxury"])}`; };
function quick(reply, res, plan) {
  const r = reply || "";
  if (/what kind of trip/i.test(r)) return chips(state.types.map(k => [cap(k), k + " trip"]));
  if (/which month/i.test(r)) return chips(MON.map(m => [m.slice(0, 3), "in " + m]));
  if (/how many days/i.test(r)) return chips(["3 days", "5 days", "7 days", "10 days"].map(x => [x]));
  if (/total budget/i.test(r)) return chips([["1,000 euros"], ["2,000 euros"], ["4,000 euros"], ["No limit", "no limit"]]);
  if (res && res.length) return chips([["Make it cheaper", "make it cheap"], ["Make it luxury"], ["Make it 7 days"], ["Avoid crowds"], ["Plan " + res[0].destination]]);
  if (plan) return chips([["Make it cheaper", "make it cheap"], ["Something quieter", "avoid crowds"], ["Start over"]]);
  chips([["Relaxed beach trip in June, 5 days, 2000 euros"], ["Culture trip in May, 8 days, 3000 euros"], ["City break in October, 4 days"], ["Surprise me", surpriseMsg()]]);
}
async function send(msg) {
  if (state.busy || !msg.trim()) return; state.busy = true; addMsg("user", msg); $("#sugg").innerHTML = "";
  const t = typing(); ev("use", "chat");
  try {
    const j = await api("/api/chat", { session_id: sid, message: msg }); t.remove(); const bm = addMsg("bot", j.reply); addSources(bm, j.sources); drawMem(j.memory); applySlots(j.slots);
    if (j.results) { state.results = j.results; renderResults(); tab("results"); }
    if (j.plan) showPlan(j.plan, { month: j.slots?.month });
    quick(j.reply, j.results, j.plan);
    if (j.results || j.plan) scrollToWork();
  } catch (e) { t.remove(); addMsg("bot", e.message || "Something went wrong."); quick("", null); }
  state.busy = false;
}
const scrollToWork = () => { if (matchMedia("(max-width:960px)").matches) $("#work").scrollIntoView({ behavior: "smooth" }); };
$("#f").onsubmit = e => { e.preventDefault(); const v = $("#t").value.trim(); if (v) { $("#t").value = ""; send(v); } };
const greet = () => addMsg("bot", `Hi ${state.me.name.split(" ")[0]}. Tell me about the trip you have in mind: the kind of place, when, for how long and what you can spend. Or switch to Guided and tap through the options.`);
$("#newChat").onclick = async () => {
  const s = await api("/api/chat/reset", {}); $log.innerHTML = ""; greet(); drawMem(s.memory); Object.assign(G, { trip_type: null, budget: null, travelers: 1, activity: null, avoid_crowds: false, total: "", days: 5 }); drawGuided(); quick("", null);
  state.results = []; renderResults(); tab("results"); toast("Started a new trip");
};

/* ---------- guided ---------- */
const BUD = [[null, "Any"], [1, "Budget"], [2, "Mid-range"], [3, "Luxury"]], PACE = [[1, "Relaxed"], [null, "Balanced"], [3, "Active"]];
function drawGuided() {
  const on = (a, b) => a === b ? "true" : "false";
  $("#gType").innerHTML = state.types.map(t => `<button class="pill" data-k="trip_type" data-v="${t}" aria-pressed="${on(G.trip_type, t)}">${Art.icon(t)}${cap(t)}</button>`).join("");
  $("#gBud").innerHTML = BUD.map(([v, l]) => `<button class="pill" data-k="budget" data-v="${v ?? ""}" aria-pressed="${on(G.budget, v)}">${l}</button>`).join("");
  $("#gMon").innerHTML = MON.map((m, i) => `<button class="pill" data-k="month" data-v="${i + 1}" aria-pressed="${on(G.month, i + 1)}">${m.slice(0, 3)}</button>`).join("");
  $("#gPace").innerHTML = PACE.map(([v, l]) => `<button class="pill" data-k="activity" data-v="${v ?? ""}" aria-pressed="${on(G.activity, v)}">${l}</button>`).join("");
  $("#trN").textContent = G.travelers; $("#days").value = G.days; $("#dv").textContent = plural(G.days, "day");
  $("#gCrowd").checked = G.avoid_crowds; $("#gTotal").value = G.total; $("#gCur").textContent = Money.cur;
}
$("#guidedView").addEventListener("click", e => {
  const b = e.target.closest(".pill[data-k]"); if (!b) return;
  const k = b.dataset.k, v = b.dataset.v; G[k] = k === "trip_type" ? v : v === "" ? null : +v; $("#gerr").textContent = ""; drawGuided();
});
$("#trMinus").onclick = () => { G.travelers = Math.max(1, G.travelers - 1); drawGuided(); }; $("#trPlus").onclick = () => { G.travelers = Math.min(20, G.travelers + 1); drawGuided(); };
$("#days").oninput = () => { G.days = +$("#days").value; $("#dv").textContent = plural(G.days, "day"); };
$("#gCrowd").onchange = () => G.avoid_crowds = $("#gCrowd").checked; $("#gTotal").oninput = () => G.total = $("#gTotal").value;
async function runGuided() {
  if (!G.trip_type) { $("#gerr").textContent = "Choose what kind of trip you want first."; return; }
  const btn = $("#go"); btn.disabled = true; btn.innerHTML = `<span class="spin"></span> Finding trips`; ev("use", "guided");
  const body = { trip_type: G.trip_type, month: G.month, days: G.days, travelers: G.travelers, avoid_crowds: G.avoid_crowds };
  if (G.budget) body.budget = G.budget; if (G.activity) body.activity = G.activity; if (+G.total > 0) body.max_budget_eur = Math.round(Money.toEur(+G.total));
  try {
    const j = await api("/api/trips", body); state.results = j.results; renderResults(); tab("results"); scrollToWork();
    const s = await api("/api/chat/history"); drawMem(s.memory);
    if (!j.results.length) toast("No good match. Try a bigger budget or another month.");
  } catch (e) { $("#gerr").textContent = e.message; }
  btn.disabled = false; btn.textContent = "Find trips";
}
$("#go").onclick = runGuided;
$("#surprise").onclick = () => {
  const r = a => a[Math.floor(Math.random() * a.length)];
  Object.assign(G, { trip_type: r(state.types), month: 1 + Math.floor(Math.random() * 12), days: r([3, 4, 5, 7, 8]), budget: r([1, 2, 3]), activity: null }); drawGuided(); runGuided();
};

/* ---------- results ---------- */
const exampleCard = (label, fn) => `<button class="pill" data-ex="${fn}">${label}</button>`;
function renderResults() {
  const box = $("#results");
  if (!state.results.length) {
    box.innerHTML = `<div class="empty">${Art.media("Europe start", "culture")}<h3>Where will your next trip be?</h3><p>Describe it in the chat, or choose from the guided options on the left. Your matches show up here with costs, seasons and a one-click itinerary.</p>
      <div class="pills">${exampleCard("Beach trip in June", "beach")}${exampleCard("Weekend city break", "city")}${exampleCard("Surprise me", "surprise")}</div></div>`;
    return drawTabs(state.tab || "results");
  }
  box.innerHTML = state.results.map((r, i) => `<article class="ticket" data-i="${i}">
   <div class="mwrap">${Art.media(r.destination, r.trip_type)}
   <div class="stampcirc" title="Predicted match"><div>${Math.min(99, r.match_pct)}%<small>match</small></div></div>${(se => se.t ? `<span class="season ${se.c}">${se.t}</span>` : "")(Season.of(r.ctx?.month, r.best_months))}</div>
   <div class="tbody"><h3>${esc(r.destination)}<small>${esc(r.country)}</small></h3>
    ${r.route ? `<div class="route">${esc(r.route)}</div>` : `<div class="route">${esc(r.hotel)}</div>`}
    <p class="desc">${esc(r.description)}</p>
    <div class="cost"><strong>${Money.fmt(r.total_eur)}</strong><span>estimated total · ${plural(r.days, "day")} · ${plural(r.ctx?.travelers || 1, "traveller")}</span></div>
    <div class="tags">${r.highlights.split(", ").slice(0, 4).map(h => `<span class="tag">${esc(h)}</span>`).join("")}</div>
    <div class="actions">
     <button class="btn btn-sm btn-primary" data-a="plan">${Art.icon("map")}Plan the days</button>
     <button class="btn btn-sm" data-a="save">${Art.icon("bookmark")}Save</button>
     <button class="btn btn-sm btn-ghost" data-a="up" aria-label="Good match" title="Good match">${Art.icon("thumbup")}</button>
     <button class="btn btn-sm btn-ghost" data-a="down" aria-label="Not for me" title="Not for me">${Art.icon("thumbdown")}</button>
     <button class="btn btn-sm btn-ghost" data-a="cmp">${Art.icon("compare")}Compare</button>
     <button class="btn btn-sm btn-ghost" data-a="det" aria-expanded="false">${Art.icon("info")}Details</button></div>
    <div class="detail" id="det${i}" hidden></div></div></article>`).join("");
  drawTabs(state.tab || "results");
}
$("#results").addEventListener("click", async e => {
  const ex = e.target.closest("[data-ex]");
  if (ex) { if (ex.dataset.ex === "surprise") return state.mode === "guided" ? $("#surprise").click() : send(surpriseMsg()); setMode("chat"); return send(ex.dataset.ex === "beach" ? "beach trip in June, 5 days" : "city break, 3 days"); }
  const b = e.target.closest("[data-a]"); if (!b) return;
  const i = +b.closest(".ticket").dataset.i, r = state.results[i], a = b.dataset.a, ctx = r.ctx || {};
  try {
    if (a === "plan") { b.disabled = true; await openResult(r); b.disabled = false; }
    if (a === "save") { b.disabled = true; const p = await planFor(r); await api("/api/favorites", { destination: r.destination, hotel: r.hotel, days: r.days, plan: p }); b.innerHTML = Art.icon("check") + "Saved"; toast("Saved to your trips"); }
    if (a === "up" || a === "down") {
      await api("/api/feedback", { destination: r.destination, hotel: r.hotel, liked: a === "up", trip_type: ctx.trip_type, budget: ctx.budget, month: ctx.month, days: ctx.days });
      $$("[data-a=up],[data-a=down]", b.parentElement).forEach(x => x.disabled = true); b.style.color = a === "up" ? "var(--ok)" : "var(--bad)"; toast("Thanks, that helps improve the ranking");
    }
    if (a === "cmp") { if (!state.cmp.includes(r.destination)) state.cmp = [...state.cmp.slice(-2), r.destination]; drawTabs(state.tab); toast(`${r.destination} added to Compare (${state.cmp.length}/3)`); }
    if (a === "det") await toggleDetails(i, r, b);
  } catch (err) { b.disabled = false; toast(err.message); }
});
async function toggleDetails(i, r, b) {
  const box = $("#det" + i); if (!box.hidden) { box.hidden = true; b.setAttribute("aria-expanded", "false"); return; }
  const d = await api("/api/destination/" + encodeURIComponent(r.destination)), best = d.hotels.find(x => x.name === r.hotel) || d.hotels[0], day = best.price + d.daily_spend_eur;
  box.innerHTML = `<div><div class="label" style="margin-bottom:6px">Best months</div><div class="months">${MO.map((m, k) => `<span class="${d.best_months.includes(k + 1) ? "on" : ""}">${m[0]}</span>`).join("")}</div></div>
   <div><div class="label" style="margin-bottom:6px">One traveller, per day: about ${Money.fmt(day)}</div><div class="stack"><i style="width:${best.price / day * 100}%;background:var(--accent)"></i><i style="width:${d.daily_spend_eur / day * 100}%;background:var(--teal)"></i></div>
    <div class="legend"><div><span><span class="dot" style="background:var(--accent)"></span>${esc(best.name)}</span><b>${Money.fmt(best.price)}</b></div><div><span><span class="dot" style="background:var(--teal)"></span>Food and activities</span><b>${Money.fmt(d.daily_spend_eur)}</b></div></div></div>
   <div class="small muted">Rated ${d.rating} · usually ${esc(d.crowd_level)} crowds · around ${d.avg_temp_c}°C on average · airport ${esc(d.airport_code)}</div>
   <div class="small"><b>Other places to stay:</b> ${d.hotels.filter(h => h.name !== best.name).map(h => `${esc(h.name)} (${Money.fmt(h.price)})`).join(", ") || "none listed"}</div>`;
  box.hidden = false; b.setAttribute("aria-expanded", "true");
}
const planFor = r => api("/api/plan", { legs: r.legs, travelers: r.ctx?.travelers || 1 });
async function openResult(r) { const p = await planFor(r); showPlan(p, { month: r.ctx?.month, travelers: r.ctx?.travelers }); scrollToWork(); }

/* =====================================================================  Part 2  */
/* ---------- itinerary ---------- */
const pad = n => String(n).padStart(2, "0"), ymd = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const firstCity = p => p.legs?.[0]?.destination || p.destination.split(" → ")[0];
function defaultStart(month) {
  const t = new Date(); if (!month) return ymd(new Date(t.getTime() + 30 * 864e5));
  let d = new Date(t.getFullYear(), month - 1, 1); if (d < t) d = new Date(t.getFullYear() + 1, month - 1, 1); return ymd(d);
}
function showPlan(p, ctx = {}) { state.plan = p; state.planCtx = ctx; renderPlan(); tab("plan"); }
const planText = p => `${p.destination}\n${p.summary}\n\n` + p.days.map(d => `Day ${d.day}${d.city ? " (" + d.city + ")" : ""}: ${d.text}`).join("\n") + `\n\nEstimated total: ${Money.fmt(p.budget.total)} for ${plural(p.budget.travelers, "traveller")}.`;
const icsEscape = s => String(s).replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\n/g, "\\n");
function makeIcs(p, startStr) {
  const [Y, M, D] = startStr.split("-").map(Number), fmt = d => `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}`, now = new Date().toISOString().replace(/[-:]|\.\d+/g, "");
  const out = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Roamly//EN", "CALSCALE:GREGORIAN"];
  p.days.forEach(d => {
    const s = new Date(Y, M - 1, D + d.day - 1), e = new Date(Y, M - 1, D + d.day);
    out.push("BEGIN:VEVENT", `UID:${crypto.randomUUID()}@roamly`, `DTSTAMP:${now}`, `DTSTART;VALUE=DATE:${fmt(s)}`, `DTEND;VALUE=DATE:${fmt(e)}`,
      `SUMMARY:${icsEscape(`${d.city || p.destination}: ${d.title}`)}`, `DESCRIPTION:${icsEscape(d.text)}`, "END:VEVENT");
  });
  out.push("END:VCALENDAR"); return out.join("\r\n");
}
const wxIcon = l => /rain|drizzle|shower|thunder/i.test(l) ? "rain" : /clear|sun/i.test(l) ? "sun" : "cloud";
function renderPlan() {
  const p = state.plan, box = $("#plan");
  if (!p) { box.innerHTML = `<div class="empty">${Art.media("Itinerary start", "city")}<h3>No itinerary yet</h3><p>Press "Plan the days" on any result, or ask the chat to "plan" a destination.</p></div>`; return; }
  const b = p.budget, f = p.facts, city = firstCity(p), month = state.planCtx.month || new Date().getMonth() + 1, tot = b.total || 1;
  const seg = (v, c) => v ? `<i style="width:${v / tot * 100}%;background:${c}"></i>` : "", row = (l, v, c) => v ? `<div><span><span class="dot" style="background:${c}"></span>${l}</span><b>${Money.fmt(v)}</b></div>` : "";
  box.innerHTML = `
  <div class="plan-head">${Art.media(p.destination, f.trip_type)}<div class="cap"><span class="eyebrow" style="color:#fffaf0;opacity:.85">${plural(p.days.length, "day")} · ${plural(b.travelers, "traveller")}</span><h2>${esc(p.destination)}</h2><p class="small" style="opacity:.9">Staying at ${esc(p.hotel)}${p.legs && p.legs.length > 1 ? " and more" : ""}</p></div></div>
  <div class="rowbtns">
   <button class="btn btn-sm btn-primary" data-pa="save">${Art.icon("bookmark")}Save trip</button>
   <button class="btn btn-sm" data-pa="share">${Art.icon("share")}Share link</button>
   <button class="btn btn-sm" data-pa="copy">${Art.icon("copy")}Copy</button>
   <button class="btn btn-sm" data-pa="print">${Art.icon("print")}Print</button>
   <a class="btn btn-sm" href="#book">${Art.icon("plane")}Flights and stays</a>
  </div>
  <div class="rowbtns"><label class="small muted" for="startDate">Trip starts</label><input type="date" id="startDate" value="${defaultStart(state.planCtx.month)}"><button class="btn btn-sm" data-pa="ics">${Art.icon("calendar")}Add to calendar</button></div>
  <p style="color:var(--ink-2)">${esc(p.summary)}</p>${p.source === "llm" ? `<p class="small muted">Overview written by the language model; stops and costs come from our data.</p>` : ""}
  <div class="infogrid">
   <div class="infocard"><h4>Estimated budget</h4><div class="big">${Money.fmt(b.total)}</div><p class="small muted">${plural(b.travelers, "traveller")} · ${plural(b.rooms, "room")} · about ${Money.fmt(b.per_person)} each</p>
    <div class="stack" style="margin-top:12px">${seg(b.hotel, "var(--accent)")}${seg(b.food_activities, "var(--teal)")}${seg(b.transport, "var(--gold)")}</div>
    <div class="legend">${row("Hotels", b.hotel, "var(--accent)")}${row("Food and activities", b.food_activities, "var(--teal)")}${row("City-to-city travel", b.transport, "var(--gold)")}</div><p class="hint" style="margin-top:8px">Flights not included.</p></div>
   <div class="infocard"><h4>Weather in ${esc(city)}</h4><div id="wx"><p class="small muted"><span class="spin"></span> Loading</p></div></div>
   <div class="infocard"><h4>Know before you go${p.legs && p.legs.length > 1 ? " (" + esc(city) + ")" : ""}</h4><dl class="facts-list">
    <dt>Country</dt><dd>${esc(f.country)}</dd><dt>Language</dt><dd>${esc(f.language)}</dd><dt>Currency</dt><dd>${esc(f.currency)}</dd><dt>Airport</dt><dd>${esc(f.airport_code)}</dd>
    <dt>Entry</dt><dd>${/^y/i.test(f.schengen) ? "Schengen area" : "Outside Schengen: check entry rules"}</dd><dt>Getting around</dt><dd>${esc(f.getting_around)}</dd><dt>Try</dt><dd>${f.food.map(esc).join(", ")}</dd></dl>
    <p class="small" style="margin-top:10px"><b>Tip:</b> ${esc(f.tip)}</p></div>
  </div>
  <section class="book card" id="book" aria-label="Flights and places to stay">
   <div class="bk"><h4>Flights</h4><p class="small muted">We don't have live fares. These open a search on each site, filled in with your airport and trip dates, so you can compare real prices.</p>
    <div class="field" style="margin:12px 0"><label for="homeAp">Your home airport</label><input id="homeAp" type="text" maxlength="3" placeholder="e.g. LHR" style="text-transform:uppercase;max-width:140px" value="${esc((localStorage.home || "").toUpperCase())}"></div>
    <p class="small" id="bkDates"></p><div class="bk-links" id="bkFlights"></div></div>
   <div class="bk"><h4>Where to stay</h4><div id="stays"><p class="small muted"><span class="spin"></span> Loading</p></div></div>
  </section>
  <div id="pmap" class="map" role="region" aria-label="Map of the itinerary" tabindex="0"></div>
  <div class="legend-map"><label><input type="checkbox" id="roads" checked> Show road routes</label><span>Numbers are stops, coloured by day. Square pins are hotels (approximate location).</span></div>
  <ol class="days">${p.days.map(d => `<li class="day card"><button class="dn" data-day="${d.day}" style="background:${TravelMap.colors[(d.day - 1) % 7]}" aria-label="Show day ${d.day} on the map">${d.day}</button><div class="db">
    <h3>${d.city ? `<small class="eyebrow">${esc(d.city)}</small><br>` : ""}${esc(d.title)}${d.daytrip ? ' <span class="tag">day trip</span>' : ""}</h3><p>${esc(d.text)}</p>
    <div class="stops">${d.stops.map(s => `<a class="stop" target="_blank" rel="noopener" href="${mapsLink(s.lat, s.lon)}" title="Open in Maps">${Art.kind(s.kind)}${esc(s.name)}</a>`).join("")}</div>
    <div class="road" id="road${d.day}">${d.km ? `about ${d.km} km between stops` : ""}</div></div></li>`).join("")}</ol>`;
  drawPlanMap(); loadWeather(city, month); initBook(p, f.airport_code);
}
/* ---------- flights and stays ---------- */
const iso = d => d.toISOString().slice(0, 10), addDays = (s, n) => { const d = new Date(s + "T12:00:00Z"); d.setUTCDate(d.getUTCDate() + n); return iso(d); };
function bookDates(p) { const a = $("#startDate").value; return a ? { a, b: addDays(a, p.days.length) } : null; }
function drawFlights(p, code) {
  const home = ($("#homeAp").value || "").replace(/[^a-z]/gi, "").toUpperCase(), dt = bookDates(p), ext = Art.icon("external", 13);
  const g = `https://www.google.com/travel/flights?q=${encodeURIComponent(`Flights ${home ? "from " + home + " " : ""}to ${code}${dt ? ` on ${dt.a} through ${dt.b}` : ""}`)}`;
  const links = [["Google Flights", g]];
  if (home.length === 3) links.push(["Skyscanner", `https://www.skyscanner.net/transport/flights/${home.toLowerCase()}/${code.toLowerCase()}/${dt ? dt.a.slice(2).replaceAll("-", "") + "/" + dt.b.slice(2).replaceAll("-", "") + "/" : ""}`],
    ["Kayak", `https://www.kayak.com/flights/${home}-${code}${dt ? "/" + dt.a + "/" + dt.b : ""}`]);
  $("#bkDates").textContent = `${home.length === 3 ? home : "Anywhere"} to ${code}${dt ? ", " + dt.a + " to " + dt.b : ""}. Flights are not in the budget above.`;
  $("#bkFlights").innerHTML = links.map(([l, u]) => `<a class="btn btn-sm" href="${u}" target="_blank" rel="noopener">${Art.icon("plane")}${l} ${ext}</a>`).join("") + (home.length === 3 ? "" : `<span class="hint">Add your home airport for Skyscanner and Kayak.</span>`);
}
async function drawStays(p) {
  const legs = p.legs && p.legs.length ? p.legs : [{ destination: firstCity(p), hotel: p.hotel, days: p.days.length }], dt = bookDates(p), rooms = p.budget.rooms || 1;
  try {
    const data = await Promise.all(legs.map(l => api("/api/destination/" + encodeURIComponent(l.destination))));
    $("#stays").innerHTML = data.map((d, i) => {
      const l = legs[i], mine = d.hotels.find(h => h.name === l.hotel), hs = [...d.hotels].sort((x, y) => x.price - y.price), cheapest = hs[0].price;
      const label = h => h.name === l.hotel ? `<span class="tag">In your plan</span>` : h.price === cheapest ? `<span class="tag">Cheapest</span>` : mine && h.price > mine.price ? `<span class="tag">Upgrade</span>` : "";
      const url = h => `https://www.booking.com/searchresults.html?ss=${encodeURIComponent(h.name + " " + l.destination)}${legs.length === 1 && dt ? `&checkin=${dt.a}&checkout=${dt.b}` : ""}&group_adults=${p.budget.travelers || 1}&no_rooms=${rooms}`;
      return (legs.length > 1 ? `<div class="label" style="margin:${i ? 16 : 0}px 0 8px">${esc(l.destination)}, ${plural(l.days, "night")}</div>` : "") +
        hs.map(h => `<a class="stay${h.name === l.hotel ? " mine" : ""}" href="${url(h)}" target="_blank" rel="noopener"><span><b>${esc(h.name)}</b> ${label(h)}<br><small class="muted">${esc(h.category)} · about ${Money.fmt(h.price * l.days * rooms)} for ${plural(l.days, "night")}</small></span><span class="pr">${Money.fmt(h.price)}<small>a night</small></span></a>`).join("");
    }).join("") + `<p class="hint" style="margin-top:10px">Nightly prices are estimates from our data. Booking.com opens with your dates and group size filled in.</p>`;
  } catch { $("#stays").innerHTML = `<p class="small muted">Could not load stays right now.</p>`; }
}
function initBook(p, code) {
  drawFlights(p, code); drawStays(p);
  $("#homeAp").oninput = e => { const v = e.target.value.replace(/[^a-z]/gi, "").toUpperCase(); e.target.value = v; localStorage.home = v; drawFlights(p, code); };
  $("#startDate").addEventListener("change", () => { drawFlights(p, code); drawStays(p); });
}
function drawPlanMap() {
  const p = state.plan; if (!p) return;
  state.mapH = TravelMap.draw($("#pmap"), p, { roads: $("#roads").checked, onRoad: (day, r) => { const el = $("#road" + day); if (el) el.textContent = `about ${r.km.toFixed(1)} km by road · ${Math.round(r.min)} min driving`; } });
}
async function loadWeather(city, month) {
  const box = $("#wx"); if (!box) return;
  try {
    const w = await api(`/api/weather?destination=${encodeURIComponent(city)}&month=${month}`, undefined, { noRedirect: true }); if (!$("#wx")) return;
    const days = w.forecast.map(d => `<div class="${wxIcon(d.label) === "rain" ? "rain" : ""}" title="${esc(d.label)}, ${d.rain_pct ?? 0}% chance of rain">${new Date(d.date + "T00:00").toLocaleDateString(undefined, { weekday: "short" })}${Art.icon(wxIcon(d.label))}<b>${d.max}°</b>${d.min}°</div>`).join("");
    box.innerHTML = (days ? `<div class="label" style="margin-bottom:2px">Next 7 days</div><div class="wx">${days}</div>` : "") +
      `<p class="small" style="margin-top:10px">${w.climate ? `In ${MON[month - 1]} ${w.climate.year}: highs around <b>${w.climate.avg_max}°C</b>, lows <b>${w.climate.avg_min}°C</b>, ${w.climate.rainy_days} rainy days.` : `Usually around <b>${w.avg_temp_c}°C</b>.`}</p>` +
      `<p class="hint">${w.source === "open-meteo" ? "Source: Open-Meteo." : "Live weather isn't available right now, so this is the average from our data."}</p>`;
  } catch { box.innerHTML = `<p class="small muted">Weather isn't available right now.</p>`; }
}
$("#plan").addEventListener("click", async e => {
  const d = e.target.closest("[data-day]");
  if (d && state.mapH) { $("#pmap").scrollIntoView({ behavior: "smooth", block: "center" }); return state.mapH.focusDay(+d.dataset.day); }
  const b = e.target.closest("[data-pa]"); if (!b) return; const p = state.plan, a = b.dataset.pa;
  try {
    if (a === "save") { b.disabled = true; await api("/api/favorites", { destination: p.destination, hotel: p.hotel, days: p.days.length, plan: p }); b.innerHTML = Art.icon("check") + "Saved"; toast("Saved to your trips"); }
    if (a === "share") { const j = await api("/api/share", { plan: p }); copyText(location.origin + j.path, "Link copied. Anyone with it can view this plan."); }
    if (a === "copy") copyText(planText(p), "Itinerary copied");
    if (a === "print") print();
    if (a === "ics") { const v = $("#startDate").value; if (!v) return toast("Choose a start date first"); download(`${Art.slug(p.destination)}-trip.ics`, makeIcs(p, v), "text/calendar"); toast("Calendar file downloaded"); }
  } catch (err) { b.disabled = false; toast(err.message); }
});
$("#plan").addEventListener("change", e => { if (e.target.id === "roads") drawPlanMap(); });

/* ---------- saved trips ---------- */
async function loadSaved() {
  const box = $("#saved"); box.innerHTML = `<p class="muted"><span class="spin"></span> Loading</p>`;
  const list = await api("/api/favorites"); state.saved = list;
  box.innerHTML = list.length ? list.map(f => `<article class="saved card" data-id="${f.id}">${Art.media(f.destination, f.plan?.facts?.trip_type || "city")}<div><h3>${esc(f.destination)}</h3>
    <p class="small muted">${esc(f.hotel)} · ${plural(f.days, "day")}${f.created ? " · saved " + esc(f.created) : ""}</p>
    <label class="vh" for="note${f.id}">Notes</label><textarea id="note${f.id}" data-note maxlength="500" placeholder="Add a note: who is coming, what to book…">${esc(f.note)}</textarea>
    <div class="rowbtns" style="margin:10px 0 0"><button class="btn btn-sm btn-primary" data-s="open">${Art.icon("map")}Open itinerary</button><button class="btn btn-sm" data-s="share">${Art.icon("share")}Share</button><button class="btn btn-sm btn-ghost" data-s="rm">${Art.icon("trash")}Remove</button></div></div></article>`).join("")
    : `<div class="empty">${Art.media("Saved start", "romantic")}<h3>Nothing saved yet</h3><p>Press Save on a result or an itinerary and it will wait for you here, notes and all.</p></div>`;
}
async function savedPlan(f) { return f.plan || api("/api/plan", { destination: f.destination.split(" → ")[0], hotel: f.hotel, days: Math.min(f.days, 21) }); }
$("#saved").addEventListener("click", async e => {
  const b = e.target.closest("[data-s]"); if (!b) return; const id = +b.closest("[data-id]").dataset.id, f = state.saved.find(x => x.id === id);
  try {
    if (b.dataset.s === "open") showPlan(await savedPlan(f), {});
    if (b.dataset.s === "share") { const j = await api("/api/share", { plan: await savedPlan(f) }); copyText(location.origin + j.path, "Link copied"); }
    if (b.dataset.s === "rm") { await api("/api/favorites/remove", { id }); toast("Removed"); loadSaved(); }
  } catch (err) { toast(err.message); }
});
$("#saved").addEventListener("change", async e => { if (!e.target.matches("[data-note]")) return; try { await api("/api/favorites/" + e.target.closest("[data-id]").dataset.id, { note: e.target.value }, { method: "PATCH" }); toast("Note saved"); } catch (err) { toast(err.message); } });

/* ---------- compare ---------- */
async function renderCompare() {
  const box = $("#compare");
  if (state.cmp.length < 2) { box.innerHTML = `<div class="empty">${Art.media("Compare start", "culture")}<h3>Compare places side by side</h3><p>Press Compare on two or three results (${state.cmp.length} chosen so far) and their costs, seasons and crowds line up here.</p></div>`; return; }
  box.innerHTML = `<p class="muted"><span class="spin"></span> Loading</p>`;
  const d = await Promise.all(state.cmp.map(n => api("/api/destination/" + encodeURIComponent(n))));
  const R = (l, f) => `<tr><th scope="row">${l}</th>${d.map(x => `<td>${f(x)}</td>`).join("")}</tr>`, cheapest = x => Math.min(...x.hotels.map(h => h.price));
  box.innerHTML = `<div class="scroll-x"><table class="cmp"><tr><td></td>${d.map(x => `<td class="head">${Art.media(x.destination, x.trip_type)}<h3>${esc(x.destination)}</h3><button class="link small" data-rm="${esc(x.destination)}">Remove</button></td>`).join("")}</tr>
   ${R("Country", x => esc(x.country))}${R("Trip type", x => cap(esc(x.trip_type)))}${R("Best months", x => x.best_months.map(m => MO[m - 1]).join(", "))}${R("Average temp", x => x.avg_temp_c + "°C")}
   ${R("Crowds", x => cap(esc(x.crowd_level)))}${R("Rating", x => x.rating)}${R("Daily spend", x => Money.fmt(x.daily_spend_eur))}${R("Hotels from", x => Money.fmt(cheapest(x)) + " / night")}
   ${R("Language", x => esc(x.language))}${R("Airport", x => esc(x.airport_code))}</table></div>`;
}
$("#compare").onclick = e => { const b = e.target.closest("[data-rm]"); if (b) { state.cmp = state.cmp.filter(x => x !== b.dataset.rm); drawTabs("compare"); renderCompare(); } };

/* ---------- currency ---------- */
const CURS = ["EUR", "AED", "USD", "GBP", "SAR", "INR"];
function repaint() { drawGuided(); renderResults(); if (state.plan) renderPlan(); if (state.tab === "compare") renderCompare(); }
function changeCurrency(c) {
  const old = Money.rate(); Money.set(c); if (G.total) G.total = String(Math.round(+G.total / old * Money.rate()));
  $("#cur").value = c; $("#sCur").value = c; fillRate(); repaint();
}
$("#cur").onchange = e => changeCurrency(e.target.value);
function fillRate() { const r = $("#sRate"); r.disabled = Money.cur === "EUR"; r.value = Money.cur === "EUR" ? 1 : +Money.rate().toFixed(4); $("#sRateNote").textContent = Money.cur === "EUR" ? "Euros are the base currency." : (localStorage["rate_" + Money.cur] ? "Using the rate you typed. Clear the box to go back to the automatic rate." : Money.source === "live" ? "Live rate, refreshed twice a day." : "Approximate rate: type your own if you know a better one."); }

/* ---------- admin ---------- */
const initAdmin = () => { if (!state.me.admin) return; $("#sAdmin").hidden = false; $("#retrain").onclick = async e => { const b = e.currentTarget; b.disabled = true; b.innerHTML = `<span class="spin"></span> Training, about 15 seconds`; try { await api("/api/admin/retrain", {}); toast("Ranking retrained"); } catch (x) { toast(x.message); } b.disabled = false; b.innerHTML = Art.icon("refresh") + "Retrain the ranking now"; }; $("#retrain").innerHTML = Art.icon("refresh") + "Retrain the ranking now"; };

/* ---------- settings ---------- */
const dlg = $("#settings"), cleared = () => ["sNameOk", "sPwOk"].forEach(i => $("#" + i).textContent = "");
$("#meBtn").onclick = () => {
  $("#sWho").textContent = `${state.me.email}${state.me.since ? " · member since " + state.me.since : ""}`; $("#sNameIn").value = state.me.name; $("#sHome").value = localStorage.home || ""; $("#sTheme").value = Theme.get();
  $("#sCur").value = Money.cur; fillRate(); cleared(); ["sPwErr", "sDelErr"].forEach(i => $("#" + i).textContent = ""); dlg.showModal();
};
$("#sClose").onclick = () => dlg.close(); dlg.addEventListener("click", e => { if (e.target === dlg) dlg.close(); });
$("#sCur").onchange = e => changeCurrency(e.target.value);
$("#sRate").oninput = e => { const v = parseFloat(e.target.value); if (v > 0) localStorage["rate_" + Money.cur] = v; else localStorage.removeItem("rate_" + Money.cur); repaint(); };
$("#sHome").oninput = e => { localStorage.home = e.target.value.replace(/[^a-z]/gi, "").toUpperCase(); e.target.value = localStorage.home; if (state.plan) renderPlan(); };
$("#sTheme").onchange = e => Theme.set(e.target.value);
$("#sName").onsubmit = async e => { e.preventDefault(); try { await api("/api/account", { name: $("#sNameIn").value.trim() }, { method: "PATCH" }); state.me.name = $("#sNameIn").value.trim(); setMe(); $("#sNameOk").textContent = "Saved"; } catch (err) { $("#sNameOk").textContent = err.message; } };
$("#sPw").onsubmit = async e => {
  e.preventDefault(); $("#sPwErr").textContent = ""; $("#sPwOk").textContent = "";
  try { await api("/api/account", { current_password: $("#sPwOld").value, new_password: $("#sPwNew").value }, { method: "PATCH" }); $("#sPwOk").textContent = "Password changed. Other devices were logged out."; $("#sPwOld").value = $("#sPwNew").value = ""; }
  catch (err) { $("#sPwErr").textContent = err.message; }
};
$("#sExport").onclick = async () => { try { download("roamly-my-data.json", JSON.stringify(await api("/api/account/export"), null, 2), "application/json"); } catch (e) { toast(e.message); } };
$("#sDel").onsubmit = async e => {
  e.preventDefault(); $("#sDelErr").textContent = ""; if (!confirm("Delete your account and everything in it? This cannot be undone.")) return;
  try { await api("/api/account/delete", { password: $("#sDelPw").value }); location.href = "/"; } catch (err) { $("#sDelErr").textContent = err.message; }
};
$("#sOut").onclick = async () => { await api("/api/logout", {}, { noRedirect: true }).catch(() => {}); location.href = "/"; };
const setMe = () => { $("#av").textContent = state.me.name.trim()[0]?.toUpperCase() || "?"; $("#meName").textContent = state.me.name.split(" ")[0]; };

/* ---------- keyboard + voice ---------- */
document.addEventListener("keydown", e => { if (e.key === "/" && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName) && !dlg.open) { e.preventDefault(); setMode("chat"); $("#t").focus(); } });
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
if (!SR) $("#mic").hidden = true; else { const rec = new SR(); rec.lang = navigator.language || "en-US"; rec.onresult = e => { $("#t").value = e.results[0][0].transcript; $("#f").requestSubmit(); }; $("#mic").onclick = () => rec.start(); }

/* ---------- start ---------- */
(async function init() {
  try { state.me = await api("/api/me"); } catch { return; }
  setMe(); initAdmin(); await Money.load(); $("#cur").innerHTML = $("#sCur").innerHTML = CURS.filter(c => Money.rates[c] || c === "EUR").map(c => `<option>${c}</option>`).join(""); $("#cur").value = Money.cur;
  try { state.types = (await api("/api/options")).trip_types; } catch { /* keep defaults */ }
  setMode(state.mode, true); drawGuided(); renderResults(); tab("results");
  try { const s = await api("/api/chat/history"); s.history.forEach(h => addMsg(h.role === "user" ? "user" : "bot", h.text)); if (!s.history.length) greet(); drawMem(s.memory); applySlots(s.slots); }
  catch (e) { greet(); drawMem([]); }
  quick("", null);
})();
