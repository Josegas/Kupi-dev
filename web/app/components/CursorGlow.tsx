"use client";
import { useEffect } from "react";

export default function CursorGlow() {
  useEffect(() => {
    let rafId: number;
    let mx = -600, my = -600;
    let cx = -600, cy = -600;

    const onMove = (e: MouseEvent) => {
      mx = e.clientX;
      my = e.clientY;
    };

    // El glow sigue al cursor con un lag suave (lerp)
    const tick = () => {
      cx += (mx - cx) * 0.09;
      cy += (my - cy) * 0.09;
      document.documentElement.style.setProperty("--cx", `${cx}px`);
      document.documentElement.style.setProperty("--cy", `${cy}px`);
      rafId = requestAnimationFrame(tick);
    };

    window.addEventListener("mousemove", onMove);
    rafId = requestAnimationFrame(tick);

    return () => {
      window.removeEventListener("mousemove", onMove);
      cancelAnimationFrame(rafId);
    };
  }, []);

  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 z-20"
      style={{
        background:
          "radial-gradient(550px circle at var(--cx, -600px) var(--cy, -600px), rgba(194,65,12,0.10), transparent 42%)",
      }}
    />
  );
}
