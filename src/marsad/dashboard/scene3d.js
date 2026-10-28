/* Space-time view. East and north on the floor, time as height.
 *
 * Offset mode (default): every position is drawn relative to reality (or to Marsad's advice when there is no
 * ground truth), so the true track is the vertical axis and a carry-off shows as the GNSS line leaning away from
 * it while the advised line stays close. Track mode draws the absolute east and north positions instead.
 * Reads the point list that app.js keeps and never talks to the network. Loaded the first time the tab opens.
 */
import * as THREE from "./vendor/three.module.min.js";

const fmtT = (t) => { const r = Math.round(t); return `${String(Math.floor(r / 60)).padStart(2, "0")}:${String(r % 60).padStart(2, "0")}`; };
const css = getComputedStyle(document.documentElement);
const col = (n, d) => new THREE.Color((css.getPropertyValue(n).trim() || d));

export function createSpaceTime(host, source) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(col("--panel", "#15191d"), 1);
  host.appendChild(renderer.domElement);
  const labels = document.createElement("div");
  labels.className = "stage-labels"; labels.setAttribute("aria-hidden", "true");
  host.appendChild(labels);
  const bar = document.createElement("div");
  bar.className = "stage-bar";
  for (const [k, t] of [["offset", "Offset from reality"], ["track", "Absolute track"]]) {
    const b = document.createElement("button");
    b.type = "button"; b.textContent = t; b.dataset.mode = k; b.setAttribute("aria-pressed", String(k === "offset"));
    b.addEventListener("click", () => { mode = k; for (const x of bar.children) x.setAttribute("aria-pressed", String(x.dataset.mode === k)); lastN = -1; dirty = true; });
    bar.appendChild(b);
  }
  host.appendChild(bar);
  renderer.domElement.setAttribute("role", "img");
  renderer.domElement.setAttribute("aria-label", "Space and time view of the GNSS, advised and true tracks");

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 5000);
  const world = new THREE.Group();
  scene.add(world);

  const C = {
    raw: col("--raw", "#d98cc4"), advice: col("--advice", "#6fb1ea"), truth: col("--truth", "#e8e6df"),
    grid: col("--line-2", "#39424b"), dim: col("--dim", "#6b747c"), degraded: col("--degraded", "#e0a030"),
  };

  // orbit state: yaw around the vertical axis, pitch above the floor, distance, target height
  const cam = { yaw: -0.62, pitch: 0.42, dist: 1, ty: 0, auto: true };
  let mode = "offset", marks = [];
  let extent = 100, height = 100, lastN = -1, lastT = -1, dirty = true, visible = false, raf = 0;

  function disposeGroup(g) {
    for (const o of [...g.children]) {
      g.remove(o);
      if (o.geometry) o.geometry.dispose();
      if (o.material) o.material.dispose();
    }
  }

  function line(points, color, opacity = 1, dashed = false) {
    const g = new THREE.BufferGeometry().setFromPoints(points);
    const m = dashed
      ? new THREE.LineDashedMaterial({ color, transparent: opacity < 1, opacity, dashSize: extent / 70, gapSize: extent / 90 })
      : new THREE.LineBasicMaterial({ color, transparent: opacity < 1, opacity });
    const l = new THREE.Line(g, m);
    if (dashed) l.computeLineDistances();
    return l;
  }

  function build() {
    const { pts, onset, hasTruth } = source();
    disposeGroup(world);
    if (!pts.length) return;
    const t0 = pts[0].t, t1 = pts[pts.length - 1].t;
    const rel = mode === "offset";
    const refOf = (p) => p.truth || p.nav;
    // a position as drawn: relative to the reference in offset mode, absolute otherwise
    const at = (p, a) => { if (!a) return null; if (!rel) return a; const r = refOf(p); return r ? [a[0] - r[0], a[1] - r[1]] : null; };
    let x0 = 1e18, x1 = -1e18, z0 = 1e18, z1 = -1e18;
    const grow = (a) => { if (!a) return; x0 = Math.min(x0, a[0]); x1 = Math.max(x1, a[0]); z0 = Math.min(z0, a[1]); z1 = Math.max(z1, a[1]); };
    for (const p of pts) { grow(at(p, p.raw)); grow(at(p, p.nav)); if (!rel) grow(p.truth); }
    if (x0 > x1) { if (!rel) return; x0 = x1 = z0 = z1 = 0; }
    if (rel) { const m = Math.max(Math.abs(x0), Math.abs(x1), Math.abs(z0), Math.abs(z1), 15); x0 = z0 = -m; x1 = z1 = m; }
    const cx = (x0 + x1) / 2, cz = (z0 + z1) / 2;
    extent = Math.max(rel ? 40 : 60, x1 - x0, z1 - z0) * 1.15;
    height = extent * 0.7;
    const ky = height / Math.max(30, t1 - t0);
    const P = (a, t) => new THREE.Vector3(a[0] - cx, (t - t0) * ky, -(a[1] - cz));

    // floor grid with a metric step
    const raw = extent / 6, mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 5, 10].map((k) => k * mag).find((s) => s >= raw) || mag * 10;
    const half = Math.ceil(extent / 2 / step) * step, gp = [];
    for (let v = -half; v <= half + 1e-6; v += step) { gp.push(new THREE.Vector3(v, 0, -half), new THREE.Vector3(v, 0, half), new THREE.Vector3(-half, 0, v), new THREE.Vector3(half, 0, v)); }
    world.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(gp), new THREE.LineBasicMaterial({ color: C.grid, transparent: true, opacity: 0.55 })));

    // vertical time axis at one corner, ticks every minute or so
    const ax = new THREE.Vector3(-half, 0, half);
    const tick = Math.max(10, Math.round(((t1 - t0) / 6) / 10) * 10);
    const ap = [ax, ax.clone().setY(height)];
    for (let t = tick; t <= t1 - t0; t += tick) { const y = t * ky; ap.push(new THREE.Vector3(-half, y, half), new THREE.Vector3(-half + extent / 40, y, half)); }
    world.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(ap), new THREE.LineBasicMaterial({ color: C.dim })));

    const track = (get, color, opacity, dashed) => {
      const v = []; for (const p of pts) { const a = at(p, get(p)); if (a) v.push(P(a, p.t)); }
      if (v.length > 1) world.add(line(v, color, opacity, dashed));
      return v;
    };
    // shadows of each track on the floor, so the horizontal offset reads without the height
    const shadow = (get, color) => {
      const v = []; for (const p of pts) { const a = at(p, get(p)); if (a) v.push(new THREE.Vector3(a[0] - cx, 0, -(a[1] - cz))); }
      if (v.length > 1) world.add(line(v, color, 0.28));
    };
    if (rel) world.add(line([P([0, 0], t0), P([0, 0], t1)], C.truth, 0.9, true));
    else if (hasTruth) track((p) => p.truth, C.truth, 0.9, true);
    track((p) => p.raw, C.raw, 1);
    track((p) => p.nav, C.advice, 1);
    if (!rel && hasTruth) shadow((p) => p.truth, C.truth);
    shadow((p) => p.raw, C.raw);

    // claim versus reality at fixed time slices
    const seg = []; let last = -1e9;
    for (const p of pts) {
      const ref = refOf(p);
      if (!p.raw || !ref || p.t - last < Math.max(5, (t1 - t0) / 40)) continue;
      if (Math.hypot(p.raw[0] - ref[0], p.raw[1] - ref[1]) < extent / 60) continue;
      last = p.t; seg.push(P(at(p, ref) || ref, p.t), P(at(p, p.raw), p.t));
    }
    if (seg.length) world.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(seg), new THREE.LineBasicMaterial({ color: C.raw, transparent: true, opacity: 0.45 })));

    // onset plane
    if (onset != null && onset >= t0 && onset <= t1) {
      const y = (onset - t0) * ky, h2 = half;
      const o = [new THREE.Vector3(-h2, y, -h2), new THREE.Vector3(h2, y, -h2), new THREE.Vector3(h2, y, h2), new THREE.Vector3(-h2, y, h2), new THREE.Vector3(-h2, y, -h2)];
      world.add(line(o, C.degraded, 0.8, true));
    }
    // head markers
    const last3 = (get, color) => {
      for (let i = pts.length - 1; i >= 0; i--) {
        const a = at(pts[i], get(pts[i])); if (!a) continue;
        const m = new THREE.Mesh(new THREE.SphereGeometry(extent / 130, 12, 8), new THREE.MeshBasicMaterial({ color }));
        m.position.copy(P(a, pts[i].t)); world.add(m); return m.position.clone();
      }
    };
    const hr = last3((p) => p.raw, C.raw), hn = last3((p) => p.nav, C.advice);
    if (!rel && hasTruth) last3((p) => p.truth, C.truth);

    // text marks, projected to the screen each frame
    marks = [];
    const lp = pts[pts.length - 1], refEnd = refOf(lp);
    const off = (a) => (a && refEnd ? Math.hypot(a[0] - refEnd[0], a[1] - refEnd[1]) : null);
    if (hr && off(lp.raw) != null) marks.push({ v: hr, text: `GNSS ${off(lp.raw).toFixed(0)} m off`, c: C.raw });
    if (hn && off(lp.nav) != null) marks.push({ v: hn, text: `advice ${off(lp.nav).toFixed(0)} m off`, c: C.advice });
    marks.push({ v: new THREE.Vector3(-half, height, half), text: `t = ${fmtT(t1)}`, c: C.dim });
    marks.push({ v: new THREE.Vector3(-half, 0, half), text: fmtT(t0), c: C.dim });
    if (onset != null && onset >= t0 && onset <= t1) marks.push({ v: new THREE.Vector3(half, (onset - t0) * ky, half), text: "onset", c: C.degraded });
    marks.push({ v: new THREE.Vector3(half, 0, -half), text: `grid ${step} m`, c: C.dim });

    cam.ty = height * 0.45;
    if (cam.auto) cam.dist = Math.max(extent, height) * 1.55;
  }

  function place() {
    const { yaw, pitch, dist, ty } = cam;
    camera.position.set(Math.sin(yaw) * Math.cos(pitch) * dist, ty + Math.sin(pitch) * dist, Math.cos(yaw) * Math.cos(pitch) * dist);
    camera.lookAt(0, ty, 0);
  }

  function resize() {
    const r = host.getBoundingClientRect();
    const w = Math.max(10, Math.round(r.width)), h = Math.max(10, Math.round(r.height));
    renderer.setSize(w, h, false);
    renderer.domElement.style.width = "100%"; renderer.domElement.style.height = "100%";
    camera.aspect = w / h; camera.updateProjectionMatrix(); dirty = true;
  }

  // keep one absolutely positioned label per mark in step with the camera
  function project() {
    while (labels.children.length < marks.length) labels.appendChild(document.createElement("span"));
    while (labels.children.length > marks.length) labels.lastChild.remove();
    const w = host.clientWidth, h = host.clientHeight, v = new THREE.Vector3();
    marks.forEach((m, i) => {
      v.copy(m.v).project(camera);
      const e = labels.children[i];
      e.textContent = m.text; e.style.color = "#" + m.c.getHexString();
      const x = Math.max(2, Math.min((v.x + 1) / 2 * w + 8, w - e.offsetWidth - 4));
      e.style.transform = `translate(${x.toFixed(1)}px, ${((1 - v.y) / 2 * h - 7).toFixed(1)}px)`;
      e.style.display = v.z < 1 ? "block" : "none";
    });
  }

  function draw() {
    raf = 0;
    if (!visible) return;
    const { pts } = source();
    const n = pts.length, t = n ? pts[n - 1].t : -1;
    if (n !== lastN || t !== lastT) { lastN = n; lastT = t; build(); dirty = true; }
    if (dirty) { dirty = false; place(); renderer.render(scene, camera); project(); }
    raf = requestAnimationFrame(draw);
  }

  // pointer orbit and wheel zoom
  let drag = null;
  const dom = renderer.domElement;
  dom.style.touchAction = "none"; dom.style.cursor = "grab";
  dom.addEventListener("pointerdown", (e) => { drag = { x: e.clientX, y: e.clientY }; dom.setPointerCapture(e.pointerId); dom.style.cursor = "grabbing"; });
  dom.addEventListener("pointermove", (e) => {
    if (!drag) return;
    cam.yaw -= (e.clientX - drag.x) * 0.006; cam.pitch = Math.max(0.05, Math.min(1.5, cam.pitch + (e.clientY - drag.y) * 0.005));
    drag = { x: e.clientX, y: e.clientY }; cam.auto = false; dirty = true;
  });
  const end = () => { drag = null; dom.style.cursor = "grab"; };
  dom.addEventListener("pointerup", end); dom.addEventListener("pointercancel", end);
  dom.addEventListener("wheel", (e) => { e.preventDefault(); cam.dist = Math.max(extent * 0.4, Math.min(extent * 8, cam.dist * Math.exp(e.deltaY * 0.001))); cam.auto = false; dirty = true; }, { passive: false });
  dom.addEventListener("dblclick", () => { cam.yaw = -0.62; cam.pitch = 0.42; cam.auto = true; lastN = -1; dirty = true; });
  dom.tabIndex = 0;
  dom.addEventListener("keydown", (e) => {
    const k = { ArrowLeft: [-0.08, 0], ArrowRight: [0.08, 0], ArrowUp: [0, 0.06], ArrowDown: [0, -0.06] }[e.key];
    if (k) { e.preventDefault(); cam.yaw += k[0]; cam.pitch = Math.max(0.05, Math.min(1.5, cam.pitch + k[1])); cam.auto = false; dirty = true; }
  });

  new ResizeObserver(resize).observe(host);
  resize();

  return {
    show(v) { visible = v; if (v) { lastN = -1; resize(); if (!raf) raf = requestAnimationFrame(draw); } },
    refresh() { dirty = true; if (visible && !raf) raf = requestAnimationFrame(draw); },
  };
}
