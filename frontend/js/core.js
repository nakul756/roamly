/* Helpers shared by the app, landing and share pages. */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const MO = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const MON = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

async function api(url, body, opts = {}) {
  const o = { method: opts.method || (body !== undefined ? "POST" : "GET"), headers: {} };
  if (body !== undefined) { o.headers["Content-Type"] = "application/json"; o.body = JSON.stringify(body); }
  let r;
  try { r = await fetch(url, o); } catch { const e = new Error("Can't reach the server. Is it running?"); e.status = 0; throw e; }
  let j = null; try { j = await r.json(); } catch { /* not JSON */ }
  if (r.status === 401 && !opts.noRedirect) { location.href = "/login.html?next=" + encodeURIComponent(location.pathname + location.search); throw new Error("Please log in"); }
  if (!r.ok) {
    const e = new Error(typeof j?.detail === "string" ? j.detail : Array.isArray(j?.detail) ? "Please check what you entered." : "Something went wrong. Please try again.");
    e.status = r.status; throw e;
  }
  return j;
}

/* theme (the first paint is handled by theme.js) */
const Theme = {
  get() { return localStorage.getItem("theme") || "auto"; },
  set(t) { localStorage.setItem("theme", t); const eff = t === "auto" ? (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light") : t; document.documentElement.dataset.theme = eff; document.dispatchEvent(new Event("themechange")); },
  toggle() { this.set(document.documentElement.dataset.theme === "dark" ? "light" : "dark"); },
};
function bindThemeButtons() {
  $$("[data-theme-toggle]").forEach(b => {
    const paint = () => { b.innerHTML = Art.icon(document.documentElement.dataset.theme === "dark" ? "sun" : "moon", 19); b.setAttribute("aria-label", "Switch colour theme"); };
    paint(); b.onclick = () => { Theme.toggle(); paint(); };
  });
}

/* money: amounts are stored in EUR; rates come from /api/rates (live when the server can reach the internet) */
const Money = {
  cur: localStorage.getItem("cur") || "EUR", rates: { EUR: 1 }, source: "approximate",
  async load() { try { const j = await api("/api/rates", undefined, { noRedirect: true }); this.rates = j.rates; this.source = j.source; } catch { this.rates = { EUR: 1, AED: 4.3, USD: 1.15, GBP: 0.86, SAR: 4.3, INR: 95 }; } },
  rate() { const o = parseFloat(localStorage.getItem("rate_" + this.cur)); return this.cur === "EUR" ? 1 : (o > 0 ? o : this.rates[this.cur] || 1); },
  fmt(eur) { try { return new Intl.NumberFormat(undefined, { style: "currency", currency: this.cur, maximumFractionDigits: 0 }).format(eur * this.rate()); } catch { return Math.round(eur * this.rate()) + " " + this.cur; } },
  toEur(x) { return x / this.rate(); },
  set(c) { this.cur = c; localStorage.setItem("cur", c); },
};

/* in season / shoulder season (one month away from the best months) / off season */
const Season = { of(month, best) {
  if (!month || !best || !best.length) return { t: "", c: "" };
  const d = Math.min(...best.map(b => { const x = Math.abs(b - month) % 12; return Math.min(x, 12 - x); }));
  return d === 0 ? { t: "In season", c: "in" } : d === 1 ? { t: "Shoulder season", c: "shoulder" } : { t: "Off season", c: "off" };
} };

function toast(msg) {
  let t = $("#toast"); if (!t) { t = document.createElement("div"); t.id = "toast"; t.className = "toast"; t.setAttribute("role", "status"); document.body.append(t); }
  t.textContent = msg; t.classList.add("show"); clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("show"), 2600);
}
async function copyText(text, ok = "Copied") { try { await navigator.clipboard.writeText(text); toast(ok); } catch { prompt("Copy this:", text); } }
const mapsLink = (lat, lon) => `https://www.google.com/maps/search/?api=1&query=${lat},${lon}`;
function download(name, text, type) { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name; document.body.append(a); a.click(); setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500); }
