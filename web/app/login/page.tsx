"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, Mail, Lock, Eye, EyeOff } from "lucide-react";
import KupiLogo from "../components/KupiLogo";
import { useAuth } from "../lib/auth";
import { useLang } from "../lib/i18n";

export default function LoginPage() {
  const { signIn, signUp, signInWithGoogle, user } = useAuth();
  const { t } = useLang();
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);

  // Si ya está logueado, redirigir
  if (user) {
    router.push("/buscar");
    return null;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setLoading(true);

    if (mode === "signup") {
      const { error: err } = await signUp(email, password);
      if (err) {
        setError(err);
      } else {
        setSuccess(t.auth.checkEmail);
      }
    } else {
      const { error: err } = await signIn(email, password);
      if (err) {
        setError(err);
      } else {
        router.push("/buscar");
      }
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-[var(--bg)] flex flex-col items-center justify-center px-4">
      {/* Header */}
      <div className="w-full max-w-sm mb-8">
        <Link href="/buscar" className="kupi-link inline-flex items-center gap-1.5 text-[13px] text-[var(--text-muted)] mb-6">
          <ArrowLeft size={14} />
          {t.auth.back}
        </Link>
        <div className="flex justify-center mb-4">
          <KupiLogo size={140} imageSrc="/Kupilogo6.png" />
        </div>
        <h1
          className="text-[22px] font-bold text-[var(--text-primary)] text-center"
          style={{ fontFamily: "var(--font-display)" }}
        >
          {mode === "login" ? t.auth.loginTitle : t.auth.createAccount}
        </h1>
        <p className="text-[13px] text-[var(--text-muted)] text-center mt-1">
          {mode === "login"
            ? t.auth.loginSubtitle
            : t.auth.signupSubtitle}
        </p>
      </div>

      {/* Formulario */}
      <div className="w-full max-w-sm">
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          {/* Email */}
          <div className="kupi-input flex items-center gap-2 bg-[var(--surface)] border border-[var(--border)] rounded-xl px-4 py-3">
            <Mail size={16} className="text-[var(--text-muted)] shrink-0" />
            <input
              type="email"
              placeholder={t.auth.emailPlaceholder}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="flex-1 bg-transparent text-[14px] text-[var(--text-primary)] placeholder-[var(--text-muted)] outline-none"
            />
          </div>

          {/* Password */}
          <div className="kupi-input flex items-center gap-2 bg-[var(--surface)] border border-[var(--border)] rounded-xl px-4 py-3">
            <Lock size={16} className="text-[var(--text-muted)] shrink-0" />
            <input
              type={showPassword ? "text" : "password"}
              placeholder={t.auth.password}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              className="flex-1 bg-transparent text-[14px] text-[var(--text-primary)] placeholder-[var(--text-muted)] outline-none"
            />
            <button type="button" onClick={() => setShowPassword(!showPassword)} className="text-[var(--text-muted)]">
              {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>

          {/* Error / Success */}
          {error && (
            <p className="text-[13px] text-red-500 bg-red-50 dark:bg-red-900/10 rounded-lg px-3 py-2">{error}</p>
          )}
          {success && (
            <p className="text-[13px] text-[var(--savings)] bg-green-50 dark:bg-green-900/10 rounded-lg px-3 py-2">{success}</p>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={loading}
            className="kupi-btn w-full bg-[var(--brand)] text-white font-semibold text-[14px] rounded-xl py-3 mt-1 disabled:opacity-50"
          >
            {loading ? t.auth.loading : mode === "login" ? t.auth.enter : t.auth.createAccount}
          </button>
        </form>

        {/* Divider */}
        <div className="flex items-center gap-3 my-5">
          <div className="flex-1 border-t border-[var(--border)]" />
          <span className="text-[12px] text-[var(--text-muted)]">{t.auth.or}</span>
          <div className="flex-1 border-t border-[var(--border)]" />
        </div>

        {/* Google */}
        <button
          onClick={signInWithGoogle}
          className="kupi-btn w-full bg-[var(--surface)] border border-[var(--border)] text-[var(--text-primary)] font-semibold text-[14px] rounded-xl py-3 flex items-center justify-center gap-2"
        >
          <svg width="18" height="18" viewBox="0 0 24 24">
            <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/>
            <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
            <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
            <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
          </svg>
          {t.auth.continueGoogle}
        </button>

        {/* Toggle mode */}
        <p className="text-center text-[13px] text-[var(--text-muted)] mt-5">
          {mode === "login" ? (
            <>
              {t.auth.noAccount}{" "}
              <button onClick={() => { setMode("signup"); setError(null); setSuccess(null); }} className="text-[var(--brand)] font-semibold">
                {t.auth.createAccount}
              </button>
            </>
          ) : (
            <>
              {t.auth.hasAccount}{" "}
              <button onClick={() => { setMode("login"); setError(null); setSuccess(null); }} className="text-[var(--brand)] font-semibold">
                {t.auth.signIn}
              </button>
            </>
          )}
        </p>
      </div>
    </div>
  );
}
