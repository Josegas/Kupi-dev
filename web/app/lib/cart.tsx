"use client";
import { createContext, useContext, useState, useCallback, ReactNode } from "react";

export interface CartItem {
  name: string;
  price: number;
  image_url: string;
  rappi_product_id?: string;
  ubereats_product_id?: string;
}

interface CartContextType {
  items: CartItem[];
  addItem: (item: CartItem) => boolean;
  removeItem: (index: number) => void;
  clearCart: () => void;
  canAdd: (item: CartItem) => boolean;
  itemCount: number;
  subtotal: number;
}

const MAX_CART_ITEMS = 10;

/** Devuelve las plataformas en común entre todos los items */
function commonPlatforms(items: CartItem[]): Set<string> {
  if (items.length === 0) return new Set(["rappi", "ubereats"]);
  const platforms = new Set<string>();
  if (items.every((i) => i.rappi_product_id)) platforms.add("rappi");
  if (items.every((i) => i.ubereats_product_id)) platforms.add("ubereats");
  return platforms;
}

const CartContext = createContext<CartContextType>({
  items: [],
  addItem: () => false,
  removeItem: () => {},
  clearCart: () => {},
  canAdd: () => true,
  itemCount: 0,
  subtotal: 0,
});

export function CartProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<CartItem[]>([]);

  const canAdd = useCallback(
    (item: CartItem): boolean => {
      if (items.length >= MAX_CART_ITEMS) return false;
      // Checar que al agregar el nuevo item, siga habiendo al menos una plataforma en común
      const withNew = [...items, item];
      return commonPlatforms(withNew).size > 0;
    },
    [items],
  );

  const addItem = useCallback(
    (item: CartItem): boolean => {
      let added = false;
      setItems((prev) => {
        if (prev.length >= MAX_CART_ITEMS) return prev;
        const withNew = [...prev, item];
        if (commonPlatforms(withNew).size === 0) return prev;
        added = true;
        return withNew;
      });
      return added;
    },
    [],
  );

  const removeItem = useCallback((index: number) => {
    setItems((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const clearCart = useCallback(() => setItems([]), []);

  const itemCount = items.length;
  const subtotal = items.reduce((sum, item) => sum + item.price, 0);

  return (
    <CartContext.Provider value={{ items, addItem, removeItem, clearCart, canAdd, itemCount, subtotal }}>
      {children}
    </CartContext.Provider>
  );
}

export function useCart() {
  return useContext(CartContext);
}
