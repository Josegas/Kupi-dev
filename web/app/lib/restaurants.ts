export interface RestaurantConfig {
  id: string;
  name: string;
  cuisine: string;
  rating: number;
  platforms: number;
  fromPrice: number;
  imageUrl?: string;
  rappi_store_id: string;
  ubereats_store_id: string;
  // DiDi Food: ID numérico de la sucursal en stores.json.
  // null = sucursal no disponible en DiDi o branch no confirmada.
  didi_store_id: string | null;
  // false = restaurante cerrado permanentemente o suspendido; se oculta del listado.
  // undefined/true = disponible normalmente.
  available?: boolean;
}

// Ya no hay restaurantes hardcodeados — todo viene de búsqueda dinámica o Supabase
export const RESTAURANTS: RestaurantConfig[] = [];
