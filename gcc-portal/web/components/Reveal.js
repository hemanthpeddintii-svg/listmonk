"use client";
import { useEffect, useRef } from "react";
export default function Reveal({ children, as: T = "div", delay = 0, className = "" }) {
  const r = useRef(null);
  useEffect(() => { const el = r.current; const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { el.classList.add("seen"); io.disconnect(); } }, { threshold: 0.15 }); io.observe(el); return () => io.disconnect(); }, []);
  return <T ref={r} className={"reveal " + className} style={{ transitionDelay: `${delay}ms` }}>{children}</T>;
}
