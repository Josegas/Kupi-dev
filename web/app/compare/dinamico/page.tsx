"use client";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import CompareClient from "../CompareClient";
import { RestaurantConfig } from "../../lib/restaurants";

function DinamicoInner() {
  const searchParams = useSearchParams();
  const rappi = searchParams.get("rappi") || "";
  const ue = searchParams.get("ue") || "";
  const name = searchParams.get("name") || "Restaurante";

  if (!rappi && !ue) {
    return (
      <div className="min-h-screen bg-[var(--bg)] flex items-center justify-center">
        <p className="text-[var(--text-muted)]">Faltan parametros de restaurante.</p>
      </div>
    );
  }

  const restaurant: RestaurantConfig = {
    id: "dinamico",
    name,
    cuisine: "",
    rating: 0,
    platforms: (rappi ? 1 : 0) + (ue ? 1 : 0),
    fromPrice: 0,
    rappi_store_id: rappi,
    ubereats_store_id: ue,
    didi_store_id: null,
  };

  return <CompareClient restaurant={restaurant} />;
}

export default function DinamicoPage() {
  return (
    <Suspense fallback={<div className="min-h-screen" />}>
      <DinamicoInner />
    </Suspense>
  );
}
