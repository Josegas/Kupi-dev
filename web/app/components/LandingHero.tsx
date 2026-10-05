"use client";
import { useEffect, useRef } from "react";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useLang } from "../lib/i18n";


const FLOAT_ROWS = [
  "Rappi · $189 \u00a0·\u00a0 Uber Eats · $214",
  "McDonald's · $142 \u00a0·\u00a0 Uber Eats · $138",
  "Domino's · $229 \u00a0·\u00a0 Uber Eats · $241",
];

export default function LandingHero() {
  const ref = useRef<HTMLElement>(null);
  const { t } = useLang();

  useEffect(() => {
    gsap.registerPlugin(ScrollTrigger);

    const ctx = gsap.context(() => {
      const tl = gsap.timeline({ defaults: { ease: "power3.out" } });

      tl.from(".lh-eyebrow", { opacity: 0, y: 14, duration: 0.55 }, 0.1)
        .from(".lh-line",    { scaleX: 0, transformOrigin: "left center", duration: 0.45, ease: "power2.inOut" }, 0.28)
        .from(".lh-word",    { opacity: 0, y: 38, rotateX: -18, duration: 0.65, stagger: 0.065 }, 0.38)
        .from(".lh-body",    { opacity: 0, y: 18, duration: 0.55 }, 0.9);

      // Parallax suave en los orbs al hacer scroll
      gsap.to(".landing-orb-orange", {
        y: -70,
        ease: "none",
        scrollTrigger: {
          trigger: "body",
          start: "top top",
          end: "bottom top",
          scrub: 2.5,
        },
      });
      gsap.to(".landing-orb-green", {
        y: -45,
        ease: "none",
        scrollTrigger: {
          trigger: "body",
          start: "top top",
          end: "bottom top",
          scrub: 3.5,
        },
      });
    }, ref);

    return () => ctx.revert();
  }, []);

  return (
    <section
      ref={ref}
      className="flex-1 flex items-center px-10 md:px-16 py-12 relative z-10"
    >
      {/* Columna izquierda: texto */}
      <div className="flex flex-col flex-1">
        {/* Eyebrow */}
        <p
          className="lh-eyebrow mb-7 text-[10px] font-semibold tracking-[0.22em] uppercase"
          style={{ color: "rgba(245,241,236,0.3)" }}
        >
          {t.landing.eyebrow}
        </p>

        {/* Línea acento naranja */}
        <div
          className="lh-line mb-8 rounded-full"
          style={{ width: "40px", height: "2px", background: "#C2410C" }}
        />

        {/* Headline */}
        <h1
          className="font-bold leading-[0.88] tracking-[-0.045em]"
          style={{
            fontFamily: "Space Grotesk, sans-serif",
            fontSize: "clamp(54px, 10vw, 136px)",
            perspective: "900px",
          }}
        >
          {t.landing.headline[0].map((word, i) => (
            <span key={i} className="lh-word inline-block" style={{ color: "#F5F1EC" }}>
              {word}&nbsp;
            </span>
          ))}
          <br />
          {t.landing.headline[1].map((word, i) => (
            <span key={i} className="lh-word inline-block" style={{ color: "rgba(245,241,236,0.22)" }}>
              {word}&nbsp;
            </span>
          ))}
        </h1>

        {/* Cuerpo */}
        <p
          className="lh-body mt-10 text-[15px] md:text-[16px] leading-relaxed max-w-sm"
          style={{ color: "rgba(245,241,236,0.4)" }}
        >
          {t.landing.body}
        </p>
      </div>

      {/* Botón Entrar — al lado derecho del headline */}
      <div
        className="lh-body hidden md:flex flex-col items-center gap-4 shrink-0 pl-16"
      >
        <Link
          href="/buscar"
          className="group flex flex-col items-center gap-4"
          style={{ textDecoration: "none" }}
        >
          <span
            className="flex items-center justify-center w-16 h-16 rounded-full"
            style={{
              background: "#C2410C",
              transition: "transform 220ms cubic-bezier(0.23,1,0.32,1), box-shadow 220ms",
              boxShadow: "0 0 0 0 rgba(194,65,12,0)",
            }}
            onMouseEnter={e => {
              (e.currentTarget as HTMLElement).style.transform = "scale(1.08)";
              (e.currentTarget as HTMLElement).style.boxShadow = "0 8px 32px rgba(194,65,12,0.4)";
            }}
            onMouseLeave={e => {
              (e.currentTarget as HTMLElement).style.transform = "scale(1)";
              (e.currentTarget as HTMLElement).style.boxShadow = "0 0 0 0 rgba(194,65,12,0)";
            }}
          >
            <ArrowUpRight size={22} color="#fff" strokeWidth={2} />
          </span>
          <span
            className="text-[11px] font-semibold tracking-[0.14em] uppercase"
            style={{ color: "rgba(245,241,236,0.35)" }}
          >
            {t.landing.enter}
          </span>
        </Link>
      </div>

      {/* Datos flotantes — columna más a la derecha */}
      <div
        className="landing-float hidden md:flex flex-col items-end gap-3 pointer-events-none shrink-0 pl-12"
        aria-hidden
      >
        {FLOAT_ROWS.map((row, i) => (
          <p key={i} className="landing-float-row">{row}</p>
        ))}
      </div>
    </section>
  );
}
