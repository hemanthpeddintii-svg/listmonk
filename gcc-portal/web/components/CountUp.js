"use client";
import { useEffect, useRef, useState } from "react";
export default function CountUp({ to, suffix = "" }) {
  const [v, setV] = useState(0), r = useRef(null);
  useEffect(() => {
    const io = new IntersectionObserver(([e]) => { if (!e.isIntersecting) return; io.disconnect(); if (matchMedia("(prefers-reduced-motion: reduce)").matches) { setV(to); return; } const s = performance.now();
      const f = (n) => { const p = Math.min(1, (n - s) / 1400); setV(Math.round((1 - Math.pow(1 - p, 4)) * to)); if (p < 1) requestAnimationFrame(f); }; requestAnimationFrame(f); });
    io.observe(r.current); return () => io.disconnect(); }, [to]);
  return <span ref={r}>{v.toLocaleString("en-IN")}{suffix}</span>;
}
