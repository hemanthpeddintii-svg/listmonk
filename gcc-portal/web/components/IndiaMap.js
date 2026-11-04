"use client";
import { useEffect, useRef } from "react";

// Coarse India outline (lon, lat). Dots are generated inside it, so the map is drawn by code, not an image.
const POLY = [[68.2,23.6],[69.2,22.2],[70.8,20.7],[72.8,21.1],[72.8,19.0],[73.5,16.5],[74.8,13.0],[75.8,11.5],[76.5,9.0],[77.5,8.1],[78.2,8.9],[79.8,10.3],[80.3,13.1],[80.1,15.5],[82.3,16.9],[84.7,19.2],[86.8,21.5],[88.0,21.6],[88.9,22.4],[88.7,24.7],[89.8,26.0],[92.0,26.8],[94.5,27.4],[97.3,28.2],[95.6,26.4],[94.4,24.2],[93.3,22.6],[92.3,24.4],[91.0,25.2],[88.3,26.6],[88.0,27.8],[84.5,28.6],[81.0,30.2],[79.0,31.0],[78.8,32.5],[79.5,34.4],[77.8,35.5],[75.5,36.6],[74.2,35.0],[74.5,32.8],[75.0,31.5],[74.0,30.3],[71.0,28.0],[70.4,26.0],[69.4,24.4]];
const CITIES = [
  ["Bengaluru",77.6,13.0,1,-1],["Hyderabad",78.5,17.4,.8],["Pune",73.9,18.5,.7,-1],["Mumbai",72.9,19.1,.7,-1,-10],
  ["Delhi NCR",77.2,28.6,.9],["Chennai",80.3,13.1,.6],["Kolkata",88.4,22.6,.35],["Ahmedabad",72.6,23.0,.4]];
const inside = (x, y) => { let c = false;
  for (let i = 0, j = POLY.length - 1; i < POLY.length; j = i++) {
    const [xi, yi] = POLY[i], [xj, yj] = POLY[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) c = !c; }
  return c; };

export default function IndiaMap({ className }) {
  const ref = useRef(null);
  useEffect(() => {
    const cv = ref.current, ctx = cv.getContext("2d");
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    let W, H, dots = [], pts = [], mouse = { x: -999, y: -999 }, raf, t0 = performance.now();
    const LON = [67, 98.5], LAT = [6, 37.5];
    const setup = () => {
      const dpr = Math.min(devicePixelRatio || 1, 2), r = cv.getBoundingClientRect();
      W = r.width; H = r.height; cv.width = W * dpr; cv.height = H * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      const mh = H * 0.92, mw = mh * (31.5 * 0.93) / 31.5;           // aspect with lat correction
      const ox = W > 820 ? W - mw - W * 0.04 : (W - mw) / 2, oy = (H - mh) / 2;
      const px = (lon) => ox + ((lon - LON[0]) / (LON[1] - LON[0])) * mw;
      const py = (lat) => oy + ((LAT[1] - lat) / (LAT[1] - LAT[0])) * mh;
      const step = Math.max(7, Math.round(mh / 62)); dots = [];
      for (let y = oy; y < oy + mh; y += step)
        for (let x = ox; x < ox + mw; x += step) {
          const lon = LON[0] + ((x - ox) / mw) * (LON[1] - LON[0]), lat = LAT[1] - ((y - oy) / mh) * (LAT[1] - LAT[0]);
          if (inside(lon, lat)) dots.push({ x, y, ox: x, oy: y, vx: 0, vy: 0, s: Math.random() });
        }
      pts = CITIES.map(([n, lo, la, w, side = 1, dy = 4], i) => ({ n, x: px(lo), y: py(la), w, side, dy, ph: i * 0.9 }));
    };
    const frame = (now) => {
      const t = (now - t0) / 1000; ctx.clearRect(0, 0, W, H);
      // each city emits a ring every ~3.4s: dots inside the ring band light up (a "refresh signal")
      const rings = pts.map(p => ({ p, r: (((t + p.ph) % 3.4) / 3.4) * Math.min(W, H) * 0.42 * (0.5 + p.w) }));
      for (const d of dots) {
        const dx = d.x - mouse.x, dy = d.y - mouse.y, md = Math.hypot(dx, dy);
        if (md < 110) { const f = (1 - md / 110) * 3.2; d.vx += (dx / md) * f; d.vy += (dy / md) * f; }
        d.vx += (d.ox - d.x) * 0.06; d.vy += (d.oy - d.y) * 0.06; d.vx *= 0.82; d.vy *= 0.82; d.x += d.vx; d.y += d.vy;
        let glow = 0;
        for (const { p, r } of rings) { const dd = Math.abs(Math.hypot(d.ox - p.x, d.oy - p.y) - r); if (dd < 16) glow = Math.max(glow, (1 - dd / 16) * (1 - r / (Math.min(W, H) * 0.7))); }
        const base = 1.1 + d.s * 0.5 + Math.sin(t * 1.4 + d.ox * 0.03 + d.oy * 0.02) * 0.25;
        ctx.beginPath(); ctx.arc(d.x, d.y, base + glow * 2.6 + (md < 110 ? (1 - md / 110) * 1.8 : 0), 0, 6.283);
        ctx.fillStyle = glow > 0.05 ? `rgba(255,75,31,${0.35 + glow * 0.65})` : "rgba(18,18,18,.28)"; ctx.fill();
      }
      // arcs between hubs with a travelling spark
      ctx.lineWidth = 1;
      [[0,1],[1,4],[4,3],[3,0],[0,5],[2,4],[6,4]].forEach(([a, b], i) => {
        const A = pts[a], B = pts[b], mx = (A.x + B.x) / 2, my = (A.y + B.y) / 2 - Math.hypot(A.x - B.x, A.y - B.y) * 0.22;
        ctx.strokeStyle = "rgba(18,18,18,.14)"; ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.quadraticCurveTo(mx, my, B.x, B.y); ctx.stroke();
        const u = ((t * 0.18 + i * 0.23) % 1), x = (1 - u) ** 2 * A.x + 2 * (1 - u) * u * mx + u * u * B.x, y = (1 - u) ** 2 * A.y + 2 * (1 - u) * u * my + u * u * B.y;
        ctx.beginPath(); ctx.arc(x, y, 3, 0, 6.283); ctx.fillStyle = "#ff4b1f"; ctx.fill();
      });
      ctx.font = "600 11px ui-monospace, Menlo, monospace";
      for (const p of pts) {
        const pulse = 1 + Math.sin(t * 3 + p.ph) * 0.15;
        ctx.beginPath(); ctx.arc(p.x, p.y, (5 + p.w * 5) * pulse, 0, 6.283); ctx.fillStyle = "#ff4b1f"; ctx.fill();
        ctx.lineWidth = 2; ctx.strokeStyle = "#f2ede4"; ctx.stroke();
        ctx.fillStyle = "#121212"; const lbl = p.n.toUpperCase(), off = 12 + p.w * 4; ctx.fillText(lbl, p.side < 0 ? p.x - off - ctx.measureText(lbl).width : p.x + off, p.y + p.dy);
      }
      if (!reduce) raf = requestAnimationFrame(frame);
    };
    const move = (e) => { const r = cv.getBoundingClientRect(); mouse = { x: e.clientX - r.left, y: e.clientY - r.top }; };
    setup(); raf = requestAnimationFrame(frame);
    addEventListener("resize", setup); addEventListener("pointermove", move);
    return () => { cancelAnimationFrame(raf); removeEventListener("resize", setup); removeEventListener("pointermove", move); };
  }, []);
  return <canvas ref={ref} className={className} aria-hidden="true" />;
}
