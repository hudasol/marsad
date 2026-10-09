/* Marsad watchpost: vanilla JS, canvas. No network except this server's /v1 API. */
(() => {
"use strict";
const $ = (id) => document.getElementById(id);
const css = getComputedStyle(document.documentElement);
const C = (n) => css.getPropertyValue(n).trim();
const COL = { trusted: C("--trusted"), degraded: C("--degraded"), denied: C("--denied"), raw: C("--raw"),
  advice: C("--advice"), truth: C("--truth"), bone: C("--bone"), dust: C("--dust"), dim: C("--dim"),
  line: C("--line"), line2: C("--line-2"), ink: C("--ink"), panel: C("--panel") };
const STATE_COL = { TRUSTED: COL.trusted, DEGRADED: COL.degraded, DENIED: COL.denied };
const HYP = [  // stack order bottom -> top
  ["nominal", "Nominal", "#2b3b48"], ["environmental_degradation", "Environmental", "#b8a95a"],
  ["jamming", "Jamming-like", "#4aa3df"], ["spoofing_jump", "Spoof: jump", "#e56b8f"],
  ["spoofing_drift", "Spoof: drift", "#9b7fe8"], ["replay_meaconing", "Replay", "#d9d9d9"]];
const ACTION = { USE_GNSS: "Use GNSS", USE_GNSS_WITH_CAUTION: "Use GNSS with caution",
  FALLBACK_REFERENCE: "Navigate on reference", HOLD_AND_ALERT: "Hold and alert operator" };
const FALLBACK = new Set(["FALLBACK_REFERENCE", "HOLD_AND_ALERT"]);
const MAXPTS = 6000;
let VIEW = "event";
try { VIEW = localStorage.getItem("marsad.view") || "event"; } catch (_) {}

// ------------------------------------------------------------------ state
const hash = new URLSearchParams(location.hash.replace(/^#/, ""));
const query = new URLSearchParams(location.search);
const KEY = hash.get("key") || query.get("key") || "";
const S = { vid: null, pts: [], origin: null, simulated: false, report: null, transitions: [], feed: [],
  tracks: [], sources: {}, map: null, demo: {}, vehicles: [], dirty: {}, lastState: null, es: null, retry: 0 };

async function api(path, opts = {}) {
  const h = Object.assign({ "Accept": "application/json" }, opts.headers || {});
  if (KEY) h["X-API-Key"] = KEY;
  if (opts.body) h["Content-Type"] = "application/json";
  const r = await fetch(path, Object.assign({}, opts, { headers: h }));
  let j = null; try { j = await r.json(); } catch (_) {}
  if (!r.ok) { const d = j && j.detail; throw new Error(typeof d === "string" ? d : d ? JSON.stringify(d) : r.statusText); }
  return j;
}
const fmtT = (t) => { if (t == null) return "--"; const m = Math.floor(t / 60), s = t - m * 60; return `${String(m).padStart(2, "0")}:${s.toFixed(1).padStart(4, "0")}`; };
const el = (tag, cls, txt) => { const e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; };
const mark = (k) => { S.dirty[k] = true; if (!S.raf) S.raf = requestAnimationFrame(frame); };

// ------------------------------------------------------------------ canvases
const cv = {};
for (const id of ["plot", "timeline", "posterior", "hexmap"]) {
  const c = $(id); cv[id] = { c, ctx: c.getContext("2d"), w: 0, h: 0 };
}
function fit(o) {
  const r = o.c.getBoundingClientRect(), d = window.devicePixelRatio || 1;
  const w = Math.max(10, Math.round(r.width)), h = Math.max(10, Math.round(r.height));
  if (o.c.width !== Math.round(w * d) || o.c.height !== Math.round(h * d)) { o.c.width = Math.round(w * d); o.c.height = Math.round(h * d); }
  o.w = w; o.h = h; o.ctx.setTransform(d, 0, 0, d, 0, 0);
}
const ro = new ResizeObserver(() => { for (const k in cv) mark(k); });
for (const k in cv) ro.observe(cv[k].c.parentElement);
window.addEventListener("resize", () => { for (const k in cv) mark(k); });

function frame() {
  S.raf = 0; const d = S.dirty; S.dirty = {};
  if (d.plot) drawPlot(); if (d.timeline) drawTimeline(); if (d.posterior) drawPosterior();
  if (d.hexmap) drawHex(); if (d.banner) renderBanner(); if (d.tracks) renderTracks();
}

function halo(ctx, text, x, y, color, align = "left", font) {
  if (font) ctx.font = font;
  ctx.textAlign = align; ctx.lineWidth = 4; ctx.strokeStyle = COL.panel; ctx.lineJoin = "round";
  ctx.strokeText(text, x, y); ctx.fillStyle = color; ctx.fillText(text, x, y);
}
function placed(ctx, text, x, y, color, font, right) {
  ctx.font = font; const tw = ctx.measureText(text).width;
  if (x + tw > right) halo(ctx, text, x - 24, y, color, "right", font); else halo(ctx, text, x, y, color, "left", font);
}
function niceStep(range, target) {
  const raw = range / target, p = 10 ** Math.floor(Math.log10(raw)), f = raw / p;
  return (f < 1.5 ? 1 : f < 3.5 ? 2 : f < 7.5 ? 5 : 10) * p;
}
const fmtM = (m) => (Math.abs(m) >= 1000 ? (m / 1000).toFixed(m % 1000 === 0 ? 0 : 1) + " km" : Math.round(m) + " m");
const meta = () => (S.vid === "demo" ? S.demo : S.meta) || {};
const onsetT = () => { const m = meta(); const v = m.event_start ?? m.attack_start; return v == null ? null : v; };

// ------------------------------------------------------------------ hero plot
function drawPlot() {
  const o = cv.plot; fit(o); const { ctx, w, h } = o; ctx.clearRect(0, 0, w, h);
  const ALL = S.pts; $("plot-empty").hidden = ALL.length > 0;
  if (!ALL.length) { $("plot-readout").textContent = ""; return; }
  const hasTruth = ALL.some((p) => p.truth);
  const tEnd = ALL[ALL.length - 1].t, o0 = onsetT();
  let P = ALL;
  if (VIEW === "offset" && hasTruth) return drawOffset(o, ALL, o0);
  if (VIEW !== "full") { const from = o0 != null && tEnd >= o0 - 5 ? o0 - 30 : tEnd - 150; P = ALL.filter((p) => p.t >= from); if (!P.length) P = ALL; }
  // bounds over everything that will be drawn
  let x0 = 1e18, x1 = -1e18, y0 = 1e18, y1 = -1e18;
  const ext = (a) => { if (!a) return; if (a[0] < x0) x0 = a[0]; if (a[0] > x1) x1 = a[0]; if (a[1] < y0) y0 = a[1]; if (a[1] > y1) y1 = a[1]; };
  for (const p of P) { ext(p.raw); ext(p.nav); ext(p.truth); }
  if (x0 > x1) return;
  const minSpan = 60; if (x1 - x0 < minSpan) { const c = (x0 + x1) / 2; x0 = c - minSpan / 2; x1 = c + minSpan / 2; }
  if (y1 - y0 < minSpan) { const c = (y0 + y1) / 2; y0 = c - minSpan / 2; y1 = c + minSpan / 2; }
  const pad = { l: 46, r: 132, t: 12, b: 30 };
  const aw = w - pad.l - pad.r, ah = h - pad.t - pad.b;
  const k = Math.min(aw / (x1 - x0), ah / (y1 - y0)) * 0.94;
  const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
  const X = (e) => pad.l + aw / 2 + (e - cx) * k, Y = (n) => pad.t + ah / 2 - (n - cy) * k;
  // grid (equal aspect, metres)
  const step = niceStep(Math.max(aw, ah) / k, 6);
  ctx.save(); ctx.beginPath(); ctx.rect(pad.l, pad.t, aw, ah); ctx.clip();
  ctx.lineWidth = 1; ctx.strokeStyle = "rgba(141,153,164,.13)"; ctx.beginPath();
  const eMin = cx - aw / 2 / k, eMax = cx + aw / 2 / k, nMin = cy - ah / 2 / k, nMax = cy + ah / 2 / k;
  for (let e = Math.ceil(eMin / step) * step; e <= eMax; e += step) { const x = Math.round(X(e)) + .5; ctx.moveTo(x, pad.t); ctx.lineTo(x, pad.t + ah); }
  for (let n = Math.ceil(nMin / step) * step; n <= nMax; n += step) { const y = Math.round(Y(n)) + .5; ctx.moveTo(pad.l, y); ctx.lineTo(pad.l + aw, y); }
  ctx.stroke();
  // paths
  const line = (get, style, dash, lw, alpha = 1) => {
    ctx.strokeStyle = style; ctx.lineWidth = lw; ctx.setLineDash(dash); ctx.globalAlpha = alpha; ctx.lineJoin = "round"; ctx.lineCap = "round";
    ctx.beginPath(); let pen = false;
    for (const p of P) { const a = get(p); if (!a) { pen = false; continue; } const x = X(a[0]), y = Y(a[1]); pen ? ctx.lineTo(x, y) : ctx.moveTo(x, y); pen = true; }
    ctx.stroke(); ctx.setLineDash([]); ctx.globalAlpha = 1;
  };
  // offset whiskers: how far GNSS claimed to be from reality (or from Marsad's advice when no truth)
  { let lastC = -1e9; ctx.lineWidth = 1.3; ctx.strokeStyle = COL.raw; ctx.fillStyle = COL.raw;
    for (const p of P) {
      if (p.t - lastC < 6 || !p.raw) continue; const ref = p.truth || p.nav; if (!ref) continue;
      if (Math.hypot(p.raw[0] - ref[0], p.raw[1] - ref[1]) < 8) continue; lastC = p.t;
      ctx.globalAlpha = .5; ctx.beginPath(); ctx.moveTo(X(ref[0]), Y(ref[1])); ctx.lineTo(X(p.raw[0]), Y(p.raw[1])); ctx.stroke();
      ctx.globalAlpha = .9; ctx.beginPath(); ctx.arc(X(p.raw[0]), Y(p.raw[1]), 2.2, 0, 6.3); ctx.fill(); ctx.globalAlpha = 1;
    } }
  if (hasTruth) line((p) => p.truth, COL.truth, [1.5, 4], 2, 0.8);
  line((p) => p.raw, COL.raw, [], 1.4, 0.9);
  // Marsad advised track: solid sky when on GNSS, dashed amber when navigating on the reference
  const runs = []; let cur = null;
  for (let i = 0; i < P.length; i++) {
    const p = P[i]; if (!p.nav) { cur = null; continue; }
    const fb = FALLBACK.has(p.action);
    if (!cur || cur.fb !== fb) { cur = { fb, pts: [] }; runs.push(cur); if (i > 0 && P[i - 1].nav) cur.pts.push(P[i - 1].nav); }
    cur.pts.push(p.nav);
  }
  for (const r of runs) {
    ctx.beginPath(); r.pts.forEach((a, i) => (i ? ctx.lineTo(X(a[0]), Y(a[1])) : ctx.moveTo(X(a[0]), Y(a[1]))));
    ctx.strokeStyle = r.fb ? COL.degraded : COL.advice; ctx.lineWidth = r.fb ? 3.4 : 2.4; ctx.setLineDash(r.fb ? [9, 5] : []); ctx.lineJoin = "round"; ctx.stroke();
  }
  ctx.setLineDash([]); ctx.restore();
  // frame + axes
  ctx.strokeStyle = COL.line2; ctx.lineWidth = 1; ctx.strokeRect(pad.l + .5, pad.t + .5, aw, ah);
  ctx.font = "10.5px " + C("--f-mono"); ctx.fillStyle = COL.dim; ctx.textAlign = "center";
  for (let e = Math.ceil(eMin / step) * step; e <= eMax; e += step) ctx.fillText(fmtM(e), X(e), pad.t + ah + 14);
  ctx.textAlign = "right";
  for (let n = Math.ceil(nMin / step) * step; n <= nMax; n += step) ctx.fillText(fmtM(n), pad.l - 6, Y(n) + 3);
  ctx.textAlign = "left"; ctx.fillStyle = COL.dim; ctx.fillText("east", pad.l + aw - 28, pad.t + ah - 6); ctx.fillText("north", pad.l + 6, pad.t + 12);
  // scale bar
  const sb = niceStep(80 / k, 1); ctx.strokeStyle = COL.bone; ctx.lineWidth = 2; ctx.beginPath();
  ctx.moveTo(pad.l + 12, pad.t + ah - 14); ctx.lineTo(pad.l + 12 + sb * k, pad.t + ah - 14); ctx.stroke();
  ctx.fillStyle = COL.bone; ctx.textAlign = "left"; ctx.fillText(fmtM(sb), pad.l + 12, pad.t + ah - 20);

  // event markers
  const t0 = onsetT();
  const ctxClip = () => { ctx.save(); ctx.beginPath(); ctx.rect(pad.l - 2, pad.t - 2, aw + 4, ah + 4); ctx.clip(); };
  if (t0 != null) {
    const p = P.find((q) => q.t >= t0);
    const a = p && (p.truth || p.nav || p.raw);
    if (a) {
      const x = X(a[0]), y = Y(a[1]); ctxClip();
      ctx.strokeStyle = COL.bone; ctx.lineWidth = 1.8; ctx.fillStyle = COL.ink;
      ctx.beginPath(); ctx.moveTo(x, y - 8); ctx.lineTo(x + 8, y); ctx.lineTo(x, y + 8); ctx.lineTo(x - 8, y); ctx.closePath(); ctx.fill(); ctx.stroke();
      placed(ctx, S.simulated ? "event onset (simulated)" : "event onset", x + 12, y - 8, COL.bone, "600 11px " + C("--f-ui"), pad.l + aw - 4);
      ctx.restore();
    }
    const sw = P.find((q) => q.t >= t0 && FALLBACK.has(q.action) && q.nav);
    if (sw) {
      const x = X(sw.nav[0]), y = Y(sw.nav[1]); ctxClip();
      ctx.fillStyle = COL.degraded; ctx.strokeStyle = COL.ink; ctx.lineWidth = 2; ctx.fillRect(x - 6, y - 6, 12, 12); ctx.strokeRect(x - 6, y - 6, 12, 12);
      placed(ctx, `switched to reference, ${(sw.t - t0).toFixed(0)} s after onset`, x + 12, Math.min(y + 18, pad.t + ah - 8), COL.degraded, "600 11px " + C("--f-ui"), pad.l + aw - 4);
      ctx.restore();
    }
  }
  // heads + direct labels
  const last = ALL[ALL.length - 1];
  const lastOf = (k) => { for (let i = ALL.length - 1; i >= 0; i--) if (ALL[i][k]) return ALL[i][k]; return null; };
  const heads = [];
  const th = hasTruth ? lastOf("truth") : null, rh = lastOf("raw"), nh = lastOf("nav");
  if (th) heads.push({ a: th, c: COL.truth, text: "Reality (simulated)", shape: "ring" });
  if (rh) heads.push({ a: rh, c: COL.raw, text: last.raw ? "GNSS says" : "GNSS says (last fix)", shape: "cross" });
  if (nh) heads.push({ a: nh, c: FALLBACK.has(last.action) ? COL.degraded : COL.advice, text: "Marsad advises", shape: "dot" });
  // connector from reality to GNSS claim
  if (th && rh) {
    const dd = Math.hypot(rh[0] - th[0], rh[1] - th[1]);
    if (dd > 6) {
      ctxClip(); ctx.setLineDash([3, 3]); ctx.strokeStyle = COL.raw; ctx.lineWidth = 1.2; ctx.beginPath(); ctx.moveTo(X(th[0]), Y(th[1])); ctx.lineTo(X(rh[0]), Y(rh[1])); ctx.stroke(); ctx.setLineDash([]);
      halo(ctx, `${dd.toFixed(0)} m`, (X(th[0]) + X(rh[0])) / 2 + 6, (Y(th[1]) + Y(rh[1])) / 2 - 4, COL.raw, "left", "600 11px " + C("--f-mono")); ctx.restore();
    }
  }
  for (const hd of heads) {
    const x = X(hd.a[0]), y = Y(hd.a[1]); hd.x = x; hd.y = y; ctx.strokeStyle = hd.c; ctx.fillStyle = hd.c; ctx.lineWidth = 2;
    if (hd.shape === "ring") { ctx.beginPath(); ctx.arc(x, y, 7, 0, 6.3); ctx.stroke(); ctx.beginPath(); ctx.arc(x, y, 2, 0, 6.3); ctx.fill(); }
    else if (hd.shape === "cross") { ctx.beginPath(); ctx.moveTo(x - 6, y - 6); ctx.lineTo(x + 6, y + 6); ctx.moveTo(x + 6, y - 6); ctx.lineTo(x - 6, y + 6); ctx.stroke(); }
    else { ctx.beginPath(); ctx.arc(x, y, 5.5, 0, 6.3); ctx.fill(); ctx.strokeStyle = COL.ink; ctx.lineWidth = 1.5; ctx.stroke(); }
  }
  heads.sort((a, b) => a.y - b.y); let prev = -1e9;
  for (const hd of heads) { hd.ly = Math.max(hd.y, prev + 15); prev = hd.ly; }
  ctx.font = "600 11.5px " + C("--f-ui");
  for (const hd of heads) {
    const lx = Math.min(hd.x + 14, w - pad.r + 8); const ly = Math.min(Math.max(hd.ly, pad.t + 10), pad.t + ah - 4);
    if (Math.abs(ly - hd.y) > 3 || hd.x + 14 > w - pad.r + 8) { ctx.strokeStyle = hd.c; ctx.lineWidth = 1; ctx.globalAlpha = .6; ctx.beginPath(); ctx.moveTo(hd.x, hd.y); ctx.lineTo(lx - 3, ly - 4); ctx.stroke(); ctx.globalAlpha = 1; }
    halo(ctx, hd.text, lx, ly, hd.c, "left");
  }
  // readout
  let ro = `t ${fmtT(last.t)}`;
  if (th && rh) { const e = Math.hypot(rh[0] - th[0], rh[1] - th[1]); ro += `  |  GNSS is ${e.toFixed(0)} m from reality${last.raw ? "" : " (no current fix)"}`; }
  if (th && nh) { const e = Math.hypot(nh[0] - th[0], nh[1] - th[1]); ro += `  |  Marsad advice is ${e.toFixed(0)} m from reality`; }
  if (th) ro += "  |  simulated ground truth";
  $("plot-readout").textContent = ro;
  o.c.setAttribute("aria-label", `Position plot. ${ro}`);
}

// Offset view: every position expressed relative to reality, so a slow carry-off becomes visible.
function drawOffset(o, ALL, t0) {
  const { ctx, w, h } = o; const from = t0 != null && ALL[ALL.length - 1].t >= t0 - 5 ? t0 - 30 : -1e18;
  const P = ALL.filter((p) => p.t >= from && p.truth);
  const rel = (a, b) => (a && b ? [a[0] - b[0], a[1] - b[1]] : null);
  let R = 12; for (const p of P) { for (const a of [rel(p.raw, p.truth), rel(p.nav, p.truth)]) if (a) R = Math.max(R, Math.hypot(a[0], a[1])); }
  R *= 1.18; const pad = { l: 20, r: 150, t: 14, b: 26 }, aw = w - pad.l - pad.r, ah = h - pad.t - pad.b;
  const k = Math.min(aw, ah) / 2 / R, cx = pad.l + aw / 2, cy = pad.t + ah / 2;
  const X = (e) => cx + e * k, Y = (n) => cy - n * k;
  ctx.strokeStyle = "rgba(141,153,164,.16)"; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(cx - R * k, cy); ctx.lineTo(cx + R * k, cy); ctx.moveTo(cx, cy - R * k); ctx.lineTo(cx, cy + R * k); ctx.stroke();
  const st = niceStep(R, 3); ctx.font = "10.5px " + C("--f-mono"); ctx.textAlign = "left";
  for (let r = st; r < R; r += st) { ctx.strokeStyle = "rgba(141,153,164,.22)"; ctx.beginPath(); ctx.arc(cx, cy, r * k, 0, 6.3); ctx.stroke(); ctx.fillStyle = COL.dim; ctx.fillText(fmtM(r), cx + r * k * 0.7071 + 3, cy - r * k * 0.7071 - 3); }
  const path = (get, style, dash, lw) => { ctx.strokeStyle = style; ctx.lineWidth = lw; ctx.setLineDash(dash); ctx.lineJoin = "round"; ctx.beginPath(); let pen = false;
    for (const p of P) { const a = get(p); if (!a) { pen = false; continue; } pen ? ctx.lineTo(X(a[0]), Y(a[1])) : ctx.moveTo(X(a[0]), Y(a[1])); pen = true; } ctx.stroke(); ctx.setLineDash([]); };
  path((p) => rel(p.raw, p.truth), COL.raw, [], 2);
  let cur = null; const runs = [];
  for (const p of P) { const a = rel(p.nav, p.truth); if (!a) { cur = null; continue; } const fb = FALLBACK.has(p.action); if (!cur || cur.fb !== fb) { cur = { fb, pts: [] }; runs.push(cur); } cur.pts.push(a); }
  for (const r of runs) { ctx.beginPath(); r.pts.forEach((a, i) => (i ? ctx.lineTo(X(a[0]), Y(a[1])) : ctx.moveTo(X(a[0]), Y(a[1])))); ctx.strokeStyle = r.fb ? COL.degraded : COL.advice; ctx.lineWidth = r.fb ? 3.2 : 2.4; ctx.setLineDash(r.fb ? [8, 5] : []); ctx.stroke(); ctx.setLineDash([]); }
  // reality at the centre
  ctx.strokeStyle = COL.truth; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(cx, cy, 7, 0, 6.3); ctx.stroke(); ctx.fillStyle = COL.truth; ctx.beginPath(); ctx.arc(cx, cy, 2, 0, 6.3); ctx.fill();
  halo(ctx, "Reality (simulated)", cx + 12, cy + 16, COL.truth, "left", "600 11.5px " + C("--f-ui"));
  const last = ALL[ALL.length - 1], lastRel = (key) => { for (let i = P.length - 1; i >= 0; i--) { const a = rel(P[i][key], P[i].truth); if (a) return a; } return null; };
  const heads = [];
  const ra = lastRel("raw"), na = lastRel("nav");
  if (ra) heads.push({ a: ra, c: COL.raw, t: `GNSS says: ${Math.hypot(ra[0], ra[1]).toFixed(0)} m off${last.raw ? "" : " (last fix)"}` });
  if (na) heads.push({ a: na, c: FALLBACK.has(last.action) ? COL.degraded : COL.advice, t: `Marsad advises: ${Math.hypot(na[0], na[1]).toFixed(0)} m off` });
  heads.sort((a, b) => Y(a.a[1]) - Y(b.a[1])); let prev = -1e9;
  for (const hd of heads) { const x = X(hd.a[0]), y = Y(hd.a[1]); hd.x = x; hd.y = y; ctx.fillStyle = hd.c; ctx.beginPath(); ctx.arc(x, y, 5.5, 0, 6.3); ctx.fill(); ctx.strokeStyle = COL.ink; ctx.lineWidth = 1.5; ctx.stroke(); hd.ly = Math.max(y, prev + 15); prev = hd.ly; }
  for (const hd of heads) { const lx = Math.min(hd.x + 12, w - pad.r + 4); halo(ctx, hd.t, lx, hd.ly + 4, hd.c, "left", "600 11.5px " + C("--f-ui")); }
  ctx.fillStyle = COL.dim; ctx.textAlign = "left"; ctx.font = "10.5px " + C("--f-mono"); ctx.fillText("Rings: distance from reality. Each trail starts at the origin.", pad.l, h - 8);
  const ro = `t ${fmtT(last.t)}  |  positions relative to simulated ground truth  |  ` + heads.map((x) => x.t).join("  |  ");
  $("plot-readout").textContent = ro; o.c.setAttribute("aria-label", "Offset from reality. " + ro);
}

// ------------------------------------------------------------------ timeline + posterior
let hatch = null;
function patterns(ctx) {
  if (hatch) return hatch;
  const mk = (draw) => { const c = document.createElement("canvas"); c.width = c.height = 8; const g = c.getContext("2d"); draw(g); return ctx.createPattern(c, "repeat"); };
  hatch = {
    DEGRADED: mk((g) => { g.strokeStyle = COL.degraded; g.globalAlpha = .55; g.lineWidth = 1.4; g.beginPath(); g.moveTo(0, 8); g.lineTo(8, 0); g.stroke(); }),
    DENIED: mk((g) => { g.strokeStyle = COL.denied; g.globalAlpha = .7; g.lineWidth = 1.6; g.beginPath(); g.moveTo(0, 8); g.lineTo(8, 0); g.moveTo(0, 0); g.lineTo(8, 8); g.stroke(); }),
  };
  return hatch;
}
function domain() {
  const P = S.pts; if (!P.length) return [0, 1];
  let a = P[0].t, b = P[P.length - 1].t;
  if (S.vid === "demo" && S.demo.duration) b = Math.max(b, S.demo.duration);
  return [a, Math.max(b, a + 1)];
}
function drawTimeline() {
  const o = cv.timeline; fit(o); const { ctx, w, h } = o; ctx.clearRect(0, 0, w, h);
  const P = S.pts; if (!P.length) return;
  const pad = { l: 30, r: 8, t: 8, b: 20 }, aw = w - pad.l - pad.r, ah = h - pad.t - pad.b;
  const [d0, d1] = domain(); const X = (t) => pad.l + (t - d0) / (d1 - d0) * aw, Y = (v) => pad.t + (1 - v) * ah;
  const pat = patterns(ctx);
  // state bands
  let i = 0;
  while (i < P.length) {
    let j = i; while (j + 1 < P.length && P[j + 1].state === P[i].state) j++;
    const xa = X(P[i].t), xb = j + 1 < P.length ? X(P[j + 1].t) : X(P[j].t) + 1;
    if (P[i].state !== "TRUSTED") {
      ctx.fillStyle = STATE_COL[P[i].state]; ctx.globalAlpha = .12; ctx.fillRect(xa, pad.t, xb - xa, ah); ctx.globalAlpha = 1;
      ctx.fillStyle = pat[P[i].state]; ctx.fillRect(xa, pad.t, xb - xa, ah);
    }
    i = j + 1;
  }
  // grid + axes
  ctx.strokeStyle = "rgba(141,153,164,.16)"; ctx.lineWidth = 1; ctx.font = "10px " + C("--f-mono"); ctx.fillStyle = COL.dim;
  ctx.textAlign = "right"; for (const v of [0, .5, 1]) { const y = Math.round(Y(v)) + .5; ctx.beginPath(); ctx.moveTo(pad.l, y); ctx.lineTo(pad.l + aw, y); ctx.stroke(); ctx.fillText(v.toFixed(1), pad.l - 4, y + 3); }
  const st = niceStep(d1 - d0, Math.max(2, Math.floor(aw / 70))); ctx.textAlign = "center";
  for (let t = Math.ceil(d0 / st) * st; t <= d1; t += st) { const x = X(t); ctx.fillText(fmtT(t).slice(0, 5), x, h - 6); ctx.beginPath(); ctx.moveTo(Math.round(x) + .5, pad.t + ah); ctx.lineTo(Math.round(x) + .5, pad.t + ah + 3); ctx.stroke(); }
  // thresholds
  ctx.setLineDash([4, 4]); ctx.strokeStyle = "rgba(235,230,216,.35)"; ctx.beginPath(); ctx.moveTo(pad.l, Y(.5)); ctx.lineTo(pad.l + aw, Y(.5)); ctx.stroke(); ctx.setLineDash([]);
  // onset
  const t0 = onsetT(); if (t0 != null && t0 >= d0 && t0 <= d1) {
    ctx.strokeStyle = COL.bone; ctx.setLineDash([2, 3]); ctx.beginPath(); ctx.moveTo(X(t0), pad.t); ctx.lineTo(X(t0), pad.t + ah); ctx.stroke(); ctx.setLineDash([]);
    halo(ctx, "onset", X(t0) + 4, pad.t + 10, COL.bone, "left", "600 10px " + C("--f-ui"));
  }
  // trust line, coloured by state, with state shape markers at transitions
  ctx.lineWidth = 2; ctx.lineJoin = "round";
  for (let k = 1; k < P.length; k++) { ctx.strokeStyle = STATE_COL[P[k].state] || COL.bone; ctx.beginPath(); ctx.moveTo(X(P[k - 1].t), Y(P[k - 1].trust)); ctx.lineTo(X(P[k].t), Y(P[k].trust)); ctx.stroke(); }
  for (const tr of S.transitions) {
    if (tr.t < d0) continue; const x = X(tr.t), y = Y(tr.trust ?? .5); ctx.fillStyle = STATE_COL[tr.to] || COL.bone; ctx.strokeStyle = COL.panel; ctx.lineWidth = 1.5;
    ctx.beginPath(); if (tr.to === "TRUSTED") ctx.arc(x, y, 4, 0, 6.3); else if (tr.to === "DEGRADED") { ctx.moveTo(x, y - 5); ctx.lineTo(x + 5, y + 4); ctx.lineTo(x - 5, y + 4); ctx.closePath(); } else ctx.rect(x - 4, y - 4, 8, 8);
    ctx.fill(); ctx.stroke();
  }
  ctx.strokeStyle = COL.line2; ctx.strokeRect(pad.l + .5, pad.t + .5, aw, ah);
  o.c.setAttribute("aria-label", `Trust over time. Latest ${P[P.length - 1].trust.toFixed(2)}, state ${P[P.length - 1].state}.`);
}
function drawPosterior() {
  const o = cv.posterior; fit(o); const { ctx, w, h } = o; ctx.clearRect(0, 0, w, h);
  const P = S.pts; if (!P.length) return;
  const pad = { l: 24, r: 4, t: 8, b: 20 }, aw = w - pad.l - pad.r, ah = h - pad.t - pad.b;
  const [d0, d1] = domain(); const cols = Math.max(20, Math.floor(aw / 3)), bw = aw / cols;
  const cell = new Array(cols).fill(null);
  for (const p of P) { const c = Math.min(cols - 1, Math.floor((p.t - d0) / (d1 - d0) * cols)); cell[c] = p.probs; }
  for (let c = 0; c < cols; c++) {
    const pr = cell[c]; if (!pr) continue; let y = pad.t + ah;
    for (const [k, , col] of HYP) { const v = pr[k] || 0, hh = v * ah; if (hh < .3) continue; ctx.fillStyle = col; ctx.fillRect(pad.l + c * bw, y - hh, bw + 0.6, hh); y -= hh; }
  }
  ctx.strokeStyle = COL.line2; ctx.strokeRect(pad.l + .5, pad.t + .5, aw, ah);
  ctx.font = "10px " + C("--f-mono"); ctx.fillStyle = COL.dim; ctx.textAlign = "right";
  for (const v of [0, .5, 1]) ctx.fillText(v.toFixed(1), pad.l - 4, pad.t + (1 - v) * ah + 3);
  ctx.textAlign = "center"; const st = niceStep(d1 - d0, Math.max(2, Math.floor(aw / 70)));
  for (let t = Math.ceil(d0 / st) * st; t <= d1; t += st) ctx.fillText(fmtT(t).slice(0, 5), pad.l + (t - d0) / (d1 - d0) * aw, h - 6);
  const t0 = onsetT(); if (t0 != null && t0 >= d0 && t0 <= d1) { const x = pad.l + (t0 - d0) / (d1 - d0) * aw; ctx.strokeStyle = COL.bone; ctx.setLineDash([2, 3]); ctx.beginPath(); ctx.moveTo(x, pad.t); ctx.lineTo(x, pad.t + ah); ctx.stroke(); ctx.setLineDash([]); }
}
function renderPosteriorLegend() {
  const ul = $("po-legend"); const pr = (S.pts[S.pts.length - 1] || {}).probs || {};
  const rows = HYP.map(([k, name, col]) => ({ k, name, col, v: pr[k] || 0 }));
  const top = rows.filter((r) => r.k !== "nominal").sort((a, b) => b.v - a.v)[0];
  ul.replaceChildren(...rows.slice().reverse().map((r) => {
    const li = el("li", top && r.k === top.k && r.v > .05 ? "top1" : ""); const sw = el("i"); sw.style.background = r.col;
    li.append(sw, el("span", "", r.name), el("b", "", (r.v * 100).toFixed(r.v < .01 && r.v > 0 ? 1 : 0) + "%")); return li; }));
}

// ------------------------------------------------------------------ hex map
function drawHex() {
  const o = cv.hexmap; fit(o); const { ctx, w, h } = o; ctx.clearRect(0, 0, w, h);
  const fs = (S.map && S.map.features) || []; $("map-empty").hidden = fs.length > 0;
  $("map-count").textContent = fs.length ? `${fs.length} cell${fs.length > 1 ? "s" : ""}${S.map.simulated ? ", simulated" : ""}` : "";
  if (!fs.length) return;
  let a0 = 1e9, a1 = -1e9, b0 = 1e9, b1 = -1e9;
  const rings = fs.map((f) => { const g = f.geometry || {}; const r = (g.type === "Polygon" ? g.coordinates[0] : g.type === "MultiPolygon" ? g.coordinates[0][0] : []) || []; for (const [lo, la] of r) { a0 = Math.min(a0, lo); a1 = Math.max(a1, lo); b0 = Math.min(b0, la); b1 = Math.max(b1, la); } return r; });
  if (a0 > a1) return;
  const lat0 = (b0 + b1) / 2, kx = Math.cos(lat0 * Math.PI / 180);
  const spanX = Math.max((a1 - a0) * kx, 1e-4), spanY = Math.max(b1 - b0, 1e-4);
  const pad = 14, sc = Math.min((w - 2 * pad) / spanX, (h - 2 * pad - 14) / spanY);
  const ox = w / 2 - (spanX * sc) / 2, oy = (h - 14) / 2 + (spanY * sc) / 2;
  const PX = (lo) => ox + (lo - a0) * kx * sc, PY = (la) => oy - (la - b0) * sc;
  const conf = (f) => { const p = f.properties || {}; for (const k of ["confidence", "score", "intensity", "weight", "value"]) if (typeof p[k] === "number") return Math.max(0, Math.min(1, p[k])); return 0.5; };
  fs.forEach((f, i) => {
    const r = rings[i]; if (!r.length) return; const c = conf(f);
    let mx = 1e9, Mx = -1e9, my = 1e9, My = -1e9; r.forEach(([lo, la]) => { mx = Math.min(mx, PX(lo)); Mx = Math.max(Mx, PX(lo)); my = Math.min(my, PY(la)); My = Math.max(My, PY(la)); });
    ctx.beginPath();
    if (Mx - mx < 12) { const x = (mx + Mx) / 2, y = (my + My) / 2; for (let q = 0; q < 6; q++) { const an = Math.PI / 6 + q * Math.PI / 3; q ? ctx.lineTo(x + 7 * Math.cos(an), y + 7 * Math.sin(an)) : ctx.moveTo(x + 7 * Math.cos(an), y + 7 * Math.sin(an)); } }
    else r.forEach(([lo, la], j) => (j ? ctx.lineTo(PX(lo), PY(la)) : ctx.moveTo(PX(lo), PY(la))));
    ctx.closePath();
    ctx.fillStyle = `rgba(242,169,59,${0.12 + 0.8 * c})`; ctx.fill(); ctx.strokeStyle = c > .6 ? COL.denied : "rgba(242,169,59,.7)"; ctx.lineWidth = c > .6 ? 1.8 : 1; ctx.stroke();
  });
  ctx.font = "10px " + C("--f-mono"); ctx.fillStyle = COL.dim; ctx.textAlign = "left";
  const kmW = spanX * 111.32; ctx.fillText(`${kmW < 1 ? (kmW * 1000).toFixed(0) + " m" : kmW.toFixed(1) + " km"} wide`, 6, h - 4);

}

// ------------------------------------------------------------------ banner / evidence
function renderBanner() {
  const P = S.pts, last = P[P.length - 1], r = S.report;
  const top = $("top");
  const state = last ? last.state : "NONE"; top.dataset.state = state;
  $("state-word").textContent = last ? state : "NO DATA";
  $("trust-num").textContent = last ? last.trust.toFixed(2) : "--";
  $("action-text").textContent = last ? (ACTION[last.action] || last.action) : "--";
  $("action-text").title = last ? last.action : "";
  $("state-sub").textContent = r && r.summary ? r.summary : last ? "" : "Waiting for a vehicle. Start a simulated scenario or post samples.";
  $("sim-badge").hidden = !(S.simulated || (S.demo.running && S.vid === "demo"));
  $("btn-ack").disabled = !last || state === "TRUSTED";
  if (last && S.lastState && S.lastState !== state) $("live").textContent = `Vehicle ${S.vid} is now ${state}. ${ACTION[last.action] || ""}.`;
  S.lastState = last ? state : null;
  // current evidence
  const now = $("ev-now"); now.style.setProperty("--state-now", STATE_COL[state] || COL.dim); now.replaceChildren();
  if (last) {
    const evs = (r && r.evidence) || [];
    const head = el("div", "", state === "TRUSTED" ? "All checks agree." : `Right now: ${humanDom(last.dominant)}`); head.style.fontWeight = 600; now.append(head);
    if (evs.length) { const ul = el("ul"); evs.slice(0, 3).forEach((e) => ul.append(el("li", "", e.message))); now.append(ul); }
    else now.append(el("p", "none", state === "TRUSTED" ? (r && r.warmup ? "Baselines are warming up." : "No anomalies in the last 15 s.") : "No ranked evidence yet."));
  } else now.append(el("p", "none", "No data yet."));
  renderPosteriorLegend(); const ht = S.pts.some((p) => p.truth); $("lg-truth").hidden = !ht; $("lg-whisk").hidden = VIEW === "offset" && ht; $("vw-offset").disabled = !ht;
}
const humanDom = (d) => ({ environmental_degradation: "environmental degradation, not malicious", jamming: "jamming-like signal loss", spoofing_jump: "position-takeover spoofing",
  spoofing_drift: "gradual carry-off spoofing", replay_meaconing: "replay or meaconing", none: "unexplained anomaly" }[d] || d);

function addFeed(tr) {
  S.feed.unshift(tr); S.feed = S.feed.slice(0, 60); renderFeed();
}
function renderFeed() {
  const ol = $("ev-feed"); ol.replaceChildren();
  if (!S.feed.length) { const li = el("li"); li.append(el("p", "", "No state changes yet.")); li.firstChild.style.color = COL.dim; ol.append(li); return; }
  for (const tr of S.feed) {
    const li = el("li"); const head = el("div", "ev-head");
    if (tr.kind === "ack") { head.append(el("span", "t", fmtT(tr.t)), el("span", "chip TRUSTED", "")); head.lastChild.append(el("i"), document.createTextNode("Operator acknowledged")); li.append(head, el("p", "ack", tr.message)); }
    else {
      const chip = el("span", "chip " + tr.to); chip.append(el("i"), document.createTextNode(tr.to));
      head.append(el("span", "t", fmtT(tr.t)), chip, el("span", "", `from ${tr.from.toLowerCase()}, trust ${Number(tr.trust).toFixed(2)}`));
      li.append(head, el("p", "", tr.summary || ""));
      if (tr.evidence && tr.evidence.length) { const ul = el("ul"); tr.evidence.forEach((e) => ul.append(el("li", "", e))); li.append(ul); }
    }
    ol.append(li);
  }
}

// ------------------------------------------------------------------ tracks
function srcFlag(v) {
  if (!v || typeof v !== "object") return false;
  const st = String(v.state || v.status || "").toUpperCase();
  return !!(v.compromised || v.flagged || v.suspect || st === "COMPROMISED" || st === "SUSPECT" || st === "DISTRUSTED" || (typeof v.trust === "number" && v.trust < 0.5));
}
function renderTracks() {
  const body = $("tr-body"), T = S.tracks.slice().sort((a, b) => a.trust - b.trust);
  const bad = T.filter((t) => t.state !== "TRUSTED").length;
  $("tr-count").textContent = T.length ? `${T.length} tracks, ${bad} not trusted${S.tracksSim ? ", simulated" : ""}` : "";
  $("tr-empty").hidden = T.length > 0; $("tr-table").hidden = !T.length;
  body.replaceChildren(...T.slice(0, 80).map((t) => {
    const tr = el("tr", t.state === "DISTRUSTED" ? "d" : ""); const c1 = el("td"); const bar = el("span", "tbar " + t.state); bar.append(el("i"), el("span", "", t.trust.toFixed(2))); bar.title = t.state; c1.append(bar);
    const c2 = el("td", "id", t.track_id); const srcs = Array.isArray(t.sources) ? t.sources : t.sources && typeof t.sources === "object" ? Object.keys(t.sources) : [];
    c2.append(el("span", "sub", [t.cls, srcs.join(", ")].filter(Boolean).join(" · ")));
    const rs = (t.reasons || []).slice().sort((a, b) => (b.weight || 0) - (a.weight || 0)); const c3 = el("td", "why"); c3.append(el("span", "", rs.length ? rs[0].message + (rs.length > 1 ? ` (+${rs.length - 1})` : "") : t.state === "TRUSTED" ? "plausible" : "")); c3.title = rs.map((r) => r.message).join("\n");
    tr.append(c1, c2, c3); return tr;
  }));
  const chips = $("src-chips"); const names = Object.keys(S.sources || {});
  chips.replaceChildren(...names.map((n) => {
    const v = S.sources[n], f = srcFlag(v); const c = el("span", "src " + (f ? "flag" : "ok")); c.append(el("b", "", n));
    let extra = ""; if (v && typeof v === "object") { const q = v.trust ?? v.health ?? v.score; if (typeof q === "number") extra = q.toFixed(2); }
    if (f) c.append(document.createTextNode("flagged")); else if (extra) c.append(document.createTextNode(extra));
    c.title = f ? "Source looks compromised or faulty (no attribution of intent)" : "Source looks consistent"; return c; }));
}

// ------------------------------------------------------------------ data loading
async function loadVehicle(vid) {
  S.vid = vid; S.pts = []; S.transitions = []; S.feed = []; S.report = null; S.meta = null; S.lastState = null;
  if (!vid) { S.simulated = false; S.pts = []; mark("plot"); mark("timeline"); mark("posterior"); mark("banner"); renderFeed(); return; }
  try {
    const [h, t] = await Promise.all([api(`/v1/vehicles/${encodeURIComponent(vid)}/history?n=${MAXPTS}`), api(`/v1/vehicles/${encodeURIComponent(vid)}/trust`).catch(() => null)]);
    if (S.vid !== vid) return;
    S.pts = h.points; S.simulated = !!h.simulated; S.origin = h.origin; S.meta = h.meta; S.transitions = h.transitions; S.feed = h.transitions.slice().reverse().slice(0, 60);
    if (t) S.report = t.report;
  } catch (e) { /* vehicle may not exist yet */ }
  renderFeed(); for (const k of ["plot", "timeline", "posterior", "banner"]) mark(k);
}
function setVehicles(list) {
  S.vehicles = list; const sel = $("veh-select"); const cur = S.vid;
  sel.replaceChildren(...(list.length ? list : [{ vehicle_id: "", simulated: false }]).map((v) => { const o = el("option", "", v.vehicle_id ? v.vehicle_id + (v.simulated ? " (simulated)" : "") : "none"); o.value = v.vehicle_id; return o; }));
  if (cur && list.some((v) => v.vehicle_id === cur)) sel.value = cur;
}
function applyDemo(d) {
  S.demo = d || {}; const run = !!d.running;
  $("btn-stop").disabled = !run;
  const bar = $("prog-bar"); bar.style.width = d.duration ? Math.min(100, (d.sim_t || 0) / d.duration * 100) + "%" : "0";
  $("demo-line").textContent = d.kind ? `${run ? "running" : d.finished ? "finished" : d.error ? "error: " + d.error : "stopped"} | ${d.kind} seed ${d.seed} ${d.split} | ${d.speed}x | t ${fmtT(d.sim_t || 0)} / ${fmtT(d.duration)}` : "idle";
  mark("timeline"); mark("posterior"); mark("plot"); mark("banner");
}

function mergePoints(vid, pts) {
  if (vid !== S.vid || !pts.length) return;
  const last = S.pts.length ? S.pts[S.pts.length - 1].t : -1e18;
  if (pts[0].t < last - 1) { S.pts = []; S.transitions = []; S.feed = []; renderFeed(); }
  const l2 = S.pts.length ? S.pts[S.pts.length - 1].t : -1e18;
  for (const p of pts) if (p.t > l2) S.pts.push(p);
  if (S.pts.length > MAXPTS) S.pts.splice(0, S.pts.length - MAXPTS);
}

// ------------------------------------------------------------------ SSE
function setConn(s, text) { const c = $("conn"); c.dataset.s = s; $("conn-text").textContent = text; document.body.classList.toggle("is-offline", s === "offline"); }
function connect() {
  if (S.es) { S.es.close(); S.es = null; }
  setConn("connecting", "Connecting");
  const es = new EventSource("/v1/stream" + (KEY ? "?api_key=" + encodeURIComponent(KEY) : "")); S.es = es;
  const on = (name, fn) => es.addEventListener(name, (ev) => { try { fn(JSON.parse(ev.data)); } catch (e) { console.warn("bad event", name, e); } });
  es.onopen = () => { S.retry = 0; setConn("live", "Live"); };
  on("hello", async (d) => {
    $("foot-ver").textContent = `marsad ${d.version}`; setVehicles(d.vehicles); applyDemo(d.demo || {});
    const want = S.vid && d.vehicles.some((v) => v.vehicle_id === S.vid) ? S.vid : (d.vehicles.find((v) => v.vehicle_id === "demo") || d.vehicles[0] || {}).vehicle_id || null;
    $("veh-select").value = want || ""; await loadVehicle(want);
  });
  on("scene", (d) => { S.tracks = d.tracks || []; S.sources = d.sources || {}; S.map = d.map || null; S.tracksSim = !!d.simulated; mark("tracks"); mark("hexmap"); });
  on("vehicle", (d) => {
    if (!S.vehicles.some((v) => v.vehicle_id === d.vehicle_id)) { setVehicles(S.vehicles.concat([{ vehicle_id: d.vehicle_id, simulated: d.simulated }])); if (!S.vid) { $("veh-select").value = d.vehicle_id; loadVehicle(d.vehicle_id); return; } }
    if (d.vehicle_id !== S.vid) return;
    S.simulated = !!d.simulated; S.report = d.report; S.origin = d.origin; mergePoints(d.vehicle_id, d.points);
    for (const k of ["plot", "timeline", "posterior", "banner"]) mark(k);
  });
  on("transition", (d) => { if (d.vehicle_id !== S.vid) return; S.transitions.push(d); addFeed(d); mark("timeline"); });
  on("acknowledge", (d) => { if (d.vehicle_id !== S.vid) return; addFeed({ kind: "ack", t: d.t || 0, message: d.message }); });
  on("vehicle_deleted", (d) => { setVehicles(S.vehicles.filter((v) => v.vehicle_id !== d.vehicle_id)); if (d.vehicle_id === S.vid) loadVehicle(S.vehicles[0] ? S.vehicles[0].vehicle_id : null); });
  on("demo", (d) => { const started = d.running && (d.sim_t || 0) === 0; applyDemo(d); if (started) { setVehicles(S.vehicles.some((v) => v.vehicle_id === "demo") ? S.vehicles : S.vehicles.concat([{ vehicle_id: "demo", simulated: true }])); $("veh-select").value = "demo"; S.pts = []; S.transitions = []; S.feed = []; S.vid = "demo"; S.simulated = true; S.report = null; renderFeed(); } });
  es.onerror = () => {
    es.close(); S.es = null; const wait = Math.min(10, 1 << Math.min(S.retry++, 4)); let left = wait;
    const tick = () => { if (S.es) return; if (left <= 0) { connect(); return; } setConn("offline", `Disconnected, retrying in ${left}s`); left--; setTimeout(tick, 1000); };
    tick();
  };
}

// ------------------------------------------------------------------ controls
async function initScenarios() {
  const sel = $("scn-kind");
  try {
    const d = await api("/v1/demo/scenarios"); const groups = { calm: el("optgroup"), hit: el("optgroup") };
    groups.calm.label = "Honest conditions (should not alarm)"; groups.hit.label = "Interference and spoofing";
    const desc = {};
    for (const s of d.scenarios) { const o = el("option", "", s.kind); o.value = s.kind; desc[s.kind] = s.description; (s.is_attack ? groups.hit : groups.calm).append(o); }
    sel.append(groups.hit, groups.calm);
    const show = () => ($("scn-desc").textContent = desc[sel.value] || ""); sel.addEventListener("change", show);
    sel.value = query.get("kind") && desc[query.get("kind")] ? query.get("kind") : "spoof_drift"; show();
  } catch (e) { $("scn-desc").textContent = "Simulator unavailable: " + e.message; $("btn-start").disabled = true; }
}
$("scn-form").addEventListener("submit", async (ev) => {
  ev.preventDefault(); const b = $("btn-start"); b.disabled = true;
  try {
    const body = { kind: $("scn-kind").value, seed: parseInt($("scn-seed").value || "1", 10), split: document.querySelector("input[name=split]:checked").value, speed: parseFloat($("scn-speed").value) };
    const d = await api("/v1/demo/start", { method: "POST", body: JSON.stringify(body) }); applyDemo(d);
    S.vid = "demo"; S.pts = []; S.transitions = []; S.feed = []; renderFeed();
  } catch (e) { $("demo-line").textContent = "Could not start: " + e.message; } finally { b.disabled = false; }
});
$("btn-stop").addEventListener("click", async () => { try { applyDemo(await api("/v1/demo/stop", { method: "POST" })); } catch (e) { $("demo-line").textContent = e.message; } });
$("btn-ack").addEventListener("click", async () => { if (!S.vid) return; try { await api(`/v1/vehicles/${encodeURIComponent(S.vid)}/acknowledge`, { method: "POST", body: JSON.stringify({ operator: "dashboard" }) }); } catch (e) { $("live").textContent = "Acknowledge failed: " + e.message; } });
for (const r of document.querySelectorAll("input[name=view]")) {
  r.checked = r.value === VIEW; r.addEventListener("change", () => { VIEW = r.value; mark("banner"); try { localStorage.setItem("marsad.view", VIEW); } catch (_) {} mark("plot"); });
}
$("veh-select").addEventListener("change", (e) => loadVehicle(e.target.value || null));

(async () => {
  await initScenarios(); renderFeed(); for (const k of ["banner", "tracks"]) mark(k);
  connect();
  if (query.get("autostart")) $("scn-form").requestSubmit();
})();
})();
