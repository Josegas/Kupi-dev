import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_KEY!;

export const supabase = createClient(supabaseUrl, supabaseKey);

export interface Coupon {
  id: number;
  created_at: string;
  restaurant_id: string[];
  restaurant_name: string;
  platform: "rappi" | "ubereats";
  description: string;
  is_active: boolean;
  last_seen_at: string;
  deep_link: string | null;
}

export async function fetchCoupons(restaurantId?: string): Promise<Coupon[]> {
  let query = supabase
    .from("coupons")
    .select("*")
    .eq("is_active", true)
    .order("last_seen_at", { ascending: false });

  if (restaurantId) {
    query = query.contains("restaurant_id", [restaurantId]);
  }

  const { data, error } = await query;
  if (error) throw error;
  return (data ?? []) as Coupon[];
}
