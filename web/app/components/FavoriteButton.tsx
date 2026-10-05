"use client";
import { useState, useEffect } from "react";
import { Heart } from "lucide-react";
import { useAuth } from "../lib/auth";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Props {
  productName: string;
  restaurantName: string;
  rappiProductId?: string;
  ubereatsProductId?: string;
  rappiStoreId?: string;
  ubereatsStoreId?: string;
  imageUrl?: string;
  className?: string;
}

export default function FavoriteButton({
  productName,
  restaurantName,
  rappiProductId,
  ubereatsProductId,
  rappiStoreId,
  ubereatsStoreId,
  imageUrl,
  className = "",
}: Props) {
  const { user, session } = useAuth();
  const router = useRouter();
  const [isFavorite, setIsFavorite] = useState(false);
  const [favoriteId, setFavoriteId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);

  // Verificar si ya es favorito al montar
  useEffect(() => {
    if (!session?.access_token) return;
    fetch(`${API_URL}/favorites`, {
      headers: { Authorization: `Bearer ${session.access_token}` },
    })
      .then((r) => r.json())
      .then((favs: any[]) => {
        const match = favs.find(
          (f) =>
            (rappiProductId && f.rappi_product_id === rappiProductId) ||
            (ubereatsProductId && f.ubereats_product_id === ubereatsProductId)
        );
        if (match) {
          setIsFavorite(true);
          setFavoriteId(match.id);
        }
      })
      .catch(() => {});
  }, [session, rappiProductId, ubereatsProductId]);

  const toggle = async (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();

    if (!user) {
      router.push("/login");
      return;
    }

    setLoading(true);
    try {
      if (isFavorite && favoriteId) {
        await fetch(`${API_URL}/favorites/${favoriteId}`, {
          method: "DELETE",
          headers: { Authorization: `Bearer ${session!.access_token}` },
        });
        setIsFavorite(false);
        setFavoriteId(null);
      } else {
        const resp = await fetch(`${API_URL}/favorites`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${session!.access_token}`,
          },
          body: JSON.stringify({
            product_name: productName,
            restaurant_name: restaurantName,
            rappi_product_id: rappiProductId || null,
            ubereats_product_id: ubereatsProductId || null,
            rappi_store_id: rappiStoreId || null,
            ubereats_store_id: ubereatsStoreId || null,
            image_url: imageUrl || "",
          }),
        });
        if (resp.ok) {
          const data = await resp.json();
          setIsFavorite(true);
          setFavoriteId(data.id);
        }
      }
    } catch {
      // silencioso
    }
    setLoading(false);
  };

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={toggle}
      onKeyDown={(e) => { if (e.key === "Enter") toggle(e as any); }}
      className={`transition-colors cursor-pointer ${loading ? "opacity-50 pointer-events-none" : ""} ${className}`}
      title={isFavorite ? "Quitar de favoritos" : "Agregar a favoritos"}
    >
      <Heart
        size={18}
        className={`transition-colors ${
          isFavorite
            ? "fill-red-500 text-red-500"
            : "text-[var(--text-muted)] hover:text-red-400"
        }`}
      />
    </div>
  );
}
