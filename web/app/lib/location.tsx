"use client";
import { createContext, useContext, useState, useEffect, ReactNode } from "react";

interface Location {
  lat: number;
  lng: number;
  label: string;
}

// Default: Culiacán centro (donde tenemos la mayor cobertura de restaurantes)
const FALLBACK_LOCATION: Location = {
  lat: 24.8069,
  lng: -107.3940,
  label: "Culiacán, Sinaloa",
};

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
  const [hasLocation, setHasLocation] = useState(true); // default a Culiacán ya tiene datos

  // Restaurar ubicación guardada al montar
  useEffect(() => {
    try {
      const saved = localStorage.getItem("kupi-location");
      if (saved) {
        const parsed = JSON.parse(saved);
        if (parsed.lat && parsed.lng && parsed.label) {
          setLocationState(parsed);
          setHasLocation(true);
        }
      }
    } catch { /* ignore */ }
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
