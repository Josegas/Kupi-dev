import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { LocationProvider } from "./lib/location";
import { LanguageProvider } from "./lib/i18n";
import { AuthProvider } from "./lib/auth";
import { CartProvider } from "./lib/cart";
import SmoothScroll from "./components/SmoothScroll";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Kupi",
  description: "Ve el precio final con envío en Rappi y Uber Eats antes de pedir. Sin sorpresas.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        {/* Aplica el tema guardado ANTES de pintar para evitar flash de blanco */}
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('kupi-theme');if(t===null||t==='noche')document.documentElement.setAttribute('data-theme','noche');}catch(e){}})();`,
          }}
        />
      </head>
      <body className="min-h-full flex flex-col">
        <SmoothScroll>
          <AuthProvider>
            <LanguageProvider>
              <CartProvider>
                <LocationProvider>{children}</LocationProvider>
              </CartProvider>
            </LanguageProvider>
          </AuthProvider>
        </SmoothScroll>
      </body>
    </html>
  );
}
