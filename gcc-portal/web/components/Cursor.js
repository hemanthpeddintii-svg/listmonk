"use client";
import { useEffect, useRef } from "react";
export default function Cursor() {
  const d = useRef(null);
  useEffect(() => {
    if (matchMedia("(pointer: coarse)").matches) return;
    let x = 0, y = 0, tx = 0, ty = 0, raf; const el = d.current; el.style.opacity = 1;
    const mv = (e) => { tx = e.clientX; ty = e.clientY; el.classList.toggle("hot", !!e.target.closest("a,button,.opt,input,select")); };
    const loop = () => { x += (tx - x) * 0.18; y += (ty - y) * 0.18; el.style.transform = `translate(${x}px,${y}px)`; raf = requestAnimationFrame(loop); };
    addEventListener("pointermove", mv); loop(); return () => { removeEventListener("pointermove", mv); cancelAnimationFrame(raf); };
  }, []);
  return <div ref={d} className="cursor" aria-hidden="true"><i /></div>;
}
