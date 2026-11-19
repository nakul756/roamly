/* Login, signup, forgot-password and reset-password pages. */
const PAGE = document.body.dataset.page;
$$("[data-logo]").forEach(l => l.innerHTML = `${Art.brand()}`);
$$("[data-art]").forEach(el => { const [n, t] = el.dataset.art.split("|"); el.outerHTML = Art.media(n, t); });
bindThemeButtons();
$$("[data-toggle]").forEach(b => {
  const input = $("#" + b.dataset.toggle), paint = () => { b.innerHTML = Art.icon(input.type === "password" ? "eye" : "eyeoff"); b.setAttribute("aria-label", input.type === "password" ? "Show password" : "Hide password"); };
  paint(); b.onclick = () => { input.type = input.type === "password" ? "text" : "password"; paint(); };
});

const form = $("#form"), submit = $("#submit"), formErr = $("#formErr");
/* Only same-site paths: no backslashes ("/\evil.com" is read as "//evil.com" by browsers) and no "//" (protocol-relative). */
const SAFE_NEXT = /^\/[A-Za-z0-9._\-/?=&%]*$/;
const nextUrl = () => { const n = new URLSearchParams(location.search).get("next"); return n && SAFE_NEXT.test(n) && !n.startsWith("//") && !n.includes("\\") ? n : "/app.html"; };
const setErr = (id, msg) => { const e = $("#e-" + id), i = $("#" + id); if (e) e.textContent = msg || ""; if (i) i.setAttribute("aria-invalid", msg ? "true" : "false"); return !msg; };
const showErr = m => { formErr.textContent = m; formErr.hidden = !m; };
const busy = (on, label) => { submit.disabled = on; submit.innerHTML = on ? `<span class="spin"></span> Please wait` : label; };
const okEmail = v => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v);

function strength(pw) {
  if (!pw) return [0, ""];
  let s = 0; if (pw.length >= 8) s++; if (pw.length >= 12) s++; if (/[a-z]/.test(pw) && /[A-Z]/.test(pw) || /[a-z]/i.test(pw) && /\d/.test(pw)) s++; if (/[^a-z0-9]/i.test(pw) || pw.length >= 16) s++;
  if (pw.length < 8) return [1, "Too short"]; return [Math.max(s, 1), ["", "Weak", "Okay", "Good", "Strong"][Math.max(s, 1)]];
}
if ($("#meter")) $("#password").addEventListener("input", e => { const [s, t] = strength(e.target.value); $("#meter").dataset.s = s; if (t) $("#strength").textContent = "Password strength: " + t; });

if (PAGE === "login" || PAGE === "signup") api("/api/me", undefined, { noRedirect: true }).then(() => location.replace(nextUrl())).catch(() => {});

form.addEventListener("submit", async ev => {
  ev.preventDefault(); showErr("");
  const label = submit.innerHTML;
  try {
    if (PAGE === "login") {
      const e = $("#email").value.trim(), p = $("#password").value;
      if (![setErr("email", okEmail(e) ? "" : "Enter a valid email address"), setErr("password", p ? "" : "Enter your password")].every(Boolean)) return;
      busy(true); await api("/api/login", { email: e, password: p, remember: $("#remember").checked }, { noRedirect: true }); location.href = nextUrl();
    } else if (PAGE === "signup") {
      const n = $("#name").value.trim(), e = $("#email").value.trim(), p = $("#password").value;
      if (![setErr("name", n ? "" : "Tell us what to call you"), setErr("email", okEmail(e) ? "" : "Enter a valid email address"), setErr("password", p.length >= 8 ? "" : "Use at least 8 characters")].every(Boolean)) return;
      busy(true); await api("/api/register", { name: n, email: e, password: p, remember: true }, { noRedirect: true }); location.href = nextUrl();
    } else if (PAGE === "forgot") {
      const e = $("#email").value.trim(); if (!setErr("email", okEmail(e) ? "" : "Enter a valid email address")) return;
      busy(true); await api("/api/forgot", { email: e }, { noRedirect: true }); $("#formOk").hidden = false; busy(false, "Send it again");
    } else if (PAGE === "reset") {
      const token = new URLSearchParams(location.search).get("token"), p = $("#password").value, c = $("#confirm").value;
      if (!token) { showErr("This link is missing its reset code. Open the link from your email again, or request a new one."); return; }
      if (![setErr("password", p.length >= 8 ? "" : "Use at least 8 characters"), setErr("confirm", p === c ? "" : "The passwords don't match")].every(Boolean)) return;
      busy(true); await api("/api/reset", { token, password: p }, { noRedirect: true }); $("#formOk").hidden = false; $$(".field", form).forEach(f => f.hidden = true); submit.hidden = true;
    }
  } catch (err) { showErr(err.message); busy(false, label); }
});
