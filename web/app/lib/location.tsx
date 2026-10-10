"use client";
import { createContext, useContext, useState, useEffect, ReactNode } from "react";

interface Location {
  lat: number;
  lng: number;
  label: string;
}

// Sin ubicación todavía: hasLocation=false y las páginas no consultan hasta que haya una
const FALLBACK_LOCATION: Location = { lat: 0, lng: 0, label: "" };

interface LocationContextType {
  location: Location;
  setLocation: (loc: Location) => void;
  hasLocation: boolean;
}

const LocationContext = createContext<LocationContextType>({
  location: FALLBACK_LOCATION,
  setLocation: () => {},
  hasLocation: false,
});

export function LocationProvider({ children }: { children: ReactNode }) {
  const [location, setLocationState] = useState<Location>(FALLBACK_LOCATION);
  const [hasLocation, setHasLocation] = useState(false);

  // Restaurar ubicación guardada al montar; si no hay, pedirla al navegador.
  // Si el usuario la rechaza, se queda sin ubicación y la escribe en la barra de arriba.
  useEffect(() => {
    try {
      const saved = localStorage.getItem("kupi-location");
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed.lat && parsed.lng && parsed.label) {
          setLocationState(parsed);
          setHasLocation(true);
          return;
        }
      }
    } catch { /* ignore */ }
    navigator.geolocation?.getCurrentPosition(
      async ({ coords }) => {
        const label = await reverseGeocode(coords.latitude, coords.longitude);
        setLocation({ lat: coords.latitude, lng: coords.longitude, label });
      },
      () => { /* rechazada: el usuario escribe su dirección */ },
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }, []);

  const setLocation = (loc: Location) => {
    setLocationState(loc);
    setHasLocation(true);
    try { localStorage.setItem("kupi-location", JSON.stringify(loc)); } catch { /* ignore */ }
  };

  return (
    <LocationContext.Provider value={{ location, setLocation, hasLocation }}>
      {children}
    </LocationContext.Provider>
  );
}

export function useLocation() {
  return useContext(LocationContext);
}

export interface GeoSuggestion {
  lat: number;
  lng: number;
  label: string;
  fullLabel: string;
}

async function reverseGeocode(lat: number, lng: number): Promise<string> {
  const params = new URLSearchParams({ lat: String(lat), lon: String(lng), format: "json", addressdetails: "1" });
  try {
    const res = await fetch(`https://nominatim.openstreetmap.org/reverse?${params}`, {
      headers: { "Accept-Language": "es", "User-Agent": "Kupi/1.0" },
    });
    const r = await res.json();
    // Calle, colonia y ciudad (display_name empieza con el negocio más cercano, ej. una óptica)
    const a = r.address ?? {};
    const parts = [a.road, a.neighbourhood ?? a.suburb, a.city ?? a.town ?? a.village].filter(Boolean);
    if (parts.length) return parts.join(", ");
    if (r.display_name) return r.display_name.split(",").slice(0, 3).join(",");
  } catch { /* ignore */ }
  return "Mi ubicación";
}

export async function searchAddress(query: string): Promise<GeoSuggestion[]> {
  if (query.trim().length < 3) return [];
  const params = new URLSearchParams({
    q: query,
    format: "json",
    limit: "6",
    countrycodes: "mx",
    addressdetails: "1",
  });
  try {
    const res = await fetch(`https://nominatim.openstreetmap.org/search?${params}`, {
      headers: { "Accept-Language": "es", "User-Agent": "Kupi/1.0" },
    });
    const results = await res.json();
    return results.map((r: { lat: string; lon: string; display_name: string }) => ({
      lat: parseFloat(r.lat),
      lng: parseFloat(r.lon),
      label: r.display_name.split(",").slice(0, 3).join(", "),
      fullLabel: r.display_name,
    }));
  } catch {
    return [];
  }
}
