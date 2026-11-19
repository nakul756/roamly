/* Art: flat "travel poster" scenes drawn in SVG (one per trip type, coloured per destination), line icons and the logo.
   If /images/destinations/<slug>.jpg exists it is shown on top of the scene (see Art.media). */
const Art = (() => {
  // sky, sun, far, mid, near, light
  const PAL = [
    ["#f3d9a4", "#cf4f2c", "#e6a273", "#b5543a", "#5f2b25", "#f8efd8"],
    ["#cfe3df", "#e7b04a", "#8db6ae", "#4c8789", "#234a55", "#f7f1de"],
    ["#eadac2", "#c5452b", "#c9a37c", "#8a6948", "#3d3731", "#faf3e2"],
    ["#d8e1ee", "#efb158", "#9eb2cf", "#5b79a1", "#2a3d61", "#faf4e3"],
    ["#f2d6cf", "#dfa03a", "#d79992", "#a0545a", "#4a293b", "#fbf0e0"],
    ["#d6e5ce", "#e6c04b", "#9bbf99", "#598d68", "#294f3f", "#f8f2de"],
    ["#efe2c0", "#2c6868", "#d8b86f", "#af8943", "#5a4426", "#fbf5e1"],
    ["#ded5e9", "#e68b47", "#b4a2ce", "#7a69a5", "#392e5c", "#f9f1e1"],
  ];
  const hash = s => { let h = 2166136261; for (const c of String(s)) h = Math.imul(h ^ c.charCodeAt(0), 16777619); return h >>> 0; };
  const rng = seed => () => { seed |= 0; seed = seed + 0x6D2B79F5 | 0; let t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
  const slug = n => String(n).toLowerCase().split(" → ")[0].replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

  const SCENES = {
    beach: (p, r) => {
      const sx = 90 + r() * 220, sy = 92 + r() * 20;
      let s = `<circle cx="${sx}" cy="${sy}" r="${34 + r() * 8}" fill="${p[1]}"/>`;
      s += `<path d="M0 138 Q70 ${110 + r() * 14} 140 132 T290 126 T400 134 V160 H0Z" fill="${p[2]}"/>`;
      s += `<rect y="140" width="400" height="70" fill="${p[3]}"/>`;
      for (let i = 0; i < 7; i++) s += `<path d="M${r() * 340} ${148 + i * 9} q10 -5 20 0 t20 0 t20 0" stroke="${p[5]}" stroke-width="1.6" fill="none" opacity=".55"/>`;
      const bx = 60 + r() * 200;
      s += `<path d="M${bx} 160 h46 l-8 10 h-30z" fill="${p[4]}"/><path d="M${bx + 22} 158 V122 L${bx + 44} 156z" fill="${p[5]}"/><path d="M${bx + 20} 158 V130 L${bx + 4} 156z" fill="${p[1]}"/>`;
      s += `<path d="M0 205 Q120 178 250 196 T400 188 V250 H0Z" fill="${p[5]}"/><path d="M0 225 Q140 205 270 220 T400 214 V250 H0Z" fill="${p[4]}" opacity=".9"/>`;
      const ux = 40 + r() * 70;
      s += `<path d="M${ux} 214 L${ux + 8} 178" stroke="${p[4]}" stroke-width="3"/><path d="M${ux - 22} 184 a30 24 0 0 1 60 -4z" fill="${p[1]}"/><path d="M${ux + 8} 180 a8 20 0 0 1 22 0z" fill="${p[5]}"/>`;
      return s;
    },
    city: (p, r) => {
      let s = `<circle cx="${280 + r() * 70}" cy="${70 + r() * 20}" r="30" fill="${p[1]}"/>`;
      for (let x = 0, i = 0; x < 400; i++) { const w = 18 + r() * 26, h = 50 + r() * 70; s += `<rect x="${x}" y="${170 - h}" width="${w}" height="${h + 40}" fill="${p[2]}"/>`; x += w + 2; }
      for (let x = -4; x < 400;) {
        const w = 26 + r() * 30, h = 60 + r() * 80, y = 190 - h;
        s += `<rect x="${x}" y="${y}" width="${w}" height="${h + 30}" fill="${p[3]}"/>`;
        if (r() > .55) s += `<path d="M${x} ${y} l${w / 2} -22 l${w / 2} 22z" fill="${p[4]}"/>`;
        for (let wy = y + 10; wy < 186; wy += 14) for (let wx = x + 6; wx < x + w - 6; wx += 10) if (r() > .45) s += `<rect x="${wx}" y="${wy}" width="4" height="6" fill="${p[5]}" opacity=".85"/>`;
        x += w + 4 + r() * 6;
      }
      const tx = 150 + r() * 100;
      s += `<path d="M${tx} 186 L${tx + 9} 70 L${tx + 18} 186z" fill="${p[4]}"/><rect x="${tx + 6}" y="52" width="6" height="22" fill="${p[4]}"/>`;
      s += `<rect y="188" width="400" height="62" fill="${p[4]}"/>`;
      for (let i = 0; i < 6; i++) s += `<path d="M${r() * 360} ${200 + i * 8} h${30 + r() * 40}" stroke="${p[5]}" stroke-width="1.5" opacity=".35"/>`;
      return s;
    },
    culture: (p, r) => {
      const cx = 160 + r() * 80;
      let s = `<circle cx="${cx + 60}" cy="${90}" r="${38}" fill="${p[1]}"/>`;
      s += `<path d="M0 170 Q100 ${150 + r() * 10} 200 168 T400 160 V250 H0Z" fill="${p[2]}"/>`;
      const x0 = cx - 90;
      s += `<path d="M${x0 - 10} 84 L${x0 + 100} 46 L${x0 + 210} 84z" fill="${p[3]}"/><rect x="${x0 - 10}" y="84" width="220" height="12" fill="${p[5]}"/>`;
      for (let i = 0; i < 7; i++) s += `<rect x="${x0 + i * 32}" y="96" width="14" height="76" fill="${p[5]}"/><rect x="${x0 + i * 32 - 2}" y="96" width="18" height="5" fill="${p[4]}" opacity=".5"/>`;
      s += `<path d="M${x0 + 60} 52 a40 32 0 0 1 80 0z" fill="${p[4]}"/><rect x="${x0 + 98}" y="14" width="4" height="8" fill="${p[4]}"/>`;
      for (let i = 0; i < 4; i++) s += `<rect x="${x0 - 20 - i * 6}" y="${172 + i * 8}" width="${240 + i * 12}" height="8" fill="${i % 2 ? p[3] : p[5]}"/>`;
      s += `<rect y="214" width="400" height="36" fill="${p[4]}"/>`;
      for (let i = 0; i < 3; i++) { const tx = 20 + r() * 340; s += `<path d="M${tx} 214 v-34" stroke="${p[4]}" stroke-width="4"/><ellipse cx="${tx}" cy="172" rx="9" ry="22" fill="${p[4]}"/>`; }
      return s;
    },
    mountain: (p, r) => {
      let s = `<circle cx="${70 + r() * 80}" cy="${64 + r() * 14}" r="26" fill="${p[1]}"/>`;
      const peak = (x, h, w, col, snow) => {
        let t = `<path d="M${x - w} 190 L${x} ${190 - h} L${x + w} 190z" fill="${col}"/>`;
        if (snow) t += `<path d="M${x} ${190 - h} l${w * .3} ${h * .28} l-${w * .14} -${h * .08} l-${w * .16} ${h * .1} l-${w * .14} -${h * .1} l-${w * .12} ${h * .08}z" fill="${p[5]}"/>`;
        return t;
      };
      s += peak(90 + r() * 40, 110 + r() * 20, 120, p[2], true) + peak(300 + r() * 40, 120 + r() * 20, 130, p[2], true);
      s += peak(200 + r() * 40, 140 + r() * 20, 150, p[3], true);
      s += `<path d="M0 190 Q100 170 200 186 T400 178 V250 H0Z" fill="${p[4]}"/>`;
      for (let i = 0; i < 16; i++) { const x = r() * 400, y = 196 + r() * 40, h = 22 + r() * 22; s += `<path d="M${x} ${y} l7 ${h * .0} l-3.5 -${h}z" fill="${p[4]}"/><path d="M${x - 5} ${y - h * .45} l12 0 l-6 -${h * .6}z" fill="${p[3]}" opacity=".7"/>`; }
      const cx = 40 + r() * 80;
      s += `<path d="M${cx} 120 L${cx + 230} 62" stroke="${p[5]}" stroke-width="1.5" opacity=".8"/><rect x="${cx + 110}" y="${88}" width="16" height="11" rx="2" fill="${p[1]}" transform="rotate(-14 ${cx + 118} 94)"/>`;
      return s;
    },
    nature: (p, r) => {
      let s = `<rect width="400" height="250" fill="${p[4]}"/>`;
      for (let i = 0; i < 40; i++) s += `<circle cx="${r() * 400}" cy="${r() * 120}" r="${.6 + r() * 1.2}" fill="${p[5]}" opacity="${.4 + r() * .5}"/>`;
      for (let i = 0; i < 3; i++) { const y = 40 + i * 22; s += `<path d="M0 ${y + r() * 20} Q100 ${y - 30 + r() * 20} 200 ${y + 10} T400 ${y - 10 + r() * 20} V${y + 46} Q300 ${y + 70} 200 ${y + 40} T0 ${y + 60}z" fill="${[p[1], p[2], p[5]][i]}" opacity="${.5 - i * .1}"/>`; }
      s += `<path d="M0 170 Q90 140 180 168 T400 150 V250 H0Z" fill="${p[3]}"/><path d="M0 205 Q120 180 240 202 T400 192 V250 H0Z" fill="${p[2]}" opacity=".35"/>`;
      s += `<path d="M0 214 Q140 196 280 212 T400 204 V250 H0Z" fill="#0e0d0c" opacity=".55"/>`;
      for (let i = 0; i < 22; i++) { const x = r() * 400, h = 30 + r() * 50, y = 222 + r() * 20; s += `<path d="M${x} ${y} l-${h * .2} 0 l${h * .2} -${h * .55} l${h * .2} ${h * .55}z M${x - h * .17} ${y - h * .3} l${h * .34} 0 l-${h * .17} -${h * .5}z" fill="#0e0d0c" opacity=".8"/>`; }
      return s;
    },
    romantic: (p, r) => {
      let s = `<circle cx="${200 + (r() - .5) * 120}" cy="130" r="58" fill="${p[1]}"/>`;
      s += `<rect y="130" width="400" height="120" fill="${p[3]}"/><rect y="130" width="400" height="120" fill="${p[1]}" opacity=".12"/>`;
      for (let i = 0; i < 9; i++) s += `<rect x="${150 + r() * 100 - i * 4}" y="${136 + i * 9}" width="${60 - i * 4 + r() * 20}" height="3" rx="1.5" fill="${p[1]}" opacity="${.5 - i * .04}"/>`;
      s += `<path d="M0 132 Q80 118 150 130 T300 126 T400 130 V140 H0z" fill="${p[2]}"/>`;
      s += `<path d="M-10 170 Q200 120 410 170 V182 H-10z" fill="${p[4]}"/>`;
      for (let i = 0; i < 6; i++) s += `<path d="M${10 + i * 70} 182 v-1 a28 24 0 0 1 56 0 v1z" fill="${p[3]}" opacity=".9"/>`;
      s += `<path d="M0 100 Q100 70 200 96 T400 80" stroke="${p[4]}" stroke-width="1.5" fill="none"/>`;
      for (let i = 0; i < 12; i++) { const x = 8 + i * 34, y = 100 - Math.sin(i * .6) * 6 + (i % 2) * 4; s += `<circle cx="${x}" cy="${y + 8}" r="4.5" fill="${p[5]}"/><circle cx="${x}" cy="${y + 8}" r="8" fill="${p[5]}" opacity=".25"/>`; }
      s += `<path d="M0 214 Q150 196 300 212 T400 206 V250 H0z" fill="${p[4]}"/>`;
      return s;
    },
  };

  const scene = (name, type, opts = {}) => {
    const h = hash(name), p = PAL[h % PAL.length], r = rng(h);
    const body = (SCENES[type] || SCENES.city)(p, r);
    const sky = type === "nature" ? "" : `<rect width="400" height="250" fill="${p[0]}"/>`;
    return `<svg class="art" viewBox="0 0 400 250" preserveAspectRatio="xMidYMid slice" role="img" aria-label="Illustration of ${String(name).replace(/[<>&"]/g, "")}">${sky}${body}</svg>`;
  };

  /* Illustration, with a real photo laid on top if one exists. */
  const media = (name, type, cls = "") =>
    `<div class="media ${cls}">${scene(name, type)}<img src="/images/destinations/${slug(name)}.jpg" alt="" loading="lazy" onerror="this.remove()"></div>`;

  const ICONS = {
    beach: "M7 14a5 5 0 0 1 10 0M12 4v2.5M5.4 6.6l1.8 1.8M18.6 6.6l-1.8 1.8M3 18c2-2 4-2 6 0s4 2 6 0 4-2 6 0",
    city: "M4 21V9l6-3v15M10 21V4l10 4v13M3 21h18M13 10h1.5M13 14h1.5M17 11.5h1.5M17 15.5h1.5",
    culture: "M3 9l9-5 9 5M5.5 9.5v8M10 9.5v8M14 9.5v8M18.5 9.5v8M3 20h18M4 17.5h16",
    mountain: "M2 20l7.5-13 4 6.5 3-4.5L22 20zM9.5 7l-2.2 3.8 2-1 1.6 1.2",
    nature: "M12 3l5 7.5h-3l4 6.5H6l4-6.5H7zM12 17v4",
    romantic: "M12 20s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.3a4.3 4.3 0 0 1 7.5 2.5C19.5 15.4 12 20 12 20z",
    map: "M9 4L3 6v14l6-2 6 2 6-2V4l-6 2zM9 4v14M15 6v14",
    bookmark: "M6 3.5h12V21l-6-4-6 4z",
    thumbup: "M7 11v9H4v-9zM7 11l4-8c1.6 0 2.6 1 2.6 2.6V9H19a2 2 0 0 1 2 2.3l-1.2 7A2 2 0 0 1 17.8 20H7",
    thumbdown: "M7 13V4H4v9zM7 13l4 8c1.6 0 2.6-1 2.6-2.6V15H19a2 2 0 0 0 2-2.3l-1.2-7A2 2 0 0 0 17.8 4H7",
    compare: "M7 4v16M17 4v16M3 8l4-4 4 4M13 16l4 4 4-4",
    info: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM12 11v6M12 7.6v.4",
    share: "M12 15V3M7 8l5-5 5 5M5 14v6.5h14V14",
    copy: "M8.5 8.5h11v11h-11zM4.5 15.5v-11h11",
    print: "M7 8V3.5h10V8M7 17.5H4v-8h16v8h-3M7 14h10v6.5H7z",
    calendar: "M4 6h16v15H4zM4 10.5h16M8 3v4M16 3v4",
    plane: "M21 3L3 11l7 3 3 7zM10 14L21 3",
    bed: "M3 19V6M3 15h18v4M21 15v-2.5A3 3 0 0 0 18 9.500h-7V15M7 12.2a1.7 1.7 0 1 0 0-.1",
    sun: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 2.5v2M12 19.500v2M2.500 12h2M19.500 12h2M5.300 5.300l1.400 1.400M17.300 17.300l1.400 1.400M5.300 18.700l1.400-1.400M17.300 6.700l1.400-1.400",
    cloud: "M7 18a4 4 0 0 1-.3-8 5.500 5.500 0 0 1 10.600 1.300A3.400 3.400 0 0 1 17 18z",
    rain: "M7 15a4 4 0 0 1-.3-8 5.500 5.500 0 0 1 10.600 1.300A3.400 3.400 0 0 1 17 15zM9 18l-1 3M13 18l-1 3M17 18l-1 3",
    send: "M3 11l18-8-8 18-2.500-7.500z",
    mic: "M12 3a3 3 0 0 0-3 3v5a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3zM6 11a6 6 0 0 0 12 0M12 17v4",
    sliders: "M4 7h9M17 7h3M4 17h3M11 17h9M15 4.500v5M9 14.500v5",
    check: "M5 12.500l4.500 4.500L19.500 7",
    close: "M6 6l12 12M18 6L6 18",
    dice: "M5 4h14a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1zM8.500 8.500h.01M15.500 8.500h.01M12 12h.01M8.500 15.500h.01M15.500 15.500h.01",
    user: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0",
    pin: "M12 21s7-6 7-12a7 7 0 0 0-14 0c0 6 7 12 7 12zM12 11.500a2.500 2.500 0 1 0 0-5 2.500 2.500 0 0 0 0 5z",
    flag: "M5 21V4h11l-2 4 2 4H5",
    eye: "M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zM12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6z",
    eyeoff: "M3 3l18 18M10.600 6.200A9.800 9.800 0 0 1 12 6c6 0 10 6 10 6a17 17 0 0 1-3 3.600M6.500 7.500C3.600 9.400 2 12 2 12s4 6 10 6a9.700 9.700 0 0 0 3.500-.7",
    moon: "M20 14.500A8 8 0 1 1 9.500 4a6.500 6.500 0 0 0 10.500 10.500z",
    food: "M5 3v8a2 2 0 0 0 2 2v8M9 3v8M7 3v6M17 3c-2 2-3 5-3 8h3v10",
    market: "M4 9h16l-1.500 11h-13zM8 9l3-5M16 9l-3-5",
    arrow: "M5 12h14M13 6l6 6-6 6",
    plus: "M12 5v14M5 12h14",
    minus: "M5 12h14",
    trash: "M4 7h16M9 7V4h6v3M6 7l1 14h10l1-14",
    external: "M14 4h6v6M20 4l-9 9M18 14v6H4V6h6",
    download: "M12 4v12M7 11l5 5 5-5M5 20h14",
    refresh: "M20 11a8 8 0 0 0-14.500-3.500L4 9M4 4v5h5M4 13a8 8 0 0 0 14.500 3.500L20 15M20 20v-5h-5",
    menu: "M4 7h16M4 12h16M4 17h16",
    lock: "M6 11h12v9H6zM8.500 11V8a3.500 3.500 0 0 1 7 0v3",
  };
  const KIND = { sight: "flag", museum: "culture", food: "food", market: "market", nature: "nature", view: "mountain", beach: "beach", park: "nature", nightlife: "moon" };
  const icon = (n, size) => `<svg viewBox="0 0 24 24" width="${size || 18}" height="${size || 18}" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${ICONS[n] || ICONS.pin}"/></svg>`;
  const kind = k => icon(KIND[k] || "flag", 15);
  const logo = `<svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="14" fill="none" stroke="currentColor" stroke-width="1.8"/><circle cx="16" cy="16" r="10.500" fill="none" stroke="currentColor" stroke-width=".8" stroke-dasharray="1.500 2.500"/><path d="M16 5.500l3 10.500-3 10.500-3-10.500z" fill="var(--accent)"/><path d="M16 5.500l3 10.500h-6z" fill="currentColor"/><circle cx="16" cy="16" r="1.600" fill="var(--paper)"/></svg>`;
  /* Wordmark. Two copies, one per theme (CSS shows the right one); "cream" is the light-ink copy for dark backgrounds such as photos. */
  const brand = variant => variant === "cream" ? `<img class="brand brand-cream brand-always" src="/images/brand/roamly-wordmark-cream.png" alt="Roamly">`
    : `<img class="brand brand-ink" src="/images/brand/roamly-wordmark.png" alt="Roamly"><img class="brand brand-cream" src="/images/brand/roamly-wordmark-cream.png" alt="" aria-hidden="true">`;
  return { scene, media, icon, kind, logo, brand, slug, hash, ICONS };
})();
