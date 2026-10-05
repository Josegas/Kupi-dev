export default function KupiLogo({ size = 44, textColor, imageSrc }: { size?: number; textColor?: string; imageSrc?: string }) {
  if (imageSrc) {
    // kupi-logo-dark  → landing u otros fondos siempre oscuros (invert + brillo)
    // kupi-logo-light → nav/buscar: multiply en día, invert en noche (via CSS)
    const logoClass = textColor === "#F5F1EC" ? "kupi-logo-dark" : "kupi-logo-light";
    // eslint-disable-next-line @next/next/no-img-element
    return (
      <img
        src={imageSrc}
        alt="Kupi"
        className={logoClass}
        style={{ height: size, width: "auto", objectFit: "contain" }}
      />
    );
  }

  return (
    <div className="flex items-center gap-2.5 shrink-0">
      {/* Ícono SVG - colores fijos, se ven bien en ambos temas */}
      <svg
        width={size}
        height={size}
        viewBox="0 0 48 48"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <rect width="48" height="48" rx="12" fill="#1F2323" />
        <clipPath id="kupi-clip">
          <rect width="48" height="48" rx="12" />
        </clipPath>
        {/* Esquina naranja arriba-izquierda */}
        <polygon
          points="0,0 27,0 0,27"
          fill="#C2410C"
          clipPath="url(#kupi-clip)"
        />
        {/* Esquina verde abajo-derecha */}
        <polygon
          points="48,48 21,48 48,21"
          fill="#15803D"
          clipPath="url(#kupi-clip)"
        />
      </svg>

      {/* Wordmark - usa var(--text-primary) para adaptarse al tema */}
      <span
        style={{
          fontFamily: "var(--font-display)",
          color: textColor ?? "var(--text-primary)",
          fontSize: `${size * 0.52}px`,
          fontWeight: 700,
          letterSpacing: "-0.03em",
          lineHeight: 1,
          transition: "color 300ms cubic-bezier(0.23, 1, 0.32, 1)",
        }}
      >
        Kupi
      </span>
    </div>
  );
}
