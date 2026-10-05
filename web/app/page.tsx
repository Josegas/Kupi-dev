import KupiLogo from "./components/KupiLogo";
import LandingHero from "./components/LandingHero";
import CursorGlow from "./components/CursorGlow";
import LandingMarquee from "./components/LandingMarquee";
import LanguageToggle from "./components/LanguageToggle";

export default function Landing() {
  return (
    <div
      className="landing-root min-h-screen flex flex-col overflow-hidden relative"
      style={{ background: "#0B0B09", color: "#F5F1EC" }}
    >
      {/* Video de fondo */}
      <video
        src="/hero.mp4"
        autoPlay
        loop
        muted
        playsInline
        className="absolute inset-0 w-full h-full object-cover"
        style={{ zIndex: 0 }}
      />
      {/* Overlay oscuro sobre el video */}
      <div
        className="absolute inset-0"
        style={{ background: "linear-gradient(to bottom, rgba(11,11,9,0.72) 0%, rgba(11,11,9,0.55) 50%, rgba(11,11,9,0.85) 100%)", zIndex: 1 }}
      />

      {/* Cursor glow — sigue al mouse con lag suave */}
      <CursorGlow />

      {/* Fondos decorativos */}
      <div className="landing-orb-orange" aria-hidden />
      <div className="landing-orb-green"  aria-hidden />
      <div className="landing-grain"      aria-hidden />

      {/* Nav — logo + toggle de idioma */}
      <nav className="landing-nav relative z-10 flex items-center justify-between px-10 md:px-16 pt-8 pb-4 shrink-0">
        <KupiLogo size={140} imageSrc="/Kupilogo6.png" textColor="#F5F1EC" />
        <LanguageToggle dark />
      </nav>

      {/* Hero animado con GSAP */}
      <LandingHero />

      {/* Marquee CTA */}
      <LandingMarquee />

      {/* Footer */}
      <footer
        className="landing-footer shrink-0 px-10 md:px-16 py-5 flex items-center justify-end border-t"
        style={{ borderColor: "rgba(245,241,236,0.05)" }}
      >
        <p className="text-[10px]" style={{ color: "rgba(245,241,236,0.15)" }}>
          Kupi © 2026
        </p>
      </footer>
    </div>
  );
}
