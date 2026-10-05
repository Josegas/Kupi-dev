"use client";
import Link from "next/link";
import { useLang } from "../lib/i18n";

export default function LandingMarquee() {
  const { t } = useLang();
  const tickerContent = [...t.landing.marquee, ...t.landing.marquee];

  return (
    <Link href="/buscar" className="landing-marquee-link">
      <div className="landing-marquee-outer">
        <div className="landing-marquee-track">
          {tickerContent.map((item, i) => (
            <span key={i} className="landing-marquee-item">
              {item}
              <span className="landing-marquee-accent">·</span>
            </span>
          ))}
        </div>
      </div>
    </Link>
  );
}
