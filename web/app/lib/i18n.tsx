"use client";
import { createContext, useContext, useState, useEffect, type ReactNode } from "react";

export type Lang = "es" | "en";

export const T = {
  es: {
    landing: {
      eyebrow: "Metabuscador de precios · México",
      headline: [["El", "precio", "real,"], ["antes", "de", "pedir."]],
      body: "Compara el costo final con envío en Rappi y Uber Eats. Sin abrir dos apps.",
      enter: "Entrar",
      marquee: ["Rappi", "Uber Eats", "¿Cuál es más barato?", "Rappi", "Uber Eats", "Tú decides"],
    },
    buscar: {
      title: "¿Qué se te antoja hoy?",
      subtitle: "Ve el precio final en Rappi y Uber Eats antes de pedir. Sin sorpresas.",
      searchPlaceholder: "Busca un restaurante o platillo...",
      allCategory: "Todo",
      noResults: "Sin resultados para",
      seeAll: "Ver todo",
      categories: {
        Todo: "Todo",
        Pizza: "Pizza",
        Hamburguesas: "Hamburguesas",
        Tacos: "Tacos",
        Sushi: "Sushi",
        Pollo: "Pollo",
        Postres: "Postres",
        Café: "Café",
      },
    },
    nav: {
      locationPlaceholder: "Colonia, fraccionamiento, plaza o avenida...",
      locationHint: "Escribe tu",
      locationHintBold: "colonia, fraccionamiento, plaza comercial o avenida",
      locationExamples: "Ej:",
      noResults: "Sin resultados. Prueba con el nombre del fraccionamiento o colonia.",
      themeDay: "Día claro",
      themeNight: "Noche",
    },
    compare: {
      selectTitle: "¿Qué quieres comparar?",
      selectSubtitle: "Productos de Rappi y Uber Eats. Los que están en ambas apps se pueden comparar.",
      selectSubtitleSingle: "En tu zona este restaurante solo está disponible en {platform}.",
      searchPlaceholder: "Buscar producto…",
      retry: "Reintentar",
      noImage: "Sin imagen",
      priceTitle: "Precio final en cada plataforma",
      refresh: "Actualizar",
      checking: "Consultando precio…",
      noSearchResults: "Sin resultados para tu búsqueda.",
      noProducts: "No hay productos disponibles.",
      cheapest: "Más barato",
      product: "Producto",
      delivery: "Envío",
      serviceFee: "Cuota de servicio",
      total: "Total",
      approximate: "El precio puede variar algunos pesos.",
      approximateBold: "La plataforma más barata sí es real.",
      viewOn: "Ver en",
      goTo: "Ir a",
    },
    cart: {
      title: "Carrito",
      clear: "Vaciar",
      subtotal: "Subtotal",
      compareN: "Comparar productos",
      cartTotal: "Precio total del carrito",
      cartNote: "El precio final incluye un solo cargo de envío y cuota de servicio.",
      update: "Actualizar",
      retry: "Reintentar",
    },
    favoritos: {
      title: "Mis favoritos",
      empty: "Sin favoritos todavía",
      emptyHint: "Busca un restaurante, elige un producto y toca el corazón para guardarlo",
      searchButton: "Buscar restaurantes",
      compare: "Comparar",
      alertActive: "Alerta activa: te notificamos por email si el precio total baja 5% o más",
      alertActivate: "Activar alerta: te avisamos cuando baje el precio",
      alertActiveShort: "Alerta activa: te avisamos si baja 5% o más",
      historyTitle: "Historial de precios (últimos 7 días)",
      historyEmpty: "Sin datos todavía. Los precios se registran cada 6 horas automáticamente.",
      loadingHistory: "Cargando historial...",
      date: "Fecha",
      cheaper: "Más barato",
      equal: "Igual",
      noImage: "Sin img",
      showing: "Mostrando los últimos",
      of: "registros de",
      product: "prod",
      delivery: "envío",
      removeTitle: "Quitar de favoritos",
      historyTitle2: "Ver historial de precios",
    },
    auth: {
      myFavorites: "Mis favoritos",
      myAlerts: "Mis alertas",
      signOut: "Cerrar sesión",
      signIn: "Iniciar sesión",
      createAccount: "Crear cuenta",
      loginTitle: "Iniciar sesión",
      loginSubtitle: "Guarda tus platillos favoritos y recibe alertas de precio",
      signupSubtitle: "Compara precios sin cuenta, guarda favoritos con cuenta",
      emailPlaceholder: "tu@correo.com",
      password: "Contraseña",
      enter: "Entrar",
      loading: "Cargando...",
      continueGoogle: "Continuar con Google",
      noAccount: "¿No tienes cuenta?",
      hasAccount: "¿Ya tienes cuenta?",
      checkEmail: "Revisa tu correo para confirmar tu cuenta",
      back: "Volver",
      or: "o",
    },
  },
  en: {
    landing: {
      eyebrow: "Food price comparison · Mexico",
      headline: [["The", "real", "price,"], ["before", "you", "order."]],
      body: "Compare the final cost with delivery on Rappi and Uber Eats. Without opening two apps.",
      enter: "Enter",
      marquee: ["Rappi", "Uber Eats", "Which is cheaper?", "Rappi", "Uber Eats", "You decide"],
    },
    buscar: {
      title: "What are you craving today?",
      subtitle: "See the final price on Rappi and Uber Eats before ordering. No surprises.",
      searchPlaceholder: "Search a restaurant or dish...",
      allCategory: "All",
      noResults: "No results for",
      seeAll: "See all",
      categories: {
        Todo: "All",
        Pizza: "Pizza",
        Hamburguesas: "Burgers",
        Tacos: "Tacos",
        Sushi: "Sushi",
        Pollo: "Chicken",
        Postres: "Desserts",
        Café: "Coffee",
      },
    },
    nav: {
      locationPlaceholder: "Neighborhood, subdivision, mall or avenue...",
      locationHint: "Type your",
      locationHintBold: "neighborhood, subdivision, mall or avenue",
      locationExamples: "E.g.:",
      noResults: "No results. Try the neighborhood or subdivision name.",
      themeDay: "Light mode",
      themeNight: "Dark mode",
    },
    compare: {
      selectTitle: "What do you want to compare?",
      selectSubtitle: "Products from Rappi and Uber Eats. Those on both apps can be compared.",
      selectSubtitleSingle: "In your area this restaurant is only available on {platform}.",
      searchPlaceholder: "Search product…",
      retry: "Retry",
      noImage: "No image",
      priceTitle: "Final price on each platform",
      refresh: "Refresh",
      checking: "Checking price…",
      noSearchResults: "No results for your search.",
      noProducts: "No products available.",
      cheapest: "Cheapest",
      product: "Product",
      delivery: "Delivery",
      serviceFee: "Service fee",
      total: "Total",
      approximate: "The price may vary a few pesos.",
      approximateBold: "The cheapest platform is still accurate.",
      viewOn: "View on",
      goTo: "Go to",
    },
    cart: {
      title: "Cart",
      clear: "Clear",
      subtotal: "Subtotal",
      compareN: "Compare products",
      cartTotal: "Total cart price",
      cartNote: "Final price includes a single delivery and service fee.",
      update: "Update",
      retry: "Retry",
    },
    favoritos: {
      title: "My favorites",
      empty: "No favorites yet",
      emptyHint: "Search a restaurant, pick a product and tap the heart to save it",
      searchButton: "Search restaurants",
      compare: "Compare",
      alertActive: "Alert active: we'll notify you by email if the total price drops 5% or more",
      alertActivate: "Enable alert: we'll let you know when the price drops",
      alertActiveShort: "Alert active: we'll notify you if it drops 5% or more",
      historyTitle: "Price history (last 7 days)",
      historyEmpty: "No data yet. Prices are recorded every 6 hours automatically.",
      loadingHistory: "Loading history...",
      date: "Date",
      cheaper: "Cheaper",
      equal: "Same",
      noImage: "No img",
      showing: "Showing last",
      of: "records of",
      product: "prod",
      delivery: "delivery",
      removeTitle: "Remove from favorites",
      historyTitle2: "View price history",
    },
    auth: {
      myFavorites: "My favorites",
      myAlerts: "My alerts",
      signOut: "Sign out",
      signIn: "Sign in",
      createAccount: "Create account",
      loginTitle: "Sign in",
      loginSubtitle: "Save your favorite dishes and get price alerts",
      signupSubtitle: "Compare prices without an account, save favorites with one",
      emailPlaceholder: "you@email.com",
      password: "Password",
      enter: "Sign in",
      loading: "Loading...",
      continueGoogle: "Continue with Google",
      noAccount: "Don't have an account?",
      hasAccount: "Already have an account?",
      checkEmail: "Check your email to confirm your account",
      back: "Back",
      or: "or",
    },
  },
} as const;

type Translations = typeof T[Lang];

const LangCtx = createContext<{
  lang: Lang;
  t: Translations;
  toggle: () => void;
}>({ lang: "es", t: T.es, toggle: () => {} });

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>("es");

  useEffect(() => {
    const saved = localStorage.getItem("kupi-lang") as Lang | null;
    if (saved === "en" || saved === "es") setLang(saved);
  }, []);

  const toggle = () =>
    setLang((l) => {
      const next = l === "es" ? "en" : "es";
      localStorage.setItem("kupi-lang", next);
      return next;
    });

  return (
    <LangCtx.Provider value={{ lang, t: T[lang], toggle }}>
      {children}
    </LangCtx.Provider>
  );
}

export function useLang() {
  return useContext(LangCtx);
}
